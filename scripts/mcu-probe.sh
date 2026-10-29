#!/bin/sh
# Probe the GL-E750 MCU on /dev/ttyS0 without changing router state.
#
# The MCU shares the console UART (GL's e750-mcu opens /dev/ttyS0 at 115200).
# The console login (`askfirst`) also reads that port, so a reply can be stolen.
# This script only sends documented, well-formed JSON queries and prints what
# comes back. It does not write any UCI config and does not start a daemon.
#
#   mcu-probe.sh            # leave the console login alone
#   mcu-probe.sh --force    # stop askfirst for the probe, then restore it
#
# Exit 0 only if the MCU answered. A silent port is a valid result but not a
# success; do not treat it as "the MCU works".
set -u

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1
DEV="${MCU_DEV:-/dev/ttyS0}"
BAUD="${MCU_BAUD:-115200}"
OUT="${MCU_OUT:-/tmp/e750-mcu-probe.out}"

if [ ! -c "$DEV" ]; then
	echo "no such character device: $DEV" >&2
	exit 2
fi

pid=""
if [ "$FORCE" -eq 1 ]; then
	pid=$(ps w | grep '[a]skfirst' | awk '{print $1}' | head -1)
	if [ -n "$pid" ]; then
		kill "$pid" 2>/dev/null || true
		sleep 1
	fi
fi

# Raw 8N1, no echo/flow control; fall back to the requested baud if stty fails.
stty -F "$DEV" "$BAUD" raw -echo -crtscts 2>/dev/null || true

probe() {
	query="$1"
	label="$2"
	: > "$OUT"
	cat "$DEV" > "$OUT" &
	reader=$!
	sleep 1
	printf '%s\n' "$query" > "$DEV"
	sleep 2
	kill "$reader" 2>/dev/null || true
	wait "$reader" 2>/dev/null || true
	echo "== $label: $query"
	echo "bytes=$(wc -c < "$OUT")"
	hexdump -C "$OUT" | head -5
}

probe '{"version":"1"}' version
probe '{"mcu_status":"1"}' status

if [ "$FORCE" -eq 1 ]; then
	# Restore the console login so serial recovery is not left without one.
	setsid /sbin/askfirst /usr/libexec/login.sh <"$DEV" >"$DEV" 2>&1 &
	sleep 1
	ps w | grep '[a]skfirst' >/dev/null || echo "warning: askfirst not restored" >&2
fi

bytes=$(wc -c < "$OUT")
if [ "$bytes" -eq 0 ]; then
	echo "no MCU reply on $DEV at $BAUD" >&2
	exit 1
fi

exit 0
