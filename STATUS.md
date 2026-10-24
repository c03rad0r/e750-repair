# STATUS — what is verified, and what is not

**Last updated: 2026-10-24**

This repo was created in the middle of an active diagnosis. Read this before
trusting anything else in it.

## ⚠️ The central claim is UNVERIFIED and probably WRONG

This repo was built on the theory that the E750's dead 5 GHz radio is caused by
**missing per-device calibration data** that a stock OpenWrt image never extracts
from the factory `art` partition, and that installing it fixes the radio.

**That theory has not survived contact with the hardware.** On the target unit:

1. The calibration files were installed, byte-verified, in the correct directory,
   under both names ath10k probes for.
2. The radio **still failed**, with the identical error.
3. The decisive detail: ath10k reports
   `board_file api 1 bmi_id N/A crc32 546cca0d` followed by
   `failed to get board id: -122` — it **rejects the board file before it ever
   applies per-device calibration**. A caldata problem cannot produce that
   ordering.

`bmi_id N/A` with `sub 0000:0000` points at the **board identity** layer (the
`board.bin` / OTP board data), not at the `art` calibration blob. That is a
different class of fault from the one this repo addresses.

**Do not treat the `caldata` role as a fix.** It is an unproven hypothesis, kept
because the extraction logic is sound and may be a *necessary* step once the real
cause is found — but it is demonstrably **not sufficient**.

## ✅ What IS verified (read back from the device, 2026-10-23/24)

| Finding | Evidence |
|---|---|
| The device **boots correctly** — this was never a boot failure | Full boot log captured twice; reaches `root@OpenWrt:~#`. Kernel verifies its own checksum, squashfs mounts, UBIFS recovers, `procd` starts. |
| `192.168.1.1` unreachable is **not a fault** | `br-lan: <NO-CARRIER,...> state DOWN`. The address `192.168.1.1/24` is configured correctly; the port simply has no link. |
| The 5 GHz QCA9887 **fails identically on every boot** | `failed to get board id: -122`, `failed to read calibration data from EEPROM: -22`, `could not init core (-22)` |
| The factory `art` partition **does contain** QCA9887-shaped data at `0x5000` | `44 08 1b a8 04 01` header, MAC `94:83:c4:4d:fc:3a` (consecutive with the 2.4 GHz MAC). Whether it is *valid for this radio* is **unproven**. |
| The shipped `board.bin` carries the **placeholder** MAC `00:03:7f:12:34:56` | `dd ... \| hexdump` of `/lib/firmware/ath10k/QCA9887/hw1.0/board.bin` |
| The stock hotplug has **no ath10k case** | `/etc/hotplug.d/firmware/10-ath9k-eeprom` only handles ath9k; every board case is `meraki,mr18` |
| The target's kernel is `6.12.80`, OpenWrt SNAPSHOT `r33865-8101611355`, `ath79/nand` | `/etc/openwrt_release` |

## 🔧 What in this repo is genuinely useful

These parts are independent of whether the caldata theory is right:

- **`connection_plugins/serial_console.py`** — an Ansible serial transport. The
  device has no network access, so Ansible has no built-in way to reach it. The
  plugin also retries commands whose echo comes back corrupted (a measured
  problem on FTDI-clone adapters — see `docs/TROUBLESHOOTING.md` §3). Unit-tested
  in `tests/`.
- **`roles/verify`** — the anti-false-pass. It reads `dmesg` and `wifi status`
  back from the device and **fails** if `-22` persists. A green play cannot leave
  a dead radio. This is what caught the unproven fix.
- **`docs/TROUBLESHOOTING.md`** — the measured failure modes, including the
  ruled-out table for the serial TX corruption.
- **`docs/EVIDENCE.md`** — raw read-backs.

## ❓ Open questions (the actual work remaining)

1. **What does ath10k want from `board.bin`?** The shipped file carries a
   placeholder MAC and yields `bmi_id N/A`. Compare its embedded parameters
   against what a QCA9887 in this module revision requires.
2. **Is `art@0x5000` valid for this radio, or merely QCA9887-shaped?** A header
   match is not proof of validity.
3. **Does this ath10k build probe the nested `QCA9887/hw1.0/` directory at all,
   or a different path?** Not yet established — the log does not name the file.
4. **Is the board identity in OTP, and is it blank?** `bmi_id N/A` suggests the
   board ID could not be read; whether that is a missing file or blank hardware
   data is unresolved.

## Blocked on

- **A reliable serial cable.** The current FTDI clone corrupts ~1 char per
  transmitted line, which produced a **false result during this investigation**
  (a filename written as `pre-cal-pci-0200:00:00.0.bin` instead of `0000`). Every
  experiment costs ~10× what it should, and corruption can silently invalidate a
  measurement. A genuine FTDI or a CP2102 is needed for efficient work.
