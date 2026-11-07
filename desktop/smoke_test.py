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

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication
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
        controller.details.show()
        app.processEvents()
        assert not controller.details.grab().isNull(), "Qt window did not render"
        payload["properties"]["remaining_time"] = "invalid"
        controller.poll()
        settle()
        assert controller.rules.failure_at is not None
        assert all(method == "GET" for method, _ in requests), requests
        controller.timer.stop()
        controller.server.close()
        QLocalServer.removeServer(module.APP_ID)
        controller.tray.hide()
        controller.details.close()
        app.processEvents()
        server.shutdown()
        server.server_close()
        print(f"Qt/HTTP smoke test passed: {len(requests)} GETs, zero writes; menu, rendering, alerts and malformed responses checked.")


if __name__ == "__main__":
    main()
