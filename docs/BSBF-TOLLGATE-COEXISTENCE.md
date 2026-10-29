# BSBF + TollGate + MCU — separate-first plan and tracker

Status: **IN PROGRESS.** This supersedes the TollGate "no-go" wording in
`docs/E750-TOLLGATE.md` (corrected in this change). Execution is tracked by the
checklist below; every code change is a PR to `main`.

Canonical repo: `felixfelix-bot/e750-repair`, default branch `main` (PRs #1–#16
merged when this file lands). All code changes land as PRs to `main`, merged
with the `felixfelix-bot` session on x280. No hand edits to the device except
physical steps and emergency recovery.

## Objective

Make **BSBF** and **TollGate** each work standalone on the E750, then combine
them on the same unit. Separately investigate the MCU/OLED and whether an
upstream contribution makes sense.

The E750 is **not the only gateway**, so the combined stack can be tested with a
real rollback path; it is still the only unit with the dead QCA9887, so radio
work stays isolated.

## Corrected assessment

The earlier TollGate no-go over-weighted the dead 5 GHz radio. The truths are:

- **AP+STA on the same 2.4 GHz radio is feasible** (ath9k multi-vif, same
  channel). 5 GHz absence costs airtime/headroom, not feasibility.
- The real blockers are: no `br-lan` today, AP disabled, BSBF's nft `tproxy` +
  policy routing vs TollGate's `nodogsplash`/iptables NAT, and CPU/RAM headroom.
- Therefore: **dedicated TollGate on 2.4 GHz AP+STA is viable**; **BSBF +
  TollGate together is the hard, unproven part**, not TollGate itself.

## Current verified state (2026-10-29)

- E750: OpenWrt **25.12.5**, kernel **6.12.94**, `glinet,gl-e750`, mips_24kc.
- Radios: 2.4 GHz only; QCA9887 5 GHz dead (`-22`, `bmi_id N/A`); no cal files.
- Network: `eth0` LAN `192.168.8.1/24`; `phy1-sta0` STA to `hermes-lan`
  (primary, metric 9); `wwan0` Aldi Talk MBIM backup (metric 13); BSBF enabled;
  egress `23.182.128.219`; ~17–20 Mbps on the STA path; 4G ~0.5 Mbps.
- Firewall WAN zone cleaned to `wwan wwan1`; AP disabled; no `br-lan`.
- Health monitor installed (5-min cron) and baked into the rebuilt image
  (`9ea82c93…`, 16,619,792 B); image not flashed.
- 24 h soak running from `2026-10-29T10:15:23Z` on x280.
- Serial adapter `BH00DL3M` is bad: 0/5 clean, every command corrupted; MT6000
  `BG046H5F` on the same hub is 5/5. **Serial is not a usable recovery path yet.**
- 4G RF healthy (RSRP ≈ -59 dBm, SINR ≈ 9); ~0.5 Mbps is likely a plan
  throttle, not signal.
- MCU: documented on `/dev/ttyS0` 115200, but probes at 9600–115200 got no reply;
  GL init hints at a `soft_uart` variant. No daemon shipped.

## Phase 0 — prerequisites (blocking for risky work)

- [ ] **Fix serial first** (physical): swap the E750 cable to the known-good
      `BG046H5F` adapter; if that works, replace/reflow `BH00DL3M`.
      Verify `serial-tx-test.py` 5/5 and `serial-wake.py id`.
- [ ] Optional but recommended: run `serial-tx-test.py --loopback` (10/10) and
      the continuity/wiggle test before relying on serial for flashing.
- [ ] Finish the 24 h soak; record the pass/fail summary. Stop early only for a
      planned experiment.
- [ ] Take a fresh private backup (`scripts/e750-backup.sh`) plus the current
      image/config before any flash or `br-lan` migration.
- [ ] Confirm the built image (`9ea82c93…`) is the one to flash after serial is
      reliable; do **not** flash before that.
- [ ] Keep a second gateway/AP available for the test window (user confirmed
      this is not the only gateway).

## Phase 1 — BSBF standalone (baseline, already live)

- [ ] Re-run the client playbook from `main` and confirm idempotence.
- [ ] Health check: BSBF enabled, both endpoints, tproxy, both WANs, egress =
      server, 5 GHz warning only.
- [ ] Re-test failover: drop the STA, confirm traffic moves to `wwan0` and
      egress stays the server; restore the STA.
- [ ] Record throughput (STA-only vs BSBF) and cold-boot persistence.
- [ ] Optional P1: move the BSBF server to an EU VPS (Houston adds ~160–170 ms)
      and parameterize the server host.
- [ ] Optional P1: check the Aldi Talk plan/throttle; if 4G improves, remove
      `wwan0` from the backup list and re-test aggregation.
- [ ] Keep BSBF config as the known-good baseline for the later combined test.

## Phase 2 — TollGate standalone on 2.4 GHz AP+STA

Goal: a working captive portal with no BSBF running, on the same unit.

### 2a. `br-lan` migration (config, reversible) — DONE/LIVE

- [x] Add a `br-lan` bridge containing `eth0` + the AP interface; move the LAN
      IP/DHCP to `br-lan`.
- [x] Add `phy1-ap0` (`mode: ap`) on the same channel as the STA (channel 11),
      SSID `TollGate-E750`, open (portal), `isolate=1`.
- [x] Keep `phy1-sta0` as the WAN (`wwan`) with metric 9.
- [x] Firewall: `lan` zone = `br-lan`; WAN zone = `wwan`/`wwan1`; masq on;
      forwarding `lan -> wan`; firewall reloaded.
- [x] Rollback: `playbook-e750-ap-rollback.yml` + watchdog; tested (the first
      attempt reverted cleanly to `eth0`).
- [x] Measure: client scan sees the AP, association succeeds, ping to
      192.168.8.1 works; DHCP/DNS/NAT/throughput are the next test.
- [x] Fixes: unique AP MAC, `beacon_int=100`, `dtim_period=2`, full
      `wifi down`/`wifi up`. Evidence `evidence/ap/2026-10-29_ap-sta.txt`.
      PR #17.

### 2b. TollGate install (no BSBF) — ATTEMPTED, FAILED, ROLLED BACK

- [x] Verified the v0.6.0 `mips_24kc-ath79-nand` bundle SHA256
      (`bc5338ab…`) and installed the offline bundle on the E750.
- [x] `nodogsplash`, the portal, the backend and the admin board started on
      80/2050/2051/2121/8080/8090/8443; eth0 moved to `br-private` 192.168.9.1.
- [x] Result: TollGate's upstream manager removed the STA/AP vifs; `br-lan` was
      left DOWN, hostapd could not recreate the AP, mint probes timed out, and
      the serial showed process kills under memory pressure.
- [x] Rollback: stopped/disabled the services, restored the pre-change config,
      reset uhttpd, removed the TollGate nft includes, rebooted, re-applied
      BSBF. **BSBF is healthy again.**
- [ ] Next: **4G WAN + AP-only** (no STA) to avoid the single-radio AP+STA
      race; then Ethernet WAN + AP-only; then a two-radio/5 GHz-repaired unit.
- [ ] Do not retry the same combined-radio install; do not start Phase 3 until a
      standalone topology is stable.

Evidence: `evidence/tollgate/2026-10-29_standalone-attempt.txt`.

### 2c. Alternative topologies (if AP+STA is too slow)

- [ ] 4G WAN + AP (clean radio, but ~0.5 Mbps).
- [ ] Ethernet as WAN + AP (best backhaul, loses the LAN port; verify the single
      PHY can be reassigned in software).
- [ ] Record the measured trade-off in the docs.

## Phase 3 — Combine BSBF and TollGate

Only after both standalone tests pass.

### 3a. Traffic/zone design

- [ ] Keep `br-lan` as the portal zone; `wwan`/`wwan1` as WAN.
- [ ] Ensure pre-auth portal traffic never enters the BSBF tproxy (captive
      portal redirect/DNS must stay local).
- [ ] Route post-auth client traffic through BSBF; keep router-originated
      traffic on the normal WAN path.
- [ ] Reconcile `nodogsplash`/iptables-nft rules with the BSBF nft `tproxy`
      table; document rule order and any excludes.
- [ ] Decide whether BSBF subflows use the STA, 4G, or both while the portal is
      active (airtime budget).
- [ ] Add a kill switch: stop BSBF or TollGate independently without a reboot.

### 3b. Test matrix

- [ ] Cold boot with both enabled: portal comes up, BSBF endpoints present,
      egress = server.
- [ ] Unauthenticated client: portal works, no BSBF leak.
- [ ] Authenticated client: traffic traverses BSBF, egress = server.
- [ ] STA drop: failover to 4G still works while the portal is up.
- [ ] Portal restart / BSBF restart independently: no deadlock.
- [ ] Throughput and CPU/RAM with one and several portal clients.
- [ ] 24 h soak with both enabled; no unexplained failures.
- [ ] Rollback to BSBF-only and to TollGate-only, both tested.

### 3c. Fallbacks if coexistence is unstable

- [ ] Separate the roles: BSBF on the E750, TollGate on another AP-class device
      (MT3000-class), or vice versa.
- [ ] Boot-time mode switch (two configs/images) rather than simultaneous.
- [ ] Document the chosen fallback and why.

## Phase 4 — MCU/OLED and upstream

- [ ] **Confirm the transport before writing code.** Inspect GL's kernel
      patches/DTS for `soft_uart` and the MCU GPIOs; determine whether the MCU is
      on the hardware UART, a bit-banged soft UART, or a mux.
- [ ] Probe the correct port with GL's full sample JSON (not only `version`)
      while watching the OLED; stop if there is still no reply.
- [ ] Decide the implementation:
      - [ ] source-only procd/shell JSON daemon (fastest, risk of malformed JSON);
      - [ ] build GL's `gl-e750-mcu` for 25.12/mips_24kc (best fidelity, prebuilt
            static libs, not upstreamable);
      - [ ] clean-room serdev/userspace driver (upstream-friendly, most work).
- [ ] Solve console coexistence explicitly: disable `askfirst`, use a mux/proxy,
      or a dedicated UART. Document the trade-off (no serial console vs OLED).
- [ ] Upstream contribution:
      - [ ] a **source-only userspace package** for the JSON protocol is the
            realistic candidate for the packages feed;
      - [ ] a DT binding + serdev driver only if the hardware actually has a
            separate/muxable UART; expect pushback on console hijacking;
      - [ ] include license, tests, and a hardware note; no prebuilt blobs.
- [ ] Only after a reply and a reliable serial path: add the daemon to the image,
      with a watchdog and a kill switch.

## Phase 5 — Image and docs

- [ ] Fold the validated TollGate config (and, if ready, MCU) into
      `image/files`/`image/packages.txt`; keep PSK/UUID out of the image.
- [ ] Rebuild; the build already fails if operational files are missing.
- [ ] Update `docs/E750-TOLLGATE.md` to replace the no-go with the corrected
      separate/combined results.
- [ ] Update `docs/E750-MCU.md`, `docs/E750-IMAGE.md`,
      `docs/E750-NETWORK-HEALTH.md`, `README.md`, and this tracker.
- [ ] Keep `docs/E750-REMEDIATION.md` as the canonical checklist.

## Phase 6 — Acceptance and audit

- [ ] `python3 -m pytest -q` passes; new contract tests for the AP+STA/br-lan
      config, TollGate standalone, and the combined mode.
- [ ] Live evidence under `evidence/tollgate/`, `evidence/network/`,
      `evidence/combined/` (no PSK, UUID, private keys, or art dumps).
- [ ] 24 h soak for the combined mode; cold boot; failover; rollback.
- [ ] All changes merged to `main` via PRs; no unmerged branches.
- [ ] Final audit: no secrets, no calibration dumps, no image/signing keys.

## Risks and guardrails

- **Serial is the hard prerequisite.** Do not flash, migrate `br-lan`, or run
  MCU write experiments until the adapter works.
- **Airtime:** AP+STA shares one 2.4 GHz radio; the portal will reduce BSBF
  throughput. Measure before promising a combined mode.
- **TollGate vs BSBF rules:** both touch NAT/tproxy. Test each rule change; keep
  a kill switch and a config backup.
- **MCU JSON:** GL warns malformed JSON can shut the router down and boot-loop.
  Never autostart an unverified writer.
- **5 GHz:** repair remains a separate P0; do not couple it to the
  TollGate/BSBF work.
- **This is not the only gateway**, so a failed combined test can be rolled back
  without losing connectivity.

## Physical / non-IaC steps (explicit exceptions)

- Replace/reflow the E750 serial adapter/cable.
- SIM plan/antenna/position.
- Choose/move the BSBF server VPS.
- If the E750 is bricked, serial/U-Boot recovery is physical.

Everything else is a role, playbook, image file, test, doc, or evidence file
merged to `main` via a PR.

## Implementation queue (start here)

Status: **documentation complete; code/device work not started** (Plan mode).
Each item is a PR to `main`; device-touching items are gated on Phase 0.

| # | PR | Device-touching? | Depends on | Acceptance |
|---|---|---|---|---|
| 1 | docs: correct TollGate assessment; add this plan to `docs/` | no | none | links, checklist, 65+ tests pass |
| 2 | feat: `roles/e750_ap` + `br-lan` migration (eth0 + `phy1-ap0`, STA stays WAN), dry-run/tests | yes (apply later) | serial fixed, backup | AP+STA association, DHCP, NAT, rollback tested |
| 3 | feat: TollGate standalone role (pinned v0.6.0 bundle, SHA256, portal, no BSBF) | yes | #2 | portal/payment/DNS tests, CPU/RAM/throughput |
| 4 | feat: combined mode (zone/tproxy rules, kill switches, test matrix) | yes | #2 + #3 | full matrix + 24 h soak |
| 5 | docs/feat: MCU transport confirmation (`soft_uart`/DTS/GPIO), then daemon decision | read-only first | serial fixed for writes | reply from MCU or documented stop |
| 6 | feat: image integration for the validated TollGate/MCU config | no flash | #3/#4/#5 | build check + evidence, no flash until serial |

### First three PRs — detailed checklist

**PR 1 — docs correction (no device change)**

- [ ] Add `docs/BSBF-TOLLGATE-COEXISTENCE.md` (this plan, repo copy).
- [ ] Rewrite `docs/E750-TOLLGATE.md`: 5 GHz is not the blocker; AP+STA is
      feasible; the hard part is BSBF coexistence.
- [ ] Update `docs/E750-REMEDIATION.md` Phase 8 and the tracker.
- [ ] Add a contract test that the corrected wording and checklist exist.
- [ ] Merge via x280.

**PR 2 — AP+STA / `br-lan` role (code + dry run)**

- [ ] `roles/e750_ap`: create `br-lan` (`eth0` + `phy1-ap0`), LAN IP/DHCP on the
      bridge, AP on the STA channel, WPA2, firewall `lan` zone.
- [ ] Variables for SSID/PSK (no secret default), channel-follow-STA, `isolate`.
- [ ] Idempotent raw-only tasks; pre-change config backup; explicit rollback.
- [ ] Contract tests for the UCI shape and the rollback.
- [ ] Apply on the test unit only after Phase 0; capture association/DHCP/NAT.
- [ ] Merge.

**PR 3 — TollGate standalone role**

- [ ] Pin the v0.6.0 `mips_24kc-ath79-nand` bundle SHA256
      (`bc5338ab…`) and download/verify it.
- [ ] Install with BSBF stopped; start `nodogsplash`/TollGate; no BSBF rules.
- [ ] Portal/payment/DNS/logout test; CPU/RAM/conntrack/throughput capture.
- [ ] Disable/rollback path; no autostart until the portal is verified.
- [ ] Merge.

### Definition of done for the whole workstream

- [ ] BSBF-only, TollGate-only, and combined modes each have a tested rollback.
- [ ] AP+STA on 2.4 GHz measured and documented (throughput/airtime).
- [ ] Combined mode passes the test matrix and a 24 h soak, or the fallback is
      documented and implemented.
- [ ] MCU either works with a source-only package or is documented as
      blocked/out-of-scope with the transport evidence.
- [ ] Everything is merged to `main` via PRs; image rebuilt; no secrets.
