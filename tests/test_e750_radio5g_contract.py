#!/usr/bin/env python3
"""Contract checks for the 5 GHz portal role."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_files_exist() -> None:
    for path in (
        "roles/e750_radio5g/defaults/main.yml",
        "roles/e750_radio5g/tasks/main.yml",
        "playbook-e750-radio5g.yml",
        "playbook-e750-radio5g-verify.yml",
        "playbook-e750-radio5g-rollback.yml",
        "docs/E750-RADIO5G.md",
    ):
        assert (ROOT / path).is_file(), path


def test_role_uses_skip_otp_and_5g_ap() -> None:
    tasks = read("roles/e750_radio5g/tasks/main.yml")
    for needle in (
        "ath10k-skip-otp",
        "skip_otp=1",
        "START=19",
        "wireless.radio1",
        "channel='{{ e750_radio5g_channel }}'",
        "wireless.default_radio1.network='{{ e750_radio5g_network }}'",
        "wireless.default_radio0.disabled='1'",
        "reboot",
    ):
        assert needle in tasks, needle
    defaults = read("roles/e750_radio5g/defaults/main.yml")
    assert 'e750_radio5g_ssid: "TollGate-E750"' in defaults
    assert 'e750_radio5g_channel: "36"' in defaults
    assert "e750_radio5g_txpower: \"10\"" in defaults


def test_verify_and_rollback_are_wired() -> None:
    verify = read("playbook-e750-radio5g-verify.yml")
    assert "skip_otp" in verify
    assert "TollGate-E750" in verify
    assert "hermes-lan" in verify
    rollback = read("playbook-e750-radio5g-rollback.yml")
    assert "wireless.radio1.disabled='1'" in rollback
    assert "ath10k-skip-otp disable" in rollback
    assert "default_radio0.disabled='0'" in rollback


def test_docs_record_calibration_caveat_and_client_test() -> None:
    doc = read("docs/E750-RADIO5G.md")
    for needle in (
        "skip_otp=1",
        "no per-device calibration",
        "txpower 10",
        "br-portal",
        "Real 5 GHz client",
        "evidence/caldata/2026-10-29_skip-otp-boot.txt",
    ):
        assert needle in doc, needle
    roadmap = read("docs/ROADMAP.md")
    assert "E750-RADIO5G.md" in roadmap


def test_no_secrets_or_psk() -> None:
    for path in (
        "roles/e750_radio5g/defaults/main.yml",
        "roles/e750_radio5g/tasks/main.yml",
        "playbook-e750-radio5g.yml",
        "playbook-e750-radio5g-verify.yml",
        "playbook-e750-radio5g-rollback.yml",
        "docs/E750-RADIO5G.md",
    ):
        text = read(path)
        assert "PRIVATE KEY" not in text
        assert ("c03rad0r" + "123") not in text
