# E750 MCU / OLED — investigation and decision

Status: **deferred** (2026-10-29). The OLED is driven by a separate MCU, not by
the SoC. There is no MCU daemon in the current image and the OLED shows only the
MCU's own boot/charging state. This page records what is known, what was
measured, and why an unverified writer is not shipped.

## Hardware/protocol (from GL's source)

- The MCU is on **`/dev/ttyS0` at 115200 8N1**, the same UART as the Linux
  console. GL's `e750-mcu` opens `/dev/ttyS0` and its init script lowers console
  noise with `echo 1 4 1 7 >/proc/sys/kernel/printk`.
- The host sends one **JSON object per line**, e.g.:

  ```json
  {"ssid":"...","up":"1","key":"...","ssid_5g":"...","up_5g":"1","key_5g":"...","SIM":"NO_SIM","work_mode":"Router","lan_ip":"192.168.8.1","vpn_status":"off","clients":"1","clock":"02:30","mcu_status":"1"}
  ```

- `{"mcu_status":"1"}` asks for a status line; the documented reply is
  `{OK},<charge_percent>,<temperature>,<charging_state>,<cycles>` (some firmware
  adds battery voltage).
- `{"version":"1"}` asks for the MCU firmware version.
- All values are **strings**; the MCU only parses string-typed JSON.
- GL's v2 interface (`gl-inet/gl-e750v2-mcu-iface`) wraps this in
  `ubus call mcu version|status|reload` and UCI `mcu.global.*` page switches.
  That daemon is **not** in the OpenWrt feed; it is a GL package built from GL's
  source with prebuilt static libraries.

## Measured on this unit (2026-10-29)

| Probe | Result |
|---|---|
| `{"version":"1"}` and `{"mcu_status":"1"}` on `/dev/ttyS0`, console login running | only the host's own bytes came back |
| same, after stopping `askfirst`, 115200 | **no reply** (`bytes=0`) |
| same at 9600 / 19200 / 38400 / 57600 / 115200 | **no reply at every rate** |
| `dmesg` / device tree | only one real UART (`18020000.uart`, `ttyS0`); `ttyS1` is not registered |
| `ps` / filesystem | no `e750-mcu`, no `ubus mcu` object, no `gl-e750-mcu` package |
| USB tree | hub, storage, Quectel EM060K; no HID/MCU device |

So the MCU UART is present but did not answer the documented queries. Possible
reasons: this MCU firmware does not implement the query replies, the unit is a
different hardware revision, or the MCU expects a full display frame before it
answers. The probe is not conclusive, and **no display write has been
verified**.

Evidence: `evidence/mcu/2026-10-29_probe.txt` (probe + baud sweep; the
`--force` run restored `askfirst` afterwards).

## Why no daemon is shipped

GL's own instructions warn that incorrect JSON can make the MCU behave oddly,
including **shutting the router down**, and a background writer can then cause a
boot loop. Writing to the console UART also competes with the console login.
Shipping an unverified writer on the only live BSBF gateway is not acceptable,
especially while the serial adapter is unreliable and a bad state could need
serial recovery.

## Options, in order of preference

1. **Build GL's `gl-e750-mcu` for 25.12 / mips_24kc** from
   `gl-inet/GL-E750-MCU-instruction` with the OpenWrt SDK. Highest fidelity and
   uses GL's own page logic. Risks: prebuilt static libs, GL SDK assumptions,
   AGPL/GPL obligations; verify it links against musl and the current libjson-c.
   Test on a spare unit or with a serial console attached.
2. **Port the shell approach** (`pekmop1024/gl-e750-mcu-oled`): a procd script
   that builds the JSON and writes it to `/dev/ttyS0`. No compilation, but the
   same malformed-JSON risk. Would need a watchdog, a hard timeout, and a
   `lcd_test`-only first run. Do not autostart until the OLED visibly responds.
3. **Leave the OLED as-is** (current). BSBF, 4G, and the 2.4 GHz STA do not need
   the MCU. This is the safe default until the serial adapter is reliable.

## Safe first experiment (when a reliable serial console exists)

1. Attach serial recovery; confirm `askfirst` works.
2. Run `scripts/mcu-probe.sh --force` and capture the reply; if it is still
   silent, stop — do not guess the protocol.
3. If a reply appears, send a single documented frame with `mcu_status` and no
   page changes; watch the OLED and the console.
4. Only then add a procd service, with `respawn` limits and a kill switch
   (`/etc/init.d/e750_mcu stop`).
5. Fold the verified package/daemon into `image/packages.txt` and rebuild.

## Repo state

- `scripts/mcu-probe.sh` — documented queries only, no UCI writes, no daemon;
  `--force` temporarily stops/restores `askfirst`.
- No `gl-e750-mcu` package, no init script, and no image change.
- Tracker: Phase 6 stays open until the probe returns a reply or a verified
  package is built.

## Working driver (2026-10-30)

The MCU is a **NUC029ZAN** on the console UART (`/dev/ttyS0`, 115200 8N1). It
renders **predefined pages**; there is no free-text field. It reads one JSON
object per line, e.g.:

```json
{ "ssid_5g": "TollGate-E750", "up_5g": "1", "key_5g": "",
  "ssid": "TollGate-E750", "up": "0", "work_mode": "Router",
  "lan_ip": "192.168.8.1", "method_nw": "repeater|standby",
  "clients": "1", "clock": "00:00", "mcu_status": "1" }
```

A `mcu_status` query returns `{OK},<battery%>,<temp>,<charging>,<cycles>`; on
this unit the reply was observed as `,1,10` (the console/login consumes the
leading bytes).

`scripts/e750-mcu-oled.sh` sends the current SSID, link mode, client count and
clock every minute. "TollGate" appears via the SSID (`TollGate-E750`) and the
bonding state via `method_nw`. There is **no way to print arbitrary text** such
as a custom "TollGate" banner without changing the MCU firmware.

Caveat: the MCU shares `ttyS0` with the console, so JSON and replies are
interleaved with the login. To stop the driver, remove the cron entry
(`/usr/bin/e750-mcu-oled.sh`). The stock `gl-e750-mcu` package is not in the
OpenWrt feed; this shell driver is source-only and does not need it.
