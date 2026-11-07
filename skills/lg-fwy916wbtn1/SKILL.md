---
name: lg-fwy916wbtn1
description: Set up, inspect, update, or troubleshoot local Rethink support for the LG FWY916WBTN1 washer-dryer, including its Y_V8_F___W.B32QEUK protocol, status decoder and Start implementation. Use for this model or an established installation of this package.
---

# LG FWY916WBTN1 through Rethink

This package adds support for internal model `Y_V8_F___W.B32QEUK` to a pinned
Rethink checkout. Its status decoder has been checked against a real panel.
Start is implemented and tested against a fake transport, but has **not** been
verified by running a real cycle. Keep that distinction in reports to users.

## Scope and machine actions

Installing, updating, building, pairing or inspecting the package does not
authorise starting a wash. Preserve an explicit request for no live cycle.
The helper's `prepare`, `verify`, `configure`, `up`, `status` and `down` commands
never invoke the Start endpoint. The status page and its GET requests are passive.
Only an explicit request to start the appliance authorises an actual Start action.

For an authorised start, use the existing UI or `POST /start/<deviceId>` with
the revision returned by `GET /status/<deviceId>` and header
`X-Rethink-Action: start`. Use the user's selected programme, including its drying
setting. The washer's physical Remote Start interlock remains in force; the user
arms it by holding Add Item for three seconds. Do not substitute raw packet
injection, the default-programme command `F02405`, or an automatic retry.
Report a command as sent until a new appliance status confirms what happened.

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
