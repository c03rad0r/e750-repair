#!/usr/bin/env python3
"""Contract checks for the E750 br-lan + AP+STA role."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_files_exist() -> None:
    for path in (
        "roles/e750_ap/defaults/main.yml",
        "roles/e750_ap/tasks/main.yml",
        "playbook-e750-ap.yml",
        "playbook-e750-ap-confirm.yml",
        "playbook-e750-ap-rollback.yml",
        "docs/E750-AP.md",
    ):
        assert (ROOT / path).is_file(), path


def test_defaults_are_safe() -> None:
    defaults = read("roles/e750_ap/defaults/main.yml")
    assert 'e750_ap_ssid: "TollGate-E750"' in defaults
    assert 'e750_ap_encryption: "none"' in defaults
    assert 'e750_ap_key: ""' in defaults
    assert 'e750_ap_channel: "11"' in defaults
    assert "e750_ap_watchdog_seconds: 600" in defaults
    assert "e750_ap_confirm_file" in defaults
    assert "e750_ap_backup_dir" in defaults
    assert ("c03rad0r" + "123") not in defaults


def test_role_uses_raw_and_builds_the_bridge_and_ap() -> None:
    tasks = read("roles/e750_ap/tasks/main.yml")
    assert "ansible.builtin.raw" in tasks
    assert "ansible.builtin.shell" not in tasks
    assert "network.brlan" in tasks
    assert "network.brlan.ports='eth0'" in tasks
    assert "network.lan.device='br-lan'" in tasks
    assert "uci -q delete network.lan.type || true" in tasks
    assert "uci -q delete wireless.default_radio0.key || true" in tasks
    assert "wireless.default_radio0.mode='ap'" in tasks
    assert "wireless.default_radio0.network='lan'" in tasks
    assert "wireless.sta.ssid" in tasks
    assert "wireless.default_radio0.macaddr" in tasks
    assert "wireless.radio0.beacon_int" in tasks
    assert "wifi down" in tasks and "wifi up" in tasks
    assert "/etc/init.d/firewall reload" in tasks
    assert "hostapd" in tasks


def test_watchdog_is_armed_before_reload_and_reverts() -> None:
    tasks = read("roles/e750_ap/tasks/main.yml")
    assert "Arm the watchdog rollback" in tasks
    assert tasks.index("Arm the watchdog rollback") < tasks.index("Reload network, restart wireless")
    assert "cp {{ e750_ap_backup_dir }}/network /etc/config/network" in tasks
    assert "cp {{ e750_ap_backup_dir }}/wireless /etc/config/wireless" in tasks
    assert "cp {{ e750_ap_backup_dir }}/firewall /etc/config/firewall" in tasks
    assert "e750-ap \"watchdog reverted" in tasks
    assert "The change is NOT confirmed yet" in tasks


def test_confirm_and_rollback_are_wired_to_the_same_paths() -> None:
    for path in ("playbook-e750-ap-confirm.yml", "playbook-e750-ap-rollback.yml"):
        text = read(path)
        assert "vars_files:" in text
        assert "roles/e750_ap/defaults/main.yml" in text
    confirm = read("playbook-e750-ap-confirm.yml")
    assert "touch {{ e750_ap_confirm_file }}" in confirm
    rollback = read("playbook-e750-ap-rollback.yml")
    assert "test -f {{ e750_ap_backup_dir }}/network" in rollback
    assert "rm -f {{ e750_ap_confirm_file }}" in rollback


def test_no_secrets_or_psk() -> None:
    for path in (
        "roles/e750_ap/defaults/main.yml",
        "roles/e750_ap/tasks/main.yml",
        "playbook-e750-ap.yml",
        "playbook-e750-ap-confirm.yml",
        "playbook-e750-ap-rollback.yml",
        "docs/E750-AP.md",
    ):
        text = read(path)
        assert "PRIVATE KEY" not in text
        assert ("c03rad0r" + "123") not in text
