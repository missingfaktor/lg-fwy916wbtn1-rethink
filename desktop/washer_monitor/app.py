"""Native Qt tray UI. Every network request is a read-only GET."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import quote, urlsplit

from PyQt6.QtCore import QLockFile, QPoint, QRect, QProcess, QStandardPaths, QTimer, QUrl, Qt
from PyQt6.QtGui import QAction, QCursor, QDesktopServices, QFont, QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket, QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMenu, QMessageBox, QProgressBar, QPushButton, QSpinBox,
    QSystemTrayIcon, QTextBrowser, QVBoxLayout,
)

from .monitor import ACTIVE, Monitor, Notice, report_time

APP_ID = "io.github.missingfaktor.LGWasherMonitor"
ICON = Path(__file__).with_name("washer.svg")
DEFAULTS = {"base": "http://127.0.0.1:44401", "device": "", "notifications": True,
            "stale_minutes": 15, "stuck_minutes": 30}


def read_json(path, default):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else default
    except (OSError, ValueError):
        return default


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def valid_base(value):
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Use an HTTP(S) server address without a username or password.")
    if parts.path not in {"", "/"} or parts.query or parts.fragment:
        raise ValueError("Use the server's root address, without a path, query or fragment.")
    return value.rstrip("/")


def duration(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        return "Not reported"
    minutes = int(value)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02} min" if hours else f"{minutes} min"


def status_icon(state, problem=False):
    # Intentionally monochrome in every state; status belongs in the popup/tooltip.
    return QIcon(str(ICON))


def popup_position(anchor, size, available):
    """Place beside the nearest panel edge, clamped to this screen's work area."""
    point = anchor.center()
    edge = min((abs(point.x() - available.left()), "left"),
               (abs(point.x() - available.right()), "right"),
               (abs(point.y() - available.top()), "top"),
               (abs(point.y() - available.bottom()), "bottom"))[1]
    x = point.x() - size.width() // 2
    y = point.y() - size.height() // 2
    gap = 4
    if edge == "bottom":
        y = available.bottom() - size.height() - gap + 1
    elif edge == "top":
        y = available.top() + gap
    elif edge == "left":
        x = available.left() + gap
    else:
        x = available.right() - size.width() - gap + 1
    return QPoint(max(available.left(), min(x, available.right() - size.width() + 1)),
                  max(available.top(), min(y, available.bottom() - size.height() + 1)))


class Details(QDialog):
    def __init__(self, controller):
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.dismissed_at = float("-inf")
        self.setWindowTitle("Washer Monitor")
        self.setWindowIcon(QIcon(str(ICON)))
        self.setFixedWidth(400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(9)
        self.connection = QLabel("Connecting to local Rethink…")
        self.stage = QLabel("Waiting for washer")
        font = QFont(self.font())
        font.setPointSize(20)
        self.stage.setFont(font)
        self.settings = QLabel("No machine report yet")
        self.settings.setWordWrap(True)
        self.estimate = QLabel("Machine estimate: not reported")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.hide()
        self.report = QLabel("Last machine report: none")
        self.report.setWordWrap(True)
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        self.warning.setTextFormat(Qt.TextFormat.PlainText)
        for widget in (self.connection, self.stage, self.settings, self.estimate, self.progress, self.report, self.warning):
            widget.setTextFormat(Qt.TextFormat.PlainText) if isinstance(widget, QLabel) else None
            layout.addWidget(widget)
        self.events = QTextBrowser()
        self.events.setFixedHeight(120)
        self.events.hide()
        layout.addWidget(self.events)
        buttons = QHBoxLayout()
        for label, callback in (("Open washer page", controller.open_page), ("Settings…", controller.settings)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        self.history_button = QPushButton("Recent alerts")
        self.history_button.setCheckable(True)
        self.history_button.toggled.connect(lambda visible: (self.events.setVisible(visible), QTimer.singleShot(0, controller.position_popup)))
        buttons.insertWidget(1, self.history_button)
        layout.addLayout(buttons)

    def hideEvent(self, event):
        self.dismissed_at = time.monotonic()
        super().hideEvent(event)


class Controller:
    def __init__(self, app, options):
        self.app = app
        self.config_path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericConfigLocation)) / "lg-washer-monitor/config.json"
        self.state_path = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "lg-washer-monitor/state.json"
        self.config = DEFAULTS | read_json(self.config_path, {})
        if options.base:
            self.config["base"] = valid_base(options.base)
        self.config["base"] = valid_base(self.config["base"])
        self.rules = self.make_rules()
        saved = read_json(self.state_path, {})
        self.rules.restore(saved.get("previous"), time.monotonic())
        self.history = saved.get("history", [])[-30:]
        self.sample = None
        self.device = self.config.get("device", "")
        self.busy = False
        self.processes = []
        self.last_saved = None
        self.network = QNetworkAccessManager(app)
        self.popup_anchor = None
        self.details = Details(self)
        self.tray = QSystemTrayIcon(status_icon("Unknown"), app)
        self.tray.setToolTip("Washer Monitor · connecting")
        self.menu = menu = QMenu()
        self.summary_action = menu.addAction("Connecting…")
        self.summary_action.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Show washer status", self.show)
        menu.addAction("Open washer page", self.open_page)
        menu.addAction("Refresh now", self.poll)
        self.mute = QAction("Notifications enabled", menu)
        self.mute.setCheckable(True)
        self.mute.setChecked(bool(self.config["notifications"]))
        self.mute.toggled.connect(self.toggle_notifications)
        menu.addAction(self.mute)
        menu.addAction("Send test notification", self.test_notification)
        menu.addAction("Settings…", self.settings)
        menu.addSeparator()
        menu.addAction("Quit monitor", app.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.messageClicked.connect(self.show)
        self.tray.show()
        self.timer = QTimer(app)
        self.timer.timeout.connect(self.poll)
        self.timer.start(10000)
        self.server = QLocalServer(app)
        self.server.newConnection.connect(self.local_connection)
        QLocalServer.removeServer(APP_ID)
        if not self.server.listen(APP_ID):
            raise RuntimeError("Cannot create the monitor's local application socket.")
        QTimer.singleShot(0, self.poll)
        if options.show:
            QTimer.singleShot(0, self.show)
        if options.test_notification:
            QTimer.singleShot(1000, self.test_notification)

    def make_rules(self):
        return Monitor(stale_minutes=max(5, int(self.config["stale_minutes"])), stuck_minutes=max(10, int(self.config["stuck_minutes"])))

    def local_connection(self):
        socket = self.server.nextPendingConnection()
        def handle():
            command = bytes(socket.readAll()).decode(errors="replace")
            if "test" in command:
                self.test_notification()
            if "show" in command:
                self.show()
            socket.disconnectFromServer()
        socket.readyRead.connect(handle)
        socket.disconnected.connect(socket.deleteLater)
        if socket.bytesAvailable():
            handle()

    def show(self):
        self.position_popup()
        self.details.show()
        self.details.raise_()
        self.details.activateWindow()

    def tray_activated(self, reason):
        if reason != QSystemTrayIcon.ActivationReason.Trigger:
            return
        if self.details.isVisible():
            self.details.hide()
        elif time.monotonic() - self.details.dismissed_at > 0.25:
            # A tray click also dismisses Qt's popup as an outside click. Do not
            # reopen it again for the same click after Qt has hidden it.
            position = QCursor.pos()
            self.popup_anchor = QRect(position.x(), position.y(), 1, 1)
            self.show()

    def position_popup(self):
        tray_rect = self.tray.geometry()
        anchor = tray_rect if tray_rect.isValid() else self.popup_anchor
        screen = self.app.screenAt(anchor.center()) if anchor is not None else self.app.primaryScreen()
        screen = screen or self.app.primaryScreen()
        available = screen.availableGeometry()
        if anchor is None:
            # Menu/launcher invocation before the first tray click: use the panel corner.
            point = available.bottomRight()
            anchor = QRect(point.x(), point.y(), 1, 1)
        self.details.adjustSize()
        self.details.move(popup_position(anchor, self.details.size(), available))

    def open_page(self):
        self.details.hide()
        QDesktopServices.openUrl(QUrl(self.config["base"] + "/washer"))

    def toggle_notifications(self, enabled):
        self.config["notifications"] = enabled
        save_json(self.config_path, self.config)

    def notify(self, notice, force=False):
        if not force and not self.config["notifications"]:
            return
        # No shell, no blocking wait; KDE honours the desktop-entry identity/history.
        process = QProcess(self.app)
        self.processes.append(process)
        def finished(*_):
            if process in self.processes:
                self.processes.remove(process)
            process.deleteLater()
        process.finished.connect(finished)
        process.errorOccurred.connect(lambda _: self.tray.showMessage(notice.title, notice.body))
        process.setProgram("notify-send")
        process.setArguments(["--app-name=Washer Monitor", "--icon=" + str(ICON),
                              "--hint=string:desktop-entry:" + APP_ID,
                              "--urgency=" + ("critical" if notice.urgent else "normal"),
                              notice.title, notice.body])
        process.start()

    def test_notification(self):
        self.notify(Notice("test", "Washer Monitor is ready", "Test notification only. Monitoring is read-only; no appliance command was sent."), force=True)

    def get(self, path, callback):
        request = QNetworkRequest(QUrl(self.config["base"] + path))
        request.setTransferTimeout(7000)
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute, QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setRawHeader(b"Accept", b"application/json")
        reply = self.network.get(request)
        def finished():
            try:
                code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                if reply.error() != QNetworkReply.NetworkError.NoError or code != 200:
                    if code == 404:
                        self.device = self.config.get("device", "")
                    raise ValueError("Local status service unavailable")
                if reply.bytesAvailable() > 1024 * 1024:
                    raise ValueError("Status response is too large")
                data = json.loads(bytes(reply.readAll()))
                callback(data)
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                self.failed(str(error))
            finally:
                reply.deleteLater()
        reply.finished.connect(finished)

    def poll(self):
        if self.busy:
            return
        self.busy = True
        if self.device:
            self.get("/status/" + quote(self.device, safe=""), self.received)
        else:
            self.get("/washers", self.discovered)

    def discovered(self, devices):
        if not isinstance(devices, list) or len(devices) != 1 or not isinstance(devices[0].get("id"), str):
            self.failed("Waiting for one connected washer. Set a device ID in Settings if there are several.")
            return
        self.device = devices[0]["id"]
        self.get("/status/" + quote(self.device, safe=""), self.received)

    def failed(self, reason):
        self.busy = False
        self.consume(self.rules.lost(time.monotonic(), reason + "."))
        self.render()

    def received(self, sample):
        if not isinstance(sample, dict) or not isinstance(sample.get("properties"), dict):
            raise ValueError("Invalid washer status response")
        p = sample["properties"]
        for key in ("status", "course", "temp", "spin", "drying_mode", "last_status_at"):
            if key in p and not isinstance(p[key], str):
                raise ValueError("Invalid washer text status")
        for key in ("initial_time", "remaining_time", "error_code"):
            if key in p and (not isinstance(p[key], (int, float)) or isinstance(p[key], bool)):
                raise ValueError("Invalid washer numeric status")
        self.busy = False
        self.sample = sample
        self.consume(self.rules.observe(sample, time.monotonic(), time.time()))
        self.render()

    def consume(self, notices):
        for notice in notices:
            self.history.append({"time": datetime.now().astimezone().isoformat(timespec="seconds"), "title": notice.title, "body": notice.body})
            self.history = self.history[-30:]
            self.notify(notice)
        saved = {"previous": self.rules.previous, "history": self.history}
        if saved != self.last_saved:
            save_json(self.state_path, saved)
            self.last_saved = json.loads(json.dumps(saved))

    def render(self):
        p = (self.sample or {}).get("properties") or {}
        online = (self.sample or {}).get("online") is True and self.rules.failure_at is None
        state = p.get("status", "Waiting for washer")
        problem = self.rules.problem
        self.details.connection.setText("Connected locally" if online else "Waiting for local connection")
        self.details.stage.setText(state if online else "Connection unavailable")
        settings = " · ".join(str(p.get(k, "—")) for k in ("course", "temp", "spin"))
        settings += "\nDrying: " + str(p.get("drying_mode", "—"))
        self.details.settings.setText(settings)
        remaining = p.get("remaining_time")
        self.details.estimate.setText("Machine estimate: " + duration(remaining) + " remaining")
        initial = p.get("initial_time")
        if online and state in ACTIVE and isinstance(initial, (int, float)) and initial > 0 and isinstance(remaining, (int, float)):
            self.details.progress.setValue(max(0, min(100, int(100 * (1 - remaining / initial)))))
            self.details.progress.show()
        else:
            self.details.progress.hide()
        stamp = report_time(p.get("last_status_at"))
        report = "none"
        if stamp is not None:
            age = max(0, int(time.time() - stamp))
            report = datetime.fromtimestamp(stamp).astimezone().strftime("%H:%M:%S") + f" ({age // 60} min ago)"
        self.details.report.setText("Updated " + report + "\nRead-only · times are machine estimates")
        if p.get("error_code", 0) != 0:
            problem = f"Machine error code: {p['error_code']}. Check the washer's display."
        self.details.warning.setText(problem or "")
        self.details.warning.setVisible(bool(problem))
        self.details.events.setPlainText("\n\n".join(f"{event['time'][11:19]} · {event['title']}\n{event['body']}" for event in reversed(self.history)) or "No alerts yet. Watching for drying, completion and problems.")
        label = (state if online else "Disconnected") + (" · " + duration(remaining) if state in ACTIVE else "")
        self.summary_action.setText(label)
        self.tray.setToolTip("Washer Monitor\n" + label + "\n" + settings + ("\n" + problem if problem else ""))
        self.tray.setIcon(status_icon(state, bool(problem)))
        if self.details.isVisible():
            self.position_popup()

    def settings(self):
        self.details.hide()
        dialog = QDialog()
        dialog.setWindowTitle("Washer Monitor settings")
        layout = QFormLayout(dialog)
        address = QLineEdit(self.config["base"])
        device = QLineEdit(self.config.get("device", ""))
        device.setPlaceholderText("Automatic when one washer is connected")
        stale = QSpinBox()
        stale.setRange(5, 120)
        stale.setSuffix(" minutes")
        stale.setValue(int(self.config["stale_minutes"]))
        stuck = QSpinBox()
        stuck.setRange(10, 180)
        stuck.setSuffix(" minutes")
        stuck.setValue(int(self.config["stuck_minutes"]))
        layout.addRow("Local server", address)
        layout.addRow("Device ID (optional)", device)
        layout.addRow("Warn without a fresh report", stale)
        layout.addRow("Warn without progress in fresh reports", stuck)
        note = QLabel("Possible-stall warnings are estimates, not a fault diagnosis.\nPauses alert after 5 minutes; lost connections after 2 minutes.")
        note.setWordWrap(True)
        layout.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        def save():
            try:
                base = valid_base(address.text().strip())
            except ValueError as error:
                QMessageBox.warning(dialog, "Check server address", str(error))
                return
            if self.busy:
                QMessageBox.information(dialog, "Refreshing status", "Please save again once the current refresh completes.")
                return
            self.config.update(base=base, device=device.text().strip(), stale_minutes=stale.value(), stuck_minutes=stuck.value())
            save_json(self.config_path, self.config)
            self.device = self.config["device"]
            self.rules = self.make_rules()
            self.sample = None
            dialog.accept()
            self.poll()
        buttons.accepted.connect(save)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        dialog.exec()


def main():
    parser = argparse.ArgumentParser(description="Read-only LG washer tray monitor")
    parser.add_argument("--show", action="store_true", help="Open status details")
    parser.add_argument("--base", help="Local Rethink management root URL")
    parser.add_argument("--test-notification", action="store_true", help="Send an explicitly labelled desktop notification test")
    options = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("lg-washer-monitor")
    app.setApplicationDisplayName("Washer Monitor")
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(QIcon(str(ICON)))
    app.setQuitOnLastWindowClosed(False)
    runtime = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
    lock = QLockFile(str(Path(runtime) / (APP_ID + ".lock")))
    if not lock.tryLock(0):
        socket = QLocalSocket()
        socket.connectToServer(APP_ID)
        if socket.waitForConnected(1000):
            socket.write(("test " if options.test_notification else "").encode() + (b"show" if options.show else b"ping"))
            socket.waitForBytesWritten(1000)
        return
    controller = Controller(app, options)
    app.aboutToQuit.connect(lambda: controller.tray.hide())
    sys.exit(app.exec())
