"""Session-local display bridge. It exposes no appliance control methods."""
import json

from PyQt6.QtCore import QObject, pyqtClassInfo, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtDBus import QDBusConnection

INTERFACE = "io.github.missingfaktor.LGWasherMonitor.Display"
SERVICE = "io.github.missingfaktor.LGWasherMonitor.Monitor"


@pyqtClassInfo("D-Bus Interface", INTERFACE)
class DesktopBus(QObject):
    changed = pyqtSignal()

    def __init__(self, controller, service=SERVICE):
        super().__init__(controller.app)
        self.controller = controller
        self.bus = QDBusConnection.sessionBus()
        self.service = service
        if not self.bus.registerService(service):
            raise RuntimeError("Cannot register the washer display on the desktop session bus.")
        if not self.bus.registerObject("/Display", self, QDBusConnection.RegisterOption.ExportAllContents):
            self.bus.unregisterService(service)
            raise RuntimeError("Cannot export the washer display.")

    @pyqtProperty(str, notify=changed)
    def Snapshot(self):
        c = self.controller
        p = (c.sample or {}).get("properties", {})
        return json.dumps({
            "online": (c.sample or {}).get("online") is True and c.rules.failure_at is None,
            "status": p.get("status", "Waiting for washer"),
            "course": p.get("course", "—"), "temperature": p.get("temp", "—"),
            "spin": p.get("spin", "—"), "drying": p.get("drying_mode", "—"),
            "remaining": p.get("remaining_time"), "initial": p.get("initial_time"),
            "reportedAt": p.get("last_status_at"), "problem": c.rules.problem,
            "error": p.get("error_code", 0), "notifications": c.config["notifications"],
            "history": c.history, "base": c.config["base"], "showSerial": c.show_serial,
        })

    @pyqtSlot()
    def Refresh(self):
        self.controller.poll()

    @pyqtSlot()
    def OpenSettings(self):
        self.controller.settings()

    @pyqtSlot()
    def TestNotification(self):
        self.controller.test_notification()

    @pyqtSlot(bool)
    def SetNotifications(self, enabled):
        self.controller.mute.setChecked(enabled)

    @pyqtSlot()
    def Quit(self):
        self.controller.app.quit()

    @pyqtSlot(str)
    def ReportView(self, details):
        if len(details) <= 2048:
            self.view_status = details

    @pyqtProperty(str)
    def ViewStatus(self):
        return getattr(self, "view_status", "{}")

    def close(self):
        self.bus.unregisterObject("/Display")
        self.bus.unregisterService(self.service)
