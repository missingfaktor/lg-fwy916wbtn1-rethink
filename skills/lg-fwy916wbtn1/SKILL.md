---
name: lg-fwy916wbtn1
description: Set up, inspect, update, or troubleshoot local Rethink support for the LG FWY916WBTN1 washer-dryer, including its Y_V8_F___W.B32QEUK protocol, status decoder and Start implementation. Use for this model or an established installation of this package.
---

# LG FWY916WBTN1 through Rethink

This package adds support for internal model `Y_V8_F___W.B32QEUK` to a pinned
Rethink checkout. Its status decoder has been checked against a real panel.
Start is tested against a fake transport. A real Cotton start at 30 °C / 800 rpm,
drying off, has been observed entering detection and washing; other programme
starts and drying execution remain unverified. Keep that distinction in reports.

## Scope and machine actions

Installing, updating, building, pairing or inspecting the package does not
authorise starting a wash. Preserve an explicit request for no live cycle.
The helper's `prepare`, `verify`, `configure`, `up`, `status` and `down` commands
never invoke the Start endpoint. The status page and its GET requests are passive.
Only an explicit request to start the appliance authorises an actual Start action.

For an authorised start, prefer `scripts/control.mjs`: it selects the requested
programme and settings on the laptop, then sends the reviewed Start request.
There is no need to select the programme on the washer's dial. Load, power and
physical Remote Start arming remain necessary; the user arms it by holding Add
Item for three seconds. Do not substitute raw packet
injection, the default-programme command `F02405`, or an automatic retry.
Report a command as sent until a new appliance status confirms what happened.

## Control from chat or a future voice client

Use the same local API as the browser. Resolve the user's requested cycle and
options; use an established household default only when their intent supports it.
Do not silently substitute an unsupported programme or omit drying.

```sh
node scripts/control.mjs catalogue
node scripts/control.mjs status
node scripts/control.mjs plan --programme wash-dry --temperature 40 --spin 1400 --drying cupboard
```

`plan` stores settings for the next cycle on the server and never sends an
appliance command. For an explicit user request to **start** that cycle, use:

```sh
node scripts/control.mjs start --programme wash-dry --temperature 40 --spin 1400 --drying cupboard
```

Do not run this last command for requests to implement, demonstrate, prepare or
test offline. `start` refuses an offline, unarmed, errored or non-standby washer.
It does not wake the machine, arm it remotely or retry. No extra approval question
is needed when the user has already explicitly requested this exact start.
The API is ready for another local client; a voice platform is not bundled.

Direct API clients use `GET /programmes`, `POST /programme/<deviceId>` with
`X-Rethink-Action: programme`, and then `POST /start/<deviceId>` with
`X-Rethink-Action: start` and the latest returned revision. The programme JSON is
`{programme, temperatureC, spinRpm, drying}`; missing options use that programme's
defaults. Selection and Start are separate actions.

## Set up or update

Use an existing installation when available. For a new one, choose a writable
runtime directory outside the installed skill and the user's notes repository.
Locate bundled helpers relative to this `SKILL.md`; all required patches are
inside `assets/`, so a copied skills-manager installation is self-contained.

1. Inspect the host, Docker context, network and existing Rethink version.
   Read [networking.md](references/networking.md) before changing pairing or Wi-Fi.
   A closed TCP port on an already-paired washer is normal, not a failed password.
2. Run `python scripts/manage.py prepare --workspace <runtime-directory>`.
   It clones the pinned upstream revision into a versioned checkout and applies
   the bundled patches. It does not modify an existing user checkout.
3. Run `python scripts/manage.py verify --workspace <runtime-directory>`.
   This installs dependencies with lifecycle scripts disabled, runs type checks
   and tests against fake washers, then builds the software. No hardware is used.
4. Configure with `python scripts/manage.py configure --workspace <runtime-directory>
   --bind-address <server-LAN-address> --hostname <DNS-name>`. Both the initial
   `common.lgthinq.com` lookup and the chosen server hostname must reach this server
   from the washer. `.local` mDNS names do not work for its modem.
5. Start passive services with `python scripts/manage.py up --workspace <runtime-directory>`.
   Pair using upstream's setup procedure only when the network side is ready and
   the user can press the machine's buttons. Keep passwords and certificates in
   local private state, not chat, logs or source control.
6. Verify the device's reported model, an inbound status and a delivery ack.
   Compare named settings to the panel; do not claim that offline tests prove a
   live cycle. `status` only makes GET requests. The page is `/washer` on the
   loopback-only management port.

For updates, `npx skills update lg-fwy916wbtn1` updates this skill's instructions,
scripts and patches. Then repeat `prepare`, `verify`, `configure`, and `up` for
the existing runtime directory. New source versions get a separate checkout;
the data directory, certificates and runtime configuration are preserved.
Do not reset a user's changed checkout or erase old runtime state to force an update.

## Optional KDE tray monitor

The source repository also contains `desktop/`, a read-only Qt tray client with
notifications and KDE login autostart. It is installed separately using
`python desktop/install.py` from a checkout of the repository. It is not bundled
in a copied skill installation. Read `desktop/README.md` there for dependencies,
notification thresholds, installation, updates and removal. It never starts or
changes the washer, and does not require a server restart.

## Diagnose or extend

- Read [protocol.md](references/protocol.md) for verified offsets, command format
  and remaining uncertainties. Similar model suffixes are not interchangeable.
- Read [architecture.md](references/architecture.md) to understand the upstream
  adapter, optional dashboard patch and external setup tools.
- `scripts/capture.mjs --base <management-URL> --output <private-file>` records
  raw packets without injecting anything. Keep captures outside source control.
- Ask for labelled panel changes while idle to validate fields. Read-only status
  observations do not require a real cycle; validating execution does.
- Do not flash firmware, bypass a door lock, or treat an unknown state as standby.
  If pairing or a start attempt fails, inspect the observed error before retrying.
