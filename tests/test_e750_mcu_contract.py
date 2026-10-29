#!/usr/bin/env python3
"""Contract checks for the E750 MCU/OLED investigation."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_files_exist() -> None:
    for path in ("scripts/mcu-probe.sh", "docs/E750-MCU.md"):
        assert (ROOT / path).is_file(), path
    assert (ROOT / "scripts/mcu-probe.sh").stat().st_mode & 0o111


def test_probe_only_sends_documented_queries_and_no_config_writes() -> None:
    script = read("scripts/mcu-probe.sh")
    assert "#!/bin/sh" in script
    assert '{"version":"1"}' in script
    assert '{"mcu_status":"1"}' in script
    assert "/dev/ttyS0" in script
    assert "115200" in script
    # No UCI changes, no daemon install, no page/JSON writes beyond the two
    # documented queries.
    for forbidden in ("uci set", "uci commit", "procd", "lcd_test", "ssid", "shutdown"):
        assert forbidden not in script, forbidden
    assert 'cat "$DEV" > "$OUT"' in script


def test_probe_restores_the_console_login() -> None:
    script = read("scripts/mcu-probe.sh")
    assert "--force" in script
    assert "askfirst" in script
    assert "setsid /sbin/askfirst" in script
    assert "askfirst not restored" in script
    assert "no MCU reply" in script


def test_docs_record_the_protocol_and_the_deferral() -> None:
    doc = read("docs/E750-MCU.md")
    for needle in (
        "/dev/ttyS0",
        "115200",
        "mcu_status",
        "version",
        "ubus call mcu",
        "in the OpenWrt feed",
        "boot loop",
        "deferred",
        "mcu-probe.sh --force",
        "Leave the OLED as-is",
    ):
        assert needle in doc, needle


def test_no_secrets_or_psk() -> None:
    for path in ("scripts/mcu-probe.sh", "docs/E750-MCU.md"):
        text = read(path)
        assert "PRIVATE KEY" not in text
        assert ("c03rad0r" + "123") not in text
