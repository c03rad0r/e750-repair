# QCA9887 5 GHz — `skip_otp` lead

Status: **partial success; disabled pending a controlled retry.** The 5 GHz
QCA9887 initialized and beaconed an AP when ath10k loaded with
`skip_otp=1`, but the initialization is not stable across a full wifi
restart and it runs without per-device calibration.

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

`wireless.radio1.disabled=1`; the 5 GHz radio is not used at boot. The 2.4 GHz
STA/AP, BSBF and portal are healthy.
