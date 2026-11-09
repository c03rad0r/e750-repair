#!/bin/sh
# Read-only 4G/LTE diagnostics for the E750. Safe to run while the modem is up.
# It deliberately does not query the IMSI/ICCID (SIM identity).
set -eu

AT_PORT="${AT_PORT:-auto}"
WDM="${WDM:-/dev/cdc-wdm0}"

echo "== 4G interface =="
ifstatus wwan1 2>/dev/null || true

echo "== MBIM =="
for c in caps pinstate registration; do
	echo "-- $c"
	umbim -d "$WDM" -t 5 "$c" 2>&1 || true
done

echo "== AT =="
if ! command -v stty >/dev/null 2>&1; then
	echo "stty missing; install coreutils-stty"
	AT_PORT=""
fi

probe_cpin() {
	# Return 0 only for a functional AT parser (CPIN or CME), never bare OK.
	tty="$1"
	out=$(mktemp /tmp/e750-diag-at.XXXXXX) || return 1
	stty -F "$tty" 115200 raw -echo -crtscts 2>/dev/null || {
		rm -f "$out"
		return 1
	}
	( cat "$tty" >"$out" ) &
	reader=$!
	sleep 1
	printf 'AT+CPIN?\r' >"$tty" 2>/dev/null || {
		kill "$reader" 2>/dev/null || true
		rm -f "$out"
		return 1
	}
	sleep 2
	kill "$reader" 2>/dev/null || true
	wait "$reader" 2>/dev/null || true
	if grep -qE '\+CPIN:|CME ERROR' "$out"; then
		rm -f "$out"
		return 0
	fi
	rm -f "$out"
	return 1
}

detect_at_port() {
	for tty in /dev/ttyUSB*; do
		[ -e "$tty" ] || continue
		if probe_cpin "$tty"; then
			echo "$tty"
			return 0
		fi
	done
	return 1
}

if [ -n "$AT_PORT" ] && [ "$AT_PORT" = "auto" ]; then
	AT_PORT=$(detect_at_port || true)
fi
if [ -z "$AT_PORT" ]; then
	echo "no functional AT port found (AT+CPIN? probe failed)"
else
	echo "using $AT_PORT"
	stty -F "$AT_PORT" 115200 raw -echo -crtscts 2>/dev/null || true
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

if [ -n "$AT_PORT" ]; then
	for c in 'AT' 'ATI' 'AT+CPIN?' 'AT+COPS?' 'AT+QCSQ' 'AT+QENG="servingcell"' 'AT+CGDCONT?'; do
		echo "-- $c"
		run_at "$c" || true
	done
fi

echo "== data =="
for f in rx_bytes tx_bytes; do
	printf 'wwan0_%s=' "$f"
	cat "/sys/class/net/wwan0/statistics/$f" 2>/dev/null || echo n/a
done
