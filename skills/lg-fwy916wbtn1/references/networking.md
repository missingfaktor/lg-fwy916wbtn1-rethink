# Pairing and local routing

LG's normal appliance connection goes out to its cloud. An already-paired
washer can refuse all incoming TCP connections and still work normally.
Rethink replaces the server the appliance connects to; it is not a client that
simply connects to the washer's normal home-network IP address.

Prefer an existing server and a DNS mechanism the user already controls.
During enrolment, route `common.lgthinq.com` to the Rethink server. The chosen
Rethink hostname must also resolve there from the appliance. Use a positive DNS
TTL, not zero. The modem does not resolve `.local` mDNS hostnames.

Prepare and verify the server, HTTPS certificate route, DNS, and MQTT listener
before asking the user to enter pairing mode. Pairing mode is Power on, then
hold Delay End for three seconds. Check the actual Wi-Fi SSID and BSSID.
This unit used `LG_Smart_Laundry2_open`, an open temporary setup network, with
the locally administered bit set on its usual Wi-Fi MAC. Do not infer identity
from a shared SSID alone. Older `LGE_...` and `[LG_...]` password schemes are
different; do not apply them to an open SSID.

Upstream's `rethink-setup.ts` implements provisioning over TLS on port 5500.
The usual SoftAP address is `192.168.120.254`, sometimes `192.168.1.1`; inspect
the route handed out rather than scanning unrelated networks. The scripts in
this package do not retrieve or print saved Wi-Fi passwords. Supply credentials
through local input or a private file, never chat, command logs or a public repo.
Use a masked/local-input wrapper around upstream's command-line password
argument if process-list exposure matters on a shared computer.

## Optional Linux access-point approach

If the router cannot provide a local DNS override, a dedicated password-protected
2.4 GHz network can keep the experiment confined to the washer. This is an
optional network design, not something the skill enables automatically.

Things learned from a successful single-radio Linux setup:

- Check `iw list` for simultaneous managed/AP support. One supported combination
  required both connections on the **same channel**, so the home uplink had to
  use the 2.4 GHz access point on the trial AP's channel.
- Save the original uplink profile's band/BSSID constraints before changing
  them. Do not replace the household router's settings to make the trial work.
- Use a virtual interface owned by hostapd for the AP. NetworkManager tried to
  initialise a second managed interface on this radio, exceeding its supported
  combination; leaving the virtual AP unmanaged and using hostapd worked.
- Docker Desktop runs inside a VM. Hardware operations need the native Linux
  Docker engine or host tools. Select the context explicitly rather than changing
  the user's global Docker default. A helper only needed host networking plus
  NET_ADMIN/NET_RAW, not a fully privileged container or host filesystem access.
- Bind DHCP and DNS exclusively to the trial interface. Restrict DHCP to the
  confirmed washer MAC. Generate a new WPA2 key and store it privately.
- Expose Rethink HTTPS/MQTTS only on that network's host address. Bind management
  to loopback; the MQTT broker can stay private to Docker's network.
- When joining the washer SoftAP for enrolment, stop the trial AP if needed,
  and put restoration of the home uplink/AP in a `finally` path with timeouts.

This repository intentionally does not automate profile changes or radio
creation across unknown hardware. A USB Wi-Fi adapter, wired uplink, spare AP
or existing DNS-capable router can be simpler than a single-radio setup.

## Rollback and updates

Keep the runtime data directory and CA private key: the paired appliance trusts
that CA, and deleting it can require pairing again. Updating a skill does not
mean resetting the machine's Wi-Fi. Keep the server address/hostname stable.

To return to LG's cloud, re-pair the washer with ThinQ to the original household
network. Then stop local services and restore any trial uplink constraints and
virtual AP. Merely stopping Rethink does not restore the washer's saved network.
