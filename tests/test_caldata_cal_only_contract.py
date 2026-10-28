#!/usr/bin/env python3
"""Contract tests for the cal-pci-only experiment. No hardware required."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_files_exist() -> None:
    for path in (
        "roles/caldata_cal_only/defaults/main.yml",
        "roles/caldata_cal_only/tasks/main.yml",
        "roles/verify_cal_only/tasks/main.yml",
        "playbook-cal-only.yml",
        "playbook-cal-only-revert.yml",
        "playbook-cal-only-verify.yml",
        "docs/CALDATA-CAL-ONLY.md",
        "docs/E750-REMEDIATION.md",
    ):
        assert (ROOT / path).is_file(), path


def test_offsets_and_magic_match_the_device() -> None:
    defaults = read("roles/caldata_cal_only/defaults/main.yml")
    assert "caldata_offset: 20480" in defaults       # 0x5000
    assert "caldata_length: 1088" in defaults        # 0x440
    assert "44081ba80401" in defaults
    assert "9483c44dfc3a" in defaults
    assert "cal-pci-{{ ath10k_bdf }}.bin" in defaults


def test_only_cal_pci_is_installed() -> None:
    tasks = read("roles/caldata_cal_only/tasks/main.yml")
    assert "cp \"{{ caldata_scratch }}\" \"{{ ath10k_fw_dir }}/{{ caldata_pci_name }}\"" in tasks
    # The pre-cal name may appear only in backup/removal checks, never as a copy
    # destination from the scratch blob.
    assert "cp \"{{ caldata_scratch }}\" \"{{ ath10k_fw_dir }}/{{ caldata_precal_name }}\"" not in tasks
    assert "11-ath10k-caldata" not in tasks
    assert "test ! -e" in tasks


def test_playbooks_are_raw_and_python_free() -> None:
    for path in ("playbook-cal-only.yml", "playbook-cal-only-revert.yml"):
        text = read(path)
        assert "gather_facts: false" in text
        assert "ansible.builtin.raw" in text
        assert "ansible.builtin.shell" not in text
    assert "gather_facts: false" in read("playbook-cal-only-verify.yml")
    assert "ANSIBLE" not in read("playbook-cal-only.yml")


def test_negative_result_is_reported_not_hidden() -> None:
    experiment = read("playbook-cal-only.yml")
    verify_only = read("playbook-cal-only-verify.yml")
    assert "rescue:" in experiment
    assert "rescue:" in verify_only
    assert "any_errors_fatal: true" not in experiment


def test_verify_refuses_a_false_pass() -> None:
    verify = read("roles/verify_cal_only/tasks/main.yml")
    assert "'-22' not in _cal_dmesg.stdout" in verify
    assert "'-122' not in _cal_dmesg.stdout" in verify
    assert "'radio1' in _cal_wifi.stdout" in verify
    assert "do not report this as a fix" in verify


def test_no_secrets_or_psk() -> None:
    for path in (
        "roles/caldata_cal_only/defaults/main.yml",
        "roles/caldata_cal_only/tasks/main.yml",
        "roles/verify_cal_only/tasks/main.yml",
        "playbook-cal-only.yml",
        "playbook-cal-only-revert.yml",
        "playbook-cal-only-verify.yml",
        "docs/CALDATA-CAL-ONLY.md",
        "docs/E750-REMEDIATION.md",
    ):
        text = read(path)
        assert ("c03rad0r" + "123") not in text
