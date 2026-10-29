# 5 GHz portal AP (QCA9887 + skip_otp)

Status: **working on the live unit** (2026-10-29), with a calibration caveat.
The 5 GHz QCA9887 initializes when ath10k loads with `skip_otp=1` and serves the
portal AP; the 2.4 GHz radio is the STA/BSBF backhaul.

```text
5 GHz  phy2-ap0  TollGate-E750  5180 MHz, VHT80, txpower 10 dBm -> br-portal 10.0.0.1
2.4 GHz phy1-sta0 hermes-lan    STA/BSBF primary
2.4 GHz AP       disabled       (airtime reserved for the STA/backhaul)
4G               wwan0          BSBF backup
```

## Why skip_otp

The QCA9887 OTP/EEPROM read fails with `-22` on this unit (`bmi_id N/A`). Loading
`ath10k_core` with `skip_otp=1` bypasses the OTP path; the radio then
initializes and beacons. `modprobe`/`modprobe.d` did not apply the parameter on
this image; `insmod` did.

The boot hook `/etc/init.d/ath10k-skip-otp` (START=19) unloads and reloads
ath10k with `skip_otp=1` before wifi starts.

## Caveat: no per-device calibration

`skip_otp` means the radio runs **without the per-device calibration** from
OTP/art. TX power/regulatory behavior is not validated. Keep `txpower 10` and do
not expose an open AP on the management LAN. For production, retry with
`cal-pci-0000:00:00.0.bin` + `skip_otp=1`, or repair the OTP/EEPROM path.

## Apply / verify / rollback

```bash
ssh x280
cd ~/e750-repair
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-e750-radio5g.yml
# reboot to load skip_otp
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-e750-radio5g-verify.yml
```

Rollback (returns to the 2.4 GHz portal AP):

```bash
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-e750-radio5g-rollback.yml
# reboot
```

## Verified

Cold boot: `skip_otp=Y`, `phy2-ap0` AP-ENABLED on ch36/VHT80, `phy1-sta0`
connected to hermes-lan, BSBF endpoints `phy1-sta0` + `wwan0` backup, egress
`23.182.128.219`, `RESULT OK`. A client scan sees `TollGate-E750` on 5 GHz.
Evidence: `evidence/caldata/2026-10-29_skip-otp-boot.txt`.

## Still to do

- [ ] Real 5 GHz client: association, DHCP, splash, payment, post-auth, logout.
- [ ] Throughput/CPU with 5 GHz portal + 2.4 GHz BSBF.
- [ ] Try `cal-pci` + `skip_otp` to restore per-device calibration/stability.
- [ ] Decide on persistence (boot script vs U-Boot `bootargs`); current hook is
      installed by the role.
- [ ] Add ath10k boot hook/radio1 defaults to the image or a first-boot script.
