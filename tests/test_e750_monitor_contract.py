#!/usr/bin/env python3
"""Contract checks for the E750 health monitor."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_files_exist() -> None:
    for path in (
        "scripts/e750-health.sh",
        "scripts/e750-health-cron.sh",
        "roles/e750_monitor/defaults/main.yml",
        "roles/e750_monitor/tasks/main.yml",
        "playbook-e750-monitor.yml",
        "docs/E750-MONITOR.md",
    ):
        assert (ROOT / path).is_file(), path


def test_scripts_are_executable_shell() -> None:
    for path in ("scripts/e750-health.sh", "scripts/e750-health-cron.sh"):
        p = ROOT / path
        assert p.stat().st_mode & 0o111
        assert p.read_text().startswith("#!/bin/sh")


def test_health_supports_quiet_cron_mode() -> None:
    text = read("scripts/e750-health.sh")
    assert '--quiet' in text
    assert 'QUIET=1' in text
    # In quiet mode only failures and the final RESULT FAIL are printed.
    assert 'bad() { printf' in text
    assert 'RESULT FAIL' in text
    # In quiet mode ok()/warn() must not return 1, or the &&/|| checks invert.
    assert "printf 'OK   %s\\n' \"$1\"; return 0" in text
    assert "printf 'WARN %s\\n' \"$1\"; return 0" in text


def test_cron_wrapper_logs_rotates_and_alerts() -> None:
    text = read("scripts/e750-health-cron.sh")
    assert "e750-health.log" in text
    assert "tail -n" in text
    assert "logger -t e750-health" in text
    assert 'exit "$rc"' in text


def test_role_installs_scripts_and_cron_idempotently() -> None:
    defaults = read("roles/e750_monitor/defaults/main.yml")
    tasks = read("roles/e750_monitor/tasks/main.yml")
    assert "*/5 * * * *" in defaults
    assert "/etc/crontabs/root" in defaults
    assert "ansible.builtin.raw" in tasks
    assert "ansible.builtin.shell" not in tasks
    assert "grep -q" in tasks
    assert "/etc/init.d/cron enable" in tasks
    assert "/etc/init.d/cron restart" in tasks
    assert "E750_HEALTH_SCRIPT_EOF" in tasks
    assert "test -s" in tasks


def test_playbook_and_docs() -> None:
    playbook = read("playbook-e750-monitor.yml")
    assert "hosts: e750_ssh" in playbook
    assert "gather_facts: false" in playbook
    assert "e750_monitor" in playbook
    doc = read("docs/E750-MONITOR.md")
    for needle in ("24 h soak", "/tmp/e750-health.log", "logread", "FAIL", "5 GHz"):
        assert needle in doc, needle


def test_no_secrets_or_psk() -> None:
    for path in (
        "scripts/e750-health.sh",
        "scripts/e750-health-cron.sh",
        "roles/e750_monitor/defaults/main.yml",
        "roles/e750_monitor/tasks/main.yml",
        "playbook-e750-monitor.yml",
        "docs/E750-MONITOR.md",
    ):
        text = read(path)
        assert "PRIVATE KEY" not in text
        assert ("c03rad0r" + "123") not in text
