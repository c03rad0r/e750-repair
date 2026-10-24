# e750-repair

Tooling to diagnose and repair a **GL.iNet GL-E750 ("Mudi")** over its serial
console — reproducibly, as Ansible, so any context window or machine can do it.

> ## ⚠️ READ [`STATUS.md`](STATUS.md) FIRST
>
> This repo was written during an active diagnosis and **its central claim is
> unverified and probably wrong**. The theory that installing missing QCA9887
> calibration data revives the dead 5 GHz radio **did not survive contact with the
> hardware** — the driver rejects the *board file* (`failed to get board id: -122`)
> before it ever applies per-device calibration, so calibration cannot be the cause.
>
> **Do not treat the `caldata` role as a fix.** It is a kept-but-unproven
> hypothesis. What IS solid and reusable here: the serial transport plugin, the
> verify role that refuses to report a false pass, and the measured
> troubleshooting notes. See STATUS.md for the full evidence/claim split.

The radio repair itself remains **unsolved**.

---

## The fault this was *intended* to fix (theory — see STATUS.md)

A stock OpenWrt image on this board boots fine but the 5 GHz radio never
initialises:

```
ath10k_pci 0000:00:00.0: qca9887 hw1.0 target 0x4100016d chip_id 0x004000ff
ath10k_pci 0000:00:00.0: failed to read device EEPROM at 0000
ath10k_pci 0000:00:00.0: failed to read calibration data from EEPROM: -22
ath10k_pci 0000:00:00.0: otp calibration failed: 2
ath10k_pci 0000:00:00.0: failed to run otp: -22 (download-cal-data)
ath10k_pci 0000:00:00.0: could not init core (-22)
ath10k_pci 0000:00:00.0: could not probe fw (-22)
```

`-22` is `-EINVAL`. Two independent causes, both fixed here:

| # | Cause | Fix |
|---|---|---|
| 1 | `/lib/firmware/ath10k/QCA9887/hw1.0/board.bin` ships as the **generic default** — its embedded MAC is the placeholder `00:03:7f:12:34:56`, not this unit's. It cannot calibrate this radio. | Install the unit's real caldata as `cal-pci-*.bin` |
| 2 | `/etc/hotplug.d/firmware/10-ath9k-eeprom` has **no ath10k case** (its only board case is `meraki,mr18`), so `art@0x5000` is never extracted. | Add `11-ath10k-caldata` |

**The calibration data is not lost.** It is intact in the factory `art`
partition; it was simply never copied where the driver looks.

## The art layout (read back from this unit, not guessed)

| Offset | Length | Contents |
|---|---|---|
| `0x1000` | `0x440` | ath9k 2.4 GHz caldata — MAC `94:83:c4:4d:fc:39` |
| `0x5000` | `0x440` | QCA9887 5 GHz caldata — MAC `94:83:c4:4d:fc:3a` |
| `0x9000` | — | empty (`0xff` fill) on this unit |

The 5 GHz blob begins `44 08 1b a8 04 01` — a QCA9887 calibration header. The two
MACs are consecutive, which is correct for a dual-radio board.

> Offsets are **board-specific**. This repo refuses to run on any board whose
> `board_name` is not `gl-e750`.

## Layout

```
playbook.yml                     the one command
group_vars/all.yml               every tunable (ports, offsets, SSID, stages)
inventory/hosts.yml              serial transport (works with no network)
inventory/ssh.example.yml        SSH transport (once br-lan has carrier)

connection_plugins/
  serial_console.py              Ansible serial transport + TX-corruption retry

roles/
  caldata/                       extract + install the QCA9887 calibration
    files/11-ath10k-caldata        the hotplug handler (survives reboot)
  radio/                         assert radios, optionally enable the APs
  verify/                        read the device back; FAIL if -22 persists

docs/EVIDENCE.md                 raw boot log excerpts and read-backs
docs/TROUBLESHOOTING.md          the failure modes seen on the bench
```

## Why a serial connection plugin

The device in scope has **no network access** (br-lan `NO-CARRIER`, radio dead), so
Ansible's SSH transport cannot reach it. `connection_plugins/serial_console.py`
provides a serial transport.

It also handles a real hardware problem: on the bench host's FTDI **clone**
adapters, TX corrupts roughly one character per line while RX is byte-perfect.

```
echo PING_OK   ->  ?cho PING_OK
cat /sys/...   ->  ?at /sys/...
```

The plugin verifies each command's echo and retries on corruption, and it sends
`Ctrl-C Ctrl-U` before every command (a mangled byte can otherwise leave the shell
in a continuation prompt, silently swallowing what follows). Ruled out as causes:
a second process on the port, XON/XOFF, wrong baud, latency timer, and pacing. A
genuine FTDI or CP2102 cable would not need the retry.

## Usage

```bash
# Repair the radio (no reboot required - the blob is installed immediately)
ansible-playbook -i inventory/hosts.yml playbook.yml

# Repair AND enable an AP
ansible-playbook -i inventory/hosts.yml playbook.yml \
    -e configure_wifi=true -e wifi_ssid=my-e750

# ...with WPA2
ansible-playbook -i inventory/hosts.yml playbook.yml \
    -e configure_wifi=true -e wifi_ssid=my-e750 \
    -e wifi_encryption=psk2 -e wifi_key='correct horse battery staple'

# Just verify a device (no changes)
ansible-playbook -i inventory/hosts.yml playbook.yml \
    -e run_caldata=false -e run_radio=false

# Once the LAN port has link, prefer SSH
ansible-playbook -i inventory/ssh.example.yml playbook.yml
```

Stages are individually switchable: `run_caldata`, `run_radio`, `run_verify`.

## What this repo deliberately does NOT do

- **Never writes to the `art` partition.** It is read-only on `art`; all writes go
  to `/lib/firmware` and `/etc/hotplug.d`, both on the overlay.
- **Never reflashes the device.** Nothing about this fault indicates a bad image —
  kernel and rootfs are healthy and the kernel verifies its own checksum. A reflash
  would not fix the radio and risks a brick.
- **Never infers kernel behaviour from a version number** — everything is probed
  and read back from the device.
- **Does not enable an AP by default.** An open AP with a guessed SSID is a side
  effect, not a repair. Set `configure_wifi=true` explicitly.

## Requirements

- `ansible-core` ≥ 2.14 on the control host
- `pyserial` for the serial transport (`pip install pyserial`)
- A 3.3 V USB-UART cable on the device's console header

## Related

- [`felixfelix-bot/openwrt-serial-lab`](https://github.com/felixfelix-bot/openwrt-serial-lab)
  — the general serial-console rig (MT3000/MT6000). This repo is the E750-specific
  repair; use that one for the generic console tooling.
