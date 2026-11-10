#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
WORK_DIR=/tmp/opencode/lpac-e750-rebuild
PREPARE_ONLY=0

usage() {
    cat <<'EOF'
Usage: build.sh [--workdir DIR] [--prepare-only]

Cross-build the checksum-pinned Amperstrand lpac for OpenWrt 25.12.5
ath79/nand mips_24kc. Nothing is installed on the host or a device.

  --workdir DIR   Build, download, dependency and output root
                  (default: /tmp/opencode/lpac-e750-rebuild)
  --prepare-only  Verify downloads and clean source stamps, then stop
  -h, --help      Show this help without downloading anything

Output: DIST/lpac-25.12.5-ath79-nand-mips.tar.gz under the workdir.
Repeat runs validate source contents and rebuild dependencies from scratch.
EOF
}

while (($#)); do
    case "$1" in
        --workdir)
            (($# >= 2)) || { echo "--workdir requires DIR" >&2; exit 2; }
            WORK_DIR=$2
            shift 2
            ;;
        --prepare-only)
            PREPARE_ONLY=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

for tool in python3 curl tar zstd cmake make perl gcc gzip; do
    command -v "$tool" >/dev/null || { echo "missing host build tool: $tool" >&2; exit 1; }
done
mkdir -p -- "$WORK_DIR"
WORK_DIR=$(CDPATH= cd -- "$WORK_DIR" && pwd -P)
if [[ "$WORK_DIR" == / ]]; then
    echo "refusing to use / as workdir" >&2
    exit 1
fi
export PYTHONDONTWRITEBYTECODE=1
python3 "$SCRIPT_DIR/prepare.py" --manifest "$SCRIPT_DIR/manifest.json" --workdir "$WORK_DIR"
if ((PREPARE_ONLY)); then
    exit 0
fi

SDK_DIR="$WORK_DIR/src/sdk"
LPAC_DIR="$WORK_DIR/src/lpac"
CJSON_DIR="$WORK_DIR/src/cjson"
CURL_DIR="$WORK_DIR/src/curl"
OPENSSL_DIR="$WORK_DIR/src/openssl"
BUILD_DIR="$WORK_DIR/build"
DEPS_DIR="$WORK_DIR/deps"
STAGE_DIR="$WORK_DIR/stage"
DIST_DIR="$WORK_DIR/dist"
TARGET=mips-openwrt-linux-musl
TOOLCHAIN_DIR="$SDK_DIR/staging_dir/toolchain-mips_24kc_gcc-14.3.0_musl"
SYSROOT="$TOOLCHAIN_DIR"
export PATH="$TOOLCHAIN_DIR/bin:$PATH"
export SOURCE_DATE_EPOCH=0
export STAGING_DIR="$SDK_DIR/staging_dir"

for path in \
    "$TOOLCHAIN_DIR/bin/$TARGET-gcc" \
    "$TOOLCHAIN_DIR/bin/$TARGET-strip" \
    "$SYSROOT/include/stdio.h"; do
    [[ -e "$path" ]] || { echo "SDK toolchain/sysroot incomplete: $path" >&2; exit 1; }
done

# A full build never reuses an unstamped dependency directory, install tree or
# output tree. Downloads and content-identified, fingerprinted sources persist.
rm -rf -- "$BUILD_DIR" "$DEPS_DIR" "$STAGE_DIR"
mkdir -p -- "$BUILD_DIR" "$DEPS_DIR" "$STAGE_DIR" "$DIST_DIR"

export CC="$TOOLCHAIN_DIR/bin/$TARGET-gcc"
export AR="$TOOLCHAIN_DIR/bin/$TARGET-ar"
export RANLIB="$TOOLCHAIN_DIR/bin/$TARGET-ranlib"
export STRIP="$TOOLCHAIN_DIR/bin/$TARGET-strip"
export CFLAGS="--sysroot=$SYSROOT -Os -fPIC"
export LDFLAGS="--sysroot=$SYSROOT"
export LIBS="-latomic -ldl -pthread"

cat > "$BUILD_DIR/toolchain.cmake" <<EOF
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR mips)
set(CMAKE_C_COMPILER "$CC")
set(CMAKE_AR "$AR")
set(CMAKE_RANLIB "$RANLIB")
set(CMAKE_STRIP "$STRIP")
set(CMAKE_SYSROOT "$SYSROOT")
set(CMAKE_FIND_ROOT_PATH "$DEPS_DIR;$SYSROOT")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
EOF

jobs=${JOBS:-}
if [[ -z "$jobs" ]]; then
    jobs=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)
fi
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo "JOBS must be a positive integer" >&2; exit 1; }

echo "== building static OpenSSL 3.5.4 for MIPS32 MSB =="
mkdir -p "$BUILD_DIR/openssl"
(
    cd "$BUILD_DIR/openssl"
    "$OPENSSL_DIR/Configure" \
        linux-mips32 \
        --prefix="$DEPS_DIR" \
        --openssldir=/etc/ssl \
        no-shared no-tests no-docs no-apps
    make -j"$jobs"
    make install_sw
)

echo "== building OpenSSL-only shared libcurl 8.16.0 =="
mkdir -p "$BUILD_DIR/curl"
(
    cd "$BUILD_DIR/curl"
    "$CURL_DIR/configure" \
        --host="$TARGET" \
        --build=x86_64-pc-linux-gnu \
        --prefix="$DEPS_DIR" \
        --with-openssl="$DEPS_DIR" \
        --without-mbedtls \
        --without-wolfssl \
        --without-gnutls \
        --without-rustls \
        --without-ca-bundle \
        --without-ca-path \
        --without-zlib \
        --without-brotli \
        --without-zstd \
        --without-nghttp2 \
        --without-nghttp3 \
        --without-ngtcp2 \
        --without-libidn2 \
        --without-libpsl \
        --without-libssh2 \
        --disable-ares \
        --disable-ldap \
        --disable-ldaps \
        --disable-rtsp \
        --disable-dict \
        --disable-file \
        --disable-ftp \
        --disable-gopher \
        --disable-imap \
        --disable-mqtt \
        --disable-pop3 \
        --disable-smb \
        --disable-smtp \
        --disable-telnet \
        --disable-tftp \
        --disable-manual \
        --disable-curldebug \
        --enable-shared \
        --disable-static
    # Do not capture the SDK/libatomic build-host directory in libcurl's RPATH.
    sed -i -e 's/^hardcode_libdir_flag_spec=.*/hardcode_libdir_flag_spec=""/' \
        -e 's/^hardcode_into_libs=.*/hardcode_into_libs=no/' \
        -e 's/^runpath_var=.*/runpath_var=""/' libtool
    make -j"$jobs"
    make install
)
# The final verifier rejects non-$ORIGIN/non-/usr/lib/lpac search directories.
grep -Eq '^#define USE_OPENSSL 1' "$BUILD_DIR/curl/lib/curl_config.h"
if grep -Eq '^#define USE_MBEDTLS 1' "$BUILD_DIR/curl/lib/curl_config.h"; then
    echo "mbedtls is forbidden in this build" >&2
    exit 1
fi

echo "== building pinned lpac and at/curl drivers =="
cmake -S "$LPAC_DIR" -B "$BUILD_DIR/lpac" -G "Unix Makefiles" \
    -DCMAKE_TOOLCHAIN_FILE="$BUILD_DIR/toolchain.cmake" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/lib/lpac \
    -DCMAKE_INSTALL_BINDIR=. \
    -DCMAKE_INSTALL_LIBDIR=lib \
    -DDRIVER_INSTALL_PATH=/usr/lib/lpac/driver \
    '-DCMAKE_INSTALL_RPATH=$ORIGIN/lib;$ORIGIN/../lib;$ORIGIN' \
    -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
    -DFETCHCONTENT_SOURCE_DIR_CJSON="$CJSON_DIR" \
    -DFETCHCONTENT_FULLY_DISCONNECTED=ON \
    -DENABLE_CJSON_TEST=OFF \
    -DENABLE_CUSTOM_COMPILER_FLAGS=OFF \
    -DBUILD_TESTING=OFF \
    -DLPAC_VERSION=2.3.0+7be0e67 \
    -DLPAC_DYNAMIC_LIBEUICC=ON \
    -DLPAC_WITH_APDU_AT=ON \
    -DLPAC_WITH_APDU_PCSC=OFF \
    -DLPAC_WITH_HTTP_CURL=ON \
    -DLPAC_WITH_APDU_GBINDER=OFF \
    -DLPAC_WITH_APDU_QMI=OFF \
    -DLPAC_WITH_APDU_QMI_QRTR=OFF \
    -DLPAC_WITH_APDU_MBIM=OFF \
    -DLPAC_WITH_APDU_UQMI=OFF \
    -DLPAC_WITH_HTTP_WINHTTP=OFF \
    -DCURL_ROOT="$DEPS_DIR" \
    -DCURL_LIBRARY="$DEPS_DIR/lib/libcurl.so" \
    -DCURL_INCLUDE_DIR="$DEPS_DIR/include"
cmake --build "$BUILD_DIR/lpac" --parallel "$jobs"
DESTDIR="$STAGE_DIR" cmake --install "$BUILD_DIR/lpac"

mkdir -p "$STAGE_DIR/usr/lib/lpac/lib"
cp -a "$DEPS_DIR"/lib/libcurl.so* "$STAGE_DIR/usr/lib/lpac/lib/"
cp -a "$TOOLCHAIN_DIR"/lib/libatomic.so.1* "$STAGE_DIR/usr/lib/lpac/lib/"
rm -rf -- "$STAGE_DIR/usr/lib/lpac/include" \
    "$STAGE_DIR/usr/lib/lpac/lib/pkgconfig" "$STAGE_DIR/usr/lib/lpac/lib/cmake"
rm -f -- "$STAGE_DIR/usr/lib/lpac/lib/libcjson.a" \
    "$STAGE_DIR/usr/lib/lpac/lib/libcurl.so" \
    "$STAGE_DIR/usr/lib/lpac/lib/libeuicc.so" \
    "$STAGE_DIR/usr/lib/lpac/lib/libeuicc-drivers.so" \
    "$STAGE_DIR/usr/lib/lpac/lib/libeuicc-driver-loader.so"
mkdir -p "$STAGE_DIR/usr/bin" "$STAGE_DIR/usr/lib/lpac/etc/ssl/certs"
cat > "$STAGE_DIR/usr/bin/lpac" <<'EOF'
#!/bin/sh
LPAC_DRIVER_HOME=/usr/lib/lpac
LPAC_HTTP_CURL_CAINFO=/usr/lib/lpac/etc/ssl/certs/ca-certificates-gsma.crt
LD_LIBRARY_PATH=/usr/lib/lpac/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
LPAC_APDU_AT_HEX=${LPAC_APDU_AT_HEX:-UPPER}
LPAC_HTTP_SSL_VERIFY=${LPAC_HTTP_SSL_VERIFY:-1}
export LPAC_DRIVER_HOME LPAC_HTTP_CURL_CAINFO LD_LIBRARY_PATH
export LPAC_APDU_AT_HEX LPAC_HTTP_SSL_VERIFY
exec /usr/lib/lpac/lpac "$@"
EOF
chmod 0755 "$STAGE_DIR/usr/bin/lpac"

TRUST_DIR="$STAGE_DIR/usr/lib/lpac/etc/ssl/certs"
{
    printf '%s\n' '# WebPKI CA certificates plus GSMA CI certificates'
    printf '%s\n' '# WebPKI CA certificates'
    cat "$WORK_DIR/downloads/$(basename "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sources"]["webpki_ca"]["filename"])' "$SCRIPT_DIR/manifest.json")")"
    printf '\n%s\n' '# GSMA CI certificates'
    cat "$WORK_DIR/downloads/$(basename "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sources"]["gsma_ci"]["filename"])' "$SCRIPT_DIR/manifest.json")")"
} > "$TRUST_DIR/ca-certificates-gsma.crt"

SHARE_DIR="$STAGE_DIR/usr/lib/lpac/share"
LICENSE_DIR="$SHARE_DIR/licenses"
mkdir -p "$LICENSE_DIR"
cp "$LPAC_DIR/src/LICENSE" "$LICENSE_DIR/LICENSE.lpac"
cp "$LPAC_DIR/euicc/LICENSE" "$LICENSE_DIR/LICENSE.libeuicc"
cp "$LPAC_DIR/driver/LICENSE" "$LICENSE_DIR/LICENSE.drivers"
cp "$CJSON_DIR/LICENSE" "$LICENSE_DIR/LICENSE.cJSON"
cp "$CURL_DIR/COPYING" "$LICENSE_DIR/LICENSE.curl"
cp "$OPENSSL_DIR/LICENSE.txt" "$LICENSE_DIR/LICENSE.openssl"
cp "$WORK_DIR/downloads/gcc-c9cd41fba9ebd288c4f101e4b99da934bcb96a11-COPYING.RUNTIME" \
    "$LICENSE_DIR/LICENSE.gcc-runtime-exception"
cp "$WORK_DIR/downloads/gcc-c9cd41fba9ebd288c4f101e4b99da934bcb96a11-COPYING3" \
    "$LICENSE_DIR/LICENSE.gcc-gpl3"
cp "$SCRIPT_DIR/manifest.json" "$SHARE_DIR/source-manifest.json"
python3 - "$SCRIPT_DIR/manifest.json" "$SHARE_DIR/build-metadata.json" <<'PY'
import json
import sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text())
metadata = {
    "schema": 1,
    "target": manifest["target"]["target"],
    "abi": manifest["target"]["abi"],
    "openwrt": manifest["target"]["openwrt"],
    "lpac_revision": manifest["sources"]["lpac"]["revision"],
    "cjson_revision": manifest["sources"]["cjson"]["revision"],
    "curl_revision": manifest["sources"]["curl"]["revision"],
    "openssl_revision": manifest["sources"]["openssl"]["revision"],
    "tls_backend": "OpenSSL",
    "runtime_library_layout": "/usr/lib/lpac/lib",
    "execution": "cross-compiled and statically inspected; target binaries not executed by builder",
}
Path(sys.argv[2]).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
PY

# Retain required dynamic symbol strings while removing local symbols/offsets.
find "$STAGE_DIR/usr/lib/lpac" -type f -print0 | while IFS= read -r -d '' file; do
    if [[ $(dd if="$file" bs=4 count=1 2>/dev/null) == $'\x7fELF' ]]; then
        "$STRIP" --strip-unneeded "$file"
    fi
done

python3 "$SCRIPT_DIR/verify.py" elf "$STAGE_DIR/usr/lib/lpac/lpac" >/dev/null
python3 "$SCRIPT_DIR/verify.py" source "$LPAC_DIR" >/dev/null
BUNDLE_NAME=lpac-25.12.5-ath79-nand-mips.tar.gz
CANDIDATE="$DIST_DIR/.$BUNDLE_NAME.candidate.$$"
trap 'rm -f -- "$CANDIDATE"' EXIT
tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner --format=gnu \
    -C "$STAGE_DIR" -cf - usr | gzip -n -9 > "$CANDIDATE"
python3 "$SCRIPT_DIR/verify.py" bundle "$CANDIDATE" > "$DIST_DIR/$BUNDLE_NAME.verify.json"
mv -f -- "$CANDIDATE" "$DIST_DIR/$BUNDLE_NAME"
trap - EXIT
(
    cd "$DIST_DIR"
    sha256sum "$BUNDLE_NAME" > SHA256SUMS
    sha256sum -c SHA256SUMS
)
printf 'artifact: %s\n' "$DIST_DIR/$BUNDLE_NAME"
printf 'verification: %s\n' "$DIST_DIR/$BUNDLE_NAME.verify.json"
