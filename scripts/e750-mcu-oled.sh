#!/bin/sh
# Drive the GL-E750 OLED through the on-board MCU.
#
# The MCU reads one JSON object per line on /dev/ttyS0 at 115200. There is no
# free-text field: the display renders predefined pages from these keys, so
# "TollGate" appears via the SSID and the link mode via method_nw.
#
#   e750-mcu-oled.sh            # send one update
#   e750-mcu-oled.sh --loop 30  # send every 30 s (cron uses this)
set -u
DEV=/dev/ttyS0
MODE=$(cat /etc/e750/mode 2>/dev/null || echo standby)
SSID=$(uci -q get wireless.default_radio1.ssid 2>/dev/null || echo TollGate-E750)
CLIENTS=$(iw dev phy1-ap0 station dump 2>/dev/null | grep -c '^Station' || echo 0)
CLOCK=$(date +%H:%M)
UP5G=$(uci -q get wireless.default_radio1.disabled 2>/dev/null || echo 0)
[ "$UP5G" = "0" ] && UP5G=1 || UP5G=0

send() {
	JSON='{ "ssid_5g": "'"$SSID"'", "up_5g": "'"$UP5G"'", "key_5g": "", "ssid": "'"$SSID"'", "up": "0", "work_mode": "Router", "lan_ip": "192.168.8.1", "method_nw": "repeater|'"$MODE"'", "clients": "'"$CLIENTS"'", "clock": "'"$CLOCK"'", "mcu_status": "1" }'
	stty -F "$DEV" 115200 raw -echo -crtscts 2>/dev/null || true
	printf '%s\n' "$JSON" > "$DEV"
}

case "${1:-}" in
--loop)
	interval="${2:-30}"
	while :; do
		send
		sleep "$interval"
	done
	;;
*)
	send
	;;
esac
