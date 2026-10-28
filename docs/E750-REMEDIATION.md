# GL-E750 remediation + BSBF IaC — plan and tracker

Status: **IN PROGRESS.** PR #1 (BSBF IaC) `01176a4`, PR #2 (cal-only negative)
`8c1e246`, and PR #3 (operator access) `dad1ecd` are merged. The cal-only
experiment was negative (same `-22`, no `-122`, no 5 GHz) and was reverted.
Next: board ID/EEPROM/OTP; 4G diagnostics; serial cable (physical).

## Execution log

- 2026-10-29 — PR #1 merged `01176a4`: BSBF server/client IaC.
- 2026-10-29 — cal-pci-only experiment: negative; reverted; PR #2 merged
  `8c1e246`.
- 2026-10-29 — T14 operator key added to Dropbear; host key verified; PR #3
  merged `dad1ecd`.

This is the canonical tracker for the E750 work.

Canonical repo: `felixfelix-bot/e750-repair`, default branch `main`.
All code changes land as PRs to `main`; no hand edits to the device except
physical steps (cable, SIM, antenna) and emergency recovery.

## Current live state (verified 2026-10-29)

- E750: OpenWrt **25.12.5**, kernel **6.12.94**, board `glinet,gl-e750`.
- Radios: **2.4 GHz only**. 5 GHz QCA9887 is absent; dmesg is the
  **pre-install signature** (`-22`, `otp calibration failed: 2`, **no `-122`**).
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
- [ ] Replace the FTDI clone with a genuine FTDI or CP2102; verify zero TX
      corruption with `serial_wake.py` / repeated `echo`. (physical)
- [ ] Keep the udev `/dev/ttyE750` name; make the serial port inventory-driven
      (`/dev/ttyE750` on x280, not hardcoded `/dev/ttyUSB3`).
- [ ] Reconcile the 16 keys in `/root/.ssh/authorized_keys`; Dropbear does not
      read that file by default.
- [x] PR #3 merged at `dad1ecd` (access role, docs, evidence).

## Phase 4 — 4G, server, and path quality (P1)

- [ ] Add `scripts/e750-modem-diag.sh` and a diagnostics package set
      (`coreutils-stty`, `picocom`): `AT+CPIN?`, `AT+COPS?`, `AT+QCSQ`/
      `AT+QENG="servingcell"`, `AT+CGDCONT?`, `umbim` queries, APN, data counter.
- [ ] Measure the Aldi Talk plan/throttle/signal; try antenna/position.
      Current 4G ≈ 0.5 Mbps, so it stays backup.
- [ ] Parameterize `bsbf_backup_interfaces`; if 4G improves, remove `wwan0`,
      re-test aggregation, update docs/evidence.
- [ ] Parameterize the BSBF server host; stand up an EU server (or document the
      Houston latency); update client server/port/UUID through the role.
- [ ] Make the STA SSID/PSK a role variable from OpenBao; remove the hardcoded
      `<redacted-psk>`. Document `hermes-lan` vs `StarGate`/`c03rad0r` (nested OMR).
- [ ] Test the clean non-nested path; capture throughput.
- [ ] PR + merge each change.

## Phase 5 — network/role cleanup (P1/P2)

- [ ] Restore `br-lan` (eth0 + AP) if the AP is ever enabled; the BSBF autoconf
      changed LAN to `eth0` and the AP is disabled. Add a role variable/docs.
- [ ] Clean the WAN firewall zone network list (`wan wan6 wwan wan1 wwan1`);
      verify `wwan1`/`wwan` are in the zone and masq is on.
- [ ] Make the `bsbf-mptcp` site patches part of the role (already idempotent);
      add a package-upgrade check and a note to re-run the role.
- [ ] Add a 4G data-usage / BSBF health monitor (status, endpoints, egress,
      failover, data counter) with an alert.
- [ ] Optional: set server `add_addr_accepted` and test additional subflows.
- [ ] PR + merge.

## Phase 6 — screen/MCU (P2)

- [ ] Build/install `gl-e750-mcu` for OpenWrt 25.12 / mips_24kc, or write a
      small MCU daemon; show battery/signal/IP; keep the license clean.
- [ ] Add `roles/e750_mcu` or an ImageBuilder package; tests/docs/evidence.
- [ ] PR + merge.

## Phase 7 — clean image (P2)

- [ ] Add an ImageBuilder recipe for `ath79/nand` / `glinet_gl-e750`:
      package list (BSBF, `ip-full`, `umbim`, `stty`, `microcom`, MCU),
      `uci-defaults` for LAN/STA/APN, no Python.
- [ ] Restore the `br-lan` bridge if the AP is enabled.
- [ ] Build, flash with a full backup, test cold boot/failover/egress.
- [ ] PR + merge.

## Phase 8 — TollGate evaluation (P2, optional)

- [ ] Evaluate the `add_gle750` MIPS branch / `mips_24kc` package on this
      device: 128 MB NAND, 117 MB RAM, 2.4 GHz only.
- [ ] Decide TollGate vs BSBF WAN; document CPU/RAM/throughput.
- [ ] If adopted, add roles/tests/docs and PR + merge.

## Phase 9 — monitoring, acceptance, and final merge

- [ ] Add health checks: `bsbf-bonding --status`, `ip mp e`, nft tproxy,
      `ifstatus wwan1/wwan`, egress, 4G data, 5 GHz presence.
- [ ] 24 h soak + reboot + failover + throughput evidence.
- [ ] Update `STATUS.md`, `README.md`, docs, and this checklist.
- [ ] Confirm every change is on `main` via PR; no unmerged branches.
- [ ] Final audit: no secrets, no private keys, no art dumps in the public repo.

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
- **5 GHz:** cause unproven; cal-only may fail; keep the art/firmware backups.
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
