# LG FWY916WBTN1 local support for Rethink

Connect the LG FWY916WBTN1 washer-dryer to a local Rethink server, read its
settings, and prepare a Start command that preserves the selected programme
and drying level. Internal ThinQ model: `Y_V8_F___W.B32QEUK`.

**Status decoding is panel-verified. Start is implemented and tested offline;
it has not been validated by running a real cycle on this exact model.**
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

Choose the programme and options on the machine, load it and add detergent,
then arm Remote Start by holding Add Item for three seconds. Review the current
settings on the local page and deliberately click **Start selected programme**.
Fresh standby settings are required, and downloaded programmes are not yet
supported. The page reports transmission separately from the machine's state.

The implementation sends the programme-preserving B32 `F026` form, with the
reported temperature, spin, rinse, soil, drying and delayed-end settings. It
does not send the default-programme `F02405` shortcut, issue a wake command,
automatically retry, or implement pause. A stale or changed selection is refused.
Actual acceptance by this model is unverified until an authorised real-cycle test.

The software's default operational tools have **no Start command**. Their only
hardware-related workflow is passive observation/pairing; they never call the
Start HTTP route. Automated tests use fake transports and synthetic fixtures.

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
