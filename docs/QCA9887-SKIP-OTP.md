# QCA9887 5 GHz — `skip_otp` lead

Status: **working as the portal AP** (2026-10-29), with no per-device
calibration. The 5 GHz QCA9887 initializes at boot via the
`/etc/init.d/ath10k-skip-otp` hook and serves `TollGate-E750` on
channel 36/VHT80; the 2.4 GHz radio is the STA/BSBF backhaul. See
[`E750-RADIO5G.md`](E750-RADIO5G.md).

See `evidence/caldata/2026-10-29_skip-otp.md` for the full log.

## What worked

```sh
rmmod ath10k_pci; rmmod ath10k_core
insmod /lib/modules/$(uname -r)/ath10k_core.ko skip_otp=1
insmod /lib/modules/$(uname -r)/ath10k_pci.ko
```

- `skip_otp` became `Y`; the OTP failure disappeared.
- `phy3`/`phy5` appeared; a 5 GHz AP on channel 36 (VHT80) reached
  `AP-ENABLED` and was visible to a client scan.
- The 2.4 GHz radio/BSBF/portal can run at the same time if the 5 GHz setup is
  done with `wifi reload` and no full `wifi down/up`.

## What did not

- `modprobe` and `/etc/modprobe.d` did not apply `skip_otp` on this image;
  `insmod` did.
- `wifi down/up` or a module reload can race:
  `failed to receive initialized event from target`, then the EEPROM `-22`
  errors return; `radio1` stays pending and the 2.4 GHz STA/portal can drop.
- No per-device calibration: tx power/regulatory behavior is not validated.
  Keep txpower low and do not expose an open 5 GHz AP on the management LAN.

## Next (serial attached)

- [ ] Load `skip_otp=1` with `insmod`, then only `wifi reload`.
- [ ] Put the 5 GHz AP on a separate `br-portal5` (e.g. 10.0.5.1), not `lan`.
- [ ] Verify beacon, association, DHCP, throughput at low txpower.
- [ ] Try `cal-pci-0000:00:00.0.bin` + `skip_otp=1` (one variable) for
      stability/calibration.
- [ ] If stable, persist via a boot script or U-Boot `bootargs`
      `ath10k_core.skip_otp=1`; use 5 GHz for the portal and 2.4 GHz for the
      STA/BSBF.
- [ ] If unstable, keep it disabled and document the result.

## Current state

`wireless.radio1.disabled=0`; the boot hook loads `skip_otp=1`; the 5 GHz AP is
`phy2-ap0` on `br-portal`; the 2.4 GHz STA/BSBF and portal are healthy.


## Experiment history

- `skip_otp=1` first let the radio reach `AP-ENABLED` on channel 36/VHT80.
- A full `wifi down/up` or module reload was **not stable**:
  `failed to receive initialized event from target`, then the EEPROM `-22`
  errors returned, `radio1` stayed pending, and the 2.4 GHz STA/portal could
  drop.
- `wireless.radio1.disabled=1` was used during rollback; it is now enabled via
  the boot hook `ath10k-skip-otp` (START=19), which loads `skip_otp=1` before
  wifi starts.


## cal-pci + skip_otp

Installed the art `0x5000`/`0x440` blob as
`cal-pci-0000:00:00.0.bin` with the boot hook still loading `skip_otp=1` and
rebooted. The 5 GHz AP remained AP-ENABLED and 2.4 GHz/BSBF stayed healthy, but
dmesg still reported the EEPROM `-22` and there was no evidence the cal file was
used. Removed the cal file and rebooted: the 5 GHz AP still works with
`skip_otp` alone. Keep the role skip_otp-only; the cal file is not in the public
image. Evidence: `evidence/caldata/2026-10-29_cal-skip-otp.txt`.
