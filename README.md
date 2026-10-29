# e750-repair

Tooling to diagnose and repair a **GL.iNet GL-E750 ("Mudi")** over its serial
console — reproducibly, as Ansible, so any context window or machine can do it.

> ## ⚠️ READ [`STATUS.md`](STATUS.md) FIRST
>
> This repo was written during an active diagnosis and **its central claim is
> unverified**. The theory that installing missing QCA9887 calibration data revives
> the dead 5 GHz radio **did not fix the radio**. A one-variable follow-up
> (2026-10-29) showed that the earlier `failed to get board id: -122` was caused
> by the `pre-cal-*` file: installing **only** `cal-pci-*.bin`, with no
> `pre-cal-*`, produces **no `-122`** and leaves the original `-22`
> EEPROM/board-id failure. See [`docs/CALDATA-CAL-ONLY.md`](docs/CALDATA-CAL-ONLY.md).
>
> An earlier version of this README argued from the log ordering that "calibration
> cannot be the cause". **That argument has been retracted as invalid** — the two
> lines come from different driver calls with independent base errors, so their
> order proves nothing. See STATUS.md.
>
> **Do not treat the `caldata` role as a fix.** The cal file alone is not
> sufficient; the current lead is the board-ID/EEPROM/OTP path (`bmi_id N/A`).
> What IS solid and reusable here: the serial transport plugin, the verify role
> that refuses to report a false pass, and the measured troubleshooting notes.

The radio repair itself remains **unsolved**.

## BSBF bonding (separate workstream)

The same unit also runs a **BSBF MPTCP client**: 4G (Aldi Talk) plus a 2.4 GHz
STA to `hermes-lan`, with `eth0` as the LAN. The 4G is marked backup because the
measured link is ~0.5 Mbps; the STA path carries ~22 Mbps. See
[`docs/BSBF-BONDING.md`](docs/BSBF-BONDING.md) and the companion server role in
[`docs/BSBF-SERVER.md`](docs/BSBF-SERVER.md).

This does **not** change the radio-repair verdict above; it is a separate,
additive role and playbook.

## Operations roles (all merged as IaC)

| Area | Doc | What it does |
|---|---|---|
| Client/server bonding | [`docs/BSBF-BONDING.md`](docs/BSBF-BONDING.md), [`docs/BSBF-SERVER.md`](docs/BSBF-SERVER.md) | MPTCP/xray client + server, failover |
| 4G diagnostics | [`docs/E750-MODEM-DIAG.md`](docs/E750-MODEM-DIAG.md) | read-only AT/MBIM signal/APN report |
| Serial reliability | [`docs/SERIAL-RELIABILITY.md`](docs/SERIAL-RELIABILITY.md) | TX test, loopback, cold-joint/continuity runbook |
| Access | [`docs/E750-ACCESS.md`](docs/E750-ACCESS.md) | Dropbear operator keys |
| Network + health | [`docs/E750-NETWORK-HEALTH.md`](docs/E750-NETWORK-HEALTH.md) | WAN zone cleanup, critical check |
| Monitoring | [`docs/E750-MONITOR.md`](docs/E750-MONITOR.md) | 5-minute cron health log + syslog |
| Clean image | [`docs/E750-IMAGE.md`](docs/E750-IMAGE.md) | pinned 25.12.5 ImageBuilder recipe (build only) |
| MCU/OLED | [`docs/E750-MCU.md`](docs/E750-MCU.md) | protocol investigation; daemon deferred |
| TollGate | [`docs/E750-TOLLGATE.md`](docs/E750-TOLLGATE.md) | v0.6.0 evaluated; standalone AP+STA is feasible |
| BSBF + TollGate | [`docs/BSBF-TOLLGATE-COEXISTENCE.md`](docs/BSBF-TOLLGATE-COEXISTENCE.md) | separate-first plan and combined-mode checklist |
| Tracker | [`docs/E750-REMEDIATION.md`](docs/E750-REMEDIATION.md) | phases, checklist, execution log |

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

`-22` is `-EINVAL`. Two candidate causes were identified, but **neither is
confirmed and the second one changed the failure rather than fixing it** — see
[`STATUS.md`](STATUS.md) and `docs/EVIDENCE.md` §3 before trusting the table below.

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
