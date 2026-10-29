#!/bin/sh
# Read-only 4G/LTE diagnostics for the E750. Safe to run while the modem is up.
# It deliberately does not query the IMSI/ICCID (SIM identity).
set -eu

AT_PORT="${AT_PORT:-/dev/ttyUSB3}"
WDM="${WDM:-/dev/cdc-wdm0}"

echo "== 4G interface =="
ifstatus wwan1 2>/dev/null || true

echo "== MBIM =="
for c in caps pinstate registration; do
	echo "-- $c"
	umbim -d "$WDM" -t 5 "$c" 2>&1 || true
done

echo "== AT =="
if command -v stty >/dev/null 2>&1; then
	stty -F "$AT_PORT" 115200 raw -echo -crtscts 2>/dev/null || true
else
	echo "stty missing; install coreutils-stty"
fi

run_at() {
	( cat "$AT_PORT" > /tmp/e750-at.out ) &
	pid=$!
	sleep 1
	printf '%s\r' "$1" > "$AT_PORT"
	sleep 2
	kill "$pid" 2>/dev/null || true
	tr -d '\r' < /tmp/e750-at.out | tail -12
}

for c in 'AT' 'ATI' 'AT+CPIN?' 'AT+COPS?' 'AT+QCSQ' 'AT+QENG="servingcell"' 'AT+CGDCONT?'; do
	echo "-- $c"
	run_at "$c" || true
done

echo "== data =="
for f in rx_bytes tx_bytes; do
	printf 'wwan0_%s=' "$f"
	cat "/sys/class/net/wwan0/statistics/$f" 2>/dev/null || echo n/a
done
