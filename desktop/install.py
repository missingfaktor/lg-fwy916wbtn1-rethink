#!/usr/bin/env python3
"""Install/update the read-only tray app for this user, without root or pip."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import sys

APP_ID = "io.github.missingfaktor.LGWasherMonitor"


def desktop_quote(value):
    # Desktop Exec uses its own quoting rules, not shell quoting.
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    home = Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    target = data / "lg-washer-monitor"
    launcher = home / ".local/bin/lg-washer-monitor"
    application = data / "applications" / (APP_ID + ".desktop")
    autostart = config / "autostart" / (APP_ID + ".desktop")
    if args.uninstall:
        for path in (launcher, application, autostart):
            path.unlink(missing_ok=True)
        if target.exists():
            shutil.rmtree(target)
        print("Removed app and login entry. Quit the running monitor from its tray menu. Preferences and history were kept.")
        return
    if importlib.util.find_spec("PyQt6") is None or not shutil.which("notify-send"):
        raise SystemExit("Requires Python 3, PyQt6 (Widgets/Network) and notify-send. Install your distribution's python-pyqt6/python3-pyqt6 and libnotify tools.")
    for directory in (target, launcher.parent, application.parent, autostart.parent):
        directory.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(__file__).parent / "washer_monitor", target / "washer_monitor", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # A tiny Python entry point avoids shell interpolation of installation paths.
    launcher.write_text("#!" + sys.executable + "\nimport sys\nsys.path.insert(0, " + repr(str(target)) + ")\nfrom washer_monitor.app import main\nmain()\n")
    launcher.chmod(0o755)
    entry = "\n".join([
        "[Desktop Entry]", "Type=Application", "Name=Washer Monitor",
        "Comment=Local washer-dryer status and notifications",
        "Exec=" + desktop_quote(launcher) + " --show",
        "Icon=" + str(target / "washer_monitor/washer.svg"),
        "Terminal=false", "Categories=Utility;Monitor;", "StartupNotify=false",
        "X-GNOME-UsesNotifications=true", "",
    ])
    application.write_text(entry)
    autostart.write_text(entry.replace(" --show\n", "\n").replace("StartupNotify=false\n", "StartupNotify=false\nOnlyShowIn=KDE;\n"))
    print(f"Installed: {launcher}\nMenu: Washer Monitor\nStarts quietly at KDE login. Run '{launcher} --show' to open it now.")
    print("Updating an existing installation: quit the running monitor, then launch it again. No washer commands are sent.")


if __name__ == "__main__":
    main()
