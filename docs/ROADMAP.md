# E750 / BSBF / TollGate — remaining roadmap

Status: **combined mode working; remaining work is hardware/decision-gated.**
Default branch: `felixfelix-bot/e750-repair:main` (all work merged via PRs; no open PRs).
Tracker: [`E750-REMEDIATION.md`](E750-REMEDIATION.md) and
[`BSBF-TOLLGATE-COEXISTENCE.md`](BSBF-TOLLGATE-COEXISTENCE.md).

## Current live state (2026-10-29)

```text
eth0       192.168.8.1/24   management LAN
br-portal  10.0.0.1/24      phy2-ap0 (TollGate-E750, 5 GHz ch36/VHT80)
phy1-sta0  hermes-lan       2.4 GHz STA/BSBF primary
2.4 GHz AP disabled         airtime reserved for the backhaul
wwan0      Aldi Talk 4G     BSBF backup
BSBF       enabled, tproxy bypass for br-portal, egress 23.182.128.219
TollGate   v0.6.0 daemon + nodogsplash + portal uhttpd :2051
health     RESULT OK
soak       24 h combined soak from 2026-10-29T17:17:45Z (first sample rc=0)
```

Verified: pre-auth splash/portal 200 and internet blocked; `ndsctl auth`;
post-auth ping + HTTP 301; cold boot re-applies the BSBF bypass and starts the
portal services. 103 contract tests pass.

## Completed milestones

| Area | State |
|---|---|
| BSBF client/server IaC | merged; live; failover tested |
| QCA9887 cal-only experiment | negative; reverted; documented |
| Operator access / Dropbear | merged; x280 + T14 keys |
| 4G diagnostics | merged; RF healthy, plan-throttled |
| Serial fault isolation + tools | merged; adapter `BH00DL3M` is bad |
| Network cleanup + health | merged; WAN zone, `RESULT OK` |
| Health monitor / image | merged; 5-min cron; image with monitor |
| MCU/OLED investigation | merged; protocol documented, daemon deferred |
| TollGate artifact evaluation | merged; v0.6.0 ath79-nand bundle |
| AP+STA (`br-lan`) | merged; client association + ping verified |
| Separate portal bridge | merged; `br-portal` + AP, management untouched |
| Combined BSBF + TollGate | merged; tproxy bypass, post-auth 301, cold boot |
| Portal role reproducibility | merged; nodogsplash/uhttpd/services in the role |

## Remaining work

### P0 — physical / recovery (needs input)

- [x] **Serial cable re-soldered** (2026-10-29): raw reliability improved from
      0/5 to **96/100** commands; ~4% errors remain.
- [x] **Checksummed serial exec** (`scripts/serial-exec.py`): base64 upload,
      device SHA-256, retransmit, decoded-script SHA-256, output SHA-256,
      `--dry-run`, dangerous-command gate. A natural bit flip was caught and
      retransmitted; the corrupted script was never executed. See
      [`SERIAL-CHECKSUM.md`](SERIAL-CHECKSUM.md).
- [x] 100-command test: 96/100 clean, 4 corrupt; the checksummed channel caught
      a natural bit flip and retransmitted. Evidence
      `evidence/serial/2026-10-29_100-command.txt`.
- [ ] Wiggle test; if errors cluster, reflow/swap the adapter. Use the
      checksummed channel for all Linux commands and `loadx`/`loady`/ZMODEM for
      U-Boot/files; never rely on the raw link for typed bootloader commands.
- [ ] ZMODEM (`sz`/`rz`) smoke test for file transfer; use `loadx`/`loady` in
      U-Boot, never typed write commands.
- [ ] Take a fresh private backup before any flash/radio experiment.
- [x] **5 GHz QCA9887 portal AP**: boot hook loads `skip_otp=1`; `phy2-ap0`
      serves `TollGate-E750` on ch36/VHT80 -> `br-portal`; 2.4 GHz is the
      STA/BSBF backhaul; cold boot verified, health OK. No per-device
      calibration; txpower 10 dBm. See [`E750-RADIO5G.md`](E750-RADIO5G.md)
      and [`QCA9887-SKIP-OTP.md`](QCA9887-SKIP-OTP.md).
- [ ] Real 5 GHz client: association, DHCP, splash, payment, post-auth
      (a veth client on `br-portal` already passes splash/portal/auth/HTTP 301).
- [x] `cal-pci` + `skip_otp` tried: AP stayed up, no evidence the cal file was
      used; removed it. `skip_otp` alone is the reproducible path.
- [ ] Add the boot hook and radio1 defaults to the image.
- [ ] Decide whether the 5 GHz repair is still required now that the combined
      2.4 GHz portal + BSBF path works (it is the long-term headroom fix).

### P1 — product / deployment

- [ ] **Real client + payment flow**: phone association, DHCP lease, splash,
      TollGate quote/invoice, post-auth traffic, logout; capture evidence.
- [ ] **Complete the 24 h combined soak** and review for unexplained failures.
- [ ] **BSBF server location**: choose an EU VPS (Houston adds ~160–170 ms) or
      keep `hermes-nvme`; parameterize and deploy.
- [ ] **Aldi Talk plan/throttle**: RF is healthy (~-59 dBm); ~0.5 Mbps is likely
      a plan limit. If it improves, test aggregation without the backup flag.
- [ ] **Secrets**: rotate the `hermes-lan` PSK (it was exposed in one diagnostic
      output) and move the STA PSK/BSBF UUID to OpenBao; remove plaintext UCI.
- [ ] **Image integration**: `tollgate-wrt` is not in the official OpenWrt
      feed. Decide on the pinned FreedomTechFeed bundle/custom feed; if adopted,
      bake the portal/TollGate packages + `br-portal`/nodogsplash defaults and
      the 5 GHz `ath10k-skip-otp` hook into the image and rebuild. Do not flash
      before a proven serial/checksum path.
- [ ] **TollGate standalone vs combined**: combined works; document whether a
      standalone 4G/STA portal is still a required mode.

### P2 — polish / upstream

- [ ] **MCU/OLED**: confirm the transport (`soft_uart`/DTS/GPIO vs `ttyS0`) and
      whether a source-only package is feasible; only then add a daemon/image
      package. Console coexistence must be explicit.
- [ ] **Upstream**: propose a source-only MCU userspace package if the protocol
      is confirmed; a serdev driver only if the hardware has a separate/muxable
      UART. Expect pushback on console hijacking.
- [ ] **Final audit**: `pytest`, `ansible-playbook --syntax-check`, no secrets,
      no art dumps, all PRs merged, image checksum recorded.
- [ ] **Optional**: EU latency test, 4G antenna/position, 24 h soak after any
      hardware change.

## Inputs needed from the operator

1. Fix/swap the serial adapter (physical).
2. A phone and a small Lightning payment for the end-to-end portal test.
3. Decision/credentials for an EU BSBF VPS.
4. Aldi Talk plan/high-speed status.
5. Decision on the TollGate custom feed for image integration.
6. Whether to continue the 5 GHz repair (physical/serial) now or later.

## Acceptance / definition of done

- Combined soak completes with no unexplained `FAIL`.
- Cold boot: BSBF endpoints + portal splash/SPA + post-auth HTTP.
- A real client completes payment and gets internet; logout works.
- Serial recovery is reliable; 5 GHz either fixed or formally deferred.
- Image builds with the chosen package set and is flashed only after the serial
  fix; checksum/evidence recorded.
- STA PSK/BSBF UUID in OpenBao; no secrets in the repo.
- All work merged to `main` via PRs; no open PRs.

## Rollback / guardrails

- Portal role has a watchdog and confirm/rollback playbooks; `eth0` management
  is separate from `br-portal`.
- BSBF keeps the management path; portal clients use normal WAN/NAT via the
  tproxy bypass.
- The open AP is only safe while nodogsplash enforces; never leave it up with
  the service stopped.
- Do not flash or run 5 GHz experiments without a reliable serial console.
