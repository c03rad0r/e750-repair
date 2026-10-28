# QCA9887 cal-pci-only experiment

Status: **negative result; reverted** (2026-10-29). This is a one-variable
experiment, not a claim that the radio is fixed.

## Why cal-only

The earlier work installed **both** `pre-cal-pci-*.bin` and `cal-pci-*.bin`.
Finding a `pre-cal-*` file makes ath10k use `ATH10K_PRE_CAL_MODE_FILE`, which
changes the BMI board-id parameter and is the likely source of the new
`failed to get board id: -122`. The cal-only run installs only the full
calibration file:

```text
/lib/firmware/ath10k/QCA9887/hw1.0/cal-pci-0000:00:00.0.bin
```

It does **not** install `pre-cal-pci-*.bin`, and it does **not** install the
`11-ath10k-caldata` hotplug handler (which materialises both names).

## Verified baseline before the experiment

- `QCA9887/hw1.0/` contains only `board.bin` and `firmware-2.bin`.
- No `cal-pci` or `pre-cal` file.
- dmesg is the pre-install signature: `-22`, `otp calibration failed: 2`,
  **no `-122`**.
- `art` (mtd2) has the blob at `0x5000`, length `0x440`, header
  `44 08 1b a8 04 01`, MAC `94:83:c4:4d:fc:3a`.
- U-Boot `bootcmd` is the fixed `cp.b 0x9f060000 ...; bootm 0x81000000`.

## Run it

From x280 (the host with the E750 LAN link):

```bash
cd ~/e750-repair
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-cal-only.yml
```

The role backs up `/lib/firmware/ath10k` to `/tmp/e750-ath10k-backup`, backs up
`art` to `/tmp/e750-art.bin`, records the baseline dmesg, extracts and validates
the blob, installs only the `cal-pci` file, reboots, and reads the result back.

## Decision tree

| Result | Meaning | Next |
|---|---|---|
| No `-22`/`-122`, `radio1` present, `phy#` count ≥ 2 | 5 GHz initialized | Configure 5 GHz; keep the file; document the fix |
| `-122` appears | The cal file triggers the board-id path | Revert, confirm baseline, pursue the `-122`/BMI lead |
| Same `-22`, no `-122` | The cal file is not used or the board ID/EEPROM failure happens first | Revert; try a top-level `cal-pci` as a separate step; investigate `board.bin`/OTP |
| New/different failure | The blob or path is wrong | Revert; capture the full dmesg |

## Revert

```bash
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-cal-only-revert.yml
```

This removes the cal/pre-cal files and reboots to the baseline. The art and
firmware backups remain in `/tmp` for inspection.

## Evidence

Store the pre/post captures under `evidence/caldata/2026-10-29_*`:

- `dmesg | grep -i ath10k`
- `wifi status`
- `iw dev`
- `ls -l /lib/firmware/ath10k/QCA9887/hw1.0/`

## Results (2026-10-29) — negative

| State | cal files | `-22` | `-122` | 5 GHz `radio1` | `phy#` count |
|---|---|---|---|---|---|
| Baseline | none | yes | **no** | no | 1 |
| cal-only | `cal-pci-0000:00:00.0.bin` only | yes | **no** | no | 1 |
| Reverted | none | yes | **no** | no | 1 |

Installed only the nested `cal-pci` blob, rebooted, and read the device back.
The firmware directory contained `cal-pci-0000:00:00.0.bin`; there was no
`pre-cal-*`. The ath10k signature was **identical to the baseline**:

```text
board_file api 1 bmi_id N/A
failed to read device EEPROM at 0000
failed to read calibration data from EEPROM: -22
otp calibration failed: 2
could not init core (-22)
could not probe fw (-22)
```

There was **no `-122`**, and no 5 GHz radio (`radio0` only, one phy). The
cal-only experiment does **not** fix the radio.

What it does establish:

- The earlier `-122` was caused by the `pre-cal-*` file, not by the cal blob.
  Installing `cal-pci` alone leaves the original `-22` path untouched.
- The cal file is present but not sufficient. The failure is still at the
  EEPROM/board-id step (`bmi_id N/A`, `failed to read device EEPROM at 0000`),
  which happens before/around the calibration download. The next lead is the
  board ID/EEPROM/OTP path, not another cal-file copy.
- A top-level `cal-pci` copy is a cheap follow-up, but it is lower value than
  the board-id path.

The experiment was reverted: the firmware directory is back to `board.bin` +
`firmware-2.bin`, with no cal files, and the baseline `-22` signature is
restored. Evidence:
[`evidence/caldata/2026-10-29_pre-cal-only.txt`](../evidence/caldata/2026-10-29_pre-cal-only.txt),
[`..._post-cal-only.txt`](../evidence/caldata/2026-10-29_post-cal-only.txt),
[`..._revert.txt`](../evidence/caldata/2026-10-29_revert.txt).
