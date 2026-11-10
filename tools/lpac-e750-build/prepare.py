#!/usr/bin/env python3
"""Download and atomically materialize checksum-pinned builder inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from verify import VerificationError, safe_extract_tar, sha256_file, verify_lpac_source, verify_sha256

STAMP_NAME = ".e750-source.json"


def tree_fingerprint(root: Path) -> str:
    """Hash source contents, executable bits and links, excluding our stamp."""
    digest = hashlib.sha256()
    entries = sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix())
    for path in entries:
        relative = path.relative_to(root).as_posix()
        if relative == STAMP_NAME:
            continue
        digest.update(relative.encode("utf-8") + b"\0")
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            digest.update(b"link\0" + os.readlink(path).encode() + b"\0")
        elif stat.S_ISDIR(info.st_mode):
            digest.update(b"directory\0")
        elif stat.S_ISREG(info.st_mode):
            digest.update(b"file\0" + str(stat.S_IMODE(info.st_mode)).encode() + b"\0")
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            digest.update(b"\0")
        else:
            raise VerificationError(f"unsupported source file type: {path}")
    return digest.hexdigest()


def download(source: dict[str, object], destination: Path) -> None:
    expected = str(source["sha256"])
    if destination.exists():
        verify_sha256(destination, expected)
        print(f"verified cached {destination.name}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + f".part.{os.getpid()}")
    try:
        subprocess.run(
            [
                "curl",
                "--proto",
                "=https",
                "--tlsv1.2",
                "--fail",
                "--location",
                "--retry",
                "3",
                "--output",
                str(partial),
                str(source["url"]),
            ],
            check=True,
        )
        verify_sha256(partial, expected)
        os.replace(partial, destination)
        print(f"downloaded and verified {destination.name}")
    finally:
        partial.unlink(missing_ok=True)


def extract_archive(name: str, archive: Path, destination: Path) -> None:
    if archive.name.endswith(".zst"):
        # Python <3.14 has no zstd tarfile backend. Decode only into our new
        # private extraction directory, then use the same safe tar validation.
        decoded = destination / "archive.tar"
        with decoded.open("wb") as stream:
            subprocess.run(["zstd", "--decompress", "--stdout", str(archive)], stdout=stream, check=True)
        safe_extract_tar(
            decoded,
            destination / "unpacked",
            # The official SDK has unnecessary absolute host-tool links.
            skip_absolute_symlinks=(name == "sdk"),
        )
        decoded.unlink()
    else:
        safe_extract_tar(archive, destination / "unpacked")


def materialize_source(
    name: str, source: dict[str, object], archive: Path, sources_dir: Path
) -> Path:
    destination = sources_dir / name
    stamp_path = destination / STAMP_NAME
    if destination.exists():
        if not stamp_path.is_file():
            raise VerificationError(
                f"unstamped existing source is not reusable: {destination}; move it away first"
            )
        stamp = json.loads(stamp_path.read_text())
        expected_identity = {
            "name": name,
            "revision": source["revision"],
            "archive_sha256": source["sha256"],
        }
        if any(stamp.get(key) != value for key, value in expected_identity.items()):
            raise VerificationError(f"source identity/stamp mismatch in {destination}")
        actual = tree_fingerprint(destination)
        if actual != stamp.get("tree_sha256"):
            raise VerificationError(
                f"dirty source tree rejected: {destination}; remove that workdir source to regenerate"
            )
        print(f"verified clean source {name} ({source['revision']})")
        return destination

    sources_dir.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{name}.extract.", dir=sources_dir))
    try:
        extract_archive(name, archive, temporary)
        unpacked = temporary / "unpacked"
        roots = list(unpacked.iterdir())
        if len(roots) != 1 or not roots[0].is_dir():
            raise VerificationError(f"{name} archive must contain exactly one source root")
        ready = temporary / "ready"
        os.rename(roots[0], ready)
        if name == "sdk":
            # OpenWrt SDKs contain a generated package-signing key. It is not
            # needed for compilation and must never enter this build or bundle.
            (ready / "private-key.pem").unlink(missing_ok=True)
        if name == "lpac":
            verify_lpac_source(ready)
        stamp = {
            "schema": 1,
            "name": name,
            "revision": source["revision"],
            "archive_sha256": source["sha256"],
            "tree_sha256": tree_fingerprint(ready),
        }
        (ready / STAMP_NAME).write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n")
        os.rename(ready, destination)
        print(f"extracted clean source {name} ({source['revision']})")
        return destination
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def prepare(manifest_path: Path, workdir: Path) -> None:
    manifest = json.loads(manifest_path.read_text())
    downloads = workdir / "downloads"
    sources = workdir / "src"
    for name, source in manifest["sources"].items():
        archive = downloads / source["filename"]
        download(source, archive)
        if source["archive"]:
            materialize_source(name, source, archive, sources)
    print(f"prepared and verified all pinned inputs under {workdir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--workdir", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.manifest.resolve(), args.workdir.resolve())


if __name__ == "__main__":
    main()
