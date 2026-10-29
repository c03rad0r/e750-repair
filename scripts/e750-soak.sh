#!/bin/sh
# Controller-side soak harness for the E750 (run on x280).
#
#   e750-soak.sh [hours] [interval_seconds]
#   e750-soak.sh 24 300      # default: 288 samples over 24 h
#   SAMPLES=2 INTERVAL=1 e750-soak.sh 0 1   # short self-test
#
# Each sample records UTC time, SSH reachability, the device health exit code,
# and the failure text. The log is append-only and ends with a summary line.
# It does not change the router; it only runs /usr/bin/e750-health --quiet.
set -u

HOURS="${1:-24}"
INTERVAL="${2:-300}"
OUT="${OUT:-$HOME/e750-soak/$(date -u +%Y%m%dT%H%M%SZ).log}"
HOST="${E750_HOST:-192.168.8.1}"
KEY="${E750_KEY:-$HOME/.ssh/id_ed25519}"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new -i $KEY root@$HOST"

if [ -n "${SAMPLES:-}" ]; then
	total="$SAMPLES"
else
	total=$(( HOURS * 3600 / INTERVAL ))
	[ "$total" -lt 1 ] && total=1
fi

mkdir -p "$(dirname "$OUT")"
{
	echo "# e750 soak start $(date -u +%Y-%m-%dT%H:%M:%SZ) samples=$total interval=${INTERVAL}s"
} >> "$OUT"

ok=0
fail=0
i=0
while [ "$i" -lt "$total" ]; do
	i=$((i + 1))
	ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
	if out=$($SSH '/usr/bin/e750-health --quiet; echo rc=$?' 2>&1); then
		rc=$(printf '%s\n' "$out" | sed -n 's/^rc=//p' | tail -1)
		if [ "${rc:-1}" = "0" ]; then
			echo "$ts rc=0" >> "$OUT"
			ok=$((ok + 1))
		else
			echo "$ts rc=${rc:-?} $(printf '%s' "$out" | tr '\n' ';')" >> "$OUT"
			fail=$((fail + 1))
		fi
	else
		echo "$ts ssh_failed $(printf '%s' "$out" | tr '\n' ';')" >> "$OUT"
		fail=$((fail + 1))
	fi
	[ "$i" -lt "$total" ] && sleep "$INTERVAL"
done

{
	echo "# e750 soak end $(date -u +%Y-%m-%dT%H:%M:%SZ) ok=$ok fail=$fail total=$total"
} >> "$OUT"

echo "soak log: $OUT (ok=$ok fail=$fail)"
[ "$fail" -eq 0 ]
