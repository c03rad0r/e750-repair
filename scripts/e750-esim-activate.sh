#!/bin/sh
# Host-side orchestrator for the E750 9eSIM activation.
#
# Run this on the operator host that can SSH to the E750 (x280 on the bench),
# after the lpac stack is installed by playbook-e750-esim.yml.
#
# Safety:
#   * the read-only gate runs before any write
#   * the paid step requires --confirm-paid, a 0600 LPA file, and a prior
#     successful free rehearsal marker
#   * the LPA is read into the shell and sent to the E750 over stdin; it is
#     never placed in a local process argument, log line, or console output
#   * no modem reset is issued after a profile operation
#
# Usage:
#   e750-esim-activate.sh --gate
#   e750-esim-activate.sh --rehearsal
#   e750-esim-activate.sh --paid --lpa-file /run/secrets/silentlink.lpa \
#     --confirm-paid
#   e750-esim-activate.sh --verify
set -eu
umask 077

HOST=${E750_HOST:-192.168.8.1}
USER=${E750_USER:-root}
KEY=${E750_SSH_KEY:-$HOME/.ssh/id_ed25519}
SSH_OPTS=${E750_SSH_OPTS:--o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new}
WWAN=${E750_ESIM_WWAN:-wwan1}
APN=${E750_ESIM_APN:-internet}
STATE_DIR=${E750_ESIM_STATE_DIR:-$HOME/.local/state/e750-esim}
LOG_DIR=$STATE_DIR/logs
# shellcheck disable=SC2016  # $ is part of the LPA syntax
REHEARSAL_LPA='LPA:1$rsp.truphone.com$QRF-SPEEDTEST'
TS=$(date -u +%Y%m%dT%H%M%SZ)-$$
ACTION=
LPA=
LPA_FILE=
CONFIRM_PAID=0
ICCID=
DOWNLOAD_LOG=

usage() {
	cat <<'EOF'
usage: e750-esim-activate.sh <action> [options]

actions:
  --gate        read-only chip info / profile list / notification list
  --rehearsal   gate + free Speedtest profile + APN + verify
  --paid        gate + paid silent.link LPA + APN + verify
  --verify      re-check the interface, APN, profiles and notifications

options:
  --lpa-file PATH   paid LPA file (mode 0600), or '-' for stdin
  --confirm-paid    explicit owner GO for the paid step
  --iccid ICCID     override the ICCID to enable after download
  --host HOST       E750 address (default 192.168.8.1)
  --user USER       SSH user (default root)
  --key PATH        SSH private key (default ~/.ssh/id_ed25519)

The paid step requires a prior --rehearsal. The LPA is sent to the E750 over
stdin and is never printed or stored in this repository. Inspect your EID,
ICCID and activation code only in the private state directory or OpenBao.
EOF
}

die() {
	echo "e750-esim-activate: $*" >&2
	exit 1
}

ssh_run() {
	# shellcheck disable=SC2086
	ssh $SSH_OPTS -i "$KEY" "$USER@$HOST" "$@"
}

remote_board() {
	ssh_run 'cat /tmp/sysinfo/board_name' 2>/dev/null | tr -d '\r\n'
}

require_access() {
	board=$(remote_board || true)
	[ "$board" = "glinet,gl-e750" ] || {
		die "E750 not reachable as glinet,gl-e750 (got '${board:-no answer}'); restore LAN access first"
	}
	ssh_run 'test -x /usr/bin/e750-esim' >/dev/null 2>&1 || {
		die "e750-esim is not installed; run playbook-e750-esim.yml first"
	}
	ssh_run 'e750-esim port' >/dev/null 2>&1 || {
		die "no functional AT port (the e750-esim AT+CPIN? probe failed)"
	}
}

gate() {
	gate_log="$LOG_DIR/gate-$TS.log"
	if {
		echo "== board =="
		remote_board
		echo "== chip info =="
		ssh_run 'e750-esim chip info'
		echo "== profiles =="
		ssh_run 'e750-esim profile list'
		echo "== notifications =="
		ssh_run 'e750-esim notification list'
	} >"$gate_log" 2>&1; then
		:
	else
		die "read-only gate failed; inspect $gate_log privately"
	fi
	rows=$(grep -cE '^[[:space:]]*[0-9]{18,22}' "$gate_log" 2>/dev/null || true)
	echo "gate: OK; profile rows: ${rows:-unknown}; private log: $gate_log"
}

extract_iccid() {
	sed -n 's/.*[Ii][Cc][Cc][Ii][Dd][^0-9]*\([0-9][0-9]\{17,21\}\).*/\1/p' "$1" | tail -1
}

resolve_iccid() {
	if [ -n "$ICCID" ]; then
		return 0
	fi
	if [ -n "$DOWNLOAD_LOG" ] && [ -f "$DOWNLOAD_LOG" ]; then
		ICCID=$(extract_iccid "$DOWNLOAD_LOG" || true)
	fi
	if [ -z "$ICCID" ]; then
		list_log="$LOG_DIR/profile-list-$TS.log"
		ssh_run 'e750-esim profile list' >"$list_log" 2>&1 || true
		ICCID=$(extract_iccid "$list_log" || true)
	fi
	[ -n "$ICCID" ] || return 1
	return 0
}

download() {
	lpa=$1
	out="$LOG_DIR/download-$TS.log"
	# shellcheck disable=SC2016  # $LPA must expand on the E750, not locally
	if printf '%s\n' "$lpa" | ssh_run 'IFS= read -r LPA; e750-esim profile download -a "$LPA"'; then
		rc=0
	else
		rc=$?
	fi >"$out" 2>&1
	if [ "$rc" -ne 0 ]; then
		echo "download failed (rc=$rc); the activation code may be consumed. Do not retry blindly." >&2
		echo "private log: $out" >&2
		return 1
	fi
	echo "download: OK; private log: $out"
	DOWNLOAD_LOG=$out
	unset lpa
	return 0
}

enable_profile() {
	iccid=$1
	out="$LOG_DIR/enable-$TS.log"
	if ssh_run "e750-esim profile enable '$iccid' 1" >"$out" 2>&1; then
		echo "enable: OK (refreshFlag)"
		return 0
	fi
	echo "enable failed; settling 90 s and retrying once"
	sleep 90
	if ssh_run "e750-esim profile enable '$iccid' 1" >>"$out" 2>&1; then
		echo "enable: OK after settle"
		return 0
	fi
	echo "enable: FAILED; inspect $out privately" >&2
	return 1
}

set_apn() {
	case "$APN" in
	'' | *[!A-Za-z0-9._-]*) die "invalid APN '$APN'" ;;
	esac
	case "$WWAN" in
	'' | *[!A-Za-z0-9_]*) die "invalid WWAN '$WWAN'" ;;
	esac
	ssh_run "uci set network.$WWAN.apn='$APN'; uci commit network; ifup $WWAN" \
		>/dev/null 2>&1 || die "failed to set APN $APN on $WWAN"
	echo "apn: $WWAN -> $APN"
}

verify() {
	out="$LOG_DIR/verify-$TS.log"
	{
		echo "== ifstatus =="
		ssh_run "ifstatus $WWAN" || true
		echo "== apn =="
		ssh_run "uci -q get network.$WWAN.apn" || true
		echo "== profiles =="
		ssh_run 'e750-esim profile list' || true
		echo "== notifications =="
		ssh_run 'e750-esim notification list' || true
		echo "== modem diag =="
		ssh_run 'test -x /usr/bin/e750-modem-diag.sh && e750-modem-diag.sh' || true
	} >"$out" 2>&1
	up=false
	if ssh_run "ifstatus $WWAN" 2>/dev/null | grep -q '"up": true'; then
		up=true
	fi
	apn_now=$(ssh_run "uci -q get network.$WWAN.apn" 2>/dev/null | tr -d '\r\n' || true)
	echo "verify: interface=$WWAN up=$up apn=${apn_now:-?}; private log: $out"
}

mark() {
	mkdir -p "$STATE_DIR"
	date -u +%Y-%m-%dT%H:%M:%SZ >"$STATE_DIR/$1"
	chmod 600 "$STATE_DIR/$1"
}

check_paid() {
	[ "$CONFIRM_PAID" = "1" ] || die "paid mode requires --confirm-paid (owner GO)"
	[ -n "$LPA_FILE" ] || die "paid mode requires --lpa-file"
	[ -f "$STATE_DIR/rehearsal-ok" ] || die "paid mode requires a successful free rehearsal (marker: $STATE_DIR/rehearsal-ok)"
	if [ "$LPA_FILE" = "-" ]; then
		LPA=$(cat)
	else
		[ -f "$LPA_FILE" ] || die "LPA file not found: $LPA_FILE"
		[ ! -L "$LPA_FILE" ] || die "LPA file must not be a symlink"
		mode=$(stat -c %a "$LPA_FILE" 2>/dev/null || true)
		[ "$mode" = "600" ] || die "LPA file must be mode 0600 (got ${mode:-unknown})"
		LPA=$(tr -d '\r\n' <"$LPA_FILE")
	fi
	case "$LPA" in
	LPA:1\$*) ;;
	*) die "not an LPA:1\$ activation code" ;;
	esac
}

cleanup() {
	unset LPA 2>/dev/null || true
	unset lpa 2>/dev/null || true
}

trap cleanup EXIT HUP INT TERM

while [ $# -gt 0 ]; do
	case "$1" in
	--gate) ACTION=gate ;;
	--rehearsal) ACTION=rehearsal ;;
	--paid) ACTION=paid ;;
	--verify) ACTION=verify ;;
	--lpa-file)
		shift
		LPA_FILE=${1:-}
		;;
	--confirm-paid) CONFIRM_PAID=1 ;;
	--iccid)
		shift
		ICCID=${1:-}
		;;
	--host)
		shift
		HOST=${1:-}
		;;
	--user)
		shift
		USER=${1:-}
		;;
	--key)
		shift
		KEY=${1:-}
		;;
	-h | --help | help)
		usage
		exit 0
		;;
	*) die "unknown argument: $1" ;;
	esac
	shift
done

[ -n "$ACTION" ] || {
	usage
	exit 2
}

if [ -n "$ICCID" ]; then
	case "$ICCID" in
	*[!0-9]*) die "ICCID must contain only digits" ;;
	esac
	[ "${#ICCID}" -ge 18 ] && [ "${#ICCID}" -le 22 ] || die "ICCID must be 18-22 digits"
fi

mkdir -p "$LOG_DIR"
echo "e750-esim-activate: host=$HOST action=$ACTION"
require_access

case "$ACTION" in
gate)
	gate
	;;
rehearsal)
	gate
	download "$REHEARSAL_LPA" || exit 1
	resolve_iccid || die "could not determine the ICCID; inspect profile list and enable manually"
	enable_profile "$ICCID" || exit 1
	set_apn
	verify
	mark rehearsal-ok
	echo "rehearsal: PASS; marker $STATE_DIR/rehearsal-ok"
	;;
paid)
	check_paid
	gate
	download "$LPA" || exit 1
	unset LPA
	LPA=
	resolve_iccid || die "could not determine the ICCID; the profile may be downloaded; inspect profile list and enable manually"
	enable_profile "$ICCID" || exit 1
	set_apn
	verify
	mark paid-ok
	echo "paid: profile installed and enabled; private marker $STATE_DIR/paid-ok"
	;;
verify)
	verify
	;;
esac
