# Portal radio + mint cleanup — 2026-10-30

Follow-up to the phone disconnect: the 5 GHz QCA9887 is uncalibrated, at 10 dBm,
and requested a hardware restart. The phone associated, got DHCP, then was
deauthenticated after ~10 s. Move the portal AP to the 2.4 GHz radio.

- [x] Move the portal AP to 2.4 GHz (`radio0`), AP+STA on the same radio
- [x] Disable the 5 GHz AP (`radio1`) and free its CPU
- [x] Verify AP beacon, DHCP, splash and post-auth flow from a veth client
- [x] Re-check pre-auth enforcement (307 is the splash redirect, not a bypass) (a fresh veth got `307` before auth)
- [x] Prune dead mints (`minibits`, `lnserver`) and keep 5 reachable mints
- [x] Set a healthy current mint (coinos) (coinos or cubabitcoin)
- [x] Persist the changes in the role/image and document
- [ ] Phone test (operator)

## Topology

```text
phy1 (2.4 GHz, QCA9531)
  phy1-sta0  hermes-lan   STA/BSBF uplink
  phy1-ap0   TollGate-E750 AP (unique MAC, ch11, HT20)
5 GHz        disabled     (uncalibrated, unstable)
```

`hermes-lan` exists only on 2.4 GHz, so AP+STA must share that radio.

## Mints

Accepted today: coinos, minibits, lnserver, macadamia, westernbtc, kashu.me,
cubabitcoin. `minibits` fails with EOF from three vantage points; `lnserver`
has no DNS. Keep the five that answer.

## Evidence

- `evidence/portal/2026-10-30_phone-disconnect.txt`
- `evidence/tollgate/2026-10-30_mint-probe.txt`
