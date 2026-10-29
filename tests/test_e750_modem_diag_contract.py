#!/usr/bin/env python3
"""Contract checks for the read-only E750 4G diagnostics."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_files_exist() -> None:
    for path in (
        "scripts/e750-modem-diag.sh",
        "roles/e750_modem_diag/defaults/main.yml",
        "roles/e750_modem_diag/tasks/main.yml",
        "playbook-e750-modem-diag.yml",
        "docs/E750-MODEM-DIAG.md",
    ):
        assert (ROOT / path).is_file(), path


def test_script_is_read_only_and_has_no_identity_queries() -> None:
    script = read("scripts/e750-modem-diag.sh")
    assert (ROOT / "scripts/e750-modem-diag.sh").stat().st_mode & 0o111
    for needle in ("AT+CPIN?", "AT+COPS?", "AT+QCSQ", "AT+QENG", "AT+CGDCONT?", "umbim"):
        assert needle in script, needle
    # Never query IMSI/ICCID or change modem state.
    for forbidden in ("subscriber", "AT+CIMI", "AT+QCCID", "AT+CGDCONT=", "AT+CFUN=", "AT+QCFG="):
        assert forbidden not in script, forbidden
    assert "wifi status" not in script


def test_no_secrets_or_psk() -> None:
    for path in (
        "scripts/e750-modem-diag.sh",
        "roles/e750_modem_diag/defaults/main.yml",
        "roles/e750_modem_diag/tasks/main.yml",
        "playbook-e750-modem-diag.yml",
        "docs/E750-MODEM-DIAG.md",
    ):
        text = read(path)
        assert ("c03rad0r" + "123") not in text
        assert "PRIVATE KEY" not in text


def test_role_is_raw_and_installs_stty() -> None:
    defaults = read("roles/e750_modem_diag/defaults/main.yml")
    tasks = read("roles/e750_modem_diag/tasks/main.yml")
    assert "coreutils-stty" in defaults
    assert "picocom" in defaults
    assert "ansible.builtin.raw" in tasks
    assert "lookup('file'" in tasks
    assert "gather_facts: false" in read("playbook-e750-modem-diag.yml")
