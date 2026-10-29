# E750 separate portal bridge (AP-only)

This role creates a captive-portal bridge **separate from the management LAN**:

```text
eth0       192.168.8.1/24   management (unchanged)
br-portal  10.0.0.1/24      5 GHz phy2-ap0 only (TollGate-E750, ch36/VHT80)
phy1-sta0  hermes-lan       2.4 GHz STA/BSBF uplink (unchanged)
2.4 GHz AP disabled         airtime reserved for the backhaul
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
- `roles/e750_portal` now configures the nodogsplash gateway/range/address and
  the `allow to 0.0.0.0/0` rule, configures the portal uhttpd on :2051, and
  enables/starts `nodogsplash`, `uhttpd` and `tollgate-wrt`. A re-apply was
  tested end-to-end; evidence `evidence/portal/2026-10-29_role-reapply.txt`.

### Client flow (veth client)

A veth pair + network namespace (`10.0.0.100/24`, default via 10.0.0.1)
simulates a portal client:

- splash/portal: 200;
- pre-auth ping/HTTP: blocked;
- `ndsctl auth <ip>`: success;
- post-auth ping: works; HTTP `http://1.1.1.1/` → **301** from Cloudflare.

### Post-auth forwarding: from bypass to bonded

The first fix was a BSBF tproxy bypass for `br-portal`
(`iifname "br-portal" return`), which made portal clients use plain NAT.

Since 2026-10-29 the portal runs **over the bond** instead. A separate table at
prerouting priority `-140` (after nodogsplash's `mangle` marks) intercepts only
authenticated clients (`0x30000`) and tproxies them into BSBF:

```text
iifname "br-portal" ip daddr != 10.0.0.0/24   meta mark & 0x00030000 == 0x00030000   fib daddr type != local meta l4proto { tcp, udp } th dport != 53   tproxy to :12345 meta mark set 0x00030001
```

Pre-auth traffic keeps its `0x10000`/`0x20000` mark and is never tproxied, so
the splash still gates access. DNS and local destinations stay out of the
tunnel. Details and evidence: [`BONDING-SERVERS-PARALLEL.md`](BONDING-SERVERS-PARALLEL.md)
and `evidence/portal/2026-10-29_portal-over-bond.txt`.

The bypass in the main table is kept: it guarantees pre-auth and non-TCP/UDP
traffic never enters the tunnel. fw4 still rejects `portal -> lan`, so
authenticated guests cannot reach `192.168.8.1`.

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
2. Add the portal packages/config to the image (or document it as a runtime
   role; `tollgate-wrt` is not in the official OpenWrt feed).
3. 24 h combined soak; update the tracker and image.

## Caveats

- The portal uses the 5 GHz radio; the 2.4 GHz radio is the STA/backhaul. This
  removes the previous airtime conflict. The 5 GHz radio runs with
  `skip_otp=1` and no per-device calibration; see
  [`E750-RADIO5G.md`](E750-RADIO5G.md).
- Authenticated portal clients are tproxied into BSBF at priority `-140`; the
  main table still returns `br-portal` so pre-auth traffic never enters the
  tunnel. The management LAN uses the same bonded path.
- The role is not in the image yet; the packages (`tollgate-wrt`,
  `nodogsplash`) are installed at runtime.
- The open AP is only safe while `nodogsplash` is enforcing; do not leave the
  AP up with the service stopped.
