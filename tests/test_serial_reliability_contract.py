#!/usr/bin/env python3
"""Contract checks for the serial reliability tools and runbook."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_files_exist() -> None:
    for path in (
        "scripts/serial-tx-test.py",
        "scripts/serial-wake.py",
        "docs/SERIAL-RELIABILITY.md",
    ):
        assert (ROOT / path).is_file(), path


def test_scripts_are_executable_python() -> None:
    for path in ("scripts/serial-tx-test.py", "scripts/serial-wake.py"):
        p = ROOT / path
        assert p.stat().st_mode & 0o111
        assert p.read_text().startswith("#!/usr/bin/env python3")


def test_tx_test_checks_echo_and_output() -> None:
    text = read("scripts/serial-tx-test.py")
    assert "out.count(nonce) >= 2" in text
    assert "wake_output" in text
    assert "summary clean=" in text


def test_wake_tool_sends_cr_burst_and_retries() -> None:
    text = read("scripts/serial-wake.py")
    assert "for _ in range(args.crs)" in text
    assert "for attempt in range(1, args.retries + 1)" in text
    assert "kill line" in text


def test_no_secrets_or_psk() -> None:
    for path in (
        "scripts/serial-tx-test.py",
        "scripts/serial-wake.py",
        "docs/SERIAL-RELIABILITY.md",
    ):
        text = read(path)
        assert "PRIVATE KEY" not in text
        assert ("c03rad0r" + "123") not in text


def test_docs_capture_the_adapter_finding() -> None:
    doc = read("docs/SERIAL-RELIABILITY.md")
    for needle in ("BH00DL3M", "BG046H5F", "askfirst", "3.3 V", "loopback"):
        assert needle in doc, needle
