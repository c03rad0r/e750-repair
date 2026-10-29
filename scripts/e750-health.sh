#!/bin/sh
# Critical health check for the E750's BSBF + WANs. Run on the E750.
# Exit 0 only if BSBF, endpoints, tproxy, both WANs, and the server egress are
# healthy. 5 GHz is a known-dead warning, not a failure.
set -u

SERVER_IP="${SERVER_IP:-23.182.128.219}"
fail=0

ok() { printf 'OK   %s\n' "$1"; }
bad() { printf 'FAIL %s\n' "$1"; fail=1; }
warn() { printf 'WARN %s\n' "$1"; }

echo "== BSBF =="
status=$(bsbf-bonding --status 2>&1 || true)
if [ "$status" = "enabled" ]; then ok "bsbf-bonding enabled"; else bad "bsbf-bonding=${status:-missing}"; fi

echo "== MPTCP endpoints =="
ep=$(ip mp e 2>&1 || true)
printf '%s\n' "$ep"
printf '%s\n' "$ep" | grep -q 'dev phy1-sta0' && ok "STA endpoint" || bad "STA endpoint missing"
printf '%s\n' "$ep" | grep -q 'backup dev wwan0' && ok "4G backup endpoint" || bad "4G backup endpoint missing"

echo "== nft tproxy =="
if nft list table ip bsbf_bonding 2>/dev/null | grep -q tproxy; then
	ok "bsbf tproxy table"
else
	bad "bsbf tproxy table missing"
fi

echo "== WANs =="
if ifstatus wwan1 2>/dev/null | grep -q '"up": true'; then ok "4G wwan1 up"; else bad "4G wwan1 down"; fi
if ifstatus wwan 2>/dev/null | grep -q '"up": true'; then ok "STA wwan up"; else bad "STA wwan down"; fi

echo "== egress =="
egress=$(curl -s --max-time 15 https://ifconfig.me 2>/dev/null || true)
if [ "$egress" = "$SERVER_IP" ]; then
	ok "egress $egress"
else
	bad "egress ${egress:-none} (expected $SERVER_IP)"
fi

echo "== 5 GHz =="
if wifi status 2>/dev/null | grep -q '"radio1"'; then
	ok "5 GHz radio present"
else
	warn "5 GHz radio absent (known QCA9887 repair issue)"
fi

echo "== 4G data =="
for f in rx_bytes tx_bytes; do
	printf 'wwan0_%s=%s\n' "$f" "$(cat /sys/class/net/wwan0/statistics/$f 2>/dev/null || echo n/a)"
done

echo "== WAN firewall zone =="
uci show firewall 2>/dev/null | grep -E '@zone\[[0-9]+\]\.(name|network)' | head

if [ "$fail" -eq 0 ]; then
	echo "RESULT OK"
else
	echo "RESULT FAIL"
fi
exit "$fail"
