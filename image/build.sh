#!/bin/sh
# Build a clean GL-E750 image from the pinned OpenWrt 25.12.5 ImageBuilder.
# This only builds; it never flashes or touches a device.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
VERSION="25.12.5"
TARGET="ath79/nand"
PROFILE="glinet_gl-e750"
IB="openwrt-imagebuilder-${VERSION}-ath79-nand.Linux-x86_64.tar.zst"
IB_DIR="openwrt-imagebuilder-${VERSION}-ath79-nand.Linux-x86_64"
IB_SHA256="0d37c8dc528132f2e1e1daa14b9a69aceb4b508c8b59b4ad4c4ee3f0c7f2e60a"
BUILD="${ROOT}/image/build"

mkdir -p "$BUILD"
cd "$BUILD"

if [ ! -f "$IB" ]; then
	curl -fL -o "$IB" "https://downloads.openwrt.org/releases/${VERSION}/targets/${TARGET}/${IB}"
fi
printf '%s  %s\n' "$IB_SHA256" "$IB" | sha256sum -c -

if [ ! -d "$IB_DIR" ]; then
	tar --zstd -xf "$IB"
fi
cd "$IB_DIR"

PACKAGES=$(grep -vE '^[[:space:]]*(#|$)' "${ROOT}/image/packages.txt" | tr '\n' ' ')
echo "profile=${PROFILE}"
echo "packages=${PACKAGES}"
echo "files=${ROOT}/image/files"

make -j"$(nproc)" image \
	PROFILE="$PROFILE" \
	PACKAGES="$PACKAGES" \
	FILES="${ROOT}/image/files"

echo "=== built images ==="
find "bin/targets/${TARGET}" -maxdepth 1 -type f \( -name '*.bin' -o -name '*.manifest' \) -printf '%p %s bytes\n' | sort
echo "=== checksums ==="
sha256sum "bin/targets/${TARGET}"/*sysupgrade.bin
