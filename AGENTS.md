# Working on this package

This repository contains source patches, agent instructions and passive setup
tools. Runtime configuration, CA keys, Wi-Fi credentials and real appliance
captures belong in a separate private workspace and must not be committed.

Use offline tests with fake appliance transports for Start changes. A request to
implement, install or update support does not authorise starting a real cycle.
Do not add live machine actions to CI, setup, page loads, status polling or retry
timers. Keep the exact model suffix and firmware evidence visible in protocol
documentation; do not silently alias a related model.

Verify patches against the pinned upstream revision, run the configuration tests
and the patched upstream verification, and keep the skill self-contained under
`skills/lg-fwy916wbtn1`. Update source patches rather than vendoring a checkout.
