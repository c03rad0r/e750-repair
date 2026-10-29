# TollGate on the E750 — evaluation

Status: **evaluated, no-go for this unit** (2026-10-29). The E750 stays a BSBF
bonded-WAN client. This is a role/conflict decision, not a statement that the
package is broken.

## Artifact check (v0.6.0)

TollGate publishes a package for exactly this target family:

| Item | Value |
|---|---|
| Release | `FreedomTechFeed/packages` **v0.6.0** |
| Asset | `tollgate-wrt-0.6.0-mips_24kc-ath79-nand-offline.tar.gz` |
| Size | 9,705,614 bytes (9.3 MB) |
| SHA256 | `bc5338ab88e9f79678aa63fdea7da9cbbc7e1ad53338fa572c2ab654ed00be7e` |
| Individual package | `tollgate-wrt_0.6.0_mips_24kc-ath79-nand.apk` (8.9 MB) |
| Bundle | 37 packages, including `nodogsplash 5.0.2`, `iptables-nft`, `jq`, `libmicrohttpd-no-ssl`, iptables/kmod modules for kernel 6.12.94 |

So installation is technically possible; the blocker is what TollGate does to
the device's role and network stack.

Evidence: `evidence/tollgate/2026-10-29_asset-check.txt`.

## Live device capacity

```text
overlay   105.7M total, 15.1M used, 85.9M free   (fits the 9.3 MB bundle)
RAM       119,796 kB total, ~15.7 MB available
board     glinet,gl-e750
arch      mips (mips_24kc)
radios    2.4 GHz only (5 GHz QCA9887 dead; AP disabled)
```

The flash fits. The CPU/RAM headroom is the concern: BSBF + xray + the 4G MBIM
stack already run on a single 650 MHz MIPS 24Kc core, and the monitor shows load
around 0.1–1.0.

## Why no-go now

1. **Role conflict.** TollGate turns the router into a WiFi access point with a
   captive portal (`nodogsplash` on :2050, TollGate on :2121, admin/portal
   uhttpd). The E750's only working radio is the **2.4 GHz STA uplink** to
   `hermes-lan`; the AP is disabled and the LAN is plain `eth0` (no `br-lan`).
   Enabling the AP needs the bridge migration that `roles/e750_network`
   deliberately refuses, and AP+STA on one 2.4 GHz radio contends with the BSBF
   path that currently carries ~17 Mbps.
2. **Firewall/nftables overlap.** TollGate's offline bundle installs
   `iptables-nft`, `xtables-nft`, and a set of iptables/kmod modules. BSBF uses
   an nft `tproxy` table plus policy routing. Both can coexist in principle, but
   a captive portal that rewrites NAT/forwarding is exactly the kind of change
   that needs a dedicated test, not the only live gateway.
3. **No tested rollback.** The E750 has no working serial adapter right now
   (PR #6/#8) and no `br-lan`; a bad captive-portal/NAT state would be harder to
   recover than an ordinary config rollback.
4. **CPU/RAM.** 15.7 MB available RAM and one 650 MHz core for BSBF, xray,
   nodogsplash, jq, uhttpd and the portal is unproven. The fleet's MT3000 class
   devices are the supported TollGate target and have far more headroom.

## Decision

- Keep the E750 as the BSBF client (`phy1-sta0` primary + `wwan0` backup).
- Do **not** install TollGate on this unit.
- If TollGate is wanted on the E750 later, the prerequisites are:
  5 GHz repaired (AP+STA), a `br-lan` migration with rollback, a reliable serial
  adapter, a full private backup, and a measured CPU/RAM/throughput test on a
  spare unit — then use the `ath79-nand` offline bundle above and verify its
  SHA256.

## If someone proceeds anyway (not recommended)

1. Full backup (`scripts/e750-backup.sh`) and a serial console.
2. Disable/stop BSBF first; do not run both data planes.
3. Verify the bundle SHA256, install the offline bundle, and immediately test:
   portal on the AP, DHCP, NAT, DNS, and a client payment flow.
4. Watch `top`, `free`, and the 2.4 GHz STA throughput; roll back if BSBF is
   needed again.

This is intentionally not automated in the repo. TollGate belongs on a
supported AP-class device, not on the bonded-WAN E750.
