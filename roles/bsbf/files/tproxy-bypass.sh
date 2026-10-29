#!/bin/sh
# Keep the captive-portal bridge out of the BSBF tproxy. Portal clients use the
# normal WAN/NAT path; the management LAN keeps the BSBF path.
LIST=/etc/bsbf/tproxy-bypass-interfaces
[ -f "$LIST" ] || exit 0
for i in $(cat "$LIST"); do
	[ -n "$i" ] || continue
	if nft list chain ip bsbf_bonding prerouting_mangle 2>/dev/null \
		| grep -q "iifname \"$i\" return"; then
		continue
	fi
	nft insert rule ip bsbf_bonding prerouting_mangle iifname "$i" return 2>/dev/null || true
done
