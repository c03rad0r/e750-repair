# E750 execution plan — 2026-10-30

Scope: the six follow-ups from the bonding/portal review.

- [x] 1. Automatic standby/aggregate controller (installed; observe-only)
- [x] 2. Portal branding ("bonded gateway")
- [x] 3. Bake the runtime pieces into the image (except tollgate-wrt, external feed)
- [x] 4. Wire the serial checksum into Ansible (plugin + docs) — see commit
      `004cfea` on `pr/fleet-e750-batch`; end-to-end run blocked by the dead console
- [x] 5. Art-blob calibration experiment — negative; OTP is required, documented
- [x] 6. MCU/OLED driver + "TollGate" via the SSID page (no free text in the MCU protocol)

## 1. Automatic standby/aggregate controller

Goal: choose `wwan0` as a backup subflow (standby) or an active subflow
(aggregate) from measured conditions, with hysteresis, instead of a fixed flag.

Inputs recorded every 60 s in `/etc/e750/metrics.csv`:

```text
ts,mode,sta_up,wwan_up,sta_rx,wwan_rx,sta_rtt,wwan_rtt,sta_loss,wwan_loss,
load1,cpu_idle,conntrack,sta_signal,wwan_signal,wan_bytes_today,decision,reason
```

Policy (default observe-only):

- aggregate only when `rtt_4g/rtt_sta < 1.5`, jitter < 25 ms, loss < 1%,
  CPU idle > 30%, data budget OK, for 5 consecutive samples;
- back to standby when the ratio > 2.0, loss > 3%, CPU idle < 15%, or the
  budget is low, for 3 samples;
- minimum dwell 30 min; manual override wins;
- STA loss > 50% for 30 s promotes the 4G (failover).

Implementation:

- `scripts/e750-path-metrics.sh` — sample and append the CSV.
- `scripts/e750-link-mode.sh` — evaluate, log, and only apply when
  `e750.linkmode.enabled=1`.
- `roles/e750_link_mode` — install scripts, `/etc/config/e750_linkmode`, cron.
- `bond.json` for the portal badge.

Evidence: first hours of `/etc/e750/metrics.csv`.

## 2. Portal branding

- nodogsplash `gatewayname`, `locales/en.json` (`html_title`, `portal_title`,
  `powered_by`), a badge in `splash.html`, and a `/bond.json` live updater.
- Separate role so re-applying it cannot touch br-portal/radios/BSBF.

Verify: `curl http://10.0.0.1:2051/splash.html` shows the badge; the JSON strings
are present.

## 3. Image bake-in

- `ath10k-skip-otp` hook + `radio1` defaults.
- `br-portal`, dnsmasq, firewall, nodogsplash, portal uhttpd.
- portal-over-bond nft + sysctls, link-mode service, branding.
- `tollgate-wrt` from a pinned custom feed (decision required).
- Build with `image/build.sh`; do not flash until the serial link is fixed.

## 4. Serial checksum

Done in the plugin; remaining: re-run after the cable is repaired and confirm
`playbook-e750-serial-check.yml` passes. Flashing remains gated.

## 5. Art-blob calibration

- Extract `art@0x5000/0x440` as `cal-pci-0000:00:00.0.bin`.
- Set `skip_otp=0`, boot once, capture dmesg.
- If the EEPROM `-22` disappears and the radio calibrates, keep it; otherwise
  revert to `skip_otp=1` and record that OTP is unrecoverable.
- Keep txpower low either way.

## 6. MCU / OLED

- Probe `ttyS0` (the MCU shares the console UART) with `scripts/mcu-probe.sh`.
- Identify the display command from the response or GL's source.
- If a display command exists, write a source-only helper that renders
  "TollGate" plus the link mode; wire it to the controller.
- If the protocol is not discoverable, document the blocker and leave the stock
  display behaviour.

## Risks

- The E750 is CPU-bound; the controller must not itself add load.
- Calibration changes can drop the 5 GHz portal; the experiment is reversible.
- The MCU shares the console; probing can disturb the recovery path (already
  dead, so the risk is contained).
- Do not flash until the console works.
