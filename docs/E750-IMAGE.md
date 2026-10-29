# Clean E750 image recipe

A reproducible OpenWrt **25.12.5** ImageBuilder image for `glinet_gl-e750`
(`ath79/nand`), with the BSBF client, MBIM/4G, diagnostics tools, and non-secret
first-boot defaults.

**This recipe builds only. It does not flash.** Flashing is blocked until the
E750 serial adapter is swapped/reflowed; a bad flash needs a working serial
recovery path.

## Contents

- `image/packages.txt` — the package set:
  - BSBF client: `bsbf-bonding`, `bsbf-quectel-usbnet`,
    `bsbf-autoconf-cellular`, `bsbf-autoconf-dhcp`, `xray-core`.
  - MPTCP/tproxy: `ip-full`, `mptcpize`, `kmod-ifb`, `kmod-nf-tproxy`,
    `kmod-nft-tproxy`.
  - 4G: `kmod-usb-net-cdc-mbim`, `kmod-usb-net-qmi-wwan`,
    `kmod-usb-serial-option`, `umbim`, `uqmi`.
  - Diagnostics: `coreutils-stty`, `picocom`, `curl`.
  - WiFi STA: `wpad-basic-mbedtls`; management: `luci`.
- `image/files/etc/uci-defaults/99-e750-defaults` — LAN `eth0`/192.168.8.1,
  DHCP `.100-.249`, 4G MBIM APN `internet.eplus.de`, WAN firewall `wwan wwan1`,
  AP disabled, key-only Dropbear, hostname/timezone. **No PSK or BSBF UUID.**
- `image/files/etc/dropbear/authorized_keys` — the current two **public**
  operator keys (x280 + T14). No private key.
- `image/files/etc/crontabs/root` — `*/5 * * * * /usr/bin/e750-health-cron.sh`.
- `image/build.sh` — pins the ImageBuilder tarball SHA256, stages
  `scripts/e750-health.sh` → `/usr/bin/e750-health` and
  `scripts/e750-health-cron.sh` → `/usr/bin/e750-health-cron.sh`, builds the
  image, and **fails the build** if the monitor, crontab, uci-defaults, or
  operator keys are missing from the rootfs.

## Build

```bash
cd ~/worktrees/e750-repair
./image/build.sh
```

The output is under `image/build/openwrt-imagebuilder-.../bin/targets/ath79/nand/`
(the `*.squashfs-sysupgrade.bin` plus manifest). The build directory is
gitignored.

## Build result (2026-10-29)

Final artifact, built on T14 with the pinned ImageBuilder **including the health
monitor and the serial tools** (`coreutils-base64`, `lrzsz`):

```text
openwrt-25.12.5-ath79-nand-glinet_gl-e750-squashfs-sysupgrade.bin
size   16650512 bytes
sha256 05152fedf29d63b8e79d4ac2db03f9360274343075a463b7b6cc8464d962c7dd
packages 190
```

Verified in the built rootfs: `/usr/bin/e750-health` (2316 B),
`/usr/bin/e750-health-cron.sh` (1017 B), `/etc/crontabs/root` (0600),
`/etc/uci-defaults/99-e750-defaults` (executable), the two public Dropbear keys,
and the `S50cron` rc.d symlink. Evidence:
`evidence/image/2026-10-29_build-serial-tools.txt` (and the earlier
`..._build-with-monitor.txt`).

> The PR #9 build (`5a6fee11…`) predates the monitor; the PR #15 build
> (`9ea82c93…`) predates the serial tools. The artifact above supersedes both.
> It is **not flashed**; flashing requires the serial link/checksum channel.

The package versions in the image match the live device (checked with
`apk list --installed`): `bsbf-* 2026.08.29~60f0d20f-r1`, `xray-core 26.3.27-r1`,
`ip-full 6.18.0-r2`, `mptcpize 0.13-r2`, `umbim 2025.10.04`, `picocom 3.1-r5`,
`coreutils-stty 9.9-r2`. The `99-e750-defaults` and the two public Dropbear keys
are present in the built rootfs. Evidence:
`evidence/image/2026-10-29_build.txt`.

The image was **not flashed**; the live device is unchanged.

## First boot / secrets

The image is a clean base. It does **not** contain:

- the `hermes-lan` WiFi PSK;
- the BSBF server IP/port/UUID.

After first boot, configure the STA and run the client playbook with credentials
from OpenBao, e.g.:

```bash
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-bsbf-client.yml \
  -e bsbf_server_ipv4=... -e bsbf_server_port=... -e bsbf_client_uuid=...
```

The image is key-only and carries the current operator public keys, so x280 and
T14 (via `-J x280`) can log in once the LAN is up. The health monitor is baked
in: `/etc/crontabs/root` schedules it every 5 minutes and
`99-e750-defaults` enables/starts cron; `/tmp/e750-health.log` appears after the
first tick.

## Flash (gated)

Do **not** flash until the serial adapter is reliable. When it is:

1. Back up the current device: `scripts/e750-backup.sh` (mtd1/mtd2/firmware/
   uci/keys) and the current image/config.
2. Verify the serial console with `serial-tx-test.py` (5/5) and, if needed,
   `--loopback`.
3. `sysupgrade` the built image; keep the serial console attached.
4. Verify LAN 192.168.8.1, 4G, key-only SSH, then run the BSBF client role.
5. Rollback: previous sysupgrade image + config backup via serial.

## Not included yet

- `gl-e750-mcu` / OLED support (Phase 6). Add it to the image once it compiles
  for 25.12/mips_24kc and the MCU protocol is confirmed.
- TollGate (Phase 8) — decide whether it belongs on this image or a separate
  one; do not combine it with the live BSBF path without a test plan.
