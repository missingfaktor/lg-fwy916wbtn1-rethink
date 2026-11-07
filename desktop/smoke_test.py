"""Optional Qt/HTTP integration test. Fake server only; run with PyQt6 installed."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time

os.environ["QT_QPA_PLATFORM"] = os.environ.get("WASHER_MONITOR_TEST_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtNetwork import QLocalServer
import washer_monitor.app as module


def main():
    requests = []
    payload = {"online": True, "properties": {"status": "Washing", "course": "Cotton",
        "temp": "30 °C", "spin": "800 rpm", "drying_mode": "Off", "remaining_time": 53,
        "initial_time": 53, "error_code": 0,
        "last_status_at": datetime.now(timezone.utc).isoformat()}}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            requests.append(("GET", self.path))
            value = [{"id": "fake-washer"}] if self.path == "/washers" else payload
            body = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            requests.append(("POST", self.path))
            self.send_error(405)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with tempfile.TemporaryDirectory(prefix="washer-tray-test-") as temporary:
        for variable in ("XDG_CONFIG_HOME", "XDG_STATE_HOME"):
            os.environ[variable] = temporary + "/" + variable
        app = QApplication([])
        app.setApplicationName("lg-washer-monitor-smoke")
        app.setQuitOnLastWindowClosed(False)
        notices = []

        class Controller(module.Controller):
            def notify(self, notice, force=False):
                notices.append(notice)

        module.APP_ID += ".Smoke" + str(os.getpid())
        controller = Controller(app, argparse.Namespace(base=f"http://127.0.0.1:{server.server_port}", show=False, test_notification=False))

        def settle():
            deadline = time.monotonic() + 3
            # Also process a scheduled initial poll when busy is initially False.
            app.processEvents()
            while controller.busy and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.005)
            assert not controller.busy, "HTTP poll did not complete"

        settle()
        assert controller.details.stage.text() == "Washing"
        assert "800 rpm" in controller.details.settings.text()
        assert "Drying: Off" in controller.details.settings.text()
        assert controller.menu.actions(), "Tray context menu was lost"
        exported = json.loads(controller.desktop_bus.Snapshot)
        assert exported["status"] == "Washing" and exported["remaining"] == 53
        assert "raw_packet" not in exported and "device" not in exported
        for stage in ("Drying", "Finished"):
            payload["properties"].update(status=stage, last_status_at=datetime.now(timezone.utc).isoformat())
            controller.poll()
            settle()
        assert [n.kind for n in notices] == ["drying", "finished"]
        controller.poll()
        settle()
        assert len(notices) == 2, "Duplicate transition notification"
        controller.test_notification()
        assert notices[-1].kind == "test"
        # All panel edges and a screen with negative coordinates stay in bounds.
        area = QRect(-1280, 24, 1280, 960)
        for anchor in (QRect(-800, 990, 24, 24), QRect(-800, 0, 24, 24),
                       QRect(-1300, 400, 24, 24), QRect(0, 400, 24, 24)):
            location = module.popup_position(anchor, QSize(400, 280), area)
            assert area.contains(QRect(location, QSize(400, 280)))
        controller.show()
        app.processEvents()
        assert controller.details.windowType() == Qt.WindowType.Popup
        assert controller.details.height() < 380, "Status popup is no longer compact"
        assert not controller.details.events.isVisible(), "History should start collapsed"
        assert not controller.details.grab().isNull(), "Qt window did not render"
        icon = module.status_icon("Washing").pixmap(64, 64).toImage()
        assert not icon.isNull()
        ink = [icon.pixelColor(x, y) for x in range(64) for y in range(64) if icon.pixelColor(x, y).alpha() > 200]
        assert ink and all(c.red() == c.green() == c.blue() == 0 for c in ink), "Icon should be black"
        controller.tray_activated(module.QSystemTrayIcon.ActivationReason.Trigger)
        assert not controller.details.isVisible(), "A second tray activation should close it"
        controller.details.dismissed_at = float("-inf")
        controller.tray_activated(module.QSystemTrayIcon.ActivationReason.Trigger)
        assert controller.details.isVisible()
        QTest.keyClick(controller.details, Qt.Key.Key_Escape)
        assert not controller.details.isVisible(), "Escape should dismiss the popup"
        if app.platformName() == "xcb":
            # Offscreen cannot grab input; exercise real click-away under Xvfb.
            outside = QWidget()
            outside.setGeometry(50, 50, 100, 100)
            outside.show()
            controller.show()
            app.processEvents()
            QTest.mouseClick(outside.windowHandle(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(10, 10))
            app.processEvents()
            assert not controller.details.isVisible(), "An outside click should dismiss the popup"
            outside.close()
        payload["properties"]["remaining_time"] = "invalid"
        controller.poll()
        settle()
        assert controller.rules.failure_at is not None
        assert all(method == "GET" for method, _ in requests), requests
        controller.timer.stop()
        controller.server.close()
        controller.desktop_bus.close()
        QLocalServer.removeServer(module.APP_ID)
        controller.tray.hide()
        controller.details.close()
        app.processEvents()
        server.shutdown()
        server.server_close()
        print(f"Qt/HTTP smoke test passed: {len(requests)} GETs, zero writes; menu, rendering, alerts and malformed responses checked.")


if __name__ == "__main__":
    main()
