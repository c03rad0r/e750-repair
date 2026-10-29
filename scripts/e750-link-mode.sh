#!/bin/sh
# Decide between standby (wwan0 backup) and aggregate (wwan0 active) and log it.
#
#   e750-link-mode.sh tick     # sample + evaluate (cron calls this)
#   e750-link-mode.sh status   # print the current decision and state
#   e750-link-mode.sh force standby|aggregate
#
# Default is observe-only: it records the proposed mode but does not change the
# MPTCP endpoint. Set e750.linkmode.enabled=1 to let it apply.
set -u

CSV="${E750_METRICS_CSV:-/etc/e750/metrics.csv}"
STATE=/etc/e750/mode.state
MODE=/etc/e750/mode
BACKUP=/etc/bsbf/bsbf-mptcp-subflow-backup
BONDJSON=/etc/tollgate/tollgate-captive-portal-site/bond.json

getopt() {
	uci -q get "e750_linkmode.settings.$1" 2>/dev/null || echo "$2"
}

now=$(date +%s)

write_mode() {
	printf '%s' "$1" > "$MODE.tmp" && mv "$MODE.tmp" "$MODE"
	printf '%s %s' "$1" "$now" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
}

bond_json() {
	[ -d "$(dirname "$BONDJSON")" ] || return 0
	printf '{"mode":"%s","uplinks":2,"reason":"%s","ts":"%s"}\n' \
		"$1" "$2" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$BONDJSON.tmp" &&
		mv "$BONDJSON.tmp" "$BONDJSON"
}

apply() {
	case "$1" in
	aggregate)
		: > "$BACKUP.tmp" && mv "$BACKUP.tmp" "$BACKUP"
		bsbf-mptcp-helper nobackup wwan0 2>/dev/null || true
		;;
	standby)
		printf 'wwan0\n' > "$BACKUP.tmp" && mv "$BACKUP.tmp" "$BACKUP"
		bsbf-mptcp-helper backup wwan0 2>/dev/null || true
		;;
	esac
	write_mode "$1"
}

avg_last() {
	field="$1"; n="$2"
	tail -n "$n" "$CSV" 2>/dev/null | awk -F, -v f="$field" '{s+=$f; c++} END {if(c) printf "%.1f", s/c; else print 0}'
}

tick() {
	/usr/bin/e750-path-metrics.sh || true

	enabled=$(getopt enabled 0)
	observe=$(getopt observe_only 1)
	rtt_enter=$(getopt rtt_ratio_enter 1.5)
	rtt_exit=$(getopt rtt_ratio_exit 2.0)
	loss_max=$(getopt loss_max 3)
	cpu_min=$(getopt cpu_idle_min 30)
	dwell=$(getopt dwell_seconds 1800)
	window=$(getopt window 5)

	sta_rtt=$(avg_last 7 "$window")
	wwan_rtt=$(avg_last 8 "$window")
	sta_loss=$(avg_last 9 "$window")
	wwan_loss=$(avg_last 10 "$window")
	cpu_idle=$(avg_last 12 "$window")

	ratio=$(awk -v s="$sta_rtt" -v w="$wwan_rtt" 'BEGIN {if (s > 0 && s < 999) printf "%.2f", w/s; else print 99}')

	current=$(cat "$MODE" 2>/dev/null || echo standby)
	since=$(cut -d' ' -f2 "$STATE" 2>/dev/null || echo 0)
	age=$((now - since))

	proposed="$current"
	reason="stable"

	if [ "$sta_loss" -gt 50 ] 2>/dev/null; then
		proposed="standby"
		reason="sta loss ${sta_loss}%"
	elif [ "$current" = "standby" ]; then
		if awk -v r="$ratio" -v e="$rtt_enter" 'BEGIN {exit !(r < e)}' \
		   && [ "${wwan_loss%.*}" -lt "${loss_max%.*}" ] 2>/dev/null \
		   && [ "${cpu_idle%.*}" -gt 30 ] 2>/dev/null; then
			proposed="aggregate"
			reason="rtt ratio $ratio, loss ${wwan_loss}%, idle ${cpu_idle}%"
		fi
	else
		if awk -v r="$ratio" -v e="$rtt_exit" 'BEGIN {exit !(r > e)}' \
		   || [ "${wwan_loss%.*}" -ge "${loss_max%.*}" ] 2>/dev/null \
		   || [ "${cpu_idle%.*}" -lt 15 ] 2>/dev/null; then
			proposed="standby"
			reason="rtt ratio $ratio, loss ${wwan_loss}%, idle ${cpu_idle}%"
		fi
	fi

	if [ "$proposed" != "$current" ] && [ "$age" -lt "$dwell" ]; then
		reason="dwell ${age}s/${dwell}s ($reason)"
		proposed="$current"
	fi

	if [ "$enabled" = "1" ] && [ "$observe" != "1" ]; then
		if [ "$proposed" != "$current" ]; then
			apply "$proposed"
			logger -t e750-link-mode "applied $proposed: $reason"
		fi
	else
		logger -t e750-link-mode "observe: current=$current proposed=$proposed ratio=$ratio ($reason)"
	fi

	bond_json "$(cat "$MODE" 2>/dev/null || echo standby)" "$reason"
}

case "${1:-tick}" in
tick) tick ;;
status)
	echo "mode=$(cat "$MODE" 2>/dev/null || echo standby)"
	echo "state=$(cat "$STATE" 2>/dev/null || echo 'standby 0')"
	echo "enabled=$(getopt enabled 0) observe_only=$(getopt observe_only 1)"
	tail -n 3 "$CSV" 2>/dev/null
	;;
force)
	apply "${2:?usage: force standby|aggregate}"
	logger -t e750-link-mode "forced ${2}"
	;;
*)
	echo "usage: $0 tick|status|force standby|aggregate" >&2
	exit 1
	;;
esac
