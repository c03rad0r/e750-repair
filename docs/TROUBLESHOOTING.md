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

## 6. `-122` on the board-id path (post-caldata-install signature)

```
ath10k_pci 0000:00:00.0: failed to get board id: -122
```

**Do not read this as "the driver hit a disk-quota error".** `-122` is `-EDQUOT`,
and **`-EDQUOT` occurs nowhere in the ath10k driver** — no ath10k function can
return it. The number is a *value* produced by the target firmware and passed
through `ath10k_bmi_execute()`'s `resp.execute.result` field into the driver's
`int ret`, where it then gets printed as if it were an errno.

Where it surfaces:

```c
ret = ath10k_core_get_board_id_from_otp(ar);
if (ret) {
        ath10k_err(ar, "failed to get board id: %d\n", ret);   /* <-- this line */
        return ret;
}
```

The diagnostic value of this line is **negative-space information**. Two other
prints that *should* appear around this call do **not**:

- `could not execute otp for board id check: %d` — the error branch *inside*
  `ath10k_core_get_board_id_from_otp()`
- `boot get otp board id result 0x%08x board_id %d chip_id %d` — the `_dbg` line
  that fires after a successful `ath10k_bmi_execute()`

So the call's own execute step did not fail; something **later** returned −122.
Consistent with `ath10k_download_board_data()` → `ath10k_bmi_read32()` failing,
whose surrounding error prints (`failed to download board data`, `could not push
board ext data`, `could not read board data addr`) are likewise **absent**.

One candidate mechanism: `ath10k_bmi_read_memory()`'s loop has no lower-bound
guard —

```c
while (length) {
        rxlen = min_t(u32, length, BMI_MAX_DATA_SIZE);
        ...
        length -= rxlen;    /* a short read underflows to ~4 GiB */
}
```

A short read underflows `length` to `0xFFFFFFFC` and spins far past the intended
window. **Unconfirmed** — see `docs/EVIDENCE.md` §3.

### Why the `-122` matters for diagnosis

It appears **only** in boots made after the caldata files were placed
(`grep -c -- '-122'`: pre-install log = 0, both post-install logs = 1). Placing a
`pre-cal-*` file sets `ar->cal_mode = ATH10K_PRE_CAL_MODE_FILE`, and that value is
read to choose which BMI parameter to send:

```c
if (ar->cal_mode == ATH10K_PRE_CAL_MODE_DT ||
    ar->cal_mode == ATH10K_PRE_CAL_MODE_FILE ||
    ar->cal_mode == ATH10K_PRE_CAL_MODE_NVMEM)
        bmi_board_id_param = BMI_PARAM_GET_FLASH_BOARD_ID;
else
        bmi_board_id_param = BMI_PARAM_GET_EEPROM_BOARD_ID;
```

Cheapest decisive test: remove the `pre-cal-*` / `cal-*` files, reboot, check
whether `-122` disappears; re-add, reboot, check whether it returns. One variable.

### Trap: `otp calibration failed: N` proves nothing about calibration

```c
if (... && result != 0) {
        ath10k_err(ar, "otp calibration failed: %d", result);
        return -EINVAL;
}
```

`result` is the **target's** answer to `ath10k_bmi_execute()`. When an earlier
`-122` aborts the setup, `ar->id.bmi_ids_valid` stays false, which selects
`BMI_PARAM_GET_FLASH_BOARD_ID` instead of `BMI_PARAM_FLASH_SECTION_ALL` — a
different question to the target, which can answer `2` for reasons unrelated to
calibration validity. **Do not argue from this line's position in the log.**

## 7. `art` is wiped (not the case on this unit)

If the `art` header assertion in the `caldata` role fails, the partition no longer
holds valid calibration:

```
Extracted caldata does NOT start with the expected QCA9887 magic (44081ba80401)
```

Do **not** copy caldata from another E750 — it encodes device-specific RF
parameters and MAC. Restore the original dump for *this* unit, or accept a
2.4 GHz-only device. This is the one scenario where a reflash of `art` is
unavoidable, and only from that unit's own backup.
