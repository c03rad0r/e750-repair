#!/bin/sh
# Best-effort rollback of the TollGate standalone attempt (ON THE ROUTER).
# Restores the config backup if present, stops/disables the services, removes
# the TollGate uhttpd instances and nft includes. Reboot afterwards.
set -u

BACKUP="${BACKUP:-/tmp/tollgate-backup}"

for s in tollgate-wrt nodogsplash; do
	[ -x "/etc/init.d/$s" ] && /etc/init.d/$s stop 2>/dev/null
	[ -x "/etc/init.d/$s" ] && /etc/init.d/$s disable 2>/dev/null
done
killall tollgate-wrt nodogsplash 2>/dev/null || true
for p in $(ps w | grep -E '/www/tollgate|/etc/tollgate' | grep -v grep | awk '{print $1}'); do
	kill "$p" 2>/dev/null || true
done

if [ -f "$BACKUP/network" ]; then
	cp "$BACKUP/network" /etc/config/network
	cp "$BACKUP/wireless" /etc/config/wireless
	cp "$BACKUP/firewall" /etc/config/firewall
	cp "$BACKUP/uhttpd" /etc/config/uhttpd 2>/dev/null || true
	echo "restored config from $BACKUP"
else
	echo "no config backup at $BACKUP; leaving the current config" >&2
fi

uci -q delete uhttpd.portal
uci -q delete uhttpd.trusted
uci -q delete uhttpd.admin
uci -q delete uhttpd.main.cert
uci -q delete uhttpd.main.key
uci -q delete uhttpd.main.listen_http
uci -q delete uhttpd.main.listen_https
uci set uhttpd.main.listen_http='0.0.0.0:80'
uci add_list uhttpd.main.listen_http='[::]:80'
uci set uhttpd.main.listen_https='0.0.0.0:443'
uci add_list uhttpd.main.listen_https='[::]:443'
uci commit uhttpd

rm -f /etc/nftables.d/20-nds-enforce.nft \
	/etc/nftables.d/30-backend-firewall.nft \
	/etc/nftables.d/31-admin-board-not-guest-reachable.nft \
	/etc/nftables.d/32-luci-not-guest-reachable.nft
/etc/init.d/firewall restart
/etc/init.d/uhttpd restart

echo "rollback done; reboot and re-apply the BSBF client playbook."
