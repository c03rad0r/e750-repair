# GL-E750 remediation + BSBF IaC — plan and tracker

Status: **5 GHz portal AP + BSBF/TollGate combined working; remaining items are
hardware/decision-gated.** PRs #1–#31 are merged on `main` at `3bff0a5`. The
QCA9887 now runs as an uncalibrated 5 GHz portal AP via `skip_otp=1`; the 2.4
GHz radio is the STA/BSBF backhaul. Serial has a checksummed exec channel (raw
link 96/100). A clean 24 h soak started `2026-10-29T17:17:45Z`. Remaining:
real 5 GHz client/payment, calibration/OTP, EU server, 4G plan, image.

## Execution log

- 2026-10-29 — PR #1 `01176a4`: BSBF client/server IaC.
- 2026-10-29 — PR #2 `8c1e246`: cal-only experiment, negative, reverted.
- 2026-10-29 — PR #3 `dad1ecd`: operator key access (x280 + T14).
- 2026-10-29 — PR #4 `e386898`: tracker sync.
- 2026-10-29 — PR #5 `36c26be`: 4G diagnostics (RF healthy, plan-throttled).
- 2026-10-29 — PR #6 `9b54cd5`: serial fault isolated (E750 leg 0/5, MT6000 5/5).
- 2026-10-29 — PR #7 `3abaa01`: WAN firewall cleanup + health check.
- 2026-10-29 — PR #8 `6e6304a`: serial loopback + cold-joint/continuity runbook.
- 2026-10-29 — PR #9 `c776230`: clean ImageBuilder image (16.6 MB, 188 pkgs).
- 2026-10-29 — PR #10 `e17d928`: 5-minute health monitor (cron + syslog).
- 2026-10-29 — PR #11 `9e44757`: MCU/OLED protocol investigation, daemon deferred.
- 2026-10-29 — PR #12 `f1a9b6f`: TollGate v0.6.0 evaluation, no-go on this unit.
- 2026-10-29 — PR #13 `c471cbc`: soak harness + final audit; soak started.

This is the canonical tracker for the E750 work. Remaining work is consolidated in
[`ROADMAP.md`](ROADMAP.md).

Canonical repo: `felixfelix-bot/e750-repair`, default branch `main`.
All code changes land as PRs to `main`; no hand edits to the device except
physical steps (cable, SIM, antenna) and emergency recovery.

## Current live state (verified 2026-10-29)

- E750: OpenWrt **25.12.5**, kernel **6.12.94**, board `glinet,gl-e750`.
- Radios: **5 GHz portal AP + 2.4 GHz STA**. The QCA9887 initializes with
  `skip_otp=1` (no per-device calibration); `phy2-ap0` is the 5 GHz portal AP on
  `br-portal` 10.0.0.1. The 2.4 GHz AP is disabled; `phy1-sta0` is the BSBF
  uplink. A normal boot without `skip_otp` still shows the `-22` OTP failure.
- Firmware dir: `QCA9887/hw1.0/` has only `board.bin` + `firmware-2.bin`;
  no `cal-pci` / `pre-cal` files. The cal-only experiment was run and reverted;
  see `docs/CALDATA-CAL-ONLY.md`.
- `art` (mtd2) still holds the QCA9887 blob at `0x5000`, length `0x440`,
  header `44 08 1b a8 04 01`, MAC `94:83:c4:4d:fc:3a`.
- U-Boot `bootcmd` is fixed:
  `cp.b 0x9f060000 0x81000000 0x400000; bootm 0x81000000`.
- Network: `eth0` LAN `192.168.8.1/24`; `phy1-sta0` 2.4 GHz STA to
  `hermes-lan` (primary, metric 9); `wwan0` Aldi Talk 4G MBIM (backup,
  metric 13). BSBF enabled; endpoints correct; egress `23.182.128.219`.
- Firewall: `lan` zone → `wan`; `wwan1`/`wwan` in the WAN zone; masq on.
- Space: 192 packages; 85.9 MB free on overlay.
- Access: Dropbear has **2** authorized keys (x280 + T14); T14 can SSH via
  x280. The E750 host key after the 25.12.5 reflash is
  `SHA256:wsNm…`; x280 and T14 agree. `/root/.ssh/authorized_keys` still has 16
  keys that Dropbear does not read. Serial `/dev/ttyE750` on x280 works but TX
  is marginal.
- Screen/MCU: no MCU package or process; the OLED shows little.
- PR #1 (BSBF client + server IaC) merged at `01176a4`.

## Merge mechanics

`c03rad0r` has pull-only on `felixfelix-bot/e750-repair`. **x280 and cobrador
are logged in as `felixfelix-bot`** with admin scopes, so merges are done there:

```bash
ssh x280 'gh pr merge 1 --repo felixfelix-bot/e750-repair --squash --delete-branch'
```

For every later PR:

```bash
ssh x280 'gh pr merge <N> --repo felixfelix-bot/e750-repair --squash --delete-branch'
```

No direct pushes to `main`. Each PR must include tests, docs, evidence, and a
rollback note.

## Phase 0 — merge the existing BSBF IaC

- [x] Re-check PR #1 (clean/mergeable, no secrets in the diff).
- [x] Merge PR #1 from x280 with the `felixfelix-bot` session.
- [x] Verify `main` contains `roles/bsbf`, `roles/bsbf_server`,
      `roles/verify_bsbf`, both playbooks, docs, and evidence.
- [x] Record the merge commit in this tracker: `01176a4`.
- [x] Keep `main` as the only deploy source; re-run the role from `main`.

## Phase 1 — preserve the baseline before touching the radio

- [x] Branch `pr/caldata-cal-only` from `main`.
- [x] Add a `docs/E750-REMEDIATION.md` (this plan) to the repo.
- [x] Back up outside git (private): mtd1 U-Boot env, mtd2 `art`, the
      `/lib/firmware/ath10k` tree, `uci export`, current dmesg, Dropbear/root
      authorized keys. Written to `~/.local/share/e750-backup-*` on x280.
- [x] Verify the art header/MAC and the current pre-install signature.
- [x] Add `scripts/e750-backup.sh` (read-only on art) so the backup is
      repeatable; the output is private and gitignored by location.
- [x] Combined with Phase 2 in PR #2 (baseline + cal-only experiment).

## Phase 2 — cal-only experiment (P0, one variable) — NEGATIVE

The previous attempt installed **both** `pre-cal-pci-*.bin` and `cal-pci-*.bin`.
`pre-cal-*` switches ath10k to `ATH10K_PRE_CAL_MODE_FILE`, which is the likely
source of the new `failed to get board id: -122`. This experiment installs
**only `cal-pci-0000:00:00.0.bin`**, not `pre-cal-*`, and skips the hotplug
handler that would recreate both.

- [x] Add `roles/caldata_cal_only` (raw/no-Python, cal-pci only, no hotplug).
- [x] Add `playbook-cal-only.yml`, `playbook-cal-only-verify.yml`, and
      `playbook-cal-only-revert.yml`.
- [x] Add `tests/test_caldata_cal_only_contract.py`.
- [x] Add `docs/CALDATA-CAL-ONLY.md` with the baseline, commands, expected
      signatures, and revert.
- [x] Run the experiment on the E750:
  - [x] extract/verify art `0x5000`/`0x440`;
  - [x] install only `cal-pci`;
  - [x] reboot; capture `dmesg | grep ath10k`, `wifi status`, `iw dev`;
  - [x] compare: `-122` present/absent, `-22`, `bmi_id`, 5 GHz phy.
- [x] Evidence under `evidence/caldata/2026-10-29_*`.
- [x] Result: **negative.** Same `-22`; **no `-122`**; no 5 GHz radio
      (`radio0` only, one phy). The cal file is present but insufficient; the
      `-122` was a `pre-cal` artifact.
- [x] Revert to the clean baseline (no cal files; baseline `-22` restored).
- [ ] Next: top-level `cal-pci` as a one-variable follow-up; then the
      board ID/EEPROM/OTP and BMI read path (`bmi_id N/A`).
- [x] PR #2 merged at `8c1e246` (experiment, tests, docs, evidence).

## Phase 3 — serial and access hardening (P0)

- [x] Add `roles/e750_access` + `playbook-e750-access.yml` (public keys only;
      preserve existing keys; mode 0600).
- [x] Add T14's public key to Dropbear: 2 keys now; T14 can SSH via x280.
- [x] Verify the Dropbear host-key change after the reflash; x280 and T14 agree
      on `SHA256:wsNm…`; stale T14 known_hosts entry removed, backup kept.
- [x] Add `docs/E750-ACCESS.md`; evidence in
      `evidence/access/2026-10-29_dropbear-keys.txt`.
- [x] Isolate the serial fault: E750 FTDI `BH00DL3M` is 0/5 clean and corrupts
      every command; MT6000 FTDI `BG046H5F` on the same hub is 5/5 clean and
      `id` works. `askfirst` needs a valid CR; the E750 prompt appears but
      commands corrupt. `latency_timer` 16→1 and `power/control=on` do not fix it.
- [x] Add `scripts/serial-tx-test.py`, `scripts/serial-wake.py`,
      `docs/SERIAL-RELIABILITY.md`, and evidence. PR #6 merged `9b54cd5`.
- [x] Add `serial-tx-test.py --loopback` plus the continuity/wiggle/reflow and
      cold-solder-joint runbook. PR #8 (loopback needs the physical TX/RX short;
      no hardware was moved).
- [ ] **Swap the E750 adapter/cable** to the known-good `BG046H5F` first, then
      replace with a genuine 3.3 V FTDI or CP2102; re-run
      `serial-tx-test.py` (expect 5/5) and `serial-wake.py id`. (physical,
      P0 recovery blocker)
- [ ] Keep the udev `/dev/ttyE750` name; make the serial port inventory-driven
      (`/dev/ttyE750` on x280, not hardcoded `/dev/ttyUSB3`).
- [ ] Reconcile the 16 keys in `/root/.ssh/authorized_keys`; Dropbear does not
      read that file by default.
- [x] PR #3 merged at `dad1ecd` (access role, docs, evidence).

## Phase 4 — 4G, server, and path quality (P1)

- [x] Add `scripts/e750-modem-diag.sh`, `roles/e750_modem_diag`, and
      `coreutils-stty`/`picocom`: `AT+CPIN?`, `AT+COPS?`, `AT+QCSQ`/
      `AT+QENG="servingcell"`, `AT+CGDCONT?`, `umbim` registration, data counter.
- [x] Run the diagnostics: SIM READY, MEDIONmobile LTE home, RSRP -59 dBm,
      SINR 9 dB, APN `internet.eplus.de`. RF is healthy; ~0.5 Mbps is likely a
      plan throttle/APN policy, not signal.
- [x] Evidence in `evidence/modem/2026-10-29_diag.txt`; docs
      `docs/E750-MODEM-DIAG.md`. PR #5 + merge.
- [ ] Check/upgrade the Aldi Talk plan; if 4G becomes faster than the STA,
      remove `wwan0` from `bsbf_backup_interfaces` and re-test aggregation.
- [ ] Parameterize the BSBF server host; stand up an EU server (or document the
      Houston latency); update client server/port/UUID through the role.
- [ ] Make the STA SSID/PSK a role variable from OpenBao; remove the hardcoded
      `<redacted-psk>`. Document `hermes-lan` vs `StarGate`/`c03rad0r` (nested OMR).
- [ ] Test the clean non-nested path; capture throughput.
- [ ] PR + merge each change.

## Phase 5 — network/role cleanup (P1/P2)

- [x] Clean the WAN firewall zone to the interfaces that exist: `wwan wwan1`
      (stale `wan`/`wan6`/`wan1` removed). masq/forwarding preserved; BSBF
      tproxy unaffected. Live 5 MB test: egress `23.182.128.219`, ~2.09 MB/s.
- [x] Add `e750_ap_enabled: false` and an explicit refusal in
      `roles/e750_network`; enabling the AP still needs a tested `br-lan`
      bridge migration (eth0 + AP). Documented in `docs/E750-NETWORK-HEALTH.md`.
- [x] Confirm the `bsbf-mptcp` site patches are re-applied by the role; document
      that a package upgrade requires re-running the client playbook.
- [x] Add `scripts/e750-health.sh`, `roles/e750_health`, and
      `playbook-e750-network-health.yml`: BSBF status, endpoints, tproxy, both
      WANs, server egress, 4G counters, 5 GHz warning. Live result `RESULT OK`.
- [x] Evidence `evidence/network/2026-10-29_firewall-health.txt`; docs
      `docs/E750-NETWORK-HEALTH.md`. PR #7 + merge.
- [ ] Optional bridge/AP migration when a 5 GHz radio makes AP+STA worthwhile.
- [ ] Optional server `add_addr_accepted` tuning.

## Phase 6 — screen/MCU (P2) — investigated, deferred

- [x] Confirm the MCU protocol: GL's `e750-mcu` uses `/dev/ttyS0` at 115200 and
      one JSON object per line; `mcu_status`/`version` are documented queries;
      the v2 UI uses `ubus call mcu` + UCI `mcu.global.*`.
- [x] Probe this unit: `{"version":"1"}` and `{"mcu_status":"1"}` at 9600,
      19200, 38400, 57600 and 115200 (console login stopped) returned **no
      reply**; only one real UART exists; no MCU daemon/package/USB device.
- [x] Add `scripts/mcu-probe.sh` (documented queries only, no UCI writes, no
      daemon, restores `askfirst`) and `docs/E750-MCU.md`.
- [x] Evidence `evidence/mcu/2026-10-29_probe.txt`. PR #11 merged.
- [ ] Build GL's `gl-e750-mcu` for 25.12/mips_24kc with the SDK, or port the
      procd shell approach — **only after** the probe returns a reply and a
      reliable serial recovery exists. Do not ship an unverified writer
      (malformed JSON can shut the MCU/router down and boot-loop).
- [ ] Fold the verified package/daemon into `image/packages.txt` and rebuild.

## Phase 7 — clean image (P2)

- [x] Add `image/` ImageBuilder recipe for `ath79/nand` / `glinet_gl-e750`:
      package list (BSBF client, `ip-full`, `mptcpize`, tproxy/ifb, MBIM,
      `umbim`, `uqmi`, `stty`, `picocom`, `curl`, `wpad-basic-mbedtls`, `luci`).
- [x] Add `image/files/etc/uci-defaults/99-e750-defaults`: LAN `eth0`
      `192.168.8.1/24`, DHCP, 4G MBIM APN `internet.eplus.de`, WAN zone
      `wwan wwan1`, AP disabled, key-only Dropbear, hostname/timezone. No PSK
      and no BSBF server/UUID.
- [x] Bake the two public operator keys (x280 + T14); no private material.
- [x] Pin the ImageBuilder tarball SHA256 in `image/build.sh`; the script only
      builds, it never flashes.
- [x] Build succeeded: 16,609,552 bytes, sha256 `5a6fee11…`, 188 packages;
      versions match the live device. Evidence
      `evidence/image/2026-10-29_build.txt`; docs `docs/E750-IMAGE.md`.
- [x] Rebuilt with the health monitor baked in: `/usr/bin/e750-health`,
      `/usr/bin/e750-health-cron.sh`, `/etc/crontabs/root` (0600), cron enabled
      at first boot. Final artifact 16,619,792 bytes, sha256 `9ea82c93…`;
      `build.sh` now fails if any operational file is missing from the rootfs.
      Evidence `evidence/image/2026-10-29_build-with-monitor.txt`. PR #15.
- [ ] Flash with a full backup and test cold boot/failover/egress — **blocked
      on a reliable serial adapter**; do not flash before the swap/reflow.
- [ ] Restore the `br-lan` bridge if the AP is ever enabled.
- [ ] Fold `gl-e750-mcu` into the image after Phase 6 (not yet: probe silent).
- [x] PR #9 + merge.

## Phase 8 — TollGate evaluation (P2) — REVISED

- [x] Verified the artifact: `FreedomTechFeed/packages` v0.6.0 publishes
      `tollgate-wrt-0.6.0-mips_24kc-ath79-nand-offline.tar.gz` (9.3 MB,
      sha256 `bc5338ab…`, 37 packages incl. nodogsplash/iptables-nft/jq).
- [x] Compared with the device: 85.9 MB free overlay (fits), ~15.7 MB available
      RAM, one 650 MHz MIPS core, 2.4 GHz only, AP disabled.
- [x] Decision (revised): **standalone TollGate is a go** on 2.4 GHz AP+STA
      (`phy1-ap0` + `phy1-sta0`, `br-lan` with `eth0`, portal on the AP, STA as
      WAN). **Simultaneous BSBF + TollGate is conditional** on the zone/tproxy
      and test matrix. The 5 GHz radio is now available for the portal.
- [x] `docs/E750-TOLLGATE.md` + evidence
      `evidence/tollgate/2026-10-29_asset-check.txt`. PR #12 merged; wording
      corrected in PR #16.
- [x] New separate-first tracker:
      `docs/BSBF-TOLLGATE-COEXISTENCE.md` (Phase 0–6, implementation queue,
      PR order, rollback and acceptance criteria).
- [x] Implement Phase 2a: `br-lan` + 2.4 GHz AP+STA
      (`roles/e750_ap`, watchdogs, confirm/rollback). Client scan, association
      and ping verified; DHCP/DNS/nft are the next TollGate test. Evidence
      `evidence/ap/2026-10-29_ap-sta.txt`; docs `docs/E750-AP.md`. PR #17.
- [x] Phase 2b attempted: TollGate v0.6.0 offline bundle installed; portal
      services started, but its upstream manager removed the STA/AP and the AP
      did not return; mint probes timed out and the kernel killed processes
      under memory pressure. Rolled back; BSBF healthy. Evidence
      `evidence/tollgate/2026-10-29_standalone-attempt.txt`.
- [x] 4G WAN + AP-only attempted: `br-lan` (eth0 + AP), AP-only, 4G as
      `network.wwan`, watchdog. After reload eth0/br-lan was unreachable; the
      AP was visible but had no LAN IP. TollGate was not started; the watchdog
      restored the config and BSBF was re-applied. Evidence
      `evidence/tollgate/2026-10-29_4g-aponly-attempt.txt`.
- [ ] Retry with separate management (`eth0` 192.168.8.1) and portal
      (`br-portal` 10.0.0.1 + AP) bridges, 4G WAN, serial attached.
- [x] Combined BSBF + TollGate mode works: `br-portal` + AP, BSBF on the
      management LAN, tproxy bypass for portal clients, post-auth HTTP 301,
      cold boot verified. Evidence
      `evidence/portal/2026-10-29_combined-bypass.txt` and
      `..._cold-boot-combined.txt`.
- [x] Clean 24 h combined soak started `2026-10-29T14:24:30Z`; complete it.
- [x] 5 GHz portal AP works with `skip_otp=1` (PR #31); 2.4 GHz is the
      STA/BSBF backhaul. Calibration/OTP and a real 5 GHz client/payment test
      remain.

## Phase 9 — monitoring, acceptance, and final merge

- [x] Add health checks: `bsbf-bonding --status`, `ip mp e`, nft tproxy,
      `ifstatus wwan1/wwan`, egress, 4G data, 5 GHz presence
      (`scripts/e750-health.sh`, `roles/e750_health`).
- [x] Schedule a 5-minute cron monitor with a rotating log and syslog on
      failure (`scripts/e750-health-cron.sh`, `roles/e750_monitor`,
      `playbook-e750-monitor.yml`). Live: two `OK` samples.
      Evidence `evidence/monitor/2026-10-29_cron-health.txt`; docs
      `docs/E750-MONITOR.md`. PR #10 merged.
- [x] Add `scripts/e750-soak.sh` (controller-side, read-only; 288 samples over
      24 h) and start the soak on x280 at `2026-10-29T10:15:23Z`. Evidence
      `evidence/soak/2026-10-29_start.txt`; live log
      `~/e750-soak/20261029T101523Z.log` on x280.
- [ ] Complete the 24 h soak; then reboot + cold-boot + failover + throughput
      evidence (the last three are already captured, the soak is the long pole).
- [x] Update `STATUS.md` and `README.md` for the cal-only result, the ops roles,
      and the current board-ID/EEPROM/OTP lead.
- [x] Confirm every change is on `main` via PR; no unmerged branches.
- [x] Final audit: no secrets, no private keys, no art dumps in the public repo
      (see the audit below).

## Final audit (2026-10-29)

- Tracked-file scan: no private keys, no WiFi PSK, no BSBF UUID, no art/cal
  dumps. The private backup stays in `~/.local/share` on x280; the ImageBuilder
  work tree (including its local signing key) is gitignored.
- Test suite: `python3 -m pytest -q` passes (see the PR log).
- All changes are merged to `main` via PRs #1–#13; no open PRs.
- Remaining work is physical/decision-gated: serial adapter swap/reflow, Aldi
  Talk plan, EU BSBF server, board-ID/EEPROM/OTP experiments, and the 24 h soak
  result.

## Acceptance criteria for every PR

- [ ] `python3 -m pytest -q` (new contract tests) passes.
- [ ] `ansible-playbook --syntax-check` passes.
- [ ] Live run on the E750 (or server) captured in `evidence/`.
- [ ] Docs updated; rollback documented.
- [ ] No UUID, PSK, private key, or art/calibration dump in the public diff.
- [ ] Merged with the `felixfelix-bot` account; branch deleted.

## Blockers / risks

- **Plan mode:** no writes/merges until the operator switches to a build agent.
- **Merge permission:** only the `felixfelix-bot` sessions on x280/cobrador can
  merge; `c03rad0r` is pull-only.
- **Serial:** the current FTDI clone corrupts TX; replace before relying on
  serial for the radio experiments.
- **5 GHz:** `skip_otp=1` works but is uncalibrated; keep txpower low and the
  art/firmware backups. Production use needs calibration/OTP validation.
- **4G:** ~0.5 Mbps, likely throttled/weak; physical plan/antenna work.
- **Server:** Houston adds ~160–170 ms; a European VPS is preferred.
- **Nested OMR:** `hermes-lan` is behind the MT6000 OMR tunnel; use an
  independent AP for a clean measurement.
- **Production relay:** `hermes-nvme` is a fleet relay; keep the BSBF server
  role reversible and documented.

## Physical / non-IaC steps (explicit exceptions)

- Replace the serial adapter.
- SIM plan/activation/antenna/position.
- Choose/move the BSBF server VPS.
- If the E750 is bricked, serial/U-Boot recovery is physical.

Everything else is a role, playbook, image recipe, test, doc, or evidence file
merged to `main` via a PR.
