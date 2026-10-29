# TollGate standalone on the E750 — gated install

Status: **attempted 2026-10-29; unstable; rolled back.** The scripts encode the
install so it is reproducible, but they **refuse by default** on this board.
See [`E750-TOLLGATE.md`](E750-TOLLGATE.md) for the full result.

## What was tried

- v0.6.0 offline bundle for `mips_24kc-ath79-nand` (37 packages).
- The portal/backend services came up, but TollGate's upstream manager removed
  the STA/AP vifs; `br-lan` was left down, hostapd could not recreate the AP,
  mint probes timed out, and the kernel killed `uhttpd`/`udhcpc` under memory
  pressure.
- Rolled back to BSBF; BSBF is healthy again.

## Why the gate

The single 2.4 GHz ath9k radio has to carry the STA uplink, the portal AP and
TollGate's own radio management on 117 MB RAM. That combination was not stable.
The 5 GHz radio is dead; a second radio is the clean fix.

Do **not** re-run this on the E750 as-is. Use one of:

1. **4G WAN + AP-only** (`wwan1` upstream, `phy1-ap0` portal, no STA). This is
   the next test; 4G is ~0.5 Mbps but enough to validate the portal.
2. **Ethernet WAN + AP-only** (best backhaul; no wired LAN left).
3. **Two-radio device / repaired 5 GHz** (portal on one radio, STA on the
   other) for production.

## 4G WAN + AP-only attempt (2026-10-29)

A second topology was applied: `br-lan` with `eth0` + `phy1-ap0`, AP-only
(`wireless.sta.disabled=1`), and 4G as `network.wwan` (MBIM), with a 600 s
watchdog.

After the reload, `eth0`/`br-lan` 192.168.8.1 was unreachable from the
controller. The AP SSID was still visible in a scan, but the portal/LAN had no
reachable IP. TollGate was **not** started; this was a network-reconfiguration
failure, not a TollGate run. The watchdog restored the config after 600 s and
access returned; BSBF was re-applied and verified.

Evidence: `evidence/tollgate/2026-10-29_4g-aponly-attempt.txt`.

**Do not retry this sequence without a reliable serial console or a separate
management interface.** The safer next design is:

- keep `eth0` as the management LAN (`192.168.8.1`);
- create a separate `br-portal` (`10.0.0.1`) containing only `phy1-ap0`;
- set `nodogsplash.gatewayinterface=br-portal` and DHCP for the portal;
- use 4G as the WAN;
- test with serial attached and a watchdog.

## Usage (controlled test only)

Copy the two scripts to the router and run:

```sh
sh tollgate-standalone-install.sh --i-understand \
  --trust-mac <management-mac> \
  --admin-password-file /root/tollgate-admin.pw \
  --wifi-password-file /root/tollgate-wifi.pw
```

The script:

- requires `--i-understand` and prints the known failure otherwise;
- backs up `network`, `wireless`, `firewall`, `uhttpd` to `/tmp/tollgate-backup`;
- downloads/verifies the pinned v0.6.0 asset by SHA256 and the bundle manifest;
- stages the management keepalive with the given trust MAC, plus the admin/WiFi
  passwords (0600);
- runs the router-side installer. The network restarts and SSH may drop; run it
  under `setsid`/`nohup` and watch `/tmp/tollgate-install.log` if detached.

## Rollback

```sh
sh tollgate-standalone-rollback.sh
reboot
```

It stops/disables `tollgate-wrt`/`nodogsplash`, restores the config backup,
removes the TollGate uhttpd instances and nft includes, and resets uhttpd to
80/443. After reboot, re-apply the BSBF client playbook.

## Evidence

- `evidence/tollgate/2026-10-29_standalone-attempt.txt`
- `evidence/tollgate/2026-10-29_asset-check.txt`
