# Checksummed serial execution

Status: **implemented and live-tested** (2026-10-29). The E750 serial cable was
re-soldered by the operator; raw command reliability improved from **0/5** to
**96/100** commands, but errors remain (~4%). The checksummed channel caught a
natural bit flip and retransmitted it. `scripts/serial-exec.py` adds
payload and output checksums with retransmission so a corrupted line cannot be
executed.

## Why

The console is an interactive shell, not a framed link. A typo or bit flip can
run a different command. The wrapper makes the host upload the exact script as
base64 text, verify it with SHA-256 **on the device**, then decode and verify
again before running it. A corrupted upload is rejected and retransmitted.

## Flow

```text
host:  cat > /tmp/e750-serial-<nonce>.b64
host:  <base64 lines>  (Ctrl-D)
dev:   sha256sum the uploaded file
host:  compare; mismatch -> retransmit the whole file
dev:   base64 -d -> /tmp/e750-serial-<nonce>.sh
dev:   sha256sum the decoded script; host compares
host:  --dry-run -> print script and hashes, do not execute
host:  sh script > out 2>&1; echo RC marker
dev:   sha256sum out
host:  capture output between markers, normalize CRLF, compare hash
```

- `--dry-run` verifies the channel and prints the script without executing.
- `--allow-dangerous` is required for scripts containing `mtd`, `sysupgrade`,
  `reboot`, `fw_setenv`, `nand`, `ubiformat`, `firstboot`, `mkfs`,
  `dd if=/dev/mtd`, or `rm -rf /`.
- On a payload mismatch the host retransmits up to `--retries` times.
- A corrupted output is rejected by the output hash; the file remains on the
  device and can be re-read.

## Live results

```text
$ serial-exec.py /dev/ttyE750 -c 'echo SERIAL_EXEC_OK; uname -a'
SERIAL_EXEC_OK
Linux e750-lab 6.12.94 #0 ... mips GNU/Linux

$ serial-exec.py /dev/ttyE750 -c 'echo DRY_RUN_MUST_NOT_PRINT' --dry-run
script_sha256=82be... bytes=28
echo DRY_RUN_MUST_NOT_PRINT

$ serial-exec.py /dev/ttyE750 -c 'echo RETRY_OK' --inject-error
payload hash mismatch on attempt 1; retransmitting
RETRY_OK

$ serial-exec.py /dev/ttyE750 -f multi.sh
payload hash mismatch on attempt 1; retransmitting   # natural bit flip, caught
line one
line two
...
rc=3

$ serial-exec.py /dev/ttyE750 -c 'reboot'
refusing dangerous script without --allow-dangerous: reboot
```

The natural bit flip is the key result: the checksum caught a real line error
and retransmitted it; the corrupted script was never executed.

## Requirements

Device: `sha256sum` (BusyBox) and `base64` (`coreutils-base64`). The image now
includes `coreutils-base64` and `lrzsz` (for ZMODEM). For a running device:

```sh
apk add coreutils-base64 lrzsz
```

Host: Python 3; the script uses only the standard library.

## Usage

```bash
# from x280, with the E750 serial console on /dev/ttyE750
python3 scripts/serial-exec.py /dev/ttyE750 -c 'uname -a'
python3 scripts/serial-exec.py /dev/ttyE750 -f repair.sh --dry-run
python3 scripts/serial-exec.py /dev/ttyE750 -f repair.sh
python3 scripts/serial-exec.py /dev/ttyE750 -f flash.sh --allow-dangerous
```

## Limits / next

- This is **not authentication**: serial access is root-equivalent. It protects
  against typos/noise, not a malicious operator.
- It is for the **Linux shell**, not U-Boot. For U-Boot use `loadx`/`loady`
  (XMODEM/YMODEM) or ZMODEM; never type `erase`/`cp.b`/`nand write`.
- Large files are base64-expanded and slow; use ZMODEM (`sz`/`rz`) or the network
  for images. Always verify the SHA-256 on the device before writing/flashing.
- Output hashing normalizes CRLF; binary output is not supported.
- A 100-command + wiggle test is still recommended before trusting the link for
  U-Boot/flashing.

## Checklist

- [x] Host `scripts/serial-exec.py` with SHA-256 payload/output and retransmit.
- [x] `--dry-run` and `--allow-dangerous` gates.
- [x] Device `coreutils-base64` installed; image packages updated.
- [x] Live tests: clean, dry-run, injected corruption, natural corruption,
      non-zero exit, output hash.
- [x] `lrzsz` installed for ZMODEM; image package added.
- [x] 100-command test: **96/100 clean, 4 corrupt**; raw commands are not safe
      for U-Boot/flash. Evidence `evidence/serial/2026-10-29_100-command.txt`.
- [ ] Wiggle test; if errors cluster, reflow/swap the adapter before relying on
      the raw link.
- [ ] ZMODEM file-transfer smoke test (`sz`/`rz`).
- [ ] Use the checksummed channel for the 5 GHz board-ID/EEPROM experiments.
- [ ] Add a checksummed U-Boot `loady` runbook.
