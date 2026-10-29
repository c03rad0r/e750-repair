#!/usr/bin/env python3
"""Contract checks for the QCA9887 skip_otp experiment record."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_docs_and_evidence_exist() -> None:
    assert (ROOT / "docs/QCA9887-SKIP-OTP.md").is_file()
    assert (ROOT / "evidence/caldata/2026-10-29_skip-otp.md").is_file()
    roadmap = read("docs/ROADMAP.md")
    assert "QCA9887-SKIP-OTP.md" in roadmap


def test_docs_record_partial_success_and_instability() -> None:
    doc = read("docs/QCA9887-SKIP-OTP.md")
    for needle in (
        "skip_otp=1",
        "AP-ENABLED",
        "channel 36",
        "not stable",
        "failed to receive initialized event",
        "wireless.radio1.disabled=1",
        "no per-device calibration",
    ):
        assert needle.lower() in doc.lower(), needle


def test_no_secrets_or_psk() -> None:
    for path in (
        "docs/QCA9887-SKIP-OTP.md",
        "evidence/caldata/2026-10-29_skip-otp.md",
    ):
        text = read(path)
        assert "PRIVATE KEY" not in text
        assert ("c03rad0r" + "123") not in text
