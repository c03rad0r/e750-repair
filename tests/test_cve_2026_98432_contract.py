#!/usr/bin/env python3
"""Contract checks for the CVE-2026-98432 hardening."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_hardening_role_and_playbook_exist() -> None:
    for path in (
        "roles/bonding_hardening/defaults/main.yml",
        "roles/bonding_hardening/tasks/main.yml",
        "roles/bonding_hardening/handlers/main.yml",
        "playbook-bonding-servers-hardening.yml",
        "scripts/cve-2026-98432-check.sh",
        "docs/CVE-2026-98432.md",
    ):
        assert (ROOT / path).is_file(), path


def test_role_pins_the_patched_kernel_and_sysctls() -> None:
    tasks = read("roles/bonding_hardening/tasks/main.yml")
    for needle in (
        "net.ipv4.tcp_migrate_req=0",
        "net.ipv4.tcp_syncookies=1",
        "/boot/vmlinuz-*+deb13-*",
        "GRUB_DEFAULT",
    ):
        assert needle in tasks, needle
    handlers = read("roles/bonding_hardening/handlers/main.yml")
    assert "update-grub" in handlers
    defaults = read("roles/bonding_hardening/defaults/main.yml")
    assert "6.12.113" in defaults
    assert "6.18.56" in defaults


def test_check_script_has_the_fixed_versions() -> None:
    script = read("scripts/cve-2026-98432-check.sh")
    for version in ("6.12.113", "6.18.56", "6.1.190", "6.6.159"):
        assert version in script, version
    assert "sort -V" in script


def test_docs_correct_the_mptcp_only_claim() -> None:
    doc = read("docs/CVE-2026-98432.md")
    assert "Plain IPv4 TCP, not MPTCP-only" in doc
    assert "6.12.113" in doc
    assert "Hetzner bonding host" in doc
    assert "GL-E750" in doc
    assert "GL-MT6000" in doc
