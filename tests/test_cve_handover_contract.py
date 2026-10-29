#!/usr/bin/env python3
"""Contract checks for the CVE handover briefing."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_handover_is_self_contained() -> None:
    doc = read("docs/HANDOVER-CVE-2026-98432.md")
    for needle in (
        "TL;DR",
        "Fleet status",
        "Pending work",
        "Verification",
        "Access notes",
        "Guardrails",
        "Handoff prompt",
        "6.12.113",
        "6.18.56",
        "7.0.0-43.43",
        "6.8.0-149.149",
        "playbook-bonding-servers-hardening.yml",
    ):
        assert needle in doc, needle


def test_handover_names_every_host_we_checked() -> None:
    doc = read("docs/HANDOVER-CVE-2026-98432.md")
    for host in (
        "hermes-nvme",
        "testserver2",
        "cax11",
        "t14",
        "cobrador",
        "x280",
        "t440",
        "dq05",
        "GL-E750",
        "GL-MT6000",
    ):
        assert host in doc, host


def test_readme_links_it() -> None:
    assert "HANDOVER-CVE-2026-98432.md" in read("README.md")
