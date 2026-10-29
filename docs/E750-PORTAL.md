# E750 separate portal bridge (AP-only)

This role creates a captive-portal bridge **separate from the management LAN**:

```text
eth0      192.168.8.1/24   management (unchanged)
br-portal 10.0.0.1/24      phy1-ap0 only
phy1-sta0 hermes-lan       STA/BSBF uplink (unchanged)
```

It does **not** touch `network.lan`, `eth0`, or `wireless.sta`. A 900 s watchdog
restores the previous config unless confirmed. This avoids the lockout seen when
the management LAN and the portal shared `br-lan`.

## Live result (2026-10-29)

- `br-portal` UP at 10.0.0.1, `eth0` still 192.168.8.1, AP visible at
  `TollGate-E750` (ch11), STA connected, BSBF endpoints intact.
- dnsmasq on :67, `dhcp.portal` configured, firewall portal zone and br-portal
  rules present.
- **TollGate v0.6.0 daemon started successfully** next to BSBF:
  `config_ok`, `network_ok`, `wallet_ok`, mint probes succeeded, and the AP/STA
  stayed up (unlike the earlier `br-lan` attempt).
- Portal SPA at `http://10.0.0.1:2051/splash.html` returned **200**.
- `nodogsplash` on :2050 returned **500 when requested from the gateway itself**.
  That was a false alarm: a real client on `br-portal` gets **200**. Setting
  `gatewayiprange 10.0.0.0/24` / `gatewayaddress 10.0.0.1` fixed the
  `Managed IP range: 0.0.0.0/0` status.

### Client test (veth, 2026-10-29)

A veth pair + network namespace provided a real client (`10.0.0.100/24`,
default via 10.0.0.1):

- splash `http://10.0.0.1:2050/` → **200**, redirects to the TollGate portal;
- portal `http://10.0.0.1:2051/splash.html` → **200**;
- `ndsctl` sees the client (IP/MAC);
- pre-auth internet is blocked (ping and HTTP fail), as intended;
- `ndsctl auth 10.0.0.100` succeeds, but **post-auth internet still fails**
  (ping/HTTP blocked) both with BSBF enabled and with BSBF stopped.

The remaining blocker is the nodogsplash mark/fw4 forwarding interaction, not
the AP, the bridge, or the TollGate daemon. Evidence:
`evidence/portal/2026-10-29_client-veth.txt`.

Because the AP is open and `portal -> wan` forwarding exists, leaving it without
working portal enforcement would be an open gateway. The role was therefore
**rolled back** after the test; BSBF is healthy and the AP is disabled again.

Evidence: `evidence/portal/2026-10-29_bridge-test.txt`.

## Apply / confirm / rollback

```bash
ssh x280
cd ~/e750-repair
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-e750-portal.yml
# verify AP/DHCP/portal, then:
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-e750-portal-confirm.yml
# rollback:
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-e750-portal-rollback.yml
```

## Next

1. Fix post-auth forwarding: inspect the `ndsNET`/`ndsAUT` marks and the fw4
   `forward_portal`/`srcnat_wan` path; confirm whether `ndsctl auth` sets the
   mark for existing/new flows. Test with a real client after `ndsctl auth`.
2. Re-test with BSBF off and on; the failure reproduced in both, so start with
   the standalone path.
3. Then re-apply the role and decide standalone vs combined.
4. Do not leave the open AP running without working enforcement.

## Caveats

- The portal and management share the 2.4 GHz radio; airtime is shared.
- The STA/BSBF path is left enabled, so this is effectively a combined-mode
  test; standalone still needs a decision on the WAN.
- The role is not in the image yet.
