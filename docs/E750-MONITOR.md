# E750 health monitoring and 24 h soak

The E750 runs a 5-minute critical health check. It is installed by
`playbook-e750-monitor.yml` and is read-only: it inspects BSBF, MPTCP
endpoints, tproxy, both WANs, and the server egress; it does not change them.

## What is installed

| Path | Purpose |
|---|---|
| `/usr/bin/e750-health` | the health check (same as `scripts/e750-health.sh`) |
| `/usr/bin/e750-health-cron.sh` | timestamped wrapper, log rotation, syslog on failure |
| `/etc/crontabs/root` | one line: `*/5 * * * * /usr/bin/e750-health-cron.sh` |
| `/tmp/e750-health.log` | last 500 lines; `OK` heartbeat or a `FAIL` block |

Cron is enabled with `/etc/init.d/cron enable` and restarted. The log is in
volatile `/tmp` so the check never wears the NAND; the 24 h soak only needs the
current boot. Failures are also sent to syslog:

```sh
logread | grep e750-health
```

## Install and sample

```bash
ssh x280
cd ~/e750-repair
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-e750-monitor.yml
```

The playbook prints one sample line, for example:

```text
2026-10-29T10:20:01+0000 OK
```

A failure prints `FAIL` and the failing checks (BSBF status, a missing endpoint,
tproxy, a down WAN, or a wrong egress).

## Live result (2026-10-29)

The role installed both scripts (non-empty), added the crontab line, and
restarted crond (PID visible). Two manual cron samples:

```text
2026-10-29T10:11:26+0000 OK
2026-10-29T10:11:29+0000 OK
```

The full report still shows `WARN 5 GHz radio absent`, `OK egress
23.182.128.219`, and the cleaned WAN zone `wwan wwan1`. Evidence:
`evidence/monitor/2026-10-29_cron-health.txt`.

### Quiet-mode gotcha (fixed)

The first install reported false `FAIL STA endpoint missing` /
`FAIL 4G backup endpoint missing` in cron mode. Cause: `ok()`/`warn()` ended
with `[ "$QUIET" -eq 0 ] && printf ...`, which returns 1 in quiet mode, so the
`check && ok || bad` chains inverted. Both helpers now `return 0` explicitly;
the contract test asserts it. The direct (non-quiet) check was always correct.

## Manual check

```sh
ssh x280 'ssh -i ~/.ssh/id_ed25519 root@192.168.8.1 \
  "/usr/bin/e750-health; echo rc=$?"'
```

`--quiet` prints only failures and the final `RESULT FAIL`; cron uses it.

## 24 h soak

Start it after the monitor is installed and the serial adapter is stable:

```sh
# on x280, collect one sample per minute for 24 h without touching the router
mkdir -p ~/e750-soak
nohup sh -c 'for i in $(seq 1440); do
  date -u +%Y-%m-%dT%H:%M:%SZ >> ~/e750-soak/soak.log
  ssh -o BatchMode=yes -i ~/.ssh/id_ed25519 root@192.168.8.1 \
    "/usr/bin/e750-health --quiet; echo rc=\$?" >> ~/e750-soak/soak.log 2>&1
  sleep 60
done' >/dev/null 2>&1 &
```

The device-side cron log is enough for a pass/fail timeline; the controller-side
loop adds an independent view (SSH reachability and egress). Review with:

```sh
grep -c ' OK$' /tmp/e750-health.log        # on the E750
grep -c 'FAIL' /tmp/e750-health.log        # on the E750
grep -c 'rc=0' ~/e750-soak/soak.log        # on x280
```

Acceptance: no unexplained `FAIL`, egress stays the BSBF server, both WANs stay
up, and a deliberate STA-drop failover still recovers. Do not run the soak
during a firmware experiment.

## Scope and caveats

- 5 GHz absence is a `WARN`, not a failure (known QCA9887 repair issue).
- The 4G rate is not part of the pass/fail; only link-up is checked.
- `ifstatus`/`nft`/`curl` must exist on the device; the image recipe includes
  them and `curl` is already present.
- The monitor does not page anyone; it logs and uses syslog. Add an external
  alert (e.g. the fleet monitor) by tailing `e750-health` syslog messages.
