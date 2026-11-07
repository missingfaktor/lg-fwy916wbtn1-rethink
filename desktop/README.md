# KDE washer tray monitor

A native Qt system-tray app for the existing local Rethink API. It uses **GET
requests only**. It cannot start, stop, pause, arm or change the washer. This is
a standalone desktop client outside Rethink, in the same repository as the model
support. The currently running server does not need restarting or updating.

## Install

Requires Python 3.10+, PyQt6 (Widgets and Network) and `notify-send`/libnotify.
Use your distribution's packages, for example `python3-pyqt6 libnotify-bin` on
Debian/Ubuntu or `python-pyqt6 libnotify` on Arch. No pip packages are downloaded
by the installer.

From the repository:

```sh
python desktop/install.py
~/.local/bin/lg-washer-monitor --show
```

The installer copies the app into your user data directory, adds **Washer
Monitor** to the application menu and starts it quietly at KDE login. Click the
thin black washer icon to toggle a compact popup beside the tray. Click outside
or press Escape to dismiss it. Recent alerts expand on request. Right-click for
refresh, settings, notification mute, a labelled test notification and Quit.
Dismissing the popup leaves monitoring running. Launching it again reuses the
existing instance.

The popup has no title bar or taskbar window. It anchors beside the tray's panel
edge and stays within the screen's available area. Positioning and click-away
behaviour are verified on KDE/X11; exact placement on Wayland depends on the
compositor's support for application-positioned popups.

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
launch it again. Preferences and history are preserved. Updating the agent skill
alone does not update this optional desktop app.

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
and HTTP GET path against a fake server when PyQt6 is installed. It suppresses
desktop notifications and never contacts a real appliance.
`PYTHONPATH=desktop python -m washer_monitor --show` runs directly from source.
See [Qt's tray documentation](https://doc.qt.io/qt-6/qsystemtrayicon.html), the
[desktop notification specification](https://specifications.freedesktop.org/notification/latest/)
and [login autostart specification](https://specifications.freedesktop.org/autostart/latest/).
