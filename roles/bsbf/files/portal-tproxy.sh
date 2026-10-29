#!/bin/sh
# Route authenticated captive-portal clients through the BSBF tproxy.
#
# nodogsplash marks authenticated clients 0x30000 in `ip mangle` at priority
# mangle (-150). This table hooks at -140, so it only ever sees traffic that
# nodogsplash has already classified as authenticated. Pre-auth traffic keeps
# its 0x10000/0x20000 mark, is never tproxied, and is rejected by ndsNET.
#
# The mark becomes 0x30001 (0x30000 | 0x1); the masked ip rule below sends it
# to the BSBF local table. DNS and local destinations stay out of the tunnel so
# dnsmasq and the portal services (2050/2051/2121) keep working.

set -e

IFACE="${BSBF_PORTAL_IFACE:-br-portal}"
NETWORK="${BSBF_PORTAL_NETWORK:-10.0.0.0/24}"
PRIORITY="${BSBF_PORTAL_PRIORITY:--140}"

nft list table ip bsbf_portal >/dev/null 2>&1 && nft delete table ip bsbf_portal
nft -f - <<NFT
table ip bsbf_portal {
	chain prerouting {
		type filter hook prerouting priority $PRIORITY; policy accept;
		iifname "$IFACE" ip daddr != $NETWORK meta mark & 0x00030000 == 0x00030000 fib daddr type != local meta l4proto { tcp, udp } th dport != 53 counter tproxy to :12345 meta mark set 0x00030001
	}
}
NFT

if ! ip rule show | grep -q 'fwmark 0x1/0x1'; then
	ip rule add fwmark 0x1/0x1 lookup 1 priority 100
fi
