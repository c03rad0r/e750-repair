# BSBF evidence

Captured from the live bench unit and the fleet VPS on 2026-10-28. UUIDs are
redacted; no client credential or WiFi PSK is stored here.

| File | Contents |
|---|---|
| `2026-10-28_e750-client.txt` | Board/OS, MPTCP endpoints, routes, nft tproxy, BSBF status, router egress, LAN-client egress + 10 MB, direct 4G/STA throughput |
| `2026-10-28_hermes-nvme-server.txt` | Host, client registration, listener, ufw, MPTCP limits, `bsbf-mptcp-configuration` drop-in, server egress |
| `2026-10-28_failover.txt` | STA down → 4G carries traffic at ~65 KB/s; STA restored → primary endpoint returns |

Headline results:

- BSBF through the 2.4 GHz STA WAN: ~2.76 MB/s (~22 Mbps).
- Direct 4G: ~63 KB/s (~0.5 Mbps), which is why `wwan0` is marked backup.
- Failover to 4G keeps the egress at the BSBF server (`23.182.128.219`).
- Server egress: ~47.8 MB/s.
