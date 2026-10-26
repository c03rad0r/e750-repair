# Evidence — raw captures backing every claim in `docs/EVIDENCE.md`

Nothing here is retyped or summarised. These are the bytes as captured.

## `boots/` — the boot captures that settle the `-122` question

| File | When | cal files | `-122` | EEPROM `-22` |
|---|---|---|---|---|
| `2026-10-23_0443_pre-install.log` | 2026-10-23 04:43 | **absent** | absent | present |
| `2026-10-23_1528_post-install.log` | 2026-10-23 15:28 | present | **present** | present |
| `2026-10-23_1723_post-install.log` | 2026-10-23 17:23 | present | **present** | present |
| `2026-10-25_serial_pre-reflash.log` | 2026-10-25 | present | **present** | present |

Verify the pivotal column yourself:

```bash
grep -c -- '-122' evidence/boots/*.log
```

Expected: `0` for `2026-10-23_0443_pre-install.log`, `1` for the other three.

**A correction worth keeping visible.** The 2026-10-25 serial capture is named
`…_serial_pre-reflash` because it DOES contain `-122` — it was a boot with the
cal files still installed, captured before the unit was reflashed. An earlier
revision of this file called it `post-reflash` and listed `-122` as absent;
`grep -c` disproved that in one command. The reflashed state is evidenced by the
live read-back below, not by this log.

Note also that `*.log` is in `.gitignore`, so these four files need the
`!evidence/boots/*.log` negation that now sits in `.gitignore`. Without it they
silently do not get committed and this README points at files that are not in
the repo. Check with `git ls-files evidence/boots/`.

Caveat on the 2026-10-25 capture: it is a genuine, distinct boot (it starts mid
boot at `procd: - init -` and its ath10k timestamps differ from both 10-23
boots; it is not a byte-subset of either). It is evidence of *an* E750 boot of
that vintage.

## `2026-10-25_reflashed-live-readback.txt`

Live read-back over SSH from the reflashed unit (`ssh -i ~/.ssh/id_bench
root@192.168.8.1`), the same session that produced §3c. Shows the identity, the
firmware directory containing only `board.bin` + `firmware-2.bin`, an empty
`cal-pci*`/`pre-cal*` search, and the live ath10k dmesg with `-122` count `0`.

This is what supplies the "cal files absent → `-122` absent" row for the
reflashed state:

| State | cal files | `-122` |
|---|---|---|
| 2026-10-23 04:43 stock | absent | absent |
| 2026-10-23 15:28 / 17:23 installed | present | present |
| 2026-10-25 serial (pre-reflash) | present | present |
| 2026-10-25 live read-back (reflashed) | absent | **absent** |

The −122 tracks cal-file presence in both directions.

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
