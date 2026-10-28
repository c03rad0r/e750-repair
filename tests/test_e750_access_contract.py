#!/usr/bin/env python3
"""Contract checks for the E750 operator-key access role."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_files_exist() -> None:
    for path in (
        "roles/e750_access/defaults/main.yml",
        "roles/e750_access/tasks/main.yml",
        "playbook-e750-access.yml",
        "docs/E750-ACCESS.md",
    ):
        assert (ROOT / path).is_file(), path


def test_role_is_raw_and_preserves_existing_keys() -> None:
    role = read("roles/e750_access/tasks/main.yml")
    assert "ansible.builtin.raw" in role
    assert "ansible.builtin.shell" not in role
    assert "sort -u" in role
    assert "chmod 600" in role
    assert "lookup('file', item)" in role
    assert "base64" not in role
    # Never truncate the live authorized_keys directly.
    assert "> {{ e750_dropbear_keys }}" not in role
    assert "mv /tmp/e750-authorized_keys" in role


def test_no_private_material_is_used() -> None:
    for path in (
        "roles/e750_access/defaults/main.yml",
        "roles/e750_access/tasks/main.yml",
        "playbook-e750-access.yml",
        "docs/E750-ACCESS.md",
    ):
        text = read(path)
        assert "PRIVATE KEY" not in text
        assert ("c03rad0r" + "123") not in text


def test_playbook_is_python_free_and_targets_the_e750() -> None:
    playbook = read("playbook-e750-access.yml")
    assert "hosts: e750_ssh" in playbook
    assert "gather_facts: false" in playbook
    assert "e750_access" in playbook
