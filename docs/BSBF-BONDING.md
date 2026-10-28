# BSBF bonding on the GL-E750

Status: **live on the bench unit, 2026-10-28.** This is a separate workstream
from the 5 GHz radio repair; it does not change the `STATUS.md` verdict.

## What it is

BSBF (BondingShouldBeFree) uses mainline MPTCP plus xray/VLESS and an nftables
TPROXY redirect. The client (this E750) sends proxied TCP/UDP to a BSBF server;
the server uses MPTCP on its inbound so the client can open subflows over each
WAN. The client marks one WAN primary and can mark others backup.

- Client: `bsbf-bonding`, `bsbf-mptcp`, `xray-core`, `ip-full`, `mptcpize`.
- Server: `bsbf_server` role in this repository, on `hermes-nvme`
  (23.182.128.219). See [`BSBF-SERVER.md`](BSBF-SERVER.md).
- No BSBF source is vendored; the roles fetch pinned upstream files.

## Topology

```text
hermes fleet ── eth0 ── E750 LAN 192.168.8.1/24
                          │
                          ├── phy1-sta0  2.4 GHz STA to hermes-lan (WAN, metric 9)
                          │      └── MT6000 hermes-lan ── OMR ── internet
                          └── wwan0      Aldi Talk 4G, MBIM (WAN, metric 13)
                                 └── BSBF server 23.182.128.219:16384
```

- `eth0` is the LAN; the E750's AP (`TollGate-E750`) stays disabled, so the
  single 2.4 GHz radio is STA-only.
- The 4G WAN is `network.wwan1` with `proto=mbim`, `device=/dev/cdc-wdm0`,
  `apn=internet.eplus.de`, `pdtype=ipv4`.
- The STA WAN is `network.wwan`, metric 9; the 4G is metric 13.
- `bsbf-mptcp-subflow-backup` contains `wwan0`, so 4G is **backup**, not part of
  the aggregate.

## Measured on this unit

| Path | Throughput | Notes |
|---|---|---|
| Direct 4G (`--interface wwan0`) | ~0.5 Mbps (62 KB/s) | Aldi Talk; likely throttled or weak signal |
| Direct STA/OMR (`--interface phy1-sta0`) | ~15 Mbps (1.89 MB/s) | 5 MB in 2.65 s |
| BSBF, STA only | **~22.6 Mbps (2.83 MB/s)** | 10 MB in 3.54 s |
| BSBF, STA + 4G **backup** | **~20.5 Mbps (2.57 MB/s)** | 10 MB in 3.90 s; 4G not used |
| BSBF failover to 4G | ~0.52 Mbps (65 KB/s) | 1 MB in 15.3 s; egress still the BSBF server |
| BSBF server egress | ~343 Mbps | 10 MB in 0.23 s |
| E750 → BSBF server RTT | ~160–170 ms | Server is in Houston; E750 is in Germany |

The 4G link is the reason it is declared backup. When 4G was the primary
initial subflow, throughput collapsed to the 4G rate. A better SIM plan,
external antenna, or a closer BSBF server would change that.

## Why the site patches exist

The upstream client has two assumptions that do not hold on this musl/ath79
build:

1. **`mptcpize` / `check.mptcp.dev` probe.** It reports “You are not using
   MPTCP” even though the kernel data path works. The role replaces only that
   probe result with a positive and changes the connectivity probe target to
   `1.1.1.1`. The actual MPTCP connection is still verified end-to-end by the
   egress check.
2. **Endpoint race at boot.** `bsbf-mptcp` only adds an endpoint when an
   interface crosses from “not supported” to “supported”. If the first add
   fails because the interface has no IPv4 address yet, it never retries. The
   role changes the condition to “no endpoint for this interface yet”, so it
   retries every second until the address is ready.

The role also patches `bsbf-bonding-nft` so a cold boot loads `nft_tproxy` and
creates the table before the upstream batch file's `destroy` command runs.

These are site patches to `/usr/sbin/bsbf-mptcp` and
`/etc/init.d/bsbf-bonding-nft`; re-running the role restores them after a
package upgrade.

## Run it

From x280 (the host with the E750 LAN link):

```bash
cd ~/e750-repair
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-bsbf-client.yml \
  -e bsbf_server_ipv4=23.182.128.219 \
  -e bsbf_server_port=16384 \
  -e bsbf_client_uuid=<uuid-from-state/bsbf/hermes-nvme.json>
```

The UUID is a credential; it lives in `state/bsbf/hermes-nvme.json` (mode 0600,
gitignored) or in OpenBao. Do not commit it.

Verification is built into `roles/verify_bsbf`: it fails unless both endpoints
exist, the 4G is backup, the tproxy table is present, xray is running, BSBF
reports `enabled`, and the router's egress is the BSBF server.

## Caveats

- **5 GHz is still dead.** The QCA9887 repair is unsolved; only 2.4 GHz is
  available. The STA and AP cannot run usefully at the same time.
- **The WiFi WAN is nested.** `hermes-lan` is the MT6000's own AP and is
  already behind the MT6000 OMR tunnel. The BSBF-over-OMR path is not an
  independent ISP path. For a clean comparison, use `StarGate`/`c03rad0r`.
- **The server is in Houston.** ~160–170 ms RTT from Germany. A European BSBF
  server would improve both latency and single-flow throughput.
- **4G is metered.** The role sets a 50 Mbps server-side client limit; the
  measured link is ~0.5 Mbps. The 4G is backup, so it is not consumed unless
  the STA fails.
- **CPU:** QCA9533, single core, ~650 MHz. The STA-only aggregate is ~22 Mbps;
  do not expect a 100 Mbps tunnel.

## Rollback

```bash
# on the E750
bsbf-bonding --disable
# restore the pre-BSBF network state if desired:
#   network.wwan.metric=13, network.wwan1 disabled, /etc/config/network from backup
# remove packages only if you are retiring the role:
apk del bsbf-bonding bsbf-mptcp bsbf-rate-limiting bsbf-quectel-usbnet \
  bsbf-autoconf-cellular bsbf-autoconf-dhcp xray-core

# on the server: see docs/BSBF-SERVER.md
```

Keep `inventory/hosts.yml` (serial console) as the recovery path; the serial
adapter is `/dev/ttyE750` on x280.
