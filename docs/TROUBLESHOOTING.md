# Troubleshooting — observed failure modes

Everything here was measured on real hardware, 2026-10-23. Nothing is inferred.

## 1. `192.168.1.1` unreachable

**Not a fault.** Check the bridge, not the address:

```
4: br-lan: <NO-CARRIER,BROADCAST,MULTICAST,UP> state DOWN
    inet 192.168.1.1/24 brd 192.168.1.255 scope global br-lan
```

`network.lan.ipaddr='192.168.1.1/24'` is configured correctly. `NO-CARRIER` +
`state DOWN` means **nothing is plugged into the router's LAN port** (or the
cable/port is bad). A down port carries no frames, so no host can ever reach it.

Fix: cable into the **LAN** port (not WAN). Confirm with
`ip -4 addr show br-lan` — the `NO-CARRIER` flag must be gone.

## 2. "It switches to U-Boot mode but there's no web UI"

**U-Boot has no web interface.** `192.168.1.1` is LuCI, which exists only once
OpenWrt's userspace is up. U-Boot is serial-only, plus optionally TFTP for
recovery. Expecting a web page at U-Boot is a category error.

Related red herring from the same log:

```
*** Warning - bad CRC, using default environment
```

The `u-boot-env` partition's CRC is invalid, so U-Boot runs on built-in defaults.
Harmless in normal operation; relevant only when doing U-Boot-level recovery.

## 3. Serial TX corrupts commands while RX is perfect

```
echo PING_OK    ->  ?cho PING_OK
cat /sys/...    ->  ?at /sys/...
ip -br addr     ->  ip -br addrroot@OpenWrt:~#   (prompt on the same line)
```

`?` is the shell's rendering of a mangled byte; it can also arrive as a quote,
which leaves the shell in a `>` continuation prompt that **silently swallows the
next command**.

Ruled out, in order:

| Hypothesis | Test | Result |
|---|---|---|
| A second process holds the port | full `/proc/*/fd` scan | FREE — no holder |
| Software flow control | `xonxoff=False` explicitly | no change |
| Wrong baud | 57600 / 38400 / 115200 | only 115200 answers |
| FTDI latency timer | lowered 16 → 1 ms | no change |
| TX pacing | 8 ms, then 20 ms per char | no change |

Remaining cause: the **FTDI clone's TX driver** (three `0403:6001` adapters on one
powered hub). **Not** a device fault — the boot log reads byte-clean at 115200.

Workarounds, both in this repo:
- `connection_plugins/serial_console.py` verifies each echo and retries
- it sends `Ctrl-C` + `Ctrl-U` before every command to clear a stuck continuation

Best fix: use a genuine FTDI or a CP2102 cable.

## 4. The console goes entirely silent

Observed after sending `reboot` over a corrupting TX line: all four ports read
**0 bytes**, even to a bare CR, and a USB reset of the adapter did not revive it.

The E750 has an **internal battery**, so it may have powered off rather than
rebooted — do not assume a hang. Recovery: power-cycle the device with a listener
already running:

```bash
python3 scripts/serial-listen.py --port /dev/ttyUSB3 --seconds 600 --out boot.log
```

Note this is **not** the `capture_all.py` style multi-port scan: once the console
port is known, watch only that one. Opening all four repeatedly is itself a source
of confusion.

## 5. A reboot does not appear to happen

`reboot` is an unverified command: on a corrupting TX line it may never reach the
shell, or may arrive mangled. Never infer a reboot from silence — check with
`uptime`, and prefer a **power-cycle you can observe** over a serial `reboot` for
recovery work.

## 6. `art` is wiped (not the case on this unit)

If the `art` header assertion in the `caldata` role fails, the partition no longer
holds valid calibration:

```
Extracted caldata does NOT start with the expected QCA9887 magic (44081ba80401)
```

Do **not** copy caldata from another E750 — it encodes device-specific RF
parameters and MAC. Restore the original dump for *this* unit, or accept a
2.4 GHz-only device. This is the one scenario where a reflash of `art` is
unavoidable, and only from that unit's own backup.
