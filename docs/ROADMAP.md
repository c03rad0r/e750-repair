# E750 / BSBF / TollGate — remaining roadmap

Status: **combined mode working; remaining work is hardware/decision-gated.**
Default branch: `felixfelix-bot/e750-repair:main` (all PRs #1–#24 merged).
Tracker: [`E750-REMEDIATION.md`](E750-REMEDIATION.md) and
[`BSBF-TOLLGATE-COEXISTENCE.md`](BSBF-TOLLGATE-COEXISTENCE.md).

## Current live state (2026-10-29)

```text
eth0       192.168.8.1/24   management LAN
br-portal  10.0.0.1/24      phy1-ap0 (TollGate-E750, ch11)
phy1-sta0  hermes-lan       BSBF primary
wwan0      Aldi Talk 4G     BSBF backup
BSBF       enabled, tproxy bypass for br-portal, egress 23.182.128.219
TollGate   v0.6.0 daemon + nodogsplash + portal uhttpd :2051
health     RESULT OK
soak       24 h combined soak from 2026-10-29T14:24:30Z (first sample rc=0)
```

Verified: pre-auth splash/portal 200 and internet blocked; `ndsctl auth`;
post-auth ping + HTTP 301; cold boot re-applies the BSBF bypass and starts the
portal services. 86 contract tests pass.

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

- [ ] **Replace/reflow the E750 serial adapter** (`BH00DL3M`). The MT6000
      `BG046H5F` leg on the same hub is clean, so the E750 leg is bad.
      Verify `serial-tx-test.py` 5/5 and `serial-wake.py id`.
- [ ] Run `serial-tx-test.py --loopback` (10/10) and the continuity/wiggle test.
- [ ] Take a fresh private backup before any flash/radio experiment.
- [ ] **5 GHz QCA9887**: board-ID/EEPROM/OTP and BMI read path (`bmi_id N/A`);
      optional top-level `cal-pci` follow-up. Do not run risky firmware work
      without serial recovery.
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
      bake the portal/TollGate packages + `br-portal`/nodogsplash defaults into
      the image and rebuild. Do not flash before the serial fix.
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
