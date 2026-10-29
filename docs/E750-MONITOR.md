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

Use the controller-side harness (run on x280). It is read-only and records one
line per sample: UTC time, `rc=0` or the failing checks, or `ssh_failed`.

```bash
ssh x280
cd ~/e750-repair
# 288 samples over 24 h, one every 5 minutes
setsid nohup sh scripts/e750-soak.sh 24 300 \
  > ~/e750-soak/run.out 2>&1 < /dev/null &
```

The harness writes `~/e750-soak/<timestamp>.log` and ends with:

```text
# e750 soak end <time> ok=<n> fail=<n> total=<n>
```

A short self-test (no effect on the device) is:

```bash
SAMPLES=2 INTERVAL=1 OUT=/tmp/soak-test.log sh scripts/e750-soak.sh 0 1
```

### Started (2026-10-29)

```text
# e750 soak start 2026-10-29T10:15:23Z samples=288 interval=300s
2026-10-29T10:15:23Z rc=0
```

Process and the first sample are recorded in
`evidence/soak/2026-10-29_start.txt`; the live log is
`~/e750-soak/20261029T101523Z.log` on x280. The device-side cron log
(`/tmp/e750-health.log`) is the independent view.

Review with:

```sh
grep -c 'rc=0' ~/e750-soak/20261029T101523Z.log     # on x280
grep -c 'FAIL\|ssh_failed' ~/e750-soak/20261029T101523Z.log
```

Acceptance: no unexplained `FAIL`/`ssh_failed`, egress stays the BSBF server,
both WANs stay up, and a deliberate STA-drop failover still recovers. Do not run
the soak during a firmware experiment.

Stop it early with:

```sh
pkill -f 'e750-soak.sh 24 300'
```

## Scope and caveats

- 5 GHz absence is a `WARN`, not a failure (known QCA9887 repair issue).
- The 4G rate is not part of the pass/fail; only link-up is checked.
- `ifstatus`/`nft`/`curl` must exist on the device; the image recipe includes
  them and `curl` is already present.
- The monitor does not page anyone; it logs and uses syslog. Add an external
  alert (e.g. the fleet monitor) by tailing `e750-health` syslog messages.
