#!/usr/bin/env python3
"""Contract checks for the E750 network cleanup + health monitor."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_files_exist() -> None:
    for path in (
        "scripts/e750-health.sh",
        "roles/e750_network/defaults/main.yml",
        "roles/e750_network/tasks/main.yml",
        "roles/e750_health/defaults/main.yml",
        "roles/e750_health/tasks/main.yml",
        "playbook-e750-network-health.yml",
        "docs/E750-NETWORK-HEALTH.md",
    ):
        assert (ROOT / path).is_file(), path


def test_health_script_is_executable_and_checks_critical_paths() -> None:
    script = ROOT / "scripts/e750-health.sh"
    assert script.stat().st_mode & 0o111
    text = script.read_text()
    for needle in (
        "bsbf-bonding --status",
        "ip mp e",
        "bsbf_bonding",
        "ifstatus wwan1",
        "ifstatus wwan",
        "ifconfig.me",
        "radio1",
        "RESULT OK",
    ):
        assert needle in text, needle


def test_network_role_cleans_only_existing_wans() -> None:
    defaults = read("roles/e750_network/defaults/main.yml")
    tasks = read("roles/e750_network/tasks/main.yml")
    assert "e750_ap_enabled: false" in defaults
    assert "wwan" in defaults and "wwan1" in defaults
    assert "uci add_list firewall.$zone.network" in tasks
    assert "/etc/init.d/firewall reload" in tasks
    assert "Refuse to enable the AP" in tasks


def test_health_role_fails_on_critical_errors() -> None:
    tasks = read("roles/e750_health/tasks/main.yml")
    assert "ansible.builtin.raw" in tasks
    assert "failed_when: _e750_health.rc != 0" in tasks
    assert "lookup('file'" in tasks


def test_playbook_and_docs() -> None:
    playbook = read("playbook-e750-network-health.yml")
    assert "hosts: e750_ssh" in playbook
    assert "gather_facts: false" in playbook
    assert "e750_network" in playbook and "e750_health" in playbook
    doc = read("docs/E750-NETWORK-HEALTH.md")
    for needle in ("firewall", "br-lan", "5 GHz", "egress", "rollback"):
        assert needle in doc, needle


def test_no_secrets_or_psk() -> None:
    for path in (
        "scripts/e750-health.sh",
        "roles/e750_network/defaults/main.yml",
        "roles/e750_network/tasks/main.yml",
        "roles/e750_health/defaults/main.yml",
        "roles/e750_health/tasks/main.yml",
        "playbook-e750-network-health.yml",
        "docs/E750-NETWORK-HEALTH.md",
    ):
        text = read(path)
        assert "PRIVATE KEY" not in text
        assert ("c03rad0r" + "123") not in text
