# E750 4G modem diagnostics

Read-only diagnostics for the Quectel EM060K-GL / Aldi Talk link. The role
installs `coreutils-stty` and `picocom` (the stock image lacks `stty` and
`microcom`, which is why the AT port could not be put in raw mode reliably).

It **does not** query the IMSI/ICCID (`subscriber`, `AT+CIMI`, `AT+QCCID`) and
does not change the APN, radio state, or interfaces.

## Run

From x280:

```bash
cd ~/e750-repair
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-e750-modem-diag.yml
```

The role runs `scripts/e750-modem-diag.sh` and prints the report.

## What it reads

- `ifstatus wwan1` — MBIM address/route state.
- `umbim -d /dev/cdc-wdm0 caps|pinstate|registration` — MBIM control state.
- `AT`, `ATI`, `AT+CPIN?`, `AT+COPS?`, `AT+QCSQ` (RSRP/RSRQ/SINR),
  `AT+QENG="servingcell"` (band/cell/signal), `AT+CGDCONT?` (APN).
- `wwan0` rx/tx byte counters.

The AT port is `/dev/ttyUSB3` at 115200 8N1; `stty` puts it in raw mode before
the queries.

## Interpreting it

| Observation | Meaning | Action |
|---|---|---|
| `+CPIN?` = `READY`, `+COPS?` registered | SIM and network are fine | look at signal |
| `+QCSQ` / `QENG` has weak RSRP/SINR | RF problem | external antenna / reposition |
| Good signal, low throughput | plan throttle or APN policy | check the Aldi Talk data plan |
| `umbim registration` not registered | attach/SIM issue | re-seat SIM; check APN |

Current measured 4G is ~0.5 Mbps, so the BSBF client keeps `wwan0` as backup and
the STA path carries the aggregate. If the diagnostics show a healthy signal but
the link is throttled, the plan is the limit; if the signal is weak, an antenna
or position change is the fix.

## Result (2026-10-29)

```text
AT+CPIN?  -> +CPIN: READY
AT+COPS?  -> +COPS: 0,0,"MEDIONmobile",7
umbim     -> registerstate: home, availabledataclasses: lte,
             provider_name: MEDIONmobile
AT+QENG   -> LTE FDD, RSRP -59 dBm, RSRQ -13 dB, SINR 9 dB
AT+CGDCONT-> internet, ims, SOS, internet.eplus.de
```

The SIM is ready, the modem is registered on Aldi Talk / MEDIONmobile (LTE,
home), and the RF signal is healthy. The active APN is `internet.eplus.de`
(context 4); the modem also carries the default `internet` context.

The measured ~0.5 Mbps is therefore **not an RF/signal problem**. It is most
likely the Aldi Talk plan's throttled/high-speed-volume state or an APN policy,
not something an antenna will fix. Check the plan's remaining high-speed data
before spending on hardware. Keep `wwan0` as the BSBF backup until the link is
actually faster than the STA path.

`umbim caps`/`pinstate` time out while the modem is connected, but the AT
queries and the MBIM registration query work; that is a diagnostic quirk, not a
data-path failure.

Evidence: `evidence/modem/2026-10-29_diag.txt`.
