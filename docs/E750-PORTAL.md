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
- `nodogsplash` on :2050 returned **500** and reported
  `Managed IP range: 0.0.0.0/0`; adding `gatewayip`/`gatewaymask` did not fix it.
- No independent client association/DHCP test was possible: the controller's
  WiFi adapter is managed and drops a test vif.

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

1. Fix the nodogsplash splash/Managed-IP-range issue, or use a minimal redirect
   page to `http://10.0.0.1:2051/splash.html`.
2. Test association, DHCP, splash and post-auth from a phone or a dedicated
   client; capture the lease and the portal flow.
3. Re-apply the role, then decide standalone (4G or STA WAN) vs combined with
   BSBF.
4. Do not leave the open AP running without enforcement.

## Caveats

- The portal and management share the 2.4 GHz radio; airtime is shared.
- The STA/BSBF path is left enabled, so this is effectively a combined-mode
  test; standalone still needs a decision on the WAN.
- The role is not in the image yet.
