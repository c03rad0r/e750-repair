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

## Live result (2026-10-29) — working combined mode

- `br-portal` UP at 10.0.0.1, `eth0` still 192.168.8.1, AP visible at
  `TollGate-E750` (ch11), STA connected, BSBF endpoints intact.
- dnsmasq on :67, `dhcp.portal` configured, firewall portal zone and br-portal
  rules present.
- **TollGate v0.6.0 daemon healthy** next to BSBF (`config_ok`, `network_ok`,
  `wallet_ok`; mint probes succeed).
- `nodogsplash` is configured with `gatewayinterface br-portal`,
  `gatewayiprange 10.0.0.0/24`, `gatewayaddress 10.0.0.1`, and a final
  `authenticated_users 'allow to 0.0.0.0/0'` (the package's private-range
  block rules otherwise ended the authenticated chain in REJECT).
- Portal SPA at `http://10.0.0.1:2051/splash.html` returns **200**; a real
  client gets **200** from the splash at :2050 (the earlier 500 was a request
  from the gateway itself).

### Client flow (veth client)

A veth pair + network namespace (`10.0.0.100/24`, default via 10.0.0.1)
simulates a portal client:

- splash/portal: 200;
- pre-auth ping/HTTP: blocked;
- `ndsctl auth <ip>`: success;
- post-auth ping: works; HTTP `http://1.1.1.1/` → **301** from Cloudflare.

### Root cause of the post-auth block

BSBF's nft **tproxy intercepted TCP from `br-portal`** and broke post-auth
traffic. The BSBF role now installs:

```text
nft insert rule ip bsbf_bonding prerouting_mangle iifname "br-portal" return
```

and persists it from the `bsbf-bonding-nft` boot hook
(`/etc/bsbf/tproxy-bypass.sh` + `/etc/bsbf/tproxy-bypass-interfaces`). Portal
clients use the normal WAN/NAT path; the management LAN keeps BSBF. fw4 still
rejects `portal -> lan`, so authenticated guests cannot reach `192.168.8.1`.

### Cold boot

`nodogsplash`, `tollgate-wrt` and the portal uhttpd are enabled. After a reboot:

- `br-portal`/AP/STA up, BSBF enabled with `phy1-sta0` primary + `wwan0` backup;
- the tproxy bypass is reinserted by the boot hook;
- splash/portal 200, pre-auth blocked, post-auth ping + HTTP 301;
- the first health sample at 1 min was transient `FAIL`, then `RESULT OK`.

Evidence: `evidence/portal/2026-10-29_client-veth.txt`,
`evidence/portal/2026-10-29_combined-bypass.txt`,
`evidence/portal/2026-10-29_cold-boot-combined.txt`.

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

1. Test from a phone/real client: association, DHCP lease, splash, payment
   flow, post-auth HTTP, logout.
2. Fold the nodogsplash/uhttpd portal settings into `roles/e750_portal` so a
   re-apply is fully reproducible.
3. Add the portal packages/config to the image (or document it as a runtime
   role).
4. 24 h combined soak; then update the tracker and image.

## Caveats

- The portal and management share the 2.4 GHz radio; airtime is shared.
- Portal clients bypass BSBF and use the normal WAN/NAT path; BSBF serves the
  management LAN. This is the working combined mode.
- The role is not in the image yet; the packages (`tollgate-wrt`,
  `nodogsplash`) are installed at runtime.
- The open AP is only safe while `nodogsplash` is enforcing; do not leave the
  AP up with the service stopped.
