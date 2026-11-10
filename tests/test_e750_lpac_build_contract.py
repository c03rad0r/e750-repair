"""Contract and safety tests for the pinned GL-E750 lpac cross-builder."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "lpac-e750-build"
VERIFY_PATH = BUILDER / "verify.py"


def load_verify():
    spec = importlib.util.spec_from_file_location("e750_lpac_verify", VERIFY_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_bytes(tar: tarfile.TarFile, name: str, data: bytes, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = mode
    tar.addfile(info, io.BytesIO(data))


def mips_elf(extra: bytes = b"") -> bytes:
    ident = b"\x7fELF" + bytes([1, 2, 1, 0, 0]) + bytes(8)
    header = struct_pack_elf32(ident, machine=8, data="big")
    return header + b"libc.musl-mips-sf.so.1\0" + extra


def x86_elf() -> bytes:
    ident = b"\x7fELF" + bytes([2, 1, 1, 0, 0]) + bytes(8)
    return ident + bytes(100)


def struct_pack_elf32(ident: bytes, machine: int, data: str) -> bytes:
    import struct

    assert data == "big"
    # ELF32 executable, requested machine, version, and MIPS o32/MIPS32 flags.
    return struct.pack(
        ">16sHHIIIIIHHHHHH",
        ident,
        2,
        machine,
        1,
        0,
        0,
        0,
        0x50001007,
        52,
        32,
        0,
        40,
        0,
        0,
    )


def make_bundle(path: Path, *, at_payload: bytes | None = None) -> None:
    at = mips_elf(b"LPAC_APDU_AT_HEX\0UPPER\0at_expect_with_deadline\0timerfd_create\0")
    http = mips_elf(
        b"LPAC_HTTP_SSL_VERIFY\0LPAC_HTTP_CURL_CAINFO\0"
        b"CURLOPT_SSL_VERIFYPEER\0CURLOPT_SSL_VERIFYHOST\0"
    )
    executable = mips_elf(b"LPAC_DRIVER_HOME\0")
    wrapper = (
        b"#!/bin/sh\n"
        b"export LPAC_DRIVER_HOME=/usr/lib/lpac\n"
        b"export LPAC_HTTP_CURL_CAINFO=/usr/lib/lpac/etc/ssl/certs/ca-certificates-gsma.crt\n"
        b"export LD_LIBRARY_PATH=/usr/lib/lpac/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\n"
        b"exec /usr/lib/lpac/lpac \"$@\"\n"
    )
    metadata = json.dumps(
        {
            "target": "ath79/nand",
            "abi": "mips_24kc",
            "lpac_revision": "7be0e679ff695d469064088ed0e69b438292e305",
        }
    ).encode()
    with tarfile.open(path, "w:gz") as tar:
        add_bytes(tar, "usr/bin/lpac", wrapper, 0o755)
        add_bytes(tar, "usr/lib/lpac/lpac", executable if at_payload is None else executable, 0o755)
        add_bytes(tar, "usr/lib/lpac/driver/driver_apdu_at_csim.so", at if at_payload is None else at_payload)
        add_bytes(tar, "usr/lib/lpac/driver/driver_http_curl.so", http)
        add_bytes(
            tar,
            "usr/lib/lpac/etc/ssl/certs/ca-certificates-gsma.crt",
            b"WebPKI CA certificates\nGSMA CI certificates\n",
        )
        add_bytes(tar, "usr/lib/lpac/share/build-metadata.json", metadata)
        add_bytes(tar, "usr/lib/lpac/share/LICENSE.lpac", b"license notice\n")


def test_pinned_manifest_and_cmake_contract() -> None:
    manifest = json.loads((BUILDER / "manifest.json").read_text())
    assert manifest["target"] == {"openwrt": "25.12.5", "target": "ath79/nand", "abi": "mips_24kc"}
    assert manifest["sources"]["lpac"]["revision"] == "7be0e679ff695d469064088ed0e69b438292e305"
    assert manifest["sources"]["lpac"]["sha256"] == "e5bca0f618e8b166fad446cbca9a316396c45aca9c8c921808a6b2def308b475"
    assert manifest["sources"]["sdk"]["sha256"] == "c23d03c6467c7ef38454c40e78a0a477ed8e0e109ec6a2614c162f24e4280e7a"
    assert manifest["sources"]["cjson"]["sha256"] == "4a53a6d3b24d3d088c9d6f1790627fbcb4966c6bc51e4c44357a273abc938e21"
    assert manifest["sources"]["gsma_ci"]["revision"] == "61cf5899512f74271f9b5d5fcba6cd0bef6f4a59"
    assert manifest["sources"]["gsma_ci"]["sha256"] == "f9654512a761f89649b451367563b82e8ce40f93d235e9563cdb273ce051c857"
    for source in manifest["sources"].values():
        assert re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
        assert source["url"].startswith("https://")

    script = (BUILDER / "build.sh").read_text()
    assert "set -euo pipefail" in script
    assert "--prepare-only" in script
    assert "--workdir" in script
    assert "/tmp/opencode/lpac-e750-rebuild" in script
    required = (
        "LPAC_WITH_APDU_AT=ON",
        "LPAC_WITH_APDU_PCSC=OFF",
        "LPAC_WITH_HTTP_CURL=ON",
        "LPAC_WITH_APDU_QMI=OFF",
        "LPAC_WITH_APDU_QMI_QRTR=OFF",
        "LPAC_WITH_APDU_UQMI=OFF",
        "LPAC_WITH_APDU_MBIM=OFF",
        "BUILD_TESTING=OFF",
    )
    for flag in required:
        assert flag in script
    assert "sudo" not in script
    assert "lpac-25.12.5-ath79-nand-mips.tar.gz" in script
    assert "LPAC_DRIVER_HOME" in script


def test_builder_help_does_not_prepare_or_download(tmp_path: Path) -> None:
    result = subprocess.run(
        [str(BUILDER / "build.sh"), "--help"],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stderr
    assert "--workdir DIR" in result.stdout
    assert "--prepare-only" in result.stdout


def test_sha256_verifier_rejects_changed_download(tmp_path: Path) -> None:
    verify = load_verify()
    archive = tmp_path / "source.tar"
    archive.write_bytes(b"pinned input")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    verify.verify_sha256(archive, digest)
    with pytest.raises(verify.VerificationError, match="sha256 mismatch"):
        verify.verify_sha256(archive, "0" * 64)


@pytest.mark.parametrize(
    ("name", "linkname"),
    [
        ("/etc/passwd", ""),
        ("../escape", ""),
        ("source/../../escape", ""),
        ("safe/link", "/absolute/target"),
        ("safe/link", "../../../escape"),
    ],
)
def test_tar_safety_rejects_absolute_and_traversing_entries(
    tmp_path: Path, name: str, linkname: str
) -> None:
    verify = load_verify()
    archive = tmp_path / "unsafe.tar"
    with tarfile.open(archive, "w") as tar:
        info = tarfile.TarInfo(name)
        if linkname:
            info.type = tarfile.SYMTYPE
            info.linkname = linkname
        else:
            payload = b"unsafe"
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
            return_after_tar = True
        if linkname:
            tar.addfile(info)
    with tarfile.open(archive) as tar, pytest.raises(verify.VerificationError):
        verify.validate_tar_members(tar)


def test_tar_safety_rejects_device(tmp_path: Path) -> None:
    verify = load_verify()
    archive = tmp_path / "device.tar"
    with tarfile.open(archive, "w") as tar:
        info = tarfile.TarInfo("source/dev/zero")
        info.type = tarfile.CHRTYPE
        info.devmajor = 1
        info.devminor = 5
        tar.addfile(info)
    with tarfile.open(archive) as tar, pytest.raises(verify.VerificationError, match="unsupported"):
        verify.validate_tar_members(tar)


def test_tar_safety_accepts_normal_relative_archive(tmp_path: Path) -> None:
    verify = load_verify()
    archive = tmp_path / "safe.tar"
    with tarfile.open(archive, "w") as tar:
        add_bytes(tar, "source/README", b"safe")
    with tarfile.open(archive) as tar:
        verify.validate_tar_members(tar)
    destination = tmp_path / "out"
    verify.safe_extract_tar(archive, destination)
    assert (destination / "source/README").read_bytes() == b"safe"


def test_sdk_absolute_host_symlink_is_never_materialized(tmp_path: Path) -> None:
    verify = load_verify()
    archive = tmp_path / "sdk.tar"
    with tarfile.open(archive, "w") as tar:
        add_bytes(tar, "sdk/toolchain/cc", b"cross compiler")
        link = tarfile.TarInfo("sdk/host/bin/bash")
        link.type = tarfile.SYMTYPE
        link.linkname = "/bin/bash"
        tar.addfile(link)
    destination = tmp_path / "out"
    verify.safe_extract_tar(archive, destination, skip_absolute_symlinks=True)
    assert (destination / "sdk/toolchain/cc").is_file()
    assert not (destination / "sdk/host/bin/bash").exists()


def test_elf_inspection_accepts_mips32_msb_musl_and_rejects_x86(tmp_path: Path) -> None:
    verify = load_verify()
    mips = tmp_path / "mips.so"
    mips.write_bytes(mips_elf())
    info = verify.inspect_elf(mips, require_musl=True)
    assert info["bits"] == 32
    assert info["endian"] == "big"
    assert info["machine"] == 8
    assert info["musl"] is True

    wrong = tmp_path / "x86.so"
    wrong.write_bytes(x86_elf())
    with pytest.raises(verify.VerificationError, match="32-bit|MIPS|big-endian"):
        verify.inspect_elf(wrong, require_musl=True)


def write_pinned_source_fixture(root: Path) -> None:
    files = {
        "driver/apdu/at_helpers.c": 'getenv_or_default(ENV_AT_HEX, "LOWER")\nstatic const char upper[] = "UPPER";\nvoid at_apply_hex_case(void) {}\n// LPAC_APDU_AT_HEX\n',
        "driver/apdu/at_cmd.h": "#define ENV_AT_HEX APDU_ENV_NAME(AT, HEX)\nint at_expect_with_deadline(void);\n",
        "driver/apdu/at_etsi_csim.c": "// LPAC_APDU_AT_HEX\nat_apply_hex_case(hex);\n",
        "driver/apdu/at_cmd_unix.c": "int at_expect_with_deadline(void) { return timerfd_create(CLOCK_MONOTONIC, 0); }\n",
        "driver/http/curl.c": (
            'getenv("LPAC_HTTP_SSL_VERIFY"); getenv("LPAC_HTTP_CURL_CAINFO");\n'
            "CURLOPT_SSL_VERIFYPEER, 1L; CURLOPT_SSL_VERIFYHOST, 2L; CURLOPT_CAINFO, cainfo;\n"
        ),
        "driver/euicc-driver-loader.c": 'getenv("LPAC_DRIVER_HOME"); get_first_runpath();\n',
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def test_source_semantics_and_wrong_patch_detection(tmp_path: Path) -> None:
    verify = load_verify()
    write_pinned_source_fixture(tmp_path)
    verify.verify_lpac_source(tmp_path)
    at_unix = tmp_path / "driver/apdu/at_cmd_unix.c"
    at_unix.write_text(at_unix.read_text().replace("timerfd_create", "poll"))
    with pytest.raises(verify.VerificationError, match="source fingerprint"):
        verify.verify_lpac_source(tmp_path)


def test_complete_bundle_verifier(tmp_path: Path) -> None:
    verify = load_verify()
    bundle = tmp_path / "lpac.tar.gz"
    make_bundle(bundle)
    result = verify.verify_bundle(bundle)
    assert result["architecture"] == "mips32-msb-musl"
    assert result["elf_count"] == 3
    assert verify.sha256_file(bundle) == hashlib.sha256(bundle.read_bytes()).hexdigest()


def test_bundle_verifier_rejects_wrong_driver_architecture(tmp_path: Path) -> None:
    verify = load_verify()
    bundle = tmp_path / "wrong.tar.gz"
    make_bundle(bundle, at_payload=x86_elf())
    with pytest.raises(verify.VerificationError, match="32-bit|MIPS|big-endian"):
        verify.verify_bundle(bundle)


def test_bundle_verifier_rejects_regressed_at_fingerprint(tmp_path: Path) -> None:
    verify = load_verify()
    bundle = tmp_path / "regressed.tar.gz"
    make_bundle(bundle, at_payload=mips_elf(b"LPAC_APDU_AT_HEX\0UPPER\0poll\0"))
    with pytest.raises(verify.VerificationError, match="fingerprint"):
        verify.verify_bundle(bundle)
