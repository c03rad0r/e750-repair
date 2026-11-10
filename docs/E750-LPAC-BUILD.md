# Reproducible lpac build for GL-E750

This builder cross-compiles the pinned Amperstrand lpac for **OpenWrt 25.12.5 ath79/nand, mips_24kc, 32-bit big-endian musl**. It neither installs host packages nor runs target binaries. It does not connect to an E750, a modem, or an eSIM.

## Inputs and tools

All source URLs, revisions, and SHA-256 digests are in `tools/lpac-e750-build/manifest.json`. In particular:

- lpac `7be0e679ff695d469064088ed0e69b438292e305`;
- the lpac-selected CoelacanthusHex/cJSON revision `4818f043bda624b5738384eae3a0189b2bd1f5e1` (supplied locally to CMake, not fetched opportunistically);
- the official OpenWrt 25.12.5 ath79/nand SDK;
- OpenSSL 3.5.4 and curl 8.16.0, built with the SDK cross-toolchain;
- Mozilla WebPKI roots plus the pinned ifd-modemifd GSMA CI bundle;
- GCC's license and runtime exception for the bundled libatomic.

Required host programs are Python 3.11+, curl, tar, zstd, CMake 3.23+, GNU make, a host C compiler, Perl, and gzip. No Python packages, container runtime, PCSC daemon, QMI/MBIM tools, or global installation are needed. Network access is used only for the pinned HTTPS downloads.

## Build

From the repository root:

```sh
# Verify downloads and extract to content-fingerprinted source trees only.
PYTHONDONTWRITEBYTECODE=1 \
  tools/lpac-e750-build/build.sh \
  --workdir /tmp/opencode/lpac-e750-rebuild --prepare-only

# Rebuild the complete bundle. JOBS is optional.
PYTHONDONTWRITEBYTECODE=1 JOBS=4 \
  tools/lpac-e750-build/build.sh \
  --workdir /tmp/opencode/lpac-e750-rebuild
```

`--workdir` defaults to `/tmp/opencode/lpac-e750-rebuild`. Prepare is idempotent: every cached archive is checked again and every source tree is compared with its stamp. An unstamped, substituted, or dirty source tree is rejected rather than silently reused. Full builds recreate the dependency, build, and staging trees.

The official SDK contains absolute host-tool convenience symlinks, so those links are deliberately not materialized. Its generated package-signing private key is also deleted immediately after extraction; SDK packaging/signing is not used. All other source archives and the final bundle must pass strict path/link inspection (no absolute paths, traversal, devices, or FIFOs).

## Artifact and verification

The output is:

```text
/tmp/opencode/lpac-e750-rebuild/dist/lpac-25.12.5-ath79-nand-mips.tar.gz
```

alongside `SHA256SUMS` and a `.verify.json` dependency report. The binary bundle itself is intentionally not committed to this repository. Verify an existing artifact without executing it:

```sh
PYTHONDONTWRITEBYTECODE=1 \
  python3 tools/lpac-e750-build/verify.py bundle \
  /tmp/opencode/lpac-e750-rebuild/dist/lpac-25.12.5-ath79-nand-mips.tar.gz
```

The verifier checks:

- safe tar members and required executable, AT/curl driver, trust, launcher, metadata, and license files;
- MIPS32 MSB/o32 ELF headers and the musl program interpreter;
- `LPAC_APDU_AT_HEX`, bounded `at_expect_with_deadline`/`timerfd_create`, `LPAC_HTTP_SSL_VERIFY`, `LPAC_HTTP_CURL_CAINFO`, and compiled `LPAC_DRIVER_HOME` fingerprints;
- OpenWrt versus host/development runtime dependencies and forbidden PCSC/QMI/MBIM/mbedtls dependencies;
- a closed dependency set and rejection of build-host RPATH/RUNPATH entries.

curl is linked to OpenSSL, not mbedtls. OpenSSL is static within `libcurl.so.4`; lpac's shared libraries, libcurl, and libatomic are shipped under `/usr/lib/lpac/lib`. The only remaining runtime requirements are OpenWrt's base musl libc and `libgcc_s.so.1`. The report lists every ELF object's `DT_NEEDED` entries. The wrapper supplies `/usr/lib/lpac/lib` through `LD_LIBRARY_PATH`, and lpac-owned objects also have origin-relative RPATHs.

`/usr/bin/lpac` exports **`LPAC_DRIVER_HOME=/usr/lib/lpac`**. This is intentionally the prefix rather than the final driver directory: this lpac revision appends `/driver` itself. It also selects the GSMA-augmented CA file, keeps TLS verification enabled by default, and defaults AT APDU hex to uppercase.

The trust file supplements the normal WebPKI roots with GSMA CI certificates; it does not replace WebPKI with a GSMA-only root store. Source manifests and component license notices are included under `/usr/lib/lpac/share`.

## Contract tests

```sh
PYTHONDONTWRITEBYTECODE=1 \
  python3 -m pytest -q -p no:cacheprovider \
  tests/test_e750_lpac_build_contract.py
```

Tests include checksum mismatch, absolute/traversing tar entries and link targets, special files, wrong ELF architecture, modified source fingerprints, SDK absolute-link handling, and success-path artifact fixtures. They disable bytecode and pytest cache writes explicitly.

This confirms cross-build and artifact properties only. It deliberately makes no claim about modem, profile, or on-device behavior; those require a separately authorized hardware gate.
