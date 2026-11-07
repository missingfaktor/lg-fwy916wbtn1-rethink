# KDE washer monitor

A native Plasma tray widget and a local notification process for the existing
Rethink API. The background process uses **GET requests only** and shares a small
cached status snapshot over the user's session D-Bus. The widget does not poll
the washer or add any server requests. Neither part can start, stop, pause, arm
or change the washer. Both live outside Rethink in this repository; the running
appliance server does not need restarting or updating.

## Install

Requires KDE Plasma (tested with 6.6), `kpackagetool6`, Python 3.10+, PyQt6
(Widgets, Network and D-Bus) and `notify-send`/libnotify.
Use your distribution's packages, for example `python3-pyqt6 libnotify-bin` on
Debian/Ubuntu or `python-pyqt6 libnotify` on Arch. No pip packages are downloaded
by the installer.

From the repository:

```sh
python desktop/install.py
~/.local/bin/lg-washer-monitor --show
```

The installer copies the background app into your user data directory, installs
the Plasma applet, adds **Washer Monitor** to the application menu and starts
the notification process quietly at KDE login. Click the
thin black washer icon to toggle a compact popup beside the tray. Click outside
or press Escape to dismiss it. Recent alerts expand on request. Right-click for
refresh, settings, notification mute, a labelled test notification and Quit.
Dismissing the popup leaves monitoring running. Launching it again reuses the
existing instance.

The popup uses Plasma's `AppletPopup`, with native slide-in/slide-out animations,
theme shadow, background and Kirigami typography. It has no title bar, header
divider or taskbar window. Plasma positions it relative to the icon, handles
click-away dismissal, and honours the desktop's animation settings. It does not
inherit the system tray's large shared popup size.

`--show` asks the widget to open using the session display bridge. In native
mode the Python process has no separate tray icon or status window. The bridge
exports display/preferences actions only, not appliance controls. Its Snapshot
omits raw packets and device identifiers; ViewStatus provides basic UI health
information for troubleshooting.

For a non-Plasma desktop, `python desktop/install.py --legacy-tray` retains the
standalone Qt tray. This fallback does not provide Plasma's styling/animation.

The app defaults to `http://127.0.0.1:44401`. Change the server address and optional
device ID in Settings. With exactly one connected washer, discovery is automatic.
The page, tray and status window show **reported** settings, not the next-wash
draft. Time remaining is the last machine estimate, never a fabricated countdown.

## Notifications

- **Started drying** when a fresh report transitions into Drying.
- **Finished** only when the machine reports Finished after an observed active
  cycle. Off/disconnection are never treated as success.
- **Machine error** immediately on a fresh report, once per error episode.
- **Still paused** after five minutes.
- **Connection lost** after two minutes of failed reads or unavailable appliance.
- **No recent update** after 15 minutes without a machine report during an active
  cycle. This is separate from a stall: a quiet appliance may still be running.
- **Possibly stuck** after 30 minutes without a stage/time change **while fresh
  reports continue arriving**. This is a heuristic; some long stages are normal.

The last two thresholds are adjustable. Alerts are deduplicated. Notifications
use KDE's desktop notification service and appear under Washer Monitor. KDE's
notification settings, including Do Not Disturb and its exceptions for critical
alerts, govern their display. The app retains a small private event history and
the last status for transition deduplication across restarts. It does not store
raw packets or appliance credentials.

The monitor and laptop must remain running. KDE login autostart does not start
Rethink or the washer's access point. Monitoring is unavailable while the laptop
is asleep; there is no background cloud service.

## Update or remove

Quit the monitor, update this repository, rerun `python desktop/install.py`, then
launch it again. Preferences and history are preserved. Plasma may retain a
loaded QML component after an applet update; logging out/in or restarting the
Plasma shell loads the new component. The installer does not restart the shell
automatically. Updating the agent skill alone does not update this desktop app.

```sh
python desktop/install.py --uninstall
```

Quit any running instance first. Removal keeps preferences/history under
`$XDG_CONFIG_HOME/lg-washer-monitor` and `$XDG_STATE_HOME/lg-washer-monitor`
(normally `~/.config` and `~/.local/state`). Remove those directories separately
if desired. Installed source lives under `$XDG_DATA_HOME/lg-washer-monitor`.

## Verification

`python -m unittest discover -s tests` includes synthetic notification transition,
stale-report, reconnect and restart tests without Qt or a real appliance.
`python desktop/smoke_test.py` additionally checks the actual Qt window, tray menu
and HTTP GET path/display snapshot against a fake server when PyQt6 is installed. It suppresses
desktop notifications and never contacts a real appliance.
`PYTHONPATH=desktop python -m washer_monitor --show` runs directly from source.
`xvfb-run -a /usr/lib/qt6/bin/qmltestrunner -input desktop/qml-tests` checks the
native popup's lifecycle, compact size and Escape dismissal with synthetic data
when the Plasma/Kirigami QML modules and Qt Quick Test tools are installed.
See [Qt's tray documentation](https://doc.qt.io/qt-6/qsystemtrayicon.html), the
[desktop notification specification](https://specifications.freedesktop.org/notification/latest/)
and [login autostart specification](https://specifications.freedesktop.org/autostart/latest/).
