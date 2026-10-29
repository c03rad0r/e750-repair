#!/bin/sh
# Append one path-quality sample to /etc/e750/metrics.csv.
#
# Read-only: it never changes the MPTCP mode. The link-mode controller reads
# this CSV to decide between standby and aggregate.
set -u

CSV="${E750_METRICS_CSV:-/etc/e750/metrics.csv}"
mkdir -p "$(dirname "$CSV")"
[ -f "$CSV" ] || echo "ts,mode,sta_up,wwan_up,sta_rx,wwan_rx,sta_rtt,wwan_rtt,sta_loss,wwan_loss,load1,cpu_idle,conntrack,sta_signal,wwan_signal,decision,reason" > "$CSV"

ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
mode=$(cat /etc/e750/mode 2>/dev/null || echo standby)

if [ -d /sys/class/net/phy1-sta0 ]; then sta_up=1; else sta_up=0; fi
if [ -d /sys/class/net/wwan0 ]; then wwan_up=1; else wwan_up=0; fi

sta_rx=$(cat /sys/class/net/phy1-sta0/statistics/rx_bytes 2>/dev/null || echo 0)
wwan_rx=$(cat /sys/class/net/wwan0/statistics/rx_bytes 2>/dev/null || echo 0)

probe() {
	iface="$1"
	out=$(ping -c 3 -W 2 -I "$iface" 1.1.1.1 2>/dev/null)
	loss=$(echo "$out" | sed -n 's/.*, \([0-9]*\)% packet loss.*/\1/p' | head -1)
	rtt=$(echo "$out" | tail -1 | awk -F'/' '/round-trip/ {print $5}' | cut -d' ' -f1)
	[ -n "$loss" ] || loss=100
	[ -n "$rtt" ] || rtt=999
	echo "$rtt $loss"
}

set -- $(probe phy1-sta0); sta_rtt="$1"; sta_loss="$2"
set -- $(probe wwan0); wwan_rtt="$1"; wwan_loss="$2"

load1=$(cut -d' ' -f1 /proc/loadavg 2>/dev/null || echo 0)
cpu_idle=$(top -bn1 2>/dev/null | awk '/CPU:/ {for(i=1;i<=NF;i++) if($i=="idle") {gsub("%","",$(i-1)); print $(i-1)}}' | head -1)
[ -n "$cpu_idle" ] || cpu_idle=100
conntrack=$(wc -l < /proc/net/nf_conntrack 2>/dev/null || echo 0)
sta_signal=$(iw dev phy1-sta0 link 2>/dev/null | sed -n 's/.*signal: \([-0-9]*\).*/\1/p' | head -1)
[ -n "$sta_signal" ] || sta_signal=0
wwan_signal="-"

echo "$ts,$mode,$sta_up,$wwan_up,$sta_rx,$wwan_rx,$sta_rtt,$wwan_rtt,$sta_loss,$wwan_loss,$load1,$cpu_idle,$conntrack,$sta_signal,$wwan_signal,," >> "$CSV"

# Keep a bounded history: header + last 5000 samples.
lines=$(wc -l < "$CSV")
if [ "$lines" -gt 5001 ]; then
	head -1 "$CSV" > "$CSV.tmp"
	tail -n 5000 "$CSV" >> "$CSV.tmp"
	mv "$CSV.tmp" "$CSV"
fi
