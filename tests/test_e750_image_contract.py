#!/usr/bin/env python3
"""Contract checks for the clean E750 ImageBuilder recipe."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_files_exist() -> None:
    for path in (
        "image/packages.txt",
        "image/build.sh",
        "image/files/etc/uci-defaults/99-e750-defaults",
        "image/files/etc/dropbear/authorized_keys",
        "docs/E750-IMAGE.md",
    ):
        assert (ROOT / path).is_file(), path


def test_build_is_pinned_and_does_not_flash() -> None:
    build = read("image/build.sh")
    assert "25.12.5" in build
    assert "ath79/nand" in build
    assert "glinet_gl-e750" in build
    assert "IB_SHA256=" in build
    assert "sha256sum -c" in build
    assert "make" in build and "image" in build
    assert "sysupgrade -n" not in build
    assert "mtd write" not in build
    assert (ROOT / "image/build.sh").stat().st_mode & 0o111


def test_packages_cover_the_bsbf_stack() -> None:
    packages = read("image/packages.txt")
    for needle in (
        "bsbf-bonding",
        "bsbf-quectel-usbnet",
        "xray-core",
        "ip-full",
        "kmod-usb-net-cdc-mbim",
        "umbim",
        "kmod-nft-tproxy",
        "coreutils-stty",
        "picocom",
    ):
        assert needle in packages, needle


def test_image_has_no_secrets() -> None:
    uci = read("image/files/etc/uci-defaults/99-e750-defaults")
    assert "internet.eplus.de" in uci
    assert "192.168.8.1" in uci
    assert ("c03rad0r" + "123") not in uci
    assert "server_ipv4" not in uci
    assert "uuid=" not in uci.lower()
    keys = read("image/files/etc/dropbear/authorized_keys")
    assert "PRIVATE KEY" not in keys
    assert "ssh-ed25519" in keys
    assert (ROOT / "image/files/etc/dropbear/authorized_keys").stat().st_mode & 0o600


def test_uci_defaults_is_executable_and_documents_the_deferrals() -> None:
    uci = ROOT / "image/files/etc/uci-defaults/99-e750-defaults"
    assert uci.stat().st_mode & 0o111
    doc = read("docs/E750-IMAGE.md")
    for needle in ("does not flash", "serial", "OpenBao", "gl-e750-mcu", "TollGate"):
        assert needle in doc, needle
