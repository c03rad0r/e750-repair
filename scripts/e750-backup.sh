#!/bin/sh
# Back up the E750's private state before any radio experiment.
#
# Run from the host that can reach the E750 LAN (x280):
#
#   E750_HOST=192.168.8.1 E750_KEY=~/.ssh/id_ed25519 scripts/e750-backup.sh
#
# The output contains the art partition and device MACs/calibration. It is
# written outside the repository, mode 0700/0600, and must not be committed.

set -eu

E750_HOST="${E750_HOST:-192.168.8.1}"
E750_USER="${E750_USER:-root}"
E750_KEY="${E750_KEY:-$HOME/.ssh/id_ed25519}"
OUT="${OUT:-$HOME/.local/share/e750-backup-$(date -u +%Y%m%dT%H%M%SZ)}"

umask 077
mkdir -p "$OUT"

SSH="ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -i $E750_KEY $E750_USER@$E750_HOST"

$SSH '
set -e
dd if=/dev/mtd1 of=/tmp/e750-mtd1.bin bs=4096 2>/dev/null
dd if=/dev/mtd2 of=/tmp/e750-art.bin bs=4096 2>/dev/null
uci export > /tmp/e750-uci-export.txt
dmesg > /tmp/e750-dmesg.txt
rm -rf /tmp/e750-ath10k-backup
cp -r /lib/firmware/ath10k /tmp/e750-ath10k-backup
cp /etc/dropbear/authorized_keys /tmp/e750-dropbear-authorized_keys
cp /root/.ssh/authorized_keys /tmp/e750-root-authorized_keys 2>/dev/null || true
ls -l /tmp/e750-mtd1.bin /tmp/e750-art.bin
'

$SSH 'tar -cf - \
  /tmp/e750-mtd1.bin \
  /tmp/e750-art.bin \
  /tmp/e750-uci-export.txt \
  /tmp/e750-dmesg.txt \
  /tmp/e750-ath10k-backup \
  /tmp/e750-dropbear-authorized_keys \
  /tmp/e750-root-authorized_keys 2>/dev/null' | gzip > "$OUT/e750-backup.tar.gz"

echo "backup written to $OUT/e750-backup.tar.gz"
echo "keep this private: it contains art/calibration and keys"
