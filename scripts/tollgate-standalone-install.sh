#!/bin/sh
# Install the TollGate v0.6.0 offline bundle on the E750 (ON THE ROUTER).
#
#   sh tollgate-standalone-install.sh --i-understand \
#      --trust-mac <management-mac> \
#      --admin-password-file /root/tollgate-admin.pw \
#      --wifi-password-file /root/tollgate-wifi.pw
#
# WARNING: this exact layout was attempted on 2026-10-29 and rolled back.
# TollGate's upstream manager removed the existing STA/AP, the AP did not
# return, mint probes timed out, and the kernel killed processes under memory
# pressure on the 117 MB RAM. Do not run it again on this unit without a
# different topology (4G WAN + AP-only, or two radios). See
# docs/TOLLGATE-STANDALONE.md and docs/E750-TOLLGATE.md.
#
# The gate below is intentional. The script backs up the pre-change config and
# leaves a rollback script next to it.
set -eu

BUNDLE_URL="https://github.com/FreedomTechFeed/packages/releases/download/v0.6.0/tollgate-wrt-0.6.0-mips_24kc-ath79-nand-offline.tar.gz"
BUNDLE_SHA256="bc5338ab88e9f79678aa63fdea7da9cbbc7e1ad53338fa572c2ab654ed00be7e"
STAGE="/tmp/tgoffline"
BACKUP="/tmp/tollgate-backup"
BUNDLE=""
TRUST_MAC=""
ADMIN_PW=""
WIFI_PW=""
UNDERSTAND=0

usage() {
	cat <<'USAGE'
usage: tollgate-standalone-install.sh --i-understand --trust-mac MAC \
         --admin-password-file FILE --wifi-password-file FILE [--bundle FILE]

  --bundle FILE   use an already-downloaded offline bundle (default: download
                  the pinned v0.6.0 ath79-nand asset)
USAGE
}

while [ $# -gt 0 ]; do
	case "$1" in
	--i-understand) UNDERSTAND=1; shift ;;
	--trust-mac) TRUST_MAC="$2"; shift 2 ;;
	--admin-password-file) ADMIN_PW="$2"; shift 2 ;;
	--wifi-password-file) WIFI_PW="$2"; shift 2 ;;
	--bundle) BUNDLE="$2"; shift 2 ;;
	-h|--help) usage; exit 0 ;;
	*) usage >&2; echo "unknown argument: $1" >&2; exit 2 ;;
	esac
done

if [ "$UNDERSTAND" -ne 1 ]; then
	cat >&2 <<'REFUSE'
REFUSED: this layout is known unstable on the E750.
It installs TollGate over the single 2.4 GHz radio and its upstream manager
removes the STA/AP; the AP did not return and the device ran out of memory.
Use 4G WAN + AP-only or a two-radio unit, and re-read
docs/TOLLGATE-STANDALONE.md. Pass --i-understand only for a controlled test.
REFUSE
	exit 2
fi
[ -n "$TRUST_MAC" ] || { echo "--trust-mac is required" >&2; exit 2; }
[ -f "$ADMIN_PW" ] || { echo "missing admin password file" >&2; exit 2; }
[ -f "$WIFI_PW" ] || { echo "missing wifi password file" >&2; exit 2; }
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = "glinet,gl-e750" ] || {
	echo "this script is only for glinet,gl-e750" >&2
	exit 2
}

mkdir -p "$BACKUP"
cp /etc/config/network /etc/config/wireless /etc/config/firewall /etc/config/uhttpd "$BACKUP"/ 2>/dev/null || true
date -u +%Y-%m-%dT%H:%M:%SZ > "$BACKUP/timestamp"
echo "backup: $BACKUP"

if [ -z "$BUNDLE" ]; then
	BUNDLE="/tmp/tg.tar.gz"
	curl -fL --max-time 300 -o "$BUNDLE" "$BUNDLE_URL"
fi
printf '%s  %s\n' "$BUNDLE_SHA256" "$BUNDLE" | sha256sum -c -

rm -rf "$STAGE"
mkdir -p "$STAGE"
tar -xzf "$BUNDLE" -C "$STAGE"
( cd "$STAGE" && sha256sum -c MANIFEST.sha256 >/dev/null )

sed "s/__TRUST_MAC__/$TRUST_MAC/" "$STAGE/templates/99z-mgmt-keepalive" > "$STAGE/99z-mgmt-keepalive"
cp "$ADMIN_PW" "$STAGE/tollgate-admin-password"
cp "$WIFI_PW" "$STAGE/tollgate-wifi-password"
chmod 600 "$STAGE/tollgate-admin-password" "$STAGE/tollgate-wifi-password"

echo "installing; the network will restart and SSH may drop."
echo "run under setsid/nohup and watch /tmp/tollgate-install.log if detached:"
echo "  setsid sh tollgate-standalone-install.sh ... > /tmp/tollgate-install.log 2>&1 &"
( cd "$STAGE" && sh install-router.sh --staging-dir "$STAGE" --trust-mac "$TRUST_MAC" )

echo
echo "rollback: sh tollgate-standalone-rollback.sh (then reboot)"
