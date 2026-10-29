#!/usr/bin/env python3
"""Contract checks for the gated TollGate standalone scripts."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_files_exist_and_are_executable() -> None:
    for path in (
        "scripts/tollgate-standalone-install.sh",
        "scripts/tollgate-standalone-rollback.sh",
        "docs/TOLLGATE-STANDALONE.md",
    ):
        assert (ROOT / path).is_file(), path
    for path in (
        "scripts/tollgate-standalone-install.sh",
        "scripts/tollgate-standalone-rollback.sh",
    ):
        assert (ROOT / path).stat().st_mode & 0o111


def test_install_refuses_without_the_gate() -> None:
    text = read("scripts/tollgate-standalone-install.sh")
    assert "--i-understand" in text
    assert "UNDERSTAND=0" in text
    assert "REFUSED: this layout is known unstable" in text
    assert "exit 2" in text
    # The gate must be checked before any download/install.
    assert text.index("if [ \"$UNDERSTAND\" -ne 1 ]") < text.index("curl -fL")


def test_install_pins_the_artifact_and_backs_up() -> None:
    text = read("scripts/tollgate-standalone-install.sh")
    assert "tollgate-wrt-0.6.0-mips_24kc-ath79-nand-offline.tar.gz" in text
    assert "bc5338ab88e9f79678aa63fdea7da9cbbc7e1ad53338fa572c2ab654ed00be7e" in text
    assert "sha256sum -c" in text
    assert "MANIFEST.sha256" in text
    assert "/tmp/tollgate-backup" in text
    assert "99z-mgmt-keepalive" in text
    assert "--trust-mac" in text
    assert "install-router.sh" in text


def test_rollback_restores_and_cleans_up() -> None:
    text = read("scripts/tollgate-standalone-rollback.sh")
    assert "cp \"$BACKUP/network\"" in text
    assert "cp \"$BACKUP/wireless\"" in text
    assert "cp \"$BACKUP/firewall\"" in text
    assert "uci -q delete uhttpd.portal" in text
    assert "uhttpd.main.listen_http='0.0.0.0:80'" in text
    assert "rm -f /etc/nftables.d/20-nds-enforce.nft" in text
    assert "/etc/init.d/firewall restart" in text
    assert "reboot" in text


def test_docs_record_the_attempt_and_the_next_topologies() -> None:
    doc = read("docs/TOLLGATE-STANDALONE.md")
    for needle in (
        "attempted 2026-10-29",
        "4G WAN + AP-only",
        "Ethernet WAN + AP-only",
        "Two-radio",
        "tollgate-standalone-rollback.sh",
        "evidence/tollgate/2026-10-29_standalone-attempt.txt",
    ):
        assert needle in doc, needle


def test_no_psk_or_private_key() -> None:
    for path in (
        "scripts/tollgate-standalone-install.sh",
        "scripts/tollgate-standalone-rollback.sh",
        "docs/TOLLGATE-STANDALONE.md",
    ):
        text = read(path)
        assert "PRIVATE KEY" not in text
        assert ("c03rad0r" + "123") not in text
