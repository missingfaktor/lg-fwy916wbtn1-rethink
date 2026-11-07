# LG FWY916WBTN1 local support for Rethink

Connect the LG FWY916WBTN1 washer-dryer to a local Rethink server, read its
settings, and prepare a Start command that preserves the selected programme
and drying level. Internal ThinQ model: `Y_V8_F___W.B32QEUK`.

**Status decoding is panel-verified. A Cotton start at 30 °C / 800 rpm with
drying off has been observed entering load detection and washing on this model.
Other programme starts and drying execution remain unverified.**
Installing this package, opening its page, or polling status never starts a wash.

## What this is

This is a maintained set of patches and setup tools, not a full fork of
[Rethink](https://github.com/anszom/rethink). A bundled agent skill makes those
tools available to Codex and other agents that support the Agent Skills format.

The model adapter is code **inside Rethink**: it registers this exact model,
decodes its status records, acknowledges delivery, and constructs a selected-
programme Start command. That support belongs upstream in Rethink long term.

The small washer page and HTTP status/Start routes are a separate, optional
patch to Rethink's management server. They currently also run inside Rethink.
Keeping this patch separate makes it possible to review or replace the UI
without confusing it with the model's protocol support.

The skill, build/configuration helper and network setup instructions live
**outside Rethink**. They prepare an isolated, pinned checkout; they do not
overwrite an existing Rethink installation. Household-specific network settings,
captures, appliance identities, Wi-Fi credentials and CA keys are excluded.

## Install the agent skill

Requires a current Node.js installation supported by the skills CLI.

```sh
npx skills add missingfaktor/lg-fwy916wbtn1-rethink --skill lg-fwy916wbtn1
```

Choose your agent, or add `-a codex` to select Codex explicitly. The default is
a project installation; add `-g` only if you want it available globally.
Then ask your agent to use `$lg-fwy916wbtn1` for the setup.

Update the installed skill with:

```sh
npx skills update lg-fwy916wbtn1
```

The skill contains its own scripts, references and patches. It does not depend
on paths elsewhere in this repository, so copied installations work too.
Updating the skill does not silently update a running appliance server: repeat
the preparation, verification and deployment steps for the existing runtime.

## Use without an agent

You need Python 3.10+, Git, Node.js 22.20+ with npm, Docker with Compose, and a
network/DNS arrangement that lets the appliance reach the local server.

```sh
git clone https://github.com/missingfaktor/lg-fwy916wbtn1-rethink.git
cd lg-fwy916wbtn1-rethink
python skills/lg-fwy916wbtn1/scripts/manage.py prepare --workspace "$PWD/.local"
python skills/lg-fwy916wbtn1/scripts/manage.py verify --workspace "$PWD/.local"
python skills/lg-fwy916wbtn1/scripts/manage.py configure --workspace "$PWD/.local" \
  --bind-address 192.168.1.10 --hostname rethink.lan
python skills/lg-fwy916wbtn1/scripts/manage.py up --workspace "$PWD/.local"
```

Replace the example bind address with the server's actual private IPv4 address.
The helper does not configure your router or Wi-Fi. Read the
[network setup notes](skills/lg-fwy916wbtn1/references/networking.md) before
pairing; both `common.lgthinq.com` during enrolment and `rethink.lan` must resolve
to the server from the washer. The usual management page is
`http://127.0.0.1:44401/washer` on the server computer.

The Docker engine can be selected with `--docker-context`. The native Linux
engine is needed for direct host Wi-Fi hardware operations; Docker Desktop's
VM is not a substitute for it. A dedicated AP is optional, not a prerequisite
when existing routing/DNS is suitable.

## Start, when you actually want a cycle

Load the machine, power it on and arm Remote Start by holding Add Item for
three seconds. Choose the programme, temperature, spin speed and drying in the
local page's **Next wash** form, then deliberately click **Start selected programme**.
The dial does not need to be used to choose the programme. The page keeps the
planned settings separate from what the washer currently reports.

A local agent or future voice client can use the same interface:

```sh
node skills/lg-fwy916wbtn1/scripts/control.mjs plan --programme wash-dry --temperature 40 --spin 1400 --drying cupboard
```

That only prepares the cycle. To actually start it after an explicit user request:

```sh
node skills/lg-fwy916wbtn1/scripts/control.mjs start --programme wash-dry --temperature 40 --spin 1400 --drying cupboard
```

`status` and `catalogue` are also available. The client refuses Start unless the
reported machine is in error-free standby with Remote Start armed. It does not
wake or arm the machine remotely and does not automatically retry. No voice
platform is bundled yet; the API/client is the integration point.

The programme catalogue includes Wash+Dry, Cotton, Eco 40-60, TurboWash 39,
Mixed Fabric, Easy Care, Allergy Care, AI Wash, Delicates, Hand/Wool, Speed 14,
Dry Only and Tub Clean. Temperature/spin/drying choices are constrained by the
model's manual. Programme IDs and some drying codes follow the related B32
family: **execution beyond the observed Cotton wash remains unverified**.

The direct API is `GET /programmes`, `POST /programme/<id>` to prepare the
settings and obtain a revision, then `POST /start/<id>` with that revision to
actuate. Selecting a cycle never sends a command to the appliance. The software
uses the B32 F026 form, not the default-programme F02405 shortcut. Automated
verification uses only fake transports and synthetic fixtures.

## KDE system tray monitor

The optional [Washer Monitor](desktop/README.md) shows the reported cycle and
remaining-time estimate in a native Plasma tray popup, with the desktop's
slide animations, shadow and typography. It notifies about drying,
completion, errors, prolonged pauses, lost contact and possible stalls. It only
reads status and lives outside Rethink; no server restart is needed.

```sh
python desktop/install.py
~/.local/bin/lg-washer-monitor --show
```

Requires PyQt6 and `notify-send`. Installation is per user, with KDE login
autostart. Missing reports are distinguished from possible stalls, and both
thresholds are adjustable. See the desktop guide for update/removal instructions.

## Reproducibility, updates and rollback

Upstream revision and container digest are pinned in
[`upstream.json`](skills/lg-fwy916wbtn1/assets/upstream.json). The two patches
are [`model.patch`](skills/lg-fwy916wbtn1/assets/model.patch) and
[`dashboard.patch`](skills/lg-fwy916wbtn1/assets/dashboard.patch).

Each patch version gets a new checkout under the runtime's `sources/` directory.
The runtime's `data/` directory holds the persistent CA/configuration and is kept
across updates. Do not delete it casually: a paired washer trusts that CA.
Never commit runtime data or captures. `manage.py down` stops local services;
returning the washer to LG's cloud requires re-pairing it through ThinQ.

More detail: [protocol evidence](skills/lg-fwy916wbtn1/references/protocol.md),
[architecture](skills/lg-fwy916wbtn1/references/architecture.md), and
[networking](skills/lg-fwy916wbtn1/references/networking.md).

## Verification and contributions

```sh
python -m unittest discover -s tests
python skills/lg-fwy916wbtn1/scripts/manage.py prepare --workspace /tmp/fwy-test
python skills/lg-fwy916wbtn1/scripts/manage.py verify --workspace /tmp/fwy-test
```

The verification checks types, the decoder, framing, selected-settings Start
generation, duplicate/stale-state refusal, and the HTTP path with a fake washer.
Do not run live-cycle tests in CI. Contributions should identify the exact model
and firmware and distinguish offline predictions from observations. Share only
sanitised fixtures; keep real captures and device IDs private.

GPL version 2; see [LICENSE](LICENSE) and [NOTICE](NOTICE). This project is not
affiliated with LG Electronics or the Rethink author.
