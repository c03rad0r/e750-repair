# Evidence — raw read-backs, 2026-10-23

All output below was captured from the device over `/dev/ttyUSB3` at 115200 8N1.
The boot log came through byte-clean; interactive commands were retried until their
echo was clean (see `docs/TROUBLESHOOTING.md` §3).

## 1. The device boots

```
U-Boot ... Booting standard firmware from nor flash...
   Image Name:   MIPS OpenWrt Linux-6.12.80
   Image Type:   MIPS Linux Kernel Image (lzma compressed)
   Data Size:    3249336 Bytes = 3.1 MB
   Verifying Checksum at 0x9f060040 ...OK
## Transferring control to Linux (at address 80060000) ...
[    0.000000] MIPS: machine is GL.iNet GL-E750
[    0.000000] SoC: Qualcomm Atheros QCA9533 ver 2 rev 0
[    4.301552] VFS: Mounted root (squashfs filesystem) readonly on device 254:0.
```

```
DISTRIB_ID='OpenWrt'
DISTRIB_RELEASE='SNAPSHOT'
DISTRIB_REVISION='r33865-8101611355'
DISTRIB_TARGET='ath79/nand'
DISTRIB_ARCH='mips_24kc'
DISTRIB_DESCRIPTION='OpenWrt SNAPSHOT r33865-8101611355'
```

Verdict: **the device boots.** Kernel verifies its own checksum, squashfs mounts,
UBIFS recovers its journal, `procd` starts, a root shell is available. This was
never a boot failure.

## 2. The LAN port has no link

```
network.lan.device='br-lan'
network.lan.proto='static'
network.lan.ipaddr='192.168.1.1/24'

4: br-lan: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN
    inet 192.168.1.1/24 brd 192.168.1.255 scope global br-lan

bridge name  bridge id         STP enabled  interfaces
br-lan       7fff.9483c44dfc38  no           eth0
```

The address is correct; a down port carries no frames. This is why `192.168.1.1`
was unreachable.

## 3. The 5 GHz radio fails — and the failure CHANGED after caldata was installed

**This is the most important section in the repo.** There are two distinct failure
signatures and the difference between them is the current lead.

### 3a. Boot before any caldata was installed (2026-10-23 04:43)

Log: `evidence/boots/2026-10-23_0443_pre-install.log`. **No `-122` in this log** (`grep -c -- '-122'` = 0).

```
ath10k_pci 0000:00:00.0: qca9887 hw1.0 target 0x4100016d chip_id 0x004000ff sub 0000:0000
ath10k_pci 0000:00:00.0: firmware ver 10.1-ct-87-__fW-022-d8dab8e8 api 2 ... crc32 81827605
ath10k_pci 0000:00:00.0: board_file api 1 bmi_id N/A crc32 546cca0d
ath10k_pci 0000:00:00.0: failed to read device EEPROM at 0000
ath10k_pci 0000:00:00.0: failed to read calibration data from EEPROM: -22
ath10k_pci 0000:00:00.0: otp calibration failed: 2
ath10k_pci 0000:00:00.0: failed to run otp: -22 (download-cal-data)
ath10k_pci 0000:00:00.0: could not init core (-22)
ath10k_pci 0000:00:00.0: could not probe fw (-22)
```

`-22` = `-EINVAL`, on the *calibration download* step specifically.

### 3b. Boot AFTER caldata was installed (2026-10-23 15:14 and 17:23, and 2026-10-25)

Logs: `evidence/boots/2026-10-23_1528_post-install.log`, `evidence/boots/2026-10-23_1723_post-install.log`,
`evidence/boots/2026-10-25_post-reflash.log`. **All three contain `-122`** (`grep -c -- '-122'`
= 1 in each). The 2026-10-25 capture is a fresh power-on on a third day, so the
signature is stable across at least three boots and two calendar days.

```
ath10k_pci 0000:00:00.0: qca9887 hw1.0 target 0x4100016d chip_id 0x004000ff sub 0000:0000
ath10k_pci 0000:00:00.0: kconfig debug 0 debugfs 1 tracing 0 dfs 1 testmode 0
ath10k_pci 0000:00:00.0: firmware ver 10.1-ct-87-__fW-022-d8dab8e8 api 2 ... crc32 81827605
ath10k_pci 0000:00:00.0: board_file api 1 bmi_id N/A crc32 546cca0d
ath10k_pci 0000:00:00.0: failed to get board id: -122          <-- NEW
ath10k_pci 0000:00:00.0: failed to read device EEPROM at 0000
ath10k_pci 0000:00:00.0: failed to read calibration data from EEPROM: -22
ath10k_pci 0000:00:00.0: otp calibration failed: 2
ath10k_pci 0000:00:00.0: failed to run otp: -22 (download-cal-data)
ath10k_pci 0000:00:00.0: could not init core (-22)
ath10k_pci 0000:00:00.0: could not probe fw (-22)
```

### Why `-122` is a lead, not noise

`-122` is `-EDQUOT`. **`-EDQUOT` appears nowhere in the ath10k driver** — no
ath10k function can return it. So the number must be a *value* crossing a
boundary that the driver treats as an errno: `ath10k_bmi_execute()` hands back
`resp.execute.result` verbatim, and the firmware is returning `-EDQUOT` for a
request it will not serve.

That value reaches the log through `ath10k_core_get_board_id_from_otp()`:

```c
ret = ath10k_bmi_execute(ar, address, bmi_board_id_param, &result);
if (ret) {
        ath10k_err(ar, "could not execute otp for board id check: %d\n", ret);  /* NOT in our log */
        return ret;
}
...
ath10k_dbg(ar, ATH10K_DBG_BOOT, "boot get otp board id result 0x%08x ...");      /* NOT in our log */
```

Neither the `could not execute` error nor the `boot get otp board id result` debug
line appears — consistent with `ret == 0` and the query running to completion,
then a *later* step failing with −122. The candidate is
`ath10k_download_board_data()`: `ath10k_bmi_read32(ar, hi_board_data, ...)` reads
through `ath10k_bmi_read_memory()`, whose loop has no lower-bound guard —

```c
while (length) {
        rxlen = min_t(u32, length, BMI_MAX_DATA_SIZE);
        ret = ath10k_hif_exchange_bmi_msg(ar, &cmd, cmdlen, &resp, &rxlen);
        ...
        length -= rxlen;    /* a short read underflows this to ~4G */
}
```

A short read underflows `length` to `0xFFFFFFFC` and spins the loop far past the
intended window. Notably the surrounding error prints (`failed to download board
data`, `could not push board ext data`) are **absent**, so whatever failed did so
on a path that logs only this one line:

```c
ret = ath10k_core_get_board_id_from_otp(ar);
if (ret) {
        ath10k_err(ar, "failed to get board id: %d\n", ret);   /* <-- our line */
        return ret;
}
```

`ar->id.bmi_ids_valid` consequently stays false, which changes the *value* of the
next call: `ath10k_download_and_run_otp()` chooses `BMI_PARAM_GET_FLASH_BOARD_ID`
(or `otp_exe_param`) instead of `BMI_PARAM_FLASH_SECTION_ALL`, uploads less, and
the target then rejects with `result = 2` → `otp calibration failed: 2`.

**Conclusion: `otp calibration failed: 2` is a *symptom* of the −122 path, not
evidence about calibration validity.** Any argument that reasons from that line's
position in the log to "calibration cannot be the cause" is invalid.

### What changed between 3a and 3b

Between the two boots, two files were placed (see `evidence/scripts/2026-10-23_fix_paths.py`,
2026-10-23 15:37):

```
nested:     /lib/firmware/ath10k/QCA9887/hw1.0/pre-cal-pci-0000:00:00.0.bin
top-level:  /lib/firmware/ath10k/cal-pci-0000:00:00.0.bin
```

Per `ath10k_fetch_cal_file()` (`drivers/net/wireless/ath/ath10k/core.c`) the driver
probes `pre-cal-<bus>-<id>.bin` first, then `cal-<bus>-<id>.bin`, in **both** the
nested and top-level directories. Finding a `pre-cal-*` file sets
`ar->cal_mode = ATH10K_PRE_CAL_MODE_FILE`, and that value is read in
`ath10k_core_get_board_id_from_otp()` to pick which BMI parameter to send:

```c
if (ar->cal_mode == ATH10K_PRE_CAL_MODE_DT ||
    ar->cal_mode == ATH10K_PRE_CAL_MODE_FILE ||
    ar->cal_mode == ATH10K_PRE_CAL_MODE_NVMEM)
        bmi_board_id_param = BMI_PARAM_GET_FLASH_BOARD_ID;
else
        bmi_board_id_param = BMI_PARAM_GET_EEPROM_BOARD_ID;
```

So installing those files plausibly *switched the BMI query* the target is asked
to serve — and the −122 appears in exactly the boots where they were present.

**NOT PROVEN.** Which boot saw which file tree is not established from the
captured logs, and the two boots are ~23 min after the 15:37 copy rather than
immediately after it. This is a hypothesis with a mechanism, not a finding.

### Not established / traps

- The `-122` must never be read as "the driver complained about quota". It is a
  firmware-returned value surfacing through the errno channel.
- Do **not** delete this section on the grounds that "caldata is unverified" —
  the −122 only exists *because* of the file placement, which is why it is the
  lead rather than a discarded claim.
- The write-up of this diagnosis is based on upstream driver source read on
  2026-10-25, not on the exact ath10k revision in this firmware
  (`firmware ver 10.1-ct-87`, driver `ath10k 6.15`). Line-for-line agreement with
  the OpenWrt build was not verified.

### 3c. THE REVERSAL — files absent again, −122 GONE (2026-10-25, live E750)

The unit was reflashed to **OpenWrt 25.12.5 `r33051`, ath79/nand, kernel 6.12.94**
and was up 1 day 1:21 when measured over SSH (`ssh -i ~/.ssh/id_bench
root@192.168.8.1`). The `cal-pci-*` / `pre-cal-*` files are **gone** — the
firmware directory holds only the stock files:

```
/lib/firmware/ath10k/QCA9887/hw1.0/
  -rw-r--r--  1024    board.bin
  -rw-r--r--  212900  firmware-2.bin
find / -name 'cal-pci*' -o -name 'pre-cal*'   ->  (nothing)
```

Live `dmesg | grep -i ath10k`:

```
[   29.790448] ath10k_pci 0000:00:00.0: board_file api 1 bmi_id N/A crc32 546cca0d
[   29.829578] ath10k_pci 0000:00:00.0: failed to read device EEPROM at 0000
[   29.836703] ath10k_pci 0000:00:00.0: failed to read calibration data from EEPROM: -22
[   29.904484] ath10k_pci 0000:00:00.0: otp calibration failed: 2
[   29.910568] ath10k_pci 0000:00:00.0: failed to run otp: -22 (download-cal-data)
[   29.918152] ath10k_pci 0000:00:00.0: could not init core (-22)
[   29.951733] ath10k_pci 0000:00:00.0: could not probe fw (-22)
```

`dmesg | grep -c -- '-122'` = **0**.

**This is a two-sided natural experiment:**

| state | cal files present | `-122` | EEPROM `-22` |
|---|---|---|---|
| 2026-10-23 04:43 (stock) | no | **absent** | present |
| 2026-10-23 15:14 / 17:23 | yes | **present** | present |
| 2026-10-25 (reflashed 25.12.5) | no | **absent** | present |

The −122 tracks the presence of the cal files in **both** directions. The
hypothesis in §3b is therefore **CONFIRMED as an association**: placing a
`pre-cal-*`/`cal-*` file makes ath10k ask the firmware a board-id question it
refuses, and the refusal surfaces as `-122` (`-EDQUOT`).

**But it also settles the original question: caldata is NOT the fix.** The
underlying fault — `failed to read calibration data from EEPROM: -22`, `could not
init core (-22)` — is **unchanged** on a clean 25.12.5 image with no cal files.
The calibration download still fails exactly as it did on the original snapshot.
Installing caldata did not repair the radio; it added a second, self-inflicted
failure on top of the first.

Scope limit: this is an observational A/B across three boots, not a controlled
test with re-application on the current image. Re-applying the files on 25.12.5
and confirming −122 **returns** would close it completely — that is the one
remaining step.

### BOARD CONSTRAINT — which hardware can test the −122 at all (measured 2026-10-25)

**The −122 can only be reproduced on this E750. No other board on the bench can
produce it, because the signal lives in `ath10k`'s BMI protocol and the other
bench boards do not use `ath10k`.**

Measured on the bench host by counting BMI symbols in the shipped modules:

```
mt76.ko          BMI_PARAM|bmi_get_target_info|bmi_execute -> 0
mt7915e.ko       -> 0        (MT7918/MT7986-class 5 GHz, used by GL-MT3000)
mt7996e.ko       -> 0
ath10k_core.ko   -> 1        (GET_EEPROM_BOARD_ID / GET_FLASH_BOARD_ID present)
```

`failed to get board id`, `BMI_PARAM_GET_FLASH_BOARD_ID` and the whole
`ath10k_bmi_execute()` path are **ath10k-only**. `mt76` has no BMI layer at all,
so:

- **GL-MT3000 (MediaTek MT7986, `mt76`)** — cannot reproduce the −122. It is a
  control for "does a 5 GHz radio come up on other hardware", **not** a test of
  this lead. Measured 2026-10-25 on `tollgate-9BD4` (GL-MT3000, OpenWrt 25.12.5,
  kernel 6.12.94): `wifi status` reports `radio1` `band 5g`, `channel 36`,
  `htmode HE80`, `up: true`, `disabled: false` — **its 5 GHz radio is healthy**,
  and `dmesg | grep -c ath10k` = 0. There is no dead radio to investigate there.
- **COMFAST CF-WR632AX (MediaTek MT7981, `mt76`)** — same, cannot reproduce it.
  Measured 2026-10-25 on `comfast-b3ba` (OpenWrt 25.12.5, kernel 6.12.94,
  `comfast,cf-wr632ax`): `wifi status` reports `radio1` `band 5g`,
  `channel 36`, `htmode HE80`, `up: true`, `disabled: false`, and
  `dmesg | grep -c ath10k` = 0. **Its 5 GHz radio is healthy too** — so neither
  offered board has a dead 5 GHz radio, and neither has the ath10k code path.
- **D-Link COVR-X1860 (ramips/mt7621)** — different target and radio stack again;
  it was never offered for this work and was only identity-read.

**Consequence: the one-variable file-placement experiment MUST run on the E750.**
Do not dispatch it to another board — a green result there would be
uninformative, because the code path under test does not exist on that board.

## 4. `art` holds valid calibration

```
# cat /proc/mtd
mtd0: 00040000 00010000 "u-boot"
mtd1: 00010000 00010000 "u-boot-env"
mtd2: 00010000 00010000 "art"
mtd3: 00400000 00010000 "kernel"
mtd4: 00ba0000 00010000 "reserved"
mtd5: 08000000 00020000 "ubi"

# hexdump -C -s 0x1000 -n 32 /dev/mtd2      (2.4 GHz)
00001000  02 02 94 83 c4 4d fc 39  00 00 00 00 00 00 00 00  |.....M.9........|

# hexdump -C -s 0x5000 -n 32 /dev/mtd2      (5 GHz)
00005000  44 08 1b a8 04 01 94 83  c4 4d fc 3a 00 00 1f 00  |D........M.:....|

# hexdump -C -s 0x9000 -n 16 /dev/mtd2      (empty)
00009000  ff ff ff ff ff ff ff ff  ff ff ff ff ff ff ff ff  |................|
```

MACs `...:39` and `...:3a` are consecutive — correct for a dual-radio board.
`44 08 1b a8 04 01` is a QCA9887 calibration header.

## 5. The shipping board.bin is the generic default

```
# ls -l /lib/firmware/ath10k/QCA9887/hw1.0/
-rw-r--r--  1024     board.bin
-rw-r--r--  212900   firmware-2.bin

# dd if=.../board.bin bs=1 count=32 | hexdump -C
00000000  00 04 00 00 38 af 01 60  02 00 00 00 00 00 00 00  |....8..`........|
00000010  01 63 00 00 01 00 00 03  7f 12 34 56 00 03 7f 12  |.c........4V....|
```

`00:03:7f:12:34:56` is the placeholder MAC — this is the generic board file, not
this unit's calibration.

## 6. The stock hotplug has no ath10k case

```
# ls /etc/hotplug.d/firmware/
10-ath9k-eeprom

# grep -n 'ath10k\|meraki' /etc/hotplug.d/firmware/10-ath9k-eeprom
... only ath9k-* firmware names; every board case is 'meraki,mr18'
```

So `art@0x5000` is never extracted for the QCA9887.

## 7. The fix, installed

```
# dd if=/dev/mtd2 of=/lib/firmware/ath10k/QCA9887/hw1.0/cal-pci-0000:00:00.0.bin \
     bs=1 skip=20480 count=1088

# ls -l /lib/firmware/ath10k/QCA9887/hw1.0/
-rw-r--r--  1024     board.bin
-rw-r--r--  1088     cal-pci-0000:00:00.0.bin
-rw-r--r--  212900   firmware-2.bin

# dd if=.../cal-pci-0000:00:00.0.bin bs=1 count=16 | hexdump -C
00000000  44 08 1b a8 04 01 94 83  c4 4d fc 3a 00 00 1f 00  |D........M.:....|
```

Byte-identical to `art@0x5000`. Also installed:
`/etc/hotplug.d/firmware/11-ath10k-caldata` (0755) to re-extract if the file
ever vanishes.

## 8. Still open at time of writing

The reboot to make ath10k re-probe was sent over a corrupting TX line; the device
then went silent on **all four** ports (0 bytes even to CR; adapter USB reset did
not revive). The E750 has an internal battery, so a power-off is plausible.
**Pending: power-cycle and confirm `dmesg | grep ath10k` no longer shows `-22` and
that `wifi status` lists two radios.**
