# E750 network cleanup and health monitor

Phase 5 of the remediation: clean the WAN firewall zone to the interfaces that
exist, document the AP/bridge limitation, and add a critical health check.

## Firewall WAN zone

The WAN zone currently lists stale names from earlier configurations:

```text
wan wan6 wwan wan1 wwan1
```

Only `wwan` (2.4 GHz STA) and `wwan1` (4G MBIM) exist. The role finds the zone
named `wan`, replaces its network list with `wwan wwan1`, commits, and reloads
the firewall. The zone's `masq`, `input`, `forward`, and the `lan -> wan`
forwarding are untouched. The BSBF nft tproxy table is separate and is not
affected by the fw4 reload.

Rollback: set the list back with `uci add_list firewall.@zone[1].network=...`
for the original names, commit, reload. The old names are harmless; the cleanup
only removes stale references.

## AP / br-lan

The current LAN is `eth0`; the AP (`TollGate-E750`) is disabled. Enabling the AP
requires a `br-lan` bridge containing `eth0` and the AP interface, plus a tested
rollback. `roles/e750_network` defaults `e750_ap_enabled: false` and **refuses**
to enable it until that migration is implemented. Do not flip the AP on with the
current `eth0`-only LAN.

## Health check

`scripts/e750-health.sh` runs on the E750 and checks:

- `bsbf-bonding --status` = `enabled`;
- `ip mp e` has `phy1-sta0` primary and `backup dev wwan0`;
- the `bsbf_bonding` nft table has `tproxy`;
- `ifstatus wwan1` and `ifstatus wwan` are up;
- the router's egress (`ifconfig.me`) equals the BSBF server;
- 5 GHz presence is a **warning** (known QCA9887 repair issue), not a failure;
- `wwan0` data counters and the WAN firewall zone are printed.

Run:

```bash
ssh x280
cd ~/e750-repair
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-e750-network-health.yml
```

The playbook applies the firewall cleanup, then runs the health role. A critical
failure fails the play; a missing 5 GHz radio only prints `WARN`.

## Evidence

`evidence/network/2026-10-29_firewall-health.txt` contains the cleaned zone and
the health report (no secrets; the WiFi PSK is not queried).
