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

## 3. The 5 GHz radio fails calibration

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
