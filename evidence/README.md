# Evidence — raw captures backing every claim in `docs/EVIDENCE.md`

Nothing here is retyped or summarised. These are the bytes as captured.

## `boots/` — the four boot captures that settle the `-122` question

| File | When | cal files | `-122` | EEPROM `-22` |
|---|---|---|---|---|
| `2026-10-23_0443_pre-install.log` | 2026-10-23 04:43 | **absent** | absent | present |
| `2026-10-23_1528_post-install.log` | 2026-10-23 15:28 | present | **present** | present |
| `2026-10-23_1723_post-install.log` | 2026-10-23 17:23 | present | **present** | present |
| `2026-10-25_post-reflash.log` | 2026-10-25 | **absent** | absent | present |

Verify the pivotal column yourself — the `-122` appears in exactly the two
post-install boots:

```bash
grep -c -- '-122' evidence/boots/*.log
```

Expected: `0` for the pre-install and post-reflash logs, `1` for the two
post-install logs.

Caveat on the 2026-10-25 capture: it is a genuine, distinct boot (it starts mid
boot at `procd: - init -` and its ath10k timestamps differ from both 10-23
boots; it is not a byte-subset of either), but it was read from the serial port
at a moment when that port was about to serve a different board. It is
therefore evidence of *an* E750 boot of that vintage, not of the unit's state
at the time it was committed. The current-state evidence is the read-back below.

## `2026-10-25_reflashed-live-readback.txt`

Live read-back over SSH from the reflashed unit (`ssh -i ~/.ssh/id_bench
root@192.168.8.1`), the same session that produced §3c. Shows the identity, the
firmware directory containing only `board.bin` + `firmware-2.bin`, an empty
`cal-pci*`/`pre-cal*` search, and the live ath10k dmesg with `-122` count `0`.

## `scripts/` — what was actually run

- `2026-10-23_install_caldata.py` — extracts `art@0x5000` and writes
  `cal-pci-0000:00:00.0.bin` into the driver's `hw1.0/` directory.
- `2026-10-23_fix_paths.py` — the second step that also placed
  `pre-cal-pci-…` and a top-level copy. **This is the step after which `-122`
  appears**, which is why the file placement is the suspect and not the
  extraction itself.

## What is NOT here

- No `art` partition dump (contains this unit's RF calibration and MAC; not
  published).
- No full filesystem images.
