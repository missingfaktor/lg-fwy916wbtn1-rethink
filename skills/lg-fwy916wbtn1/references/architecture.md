# What lives where

The current implementation modifies Rethink. It is not an independent protocol
wrapper and Rethink does not provide a plugin loader for these model classes.
This repository distributes reviewable patches rather than another copy of the
whole upstream repository.

`assets/model.patch` adds the exact model adapter, its registration and tests.
The adapter decodes status, uses upstream delivery acknowledgements, and builds
the selected-programme Start command. That support belongs in Rethink and is
the natural candidate for an upstream contribution after further validation.

`assets/dashboard.patch` adds a small status page and local status/Start HTTP
routes to Rethink's existing management server. The Start POST is the only path to
the adapter's Start method. The separate programme POST stores the next cycle's
settings in server memory. Neither a normal GET nor an old retained MQTT
message can start a cycle. This UI/API patch is separate so users and reviewers
can distinguish core appliance support from a convenience interface. A future
independent UI can replace it once a suitable upstream control interface is
available; it is not represented as already living outside Rethink.

The skill, pinned-source preparation, Docker configuration, capture helper and
command-line control client live outside Rethink. They never contain a household-specific SSID, address,
MAC, device UUID, password or CA key. Per-installation state goes in the user's
chosen private runtime directory.

The helper keeps a separate checkout for each upstream/patch hash. An updated
skill can prepare a new source version without overwriting the prior one. The
certificates and configuration live outside those source directories and are
reused. Skill updates and running-service updates are deliberately separate:
installing instructions cannot silently change the software controlling a machine.

The bundled setup tools have no Start action. The separate `control.mjs` client
has passive status/catalogue, a non-actuating plan action and an explicit Start
action for a user-authorised cycle. An agent can use it from chat, and a future
voice client can use the same API. No voice-platform integration is bundled.
The Start UI uses a current-state
revision and requires a deliberate click. The exact model's execution remains
unverified until a user explicitly authorises a real cycle test.
