#!/usr/bin/env python3
"""Contract checks for the controller-side soak harness."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_script_exists_and_is_executable() -> None:
    p = ROOT / "scripts/e750-soak.sh"
    assert p.is_file()
    assert p.stat().st_mode & 0o111
    assert p.read_text().startswith("#!/bin/sh")


def test_soak_is_read_only_and_records_a_summary() -> None:
    text = (ROOT / "scripts/e750-soak.sh").read_text()
    assert "/usr/bin/e750-health --quiet" in text
    assert "e750 soak start" in text
    assert "e750 soak end" in text
    assert "ssh_failed" in text
    assert "ok=$ok fail=$fail" in text
    # No config writes or service changes.
    for forbidden in ("uci set", "reboot", "sysupgrade", "iptables", "nft "):
        assert forbidden not in text, forbidden


def test_defaults_are_24h_and_5_minutes() -> None:
    text = (ROOT / "scripts/e750-soak.sh").read_text()
    assert 'HOURS="${1:-24}"' in text
    assert 'INTERVAL="${2:-300}"' in text
    assert "HOURS * 3600 / INTERVAL" in text
