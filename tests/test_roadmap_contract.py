#!/usr/bin/env python3
"""Contract checks for the consolidated roadmap."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_roadmap_exists_and_links_the_trackers() -> None:
    doc = read("docs/ROADMAP.md")
    for needle in (
        "E750-REMEDIATION.md",
        "BSBF-TOLLGATE-COEXISTENCE.md",
        "P0",
        "P1",
        "P2",
        "Inputs needed from the operator",
        "definition of done",
        "serial adapter",
        "5 GHz",
        "TollGate",
        "OpenBao",
    ):
        assert needle in doc, needle


def test_roadmap_records_the_current_combined_mode() -> None:
    doc = read("docs/ROADMAP.md")
    for needle in (
        "br-portal",
        "10.0.0.1",
        "tproxy bypass",
        "HTTP 301",
        "24 h combined soak",
        "2026-10-29T17:09:40Z",
    ):
        assert needle in doc, needle


def test_readme_and_remediation_link_the_roadmap() -> None:
    assert "docs/ROADMAP.md" in read("README.md")
    assert "ROADMAP.md" in read("docs/E750-REMEDIATION.md")
