# E750 serial console reliability

Status: **root cause isolated; hardware replacement/swap required** (2026-10-29).

## Symptom

The E750 console is silent over `/dev/ttyE750` on x280. The E750's console
`askfirst` process waits for a valid Enter; the host's TX corrupts it, so the
console never activates. Boot logs (E750 -> host) were byte-clean, so the
E750's TX/RX and the host's RX are fine; the **host -> E750 TX** is the fault.

## What was measured

| Device / adapter | Port | Result |
|---|---|---|
| E750, FTDI `BH00DL3M` | `/dev/ttyE750` (`ttyUSB0`) | CR burst returns garbage bytes or nothing; no shell/prompt; `askfirst` stays waiting |
| MT6000, FTDI `BG046H5F` | `/dev/ttyUSB1` | CR returns the BusyBox banner and a usable shell |
| Both adapters | same USB hub (`1-2`, ports 1 and 4) | same hub, same host; the MT6000 adapter is clean |
| E750 `serial-tx-test.py` | `/dev/ttyE750`, 5 attempts | **0/5 clean**; wake prompt appears, commands corrupt |
| MT6000 `serial-tx-test.py` | `/dev/ttyUSB1`, 5 attempts | **5/5 clean** |
| E750 `serial-wake.py id` | 6 attempts | every echo corrupted; not accepted |
| MT6000 `serial-wake.py id` | 1 attempt | `uid=0(root) gid=0(root)` |

The MT6000 control rules out the hub and the host USB controller. The E750's
`BH00DL3M` adapter/cable (or its connection at the E750 end) is the bad leg.
The E750's `askfirst` is `/sbin/askfirst /usr/libexec/login.sh`; it needs one
valid CR, and the bad TX corrupts every CR.

Settings tested on the E750 adapter:

- `latency_timer` 16 -> 1: no change.
- USB `power/control` already `on`: no change.
- 115200 8N1, raw, no flow control: the only baud that answers; same result.

## Fix

1. **Swap the E750 adapter/cable first.** Move the E750 cable to the known-good
   `BG046H5F` adapter (temporarily unplug the MT6000 console), or swap the two
   adapters. The MT6000 leg is 5/5 clean and `id` works; the E750 leg is 0/5
   with every command corrupted. If the E750 console then works, the
   `BH00DL3M` adapter/cable is confirmed bad.
2. **Replace with a known-good 3.3 V adapter** if the swap does not fix it:
   genuine FTDI FT232RL (3.3 V) or CP2102/CH340. Avoid unmarked FTDI clones.
   - 3.3 V logic (the E750 UART is 3.3 V); do not feed 5 V into the header.
   - GND common; TX -> E750 RX, RX <- E750 TX; do not connect VCC.
   - Short cable (<30 cm), shielded if possible; direct USB port, not the
     powered hub, when testing.
   - Check the E750 UART header/pins for a cold joint or swapped TX/RX; the
     MT6000 adapter working on the same hub points at the E750 adapter/cable or
     the E750-end wiring, not the host.
3. **Loopback test:** disconnect the adapter from the E750, short its TX and RX,
   and run `serial-tx-test.py`. Garbage in loopback = adapter/cable; clean
   loopback but garbage to the E750 = E750-end wiring/level.
4. **After a good adapter:** a single CR should start `askfirst`; run
   `serial-wake.py` and then the normal serial transport. The repo's
   `connection_plugins/serial_console.py` still retries corrupted commands.

## Loopback / cold-joint test

A cold solder joint on TX, RX, GND, or the Dupont/header pin is plausible. Prove
it with a loopback before reflowing:

1. Unplug the adapter/cable from the E750.
2. Short the adapter/cable **TX and RX** pins (leave GND connected normally; do
   not connect VCC).
3. Run:

   ```bash
   ssh x280 'python3 ~/e750-repair/scripts/serial-tx-test.py /dev/ttyE750 --loopback --count 10'
   ```

   `--loopback` sends a 95-byte printable pattern and compares the exact bytes;
   it does not need a shell. `summary loopback_clean=10/10` means the adapter and
   cable are good. Any corrupt/mismatched bytes means the adapter/cable/connector
   is bad (cold joint, bad crimp, or level problem).

4. Continuity with the power off: TX→RX (at the E750 end, after the adapter),
   GND→GND, and each wire end-to-end should be <1 Ω and stable while wiggling
   the connector. A jump = cold/intermittent joint.
5. Visual/reflow: inspect the FTDI header and the E750 UART pads; reflow TX/GND
   with flux; replace Dupont wires with short soldered leads; verify the
   adapter is set to **3.3 V** (the E750 UART is 3.3 V, not 5 V).

If loopback is clean but the E750 still corrupts, the E750-end RX pad/level or
the UART is the problem. If loopback is corrupt, replace/reflow the adapter or
cable; a known-good `BG046H5F` swap is the fastest confirmation.

## Software tools

```bash
# measure raw TX reliability (read-only echo commands)
ssh x280 'python3 ~/e750-repair/scripts/serial-tx-test.py /dev/ttyE750 --count 5'
ssh x280 'python3 ~/e750-repair/scripts/serial-tx-test.py /dev/ttyUSB1 --count 5'  # control

# wake the console and send a command with echo verification/retries
ssh x280 'python3 ~/e750-repair/scripts/serial-wake.py /dev/ttyE750 "id"'
```

`serial-tx-test.py` counts a command as clean only when the nonce appears twice
(console echo + command output), so a corrupted command that only echoes the
nonce is not a false pass. Its `--loopback` mode compares raw bytes when TX/RX
are shorted at the adapter/cable end.

Software retries cannot fix a line that corrupts every CR/command. The E750
console itself is fine (the prompt appears; RX is clean); the host -> E750 TX is
the fault. Until the adapter is replaced/swapped, use SSH (`x280` ->
`192.168.8.1`; T14 via `-J x280`) as the primary access and treat serial as
unavailable for recovery.

## Evidence

- `evidence/serial/2026-10-29_adapter-comparison.txt`
- `evidence/serial/2026-10-29_tx-test-e750.txt`
- `evidence/serial/2026-10-29_tx-test-mt6000.txt`

## Console activation note

The E750 uses `::askconsole:/usr/libexec/login.sh` in `/etc/inittab`; the
running process is `/sbin/askfirst /usr/libexec/login.sh`. It deliberately
waits for a valid Enter. Changing it to `respawn` would start the console
without an Enter, but commands would still be corrupted by the bad TX, so the
hardware fix is the correct one. Keep the default `askfirst` behavior.
