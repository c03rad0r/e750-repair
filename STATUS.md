# STATUS — what is verified, and what is not

**Last updated: 2026-10-24**

This repo was created in the middle of an active diagnosis. Read this before
trusting anything else in it.

## ⚠️ The central claim is UNVERIFIED — and it is now the SECOND-most interesting thing here

This repo was built on the theory that the E750's dead 5 GHz radio is caused by
**missing per-device calibration data** that a stock OpenWrt image never extracts
from the factory `art` partition, and that installing it fixes the radio.

**That theory has not been confirmed.** On the target unit:

1. The calibration files were installed, byte-verified, in the correct directory,
   under both names ath10k probes for.
2. The radio **still failed**.
3. But the failure **changed**: a `failed to get board id: -122` line appeared that
   is not present in any pre-install boot log. That is the current lead.

### RETRACTED: "the ordering is decisive"

An earlier revision of this file claimed:

> `failed to get board id: -122` … it **rejects the board file before it ever
> applies per-device calibration**. A caldata problem cannot produce that ordering.

**That argument is invalid and is withdrawn.** It reasoned from the *printed
position* of `otp calibration failed: 2` relative to the EEPROM `-22` line, but
those are outputs of **two different driver calls with independent base errors**,
so their order in the log carries no information about which step gated which.

`otp calibration failed: 2` is in fact a **symptom**, not evidence: when the
`-122` path aborts early, `ar->id.bmi_ids_valid` stays false, which changes the
BMI parameter that `ath10k_download_and_run_otp()` sends, causing the target to
reject with result `2`.

This matters because it cuts **both** ways: the −122 neither proves the caldata
theory right nor exonerates it. See `docs/EVIDENCE.md` §3 for the full comparison
of the two boot signatures.

### What −122 actually is

`-122` is `-EDQUOT`, which **ath10k never returns** — it is a value coming back
from the target firmware through `ath10k_bmi_execute()`, not an errno the driver
produced. Treating it as a driver-level error is a trap; see EVIDENCE §3.

**Do not treat the `caldata` role as a fix.** It is an unproven hypothesis whose
file placement demonstrably *changed* the failure mode rather than resolving it.
The extraction logic is sound and may still be a *necessary* step once the real
cause is found — but it is demonstrably **not sufficient**, and its side effects
are not yet understood.

## ✅ What IS verified (read back from the device, 2026-10-23/24)

| Finding | Evidence |
|---|---|
| The device **boots correctly** — this was never a boot failure | Full boot log captured twice; reaches `root@OpenWrt:~#`. Kernel verifies its own checksum, squashfs mounts, UBIFS recovers, `procd` starts. |
| `192.168.1.1` unreachable is **not a fault** | `br-lan: <NO-CARRIER,...> state DOWN`. The address `192.168.1.1/24` is configured correctly; the port simply has no link. |
| The 5 GHz QCA9887 **fails on every boot** | Pre-install boots: `failed to read device EEPROM at 0000`, `failed to read calibration data from EEPROM: -22`, `could not init core (-22)`. Post-install boots add `failed to get board id: -122`. See EVIDENCE §3 for the two signatures side by side. |
| The `-122` appears **only after** the caldata files were placed | `grep -c -- '-122'`: pre-install log `ttyUSB3.log` = **0**; post-install `poweron2/ttyUSB3.log` and `reboot_trigger.log` = **1** each. |
| `-122` cannot be an ath10k-generated errno | `-EDQUOT` does not occur anywhere in the ath10k driver; it surfaces from `ath10k_bmi_execute()`'s response `result` field. |
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

**The primary lead — answer this first:**

0. **Is the `-122` caused by the `pre-cal-*` / `cal-*` file placement?** Placing
   those files changes `ar->cal_mode` to `ATH10K_PRE_CAL_MODE_FILE`, which switches
   the BMI board-id parameter the driver sends (`BMI_PARAM_GET_FLASH_BOARD_ID`
   instead of `BMI_PARAM_GET_EEPROM_BOARD_ID`). Test: remove the files, reboot,
   confirm the `-122` line disappears; re-add, reboot, confirm it returns. This is
   a one-variable experiment and it is the cheapest decisive test available.

Then:

1. **Why does the target answer `-EDQUOT` at all?** No ath10k code returns it, so
   it is a firmware-side refusal. Determine which request it refuses and why.
2. **Is the `length` underflow in `ath10k_bmi_read_memory()` reachable here?** A
   short BMI read underflows the loop counter to ~4 GiB with no lower-bound guard.
   Confirm whether that is the mechanism behind the −122 or a red herring.
3. **What does ath10k want from `board.bin`?** The shipped file carries a
   placeholder MAC and yields `bmi_id N/A`. Compare its embedded parameters
   against what a QCA9887 in this module revision requires.
4. **Is `art@0x5000` valid for this radio, or merely QCA9887-shaped?** A header
   match is not proof of validity.
5. **Does this ath10k build probe the nested `QCA9887/hw1.0/` directory at all,
   or a different path?** Not yet established — the log does not name the file.
6. **Is the board identity in OTP, and is it blank?** `bmi_id N/A` suggests the
   board ID could not be read; whether that is a missing file or blank hardware
   data is unresolved.

## Blocked on

- **A reliable serial cable.** The current FTDI clone corrupts ~1 char per
  transmitted line, which produced a **false result during this investigation**
  (a filename written as `pre-cal-pci-0200:00:00.0.bin` instead of `0000`). Every
  experiment costs ~10× what it should, and corruption can silently invalidate a
  measurement. A genuine FTDI or a CP2102 is needed for efficient work.
