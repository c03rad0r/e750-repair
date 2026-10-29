#!/usr/bin/env python3
"""Contract checks for the TollGate-on-E750 evaluation."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_docs_and_evidence_exist() -> None:
    assert (ROOT / "docs/E750-TOLLGATE.md").is_file()
    assert (ROOT / "evidence/tollgate/2026-10-29_asset-check.txt").is_file()


def test_evaluation_records_the_real_artifact_and_checksum() -> None:
    doc = read("docs/E750-TOLLGATE.md")
    assert "v0.6.0" in doc
    assert "tollgate-wrt-0.6.0-mips_24kc-ath79-nand-offline.tar.gz" in doc
    assert "bc5338ab88e9f79678aa63fdea7da9cbbc7e1ad53338fa572c2ab654ed00be7e" in doc
    assert "85.9M free" in doc
    assert "nodogsplash" in doc


def test_decision_is_explicit_and_reversible() -> None:
    doc = read("docs/E750-TOLLGATE.md")
    assert "no-go for this unit" in doc
    assert "Keep the E750 as the BSBF client" in doc
    assert "If someone proceeds anyway" in doc
    assert "scripts/e750-backup.sh" in doc
    assert "serial console" in doc


def test_no_secrets_or_psk() -> None:
    for path in ("docs/E750-TOLLGATE.md", "evidence/tollgate/2026-10-29_asset-check.txt"):
        text = read(path)
        assert "PRIVATE KEY" not in text
        assert ("c03rad0r" + "123") not in text
