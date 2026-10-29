#!/usr/bin/env python3
"""Contract checks for the separate portal bridge role."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_files_exist() -> None:
    for path in (
        "roles/e750_portal/defaults/main.yml",
        "roles/e750_portal/tasks/main.yml",
        "playbook-e750-portal.yml",
        "playbook-e750-portal-confirm.yml",
        "playbook-e750-portal-rollback.yml",
        "docs/E750-PORTAL.md",
    ):
        assert (ROOT / path).is_file(), path


def test_defaults_separate_management_and_portal() -> None:
    defaults = read("roles/e750_portal/defaults/main.yml")
    assert 'e750_portal_bridge: "br-portal"' in defaults
    assert 'e750_portal_ip: "10.0.0.1"' in defaults
    assert 'e750_portal_ssid: "TollGate-E750"' in defaults
    assert "e750_portal_watchdog_seconds: 900" in defaults
    assert "e750_portal_confirm_file" in defaults
    assert ("c03rad0r" + "123") not in defaults


def test_role_does_not_touch_management_lan_or_sta() -> None:
    tasks = read("roles/e750_portal/tasks/main.yml")
    assert "ansible.builtin.raw" in tasks
    assert "ansible.builtin.shell" not in tasks
    assert "network.brportal" in tasks
    assert "network.portal.ipaddr" in tasks
    assert "wireless.default_radio0.network='portal'" in tasks
    # Must not move the management LAN or disable the STA.
    assert "network.lan.device" not in tasks
    assert "wireless.sta.disabled='1'" not in tasks
    assert "wifi down" in tasks and "wifi up" in tasks


def test_watchdog_and_confirm_rollback() -> None:
    tasks = read("roles/e750_portal/tasks/main.yml")
    assert "Arm the watchdog" in tasks
    assert tasks.index("Arm the watchdog") < tasks.index("Reload and restart wireless")
    assert "e750-portal \"watchdog reverted" in tasks
    assert "NOT confirmed" in tasks
    for path in ("playbook-e750-portal-confirm.yml", "playbook-e750-portal-rollback.yml"):
        assert "vars_files:" in read(path)
        assert "roles/e750_portal/defaults/main.yml" in read(path)
    assert "touch {{ e750_portal_confirm_file }}" in read("playbook-e750-portal-confirm.yml")
    assert "rm -f {{ e750_portal_confirm_file }}" in read("playbook-e750-portal-rollback.yml")


def test_docs_record_the_result_and_rollback() -> None:
    doc = read("docs/E750-PORTAL.md")
    for needle in (
        "br-portal",
        "10.0.0.1",
        "TollGate v0.6.0 daemon started successfully",
        "nodogsplash",
        "500",
        "rolled back",
        "evidence/portal/2026-10-29_bridge-test.txt",
        "Do not leave the open AP running without enforcement",
    ):
        assert needle in doc, needle


def test_no_secrets_or_psk() -> None:
    for path in (
        "roles/e750_portal/defaults/main.yml",
        "roles/e750_portal/tasks/main.yml",
        "playbook-e750-portal.yml",
        "playbook-e750-portal-confirm.yml",
        "playbook-e750-portal-rollback.yml",
        "docs/E750-PORTAL.md",
    ):
        text = read(path)
        assert "PRIVATE KEY" not in text
        assert ("c03rad0r" + "123") not in text
