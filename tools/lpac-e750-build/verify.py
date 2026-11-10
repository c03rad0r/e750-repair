#!/usr/bin/env python3
"""Safe archive, ELF and artifact checks for the GL-E750 lpac builder.

Only Python's standard library is used.  Target programs are never executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import tarfile
import tempfile
from typing import Iterable


BUNDLE_NAME = "lpac-25.12.5-ath79-nand-mips.tar.gz"
BASE_RUNTIME_LIBRARIES = (
    "libc.so",
    "libc.musl",
    "libgcc_s.so.",
    "ld-musl-mips",
)
FORBIDDEN_RUNTIME_LIBRARIES = (
    "libmbedtls",
    "libmbedx",
    "libpcsclite",
    "libqmi",
    "libmbim",
    "libqrtr",
    "libglib",
)
SOURCE_FINGERPRINTS = {
    "driver/apdu/at_cmd.h": (
        "#define ENV_AT_HEX APDU_ENV_NAME(AT, HEX)",
        "at_expect_with_deadline",
    ),
    "driver/apdu/at_etsi_csim.c": (
        "LPAC_APDU_AT_HEX",
        "at_apply_hex_case",
    ),
    "driver/apdu/at_helpers.c": (
        'getenv_or_default(ENV_AT_HEX, "LOWER")',
        'static const char upper[] = "UPPER"',
        "at_apply_hex_case",
    ),
    "driver/apdu/at_cmd_unix.c": (
        "at_expect_with_deadline",
        "timerfd_create(CLOCK_MONOTONIC",
        "CLOCK_MONOTONIC",
    ),
    "driver/http/curl.c": (
        "LPAC_HTTP_SSL_VERIFY",
        "LPAC_HTTP_CURL_CAINFO",
        "CURLOPT_SSL_VERIFYPEER, 1L",
        "CURLOPT_SSL_VERIFYHOST, 2L",
        "CURLOPT_CAINFO, cainfo",
    ),
    "driver/euicc-driver-loader.c": (
        "LPAC_DRIVER_HOME",
        "get_first_runpath",
        'getenv("LPAC_DRIVER_HOME")',
    ),
}


class VerificationError(RuntimeError):
    """A pin or artifact property is not what the builder promised."""


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_sha256(path: str | os.PathLike[str], expected: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise VerificationError(f"invalid expected sha256 for {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise VerificationError(
            f"sha256 mismatch for {path}: expected {expected}, got {actual}"
        )
    return actual


def _safe_archive_path(name: str) -> PurePosixPath:
    if not name or "\x00" in name:
        raise VerificationError("unsafe empty or NUL-containing tar path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise VerificationError(f"unsafe tar path: {name!r}")
    return path


def _safe_link(member: tarfile.TarInfo) -> None:
    target = PurePosixPath(member.linkname)
    if target.is_absolute() or not member.linkname or "\x00" in member.linkname:
        raise VerificationError(f"unsafe tar link target: {member.name!r}")
    if member.issym():
        parts = list(PurePosixPath(member.name).parent.parts)
    else:
        # POSIX hard-link names are archive-root relative.
        parts = []
    for part in target.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise VerificationError(
                    f"tar link escapes archive: {member.name!r} -> {member.linkname!r}"
                )
            parts.pop()
        else:
            parts.append(part)


def validate_tar_members(
    archive: tarfile.TarFile | Iterable[tarfile.TarInfo],
) -> list[tarfile.TarInfo]:
    """Reject traversal, absolute links and special files before extraction."""
    members = list(archive.getmembers() if isinstance(archive, tarfile.TarFile) else archive)
    for member in members:
        _safe_archive_path(member.name)
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise VerificationError(
                f"unsupported tar entry type for {member.name!r} (no devices/FIFOs)"
            )
        if member.issym() or member.islnk():
            _safe_link(member)
    return members


def safe_extract_tar(
    archive_path: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    *,
    skip_absolute_symlinks: bool = False,
) -> None:
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise VerificationError(f"refusing to overlay non-empty source directory: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:*") as archive:
        members = archive.getmembers()
        if skip_absolute_symlinks:
            # The official OpenWrt SDK contains absolute host-tool convenience
            # symlinks (for example staging_dir/host/bin/bash -> /bin/bash).
            # Never materialize those links. Keep normal strict checks for all
            # remaining members; our direct toolchain use does not need them.
            members = [
                member
                for member in members
                if not (member.issym() and PurePosixPath(member.linkname).is_absolute())
            ]
        else:
            members = archive
        validate_tar_members(members)
        archive.extractall(destination, members=members, filter="data")


def inspect_elf(
    path: str | os.PathLike[str], *, require_musl: bool = False
) -> dict[str, int | str | bool]:
    data = Path(path).read_bytes()
    if len(data) < 20 or data[:4] != b"\x7fELF":
        raise VerificationError(f"not an ELF file: {path}")
    bits = 32 if data[4] == 1 else 64 if data[4] == 2 else 0
    endian = "little" if data[5] == 1 else "big" if data[5] == 2 else "unknown"
    if bits != 32:
        raise VerificationError(f"expected 32-bit ELF, got {bits or 'unknown'}-bit: {path}")
    if endian != "big":
        raise VerificationError(f"expected big-endian ELF, got {endian}: {path}")
    fields = struct.unpack_from(">HHIIIIIHHHHHH", data, 16)
    elf_type, machine = fields[0], fields[1]
    flags = fields[6]
    if machine != 8:
        raise VerificationError(f"expected MIPS ELF machine 8, got {machine}: {path}")
    if elf_type not in (2, 3):
        raise VerificationError(f"expected executable/shared-object ELF: {path}")
    if flags & 0x20:  # EF_MIPS_ABI2 means n32, not the OpenWrt o32 ABI.
        raise VerificationError(f"unexpected MIPS n32 ABI in {path}")
    musl = b"musl" in data.lower()
    if require_musl and not musl:
        raise VerificationError(f"no musl dynamic-loader/libc fingerprint in {path}")
    return {
        "bits": bits,
        "endian": endian,
        "machine": machine,
        "type": elf_type,
        "flags": flags,
        "musl": musl,
    }


def elf_dynamic_info(path: str | os.PathLike[str]) -> dict[str, list[str]]:
    """Read DT_NEEDED/RPATH/RUNPATH without target code or target binutils."""
    data = Path(path).read_bytes()
    info = inspect_elf(path)
    if info["endian"] != "big" or info["bits"] != 32:
        raise VerificationError(f"dependency reader only supports MIPS32 MSB: {path}")
    header = struct.unpack_from(">HHIIIIIHHHHHH", data, 16)
    sh_offset, sh_entry_size, sh_count = header[5], header[10], header[11]
    result: dict[str, list[str]] = {"needed": [], "rpath": [], "runpath": []}
    if not sh_offset or not sh_count:
        return result
    if sh_entry_size < 40 or sh_offset + sh_entry_size * sh_count > len(data):
        raise VerificationError(f"truncated ELF section table: {path}")
    sections = [
        struct.unpack_from(">IIIIIIIIII", data, sh_offset + index * sh_entry_size)
        for index in range(sh_count)
    ]
    tag_names = {1: "needed", 15: "rpath", 29: "runpath"}
    for section in sections:
        if section[1] != 6:  # SHT_DYNAMIC
            continue
        _, _, _, _, offset, size, link, _, _, entry_size = section
        if link >= len(sections) or entry_size < 8 or offset + size > len(data):
            raise VerificationError(f"invalid ELF dynamic section: {path}")
        strings = sections[link]
        str_offset, str_size = strings[4], strings[5]
        if str_offset + str_size > len(data):
            raise VerificationError(f"invalid ELF string table: {path}")
        for position in range(offset, offset + size, entry_size):
            tag, value = struct.unpack_from(">II", data, position)
            if tag == 0:
                break
            if tag not in tag_names:
                continue
            end = data.find(b"\0", str_offset + value, str_offset + str_size)
            if end < 0:
                raise VerificationError(f"unterminated ELF dynamic string: {path}")
            result[tag_names[tag]].append(data[str_offset + value : end].decode("ascii"))
    return result


def elf_dynamic_dependencies(path: str | os.PathLike[str]) -> list[str]:
    return elf_dynamic_info(path)["needed"]


def verify_lpac_source(root: str | os.PathLike[str]) -> None:
    root = Path(root)
    for relative, fingerprints in SOURCE_FINGERPRINTS.items():
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise VerificationError(f"missing pinned lpac source file: {path}") from error
        for fingerprint in fingerprints:
            if fingerprint not in text:
                raise VerificationError(
                    f"lpac source fingerprint missing from {relative}: {fingerprint}"
                )


def _audit_runtime(root: Path, elf_paths: list[Path]) -> dict[str, list[str]]:
    bundled: set[str] = set()
    for directory in (root / "usr/lib/lpac/lib", root / "usr/lib/lpac/driver"):
        if directory.is_dir():
            bundled.update(path.name for path in directory.iterdir())
    dependencies: dict[str, list[str]] = {}
    for path in elf_paths:
        dynamic = elf_dynamic_info(path)
        needed = dynamic["needed"]
        dependencies[str(path.relative_to(root))] = needed
        for tag in ("rpath", "runpath"):
            for search_path in dynamic[tag]:
                for directory in search_path.split(":"):
                    if directory and not directory.startswith(("$ORIGIN", "/usr/lib/lpac/")):
                        raise VerificationError(
                            f"non-relocatable build host {tag.upper()} in {path.relative_to(root)}: {directory}"
                        )
        for library in needed:
            if library.startswith(FORBIDDEN_RUNTIME_LIBRARIES):
                raise VerificationError(f"forbidden runtime dependency {library} in {path}")
            if library not in bundled and not library.startswith(BASE_RUNTIME_LIBRARIES):
                raise VerificationError(
                    f"unclosed runtime dependency {library} required by {path.relative_to(root)}"
                )
    return dependencies


def verify_bundle(archive_path: str | os.PathLike[str]) -> dict[str, object]:
    """Extract, authenticate and audit a bundle without running target code."""
    archive_path = Path(archive_path)
    with tempfile.TemporaryDirectory(prefix="lpac-e750-verify-") as temporary:
        root = Path(temporary)
        safe_extract_tar(archive_path, root)
        required = (
            "usr/bin/lpac",
            "usr/lib/lpac/lpac",
            "usr/lib/lpac/driver/driver_apdu_at_csim.so",
            "usr/lib/lpac/driver/driver_http_curl.so",
            "usr/lib/lpac/etc/ssl/certs/ca-certificates-gsma.crt",
            "usr/lib/lpac/share/build-metadata.json",
        )
        for relative in required:
            path = root / relative
            if not path.is_file():
                raise VerificationError(f"bundle missing required payload: {relative}")
        for relative in ("usr/bin/lpac", "usr/lib/lpac/lpac"):
            if not os.access(root / relative, os.X_OK):
                raise VerificationError(f"bundle executable bit missing: {relative}")

        elf_paths = [
            path
            for path in sorted((root / "usr/lib/lpac").rglob("*"))
            if path.is_file() and not path.is_symlink() and path.read_bytes()[:4] == b"\x7fELF"
        ]
        for path in elf_paths:
            # Some leaf shared objects have no direct libc DT_NEEDED and thus
            # no literal musl string. The program interpreter and the closure
            # audit establish the ABI for those objects.
            require_musl = path == root / "usr/lib/lpac/lpac"
            inspect_elf(path, require_musl=require_musl)
        if not any(path.name == "lpac" for path in elf_paths):
            raise VerificationError("bundle lpac entry is not a MIPS ELF executable")

        at_driver = (root / "usr/lib/lpac/driver/driver_apdu_at_csim.so").read_bytes()
        for fingerprint in (
            b"LPAC_APDU_AT_HEX",
            b"at_expect_with_deadline",
            b"timerfd_create",
        ):
            if fingerprint not in at_driver:
                raise VerificationError(
                    f"AT driver binary fingerprint missing: {fingerprint.decode()}"
                )
        curl_driver = (root / "usr/lib/lpac/driver/driver_http_curl.so").read_bytes()
        for fingerprint in (b"LPAC_HTTP_SSL_VERIFY", b"LPAC_HTTP_CURL_CAINFO"):
            if fingerprint not in curl_driver:
                raise VerificationError(
                    f"curl driver binary fingerprint missing: {fingerprint.decode()}"
                )
        executable_payload = b"\0".join(path.read_bytes() for path in elf_paths)
        if b"LPAC_DRIVER_HOME" not in executable_payload:
            raise VerificationError("compiled LPAC_DRIVER_HOME fingerprint is missing")

        wrapper = (root / "usr/bin/lpac").read_bytes()
        for fingerprint in (
            b"LPAC_DRIVER_HOME=/usr/lib/lpac",
            b"LPAC_HTTP_CURL_CAINFO=/usr/lib/lpac/etc/ssl/certs/ca-certificates-gsma.crt",
            b"LD_LIBRARY_PATH=/usr/lib/lpac/lib",
            b"exec /usr/lib/lpac/lpac",
        ):
            if fingerprint not in wrapper:
                raise VerificationError(
                    f"launcher fingerprint missing: {fingerprint.decode(errors='replace')}"
                )
        trust = (root / "usr/lib/lpac/etc/ssl/certs/ca-certificates-gsma.crt").read_bytes()
        if b"WebPKI CA certificates" not in trust or b"GSMA CI certificates" not in trust:
            raise VerificationError("trust store must explicitly contain WebPKI plus GSMA CI")
        metadata = json.loads((root / "usr/lib/lpac/share/build-metadata.json").read_text())
        if metadata.get("abi") != "mips_24kc" or metadata.get("target") != "ath79/nand":
            raise VerificationError("bundle metadata target/architecture mismatch")
        dependencies = _audit_runtime(root, elf_paths)
        return {
            "archive": str(archive_path),
            "sha256": sha256_file(archive_path),
            "architecture": "mips32-msb-musl",
            "elf_count": len(elf_paths),
            "runtime_dependencies": dependencies,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    bundle = subparsers.add_parser("bundle", help="verify a completed lpac tar.gz")
    bundle.add_argument("archive", type=Path)
    elf = subparsers.add_parser("elf", help="verify one MIPS32 MSB musl ELF")
    elf.add_argument("file", type=Path)
    source = subparsers.add_parser("source", help="verify pinned lpac source fingerprints")
    source.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "bundle":
        result: object = verify_bundle(args.archive)
    elif args.command == "elf":
        result = inspect_elf(args.file, require_musl=True)
        result["dependencies"] = elf_dynamic_dependencies(args.file)
    else:
        verify_lpac_source(args.directory)
        result = {"source": str(args.directory), "fingerprints": "ok"}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
