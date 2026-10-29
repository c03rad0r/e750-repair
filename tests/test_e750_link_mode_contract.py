#!/usr/bin/env python3
"""Contract checks for the link-mode controller and portal branding."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_scripts_and_role_exist() -> None:
    for path in (
        "scripts/e750-path-metrics.sh",
        "scripts/e750-link-mode.sh",
        "roles/e750_link_mode/defaults/main.yml",
        "roles/e750_link_mode/tasks/main.yml",
        "roles/e750_link_mode/templates/e750_linkmode.j2",
        "playbook-e750-link-mode.yml",
        "roles/e750_portal_brand/defaults/main.yml",
        "roles/e750_portal_brand/tasks/main.yml",
        "playbook-e750-portal-brand.yml",
    ):
        assert (ROOT / path).is_file(), path


def test_controller_is_observe_only_and_has_hysteresis() -> None:
    defaults = read("roles/e750_link_mode/defaults/main.yml")
    assert "e750_link_mode_enabled: 0" in defaults
    assert "e750_link_mode_observe_only: 1" in defaults
    assert "dwell" in defaults
    script = read("scripts/e750-link-mode.sh")
    for needle in (
        "rtt_ratio_enter",
        "rtt_ratio_exit",
        "dwell_seconds",
        "bsbf-mptcp-helper",
        "bond.json",
    ):
        assert needle in script, needle


def test_metrics_cover_the_documented_inputs() -> None:
    script = read("scripts/e750-path-metrics.sh")
    for needle in (
        "sta_rtt",
        "wwan_rtt",
        "sta_loss",
        "cpu_idle",
        "load1",
        "conntrack",
        "sta_signal",
    ):
        assert needle in script, needle


def test_branding_is_separate_from_networking() -> None:
    tasks = read("roles/e750_portal_brand/tasks/main.yml")
    assert "gatewayname" in tasks
    assert "html_title" in tasks
    assert "bond-badge" in tasks
    for forbidden in ("brportal", "radio0", "radio1", "bsbf-bonding"):
        assert forbidden not in tasks, forbidden
