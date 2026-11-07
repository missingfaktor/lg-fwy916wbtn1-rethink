# Model and evidence

Retail model: LG FWY916WBTN1 (11 kg wash / 6 kg dry).
Internal ThinQ model: `Y_V8_F___W.B32QEUK`.
Observed modem: RTL8720cm, software 2.11.207; SoftAP reports protocol 4.9.
Other firmware or an apparently similar suffix needs its own validation.

## Status

The device sends AABB-framed packets over its outbound TLS/MQTT connection.
The `20 0a` envelope contains a `00 eb` single record or `00 ec` old/current
pair. The status record is 39 bytes; for a pair, use the **second** record.
Use Rethink's `processEnvelopedStatus` rather than a guessed absolute offset.

Offsets within one record:

- `2`: state (0 off, 1 standby, verified by physical off/on).
- `3..4`: reported remaining duration, hours/minutes; `5..6`: initial duration.
- `7`: programme; Cotton is 1, Eco 40-60 is 4. The catalogue uses the related
  B32 family's programme IDs; most have not been tested in a live cycle here.
- `8`: error code; `9`: soil setting.
- `10`: spin code; 10 is 1400 rpm, 7 is 1000 rpm.
- `11`: temperature code; 4 is 40 °C, 3 is 30 °C.
- `12`: rinse; `13`: drying level (0 off, 2 automatic, panel checked).
- `14..15`: delayed-end hours/minutes; `16`: options.
- `22`: downloaded programme code; these starts are not supported yet.

The temperature, spin and drying fields were checked by idle panel changes.
Cotton's minimum available spin changed when drying was enabled; do not impose
a universal RPM menu from another washer's model JSON.

Pre-start durations are the appliance's reported values. They are not a promise
of actual completion time and may not yet appear on its load-sensing display.
Remote Start was verified by an idle panel action: holding Add Item changed
record byte 17 from `00` to `02`, then `42`. Bit `02` is the armed indicator.
The programme field remained zero: arming does not require choosing a programme
on the dial. The package uses the armed indicator and does not infer door-lock
state from an unverified bit.

Normal delivery acknowledgements are sent under MQTT `cmd: ack`, including an
envelope sequence number. They are not Start commands. Without them this modem
can retransmit ten times and then go quiet. The adapter uses upstream's AABB ack
implementation and its regression tests.

## Start

On 7 November 2026, an explicitly requested Cotton start with 30 °C, 800 rpm and
drying off was observed entering Detecting and then Washing, with matching
reported settings and error code zero. This establishes acceptance of that
specific start, not completion or execution of other programmes/drying modes.

The implementation uses the programme-preserving B32 `WMStart` form from
upstream `Y_V8_Y___W.B32QEUK.programmeCommand`, with this washer-dryer's reported
drying level carried through instead of the wash-only sibling's hardcoded zero.
It sends one AABB-framed `F0 26` followed by a 16-byte programme body:

```
course soil spin temp rinse dry reserveH reserveM load options flags reserved smart detergent softener dispense
```

Without a laptop selection, the implementation preserves reported settings.
With a laptop selection, it builds the body from the named programme and its
chosen temperature, spin and drying, with no delayed end and standard rinse/soil
defaults. Programme limits/defaults follow the FWY916WBTN1 manual; wire IDs and
non-default drying codes follow the B32 family and need live validation.
The implementation uses
zero for load/reserved/dispensers, and sets the B32 `initialBit | remoteStart`
flags to `03`. Downloaded programmes are refused. **This wire command has only
been tested offline for this exact model**, against generated status fixtures
and a fake transport. Actual acceptance/execution has not been established.

Do not replace it with `F0 24 05 01 00`: that command starts a default programme
on related models and can discard the user's selected configuration.
Do not assume the extra WMDownload step documented for `.B_2QEUK` is required
for `.B32QEUK`; that variant is not the verified B32 command source.

Before sending, the local handler requires the current connection's report to
show error-free standby with physical Remote Start armed. A complete laptop
selection replaces the need for a panel programme. The preview is read-only;
its revision binds the device instance, reported-state version and programme
bytes. Any relevant state/selection change invalidates an earlier preview.
A duplicate request is blocked until the reported state changes. A lost
connection discards readiness. Page refreshes, plan changes, MQTT messages and
background timers cannot initiate Start.

There is no arbitrary two-minute expiry forcing someone back to the dial while
the same connection continues to report an armed standby state. The appliance
still enforces its own physical interlock. A controller reboot or server
reconnection may require arming again to produce a new ready-state report.

The physical Remote Start interlock is not bypassed. The user arms it on the
panel. No automatic wake, fallback programme, retry, pause or power operation
is included in Start.

## Sources

- [Rethink source](https://github.com/anszom/rethink), pinned by `assets/upstream.json`.
- [B32 programme command](https://github.com/anszom/rethink/blob/0de21e2e1962ef631a67780e7de85bc899857043/cloud/devices/Y_V8_Y___W.B32QEUK.ts).
- [Related combo documentation](https://github.com/anszom/rethink/wiki/Appliance:Y_V8_F___W.B_2QEUK), useful for comparison, not an assertion of exact compatibility.

Distributed tests use synthetic, zero-filled records with the panel-verified
settings. Real household captures, identities, certificates and network names
are not part of this package.
