#!/usr/bin/env python3
"""Contract checks for the checksummed serial exec tool."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_script_and_docs_exist() -> None:
    script = ROOT / "scripts/serial-exec.py"
    assert script.is_file()
    assert script.stat().st_mode & 0o111
    assert (ROOT / "docs/SERIAL-CHECKSUM.md").is_file()


def test_script_has_checksums_and_retransmit() -> None:
    text = read("scripts/serial-exec.py")
    for needle in (
        "hashlib.sha256",
        "sha256sum",
        "base64 -d",
        "payload hash mismatch",
        "retransmitting",
        "--dry-run",
        "--allow-dangerous",
        "--inject-error",
        "DANGEROUS",
        "__E750_OUT_BEGIN_",
        "output hash mismatch",
    ):
        assert needle in text, needle


def test_dangerous_commands_are_gated() -> None:
    text = read("scripts/serial-exec.py")
    for token in ("mtd ", "sysupgrade", "reboot", "fw_setenv", "nand", "ubiformat"):
        assert token in text, token
    doc = read("docs/SERIAL-CHECKSUM.md")
    assert "not authentication" in doc
    assert "U-Boot" in doc
    assert "loadx" in doc and "loady" in doc


def test_image_has_the_serial_tools() -> None:
    packages = read("image/packages.txt")
    assert "coreutils-base64" in packages
    assert "lrzsz" in packages
    assert "coreutils-base64" in read("docs/SERIAL-CHECKSUM.md")
    assert "lrzsz" in read("docs/SERIAL-CHECKSUM.md")


def test_roadmap_links_the_serial_channel() -> None:
    roadmap = read("docs/ROADMAP.md")
    assert "SERIAL-CHECKSUM.md" in roadmap
    assert "count 100" in roadmap or "Checksummed serial" in roadmap


def test_no_secrets_or_psk() -> None:
    for path in ("scripts/serial-exec.py", "docs/SERIAL-CHECKSUM.md"):
        text = read(path)
        assert "PRIVATE KEY" not in text
        assert ("c03rad0r" + "123") not in text
