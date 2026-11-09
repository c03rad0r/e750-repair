# E750 eSIM / silent.link

Status: **on-device stack and host-side activation implemented; hardware
gate pending on this unit.**
Bench note 2026-11-04: the E750 still answers ICMP on its management address
but dropbear/HTTP are closed, so the read-only gate was not run. The GL.iNet
UI found at `192.168.2.1` is a GL-MT3000, not the E750. The serial console
prompt answers, but the `BH00DL3M` TX leg is still corrupt (`0/5` clean); the
known-good `BG046H5F` control is `2/2` clean. Swap the E750 cable to a
known-good adapter before relying on serial. Re-run the gate when SSH is back;
do not treat the earlier `ttyUSB3` measurement as permanent.

This document adapts the proven NR7101 process from
`Amperstrand/conwrt` (`docs/MODEM-AS-READER-PLAYBOOK.md`, issue #619) to the
GL-E750's Quectel EM060K-GL. It is species-level only: no EID, ICCID,
activation code, token, unit MAC or bench address belongs here.

## What is proven, and what is not

| Item | State |
|---|---|
| Host-side SGP.22 chain | Proven on NR7101 / RG502Q-EA (conwrt, ifd-modemifd) |
| On-device lpac (`LPAC_APDU=at_csim`) | Proven on NR7101; E750 artifact published |
| E750 EM060K-GL AT/CSIM behaviour | **Not yet measured on this unit** |
| E750 MBIM data composition | Measured on this unit (`/dev/cdc-wdm0`) |
| E750 AT port | Measured at `/dev/ttyUSB3` on 2026-10-29; still **re-detect** |
| E750 9eSIM profile state | Blank at last inspection; confirm before writing |

The E750 is `ath79/nand`, `mips_24kc`, big-endian. Use the published artifact,
not the stock OpenWrt `lpac` package.

## The chain

```text
e750-esim (wrapper)
  -> lpac (on the E750)
  -> LPAC_APDU=at_csim
  -> functional /dev/ttyUSBx (AT+CSIM)
  -> 9eSIM (ECP3 eUICC) seated in the E750 SIM slot
```

This is **Path B** from the conwrt playbook: no pcscd, no ifd-modemifd, no
listener, no `stty` relay on the critical path. Path A (host pcscd ->
ifd-modemifd -> ssh://) remains available for PC/SC tooling, but it is not
required.

## Install

```bash
cd ~/e750-repair
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-e750-esim.yml
```

The role:

- refuses to run on a board other than `glinet,gl-e750`;
- downloads `lpac-25.12.5-ath79-nand-mips.tar.gz` from the pinned release;
- verifies sha256
  `9b7088e814d0efef8ab56d98b65263aec3199659bff633566e1f1192e24c8e99`;
- extracts to `/usr/lib/lpac` and installs `/usr/bin/lpac`;
- verifies the `LPAC_APDU_AT_HEX` and `LPAC_HTTP_SSL_VERIFY` fingerprints and
  the bundled GSMA trust store;
- installs `/usr/bin/e750-esim`.

Uninstall:

```sh
rm -rf /usr/lib/lpac /usr/bin/lpac /usr/bin/e750-esim
```

The bundle is non-invasive: its bundled libcurl/openssl live under
`/usr/lib/lpac`, not over the system libraries.

## AT port detection

`e750-esim` re-detects the port on every invocation:

```sh
e750-esim port
```

It probes each `/dev/ttyUSB*` with `AT+CPIN?` and accepts only a port that
answers `+CPIN:` or `+CME ERROR`. **Never identify the port with bare `AT`**:
several ports echo `OK`. Ports shuffle across resets, so never hardcode the
path. The measured unit answered on `/dev/ttyUSB3` at 115200 8N1, but that is
a data point, not a constant.

Override for a deliberate bench test:

```sh
E750_ESIM_AT_DEVICE=/dev/ttyUSB3 e750-esim chip info
```

## Host-side activation orchestrator

`scripts/e750-esim-activate.sh` runs on the operator host (x280 on the bench)
and drives the read-only gate, the free rehearsal, and the paid silent.link
step over SSH. It does not install lpac; run the playbook first.

```sh
scripts/e750-esim-activate.sh --gate
scripts/e750-esim-activate.sh --rehearsal
scripts/e750-esim-activate.sh --verify
```

Paid mode is gated. It requires a successful rehearsal marker, `--confirm-paid`,
and a `0600` LPA file:

```sh
# Put the code in a private file, never in chat or git.
install -m 0600 /dev/null /run/secrets/silentlink.lpa
$EDITOR /run/secrets/silentlink.lpa

scripts/e750-esim-activate.sh --paid \
  --lpa-file /run/secrets/silentlink.lpa \
  --confirm-paid
```

The LPA is read into the shell and sent to the E750 over **stdin**. It is not
placed in a local process argument, printed to the console, or written to the
repository. Private logs and markers live under
`~/.local/state/e750-esim/` (mode `0600`):

```text
logs/gate-*.log        EID/ICCID-bearing gate output
logs/download-*.log    profile download output
logs/enable-*.log      enable output
logs/verify-*.log      interface/APN/profile/notification check
rehearsal-ok           free rehearsal passed
paid-ok                paid profile installed and enabled
```

The paid step is one-shot. If a download fails, do not retry blindly; inspect
the private log and contact the provider. The script never resets the modem
after a profile operation.

If lpac does not print the new ICCID, the script falls back to the profile
list. If more than one profile is present, pass the intended ICCID explicitly:

```sh
scripts/e750-esim-activate.sh --rehearsal --iccid <speedtest-ICCID>
```

After the rehearsal, disable and delete the free Speedtest profile so it does
not occupy a slot:

```sh
e750-esim profile disable <speedtest-ICCID>
e750-esim profile delete <speedtest-ICCID>
```

## Gates

Run in this order. Do not skip the free rehearsal.

### 1. Read-only card gate

```sh
e750-esim chip info
e750-esim profile list
e750-esim notification list
```

Expect the EID, `testProfileSupport`, and a profile list. If `chip info`
fails, stop; do not try writes.

### 2. Wire-fingerprint comparison

Compare the EM060K against the RG502Q reference table:

| Exchange | Expected |
|---|---|
| Lowercase `AT+CSIM` payload | bare `ERROR` — use `LPAC_APDU_AT_HEX=UPPER` |
| `AT+CSIM=10,"0070000001"` | `+CSIM: 6,"0x9000"` (logical channel opens) |
| Channel close, 5-byte `007080xx00` | `9000` |
| Channel close, 4-byte `007080xx` | AT-level `ERROR` |
| `AT+CSIM=?` | bare `OK`, no range line |
| Basic-channel AID select | silently dropped; use logical channels |
| ES10 STORE DATA | `61xx` then chained `INS C0` works unmodified |

Drift is a finding. Record it; do not assume the RG502Q table is universal.

### 3. Free rehearsal (Speedtest)

```sh
e750-esim profile download -a 'LPA:1$rsp.truphone.com$QRF-SPEEDTEST'
e750-esim profile list
e750-esim profile enable <speedtest-ICCID>
```

**Single-quote the LPA string.** Under double quotes the shell expands the
`$` separators and lpac receives a bogus code.

The Speedtest profile is free-failure, additive and deletable. It validates
the whole write path (AT+CSIM, TLS, BPP install, notification). It may also
register and carry data depending on coverage/roaming.

APN for the test/silent.link class is normally `internet`:

```sh
# on the E750, only when you intend to switch the live 4G APN
uci set network.wwan1.apn='internet'
uci commit network
ifup wwan1
```

Verify:

```sh
ifstatus wwan1
AT+QCCID          # via e750-modem-diag or a raw AT helper
AT+CEREG?
AT+COPS?
```

### 4. Paid silent.link (owner-gated)

Only after the free rehearsal is clean and the owner signs off. The activation
code is one-shot; no retry mid-download.

```sh
e750-esim profile download -a 'LPA:1$<smdp-host>$<matching-id>'
e750-esim profile list
e750-esim profile enable <silentlink-ICCID> 1   # refreshFlag
```

Then follow the refresh ladder below. Never `AT+CFUN=1,1`.

## APN map

| Profile/provider | APN |
|---|---|
| Aldi Talk (current 4G) | `internet.eplus.de` |
| silent.link | `internet` (field-verified by the NR7101 lane) |
| nadanada | `data.esim` |
| Speedtest/BetterRoaming | `internet` (verify on the unit) |

The APN is a modem/UCI setting, not an eUICC profile setting. A successfully
installed profile with the wrong APN looks like “no data”.

## Refresh ladder (after any profile operation)

`AT+CFUN=1,1` is **FORBIDDEN** after a profile operation. It wedged the
RG502Q-EA off the USB bus; recovery was a 20-second physical power cut.

1. **RefreshFlag (preferred):** `e750-esim profile enable <ICCID> 1`. The card
   issues REFRESH and drives the modem. Verify QCCID before touching anything.
2. **Settle 90 s.** Post-operation APDU instability is real; silence in the
   first minute is not evidence.
3. **UIM slot power-cycle** only if the MBIM/QMI stack exposes it. The E750 is
   MBIM (`/dev/cdc-wdm0`); verify the available command set first. Do not
   assume a QMI `uqmi --uim-power-off` recipe works on MBIM.
4. **Gentle `CFUN 0→1`**, with settle and functional AT-port re-detection.
5. **Physical power button** is the recovery of last resort. Pull artifacts
   off the box before any reset/power cut; `/tmp` dies with the power.

## Card-safety doctrine

- Never loop secure-channel-class commands; GP/eUICC one-shot auth budgets are
  small and non-renewable.
- Use a sacrificial/test profile for fault injection or soak. The free
  Speedtest profile is the rehearsal vehicle; the paid silent.link profile is
  not.
- Do not delete an operational profile. Disable it, verify the replacement
  registers, then decide.
- Keep EID, ICCID, activation codes and tokens in OpenBao or the private
  operator registry.

## Provider-first diagnosis

Before concluding “modem wedge”, check the provider:

- silent.link: balance + registration heartbeat API (v1 `{imsi,token}`);
- nadanada: public by ICCID;
- APN and profile state (`profile list`, QCCID, CEREG);
- only then the modem/USB path.

USSD balance (`*187#`) is not a reliable path: `+CME 30` was observed on both
Norwegian roaming partners.

## Troubleshooting

| Symptom | First check |
|---|---|
| `no functional AT port` | ports shuffled/reset; re-run `e750-esim port`; check `dmesg` for USB attach |
| lowercase-hex `ERROR` | `LPAC_APDU_AT_HEX=UPPER` must be set (wrapper does it) |
| TLS failure at `es9p_initiate_authentication` | use the bundled `ca-certificates-gsma.crt`; keep verify ON |
| `euicc_init` fails right after a profile op | settle, retry; do not reset into a tired modem |
| profile installed but no data | APN, `ifstatus wwan1`, QCCID, CEREG, provider balance |
| modem silent but ports present | DEFAULT-STOP; no more resets; pull artifacts; physical power button |

## Contributing back

After a hardware run, fill Appendix B of
`Amperstrand/conwrt/docs/MODEM-AS-READER-PLAYBOOK.md` and update:

- `models/glinet-gl-e750.json` — `2c7c:030b`, MBIM composition, AT port map,
  CSIM verified;
- `recipes/glinet/e750/notes.md` — modem section;
- `e750-repair/docs/E750-MODEM-DIAG.md` — any port/composition drift.

Species-level only; no unit identifiers.
