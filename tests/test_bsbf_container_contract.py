#!/usr/bin/env python3
"""Contract checks for the BSBF container on the OMR host."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_container_role_and_playbooks_exist() -> None:
    for path in (
        "roles/bsbf_container/defaults/main.yml",
        "roles/bsbf_container/tasks/main.yml",
        "roles/bsbf_container/templates/bsbf.nft.j2",
        "roles/bsbf_container/templates/bsbf1.nspawn.j2",
        "roles/bsbf_container/templates/bsbf-net.sh.j2",
        "roles/bsbf_container/templates/bsbf-nft-apply.sh.j2",
        "roles/bsbf_container/templates/10-host0.network.j2",
        "playbook-bonding-servers.yml",
        "playbook-bonding-servers-verify.yml",
        "playbook-bonding-servers-rollback.yml",
        "docs/BONDING-SERVERS-PARALLEL.md",
    ):
        assert (ROOT / path).is_file(), path


def test_role_is_isolated_from_omr() -> None:
    tasks = read("roles/bsbf_container/tasks/main.yml")
    for needle in (
        "systemd-nspawn@",
        "mmdebstrap",
        "bsbf_container_bridge",
        "nft list table inet omr",
        "OMR is not healthy",
    ):
        assert needle in tasks, needle
    # The installer's destructive host operations must never appear here.
    for forbidden in ("systemctl stop xray", "systemctl disable --quiet xray"):
        assert forbidden not in tasks


def test_nft_rules_hit_the_omr_chain_and_never_flush_it() -> None:
    nft = read("roles/bsbf_container/templates/bsbf.nft.j2")
    assert "inet omr forward" in nft
    assert "insert rule" in nft
    assert "dnat to" in nft
    assert "masquerade" in nft
    assert "flush ruleset" not in nft
    helper = read("roles/bsbf_container/templates/bsbf-nft-apply.sh.j2")
    assert "nft -f /etc/nftables/custom.d/bsbf.nft" in helper
    assert "inet omr forward" in helper
    assert "nft -f /etc/nftables.conf" not in helper


def test_inventory_carries_both_server_types() -> None:
    inv = read("inventory/bsbf-servers.yml")
    for needle in (
        "hermes-nvme",
        "hermes-hel1:",
        "10.77.0.2",
        "ProxyJump=hermes-deploy@167.235.218.44:65222",
        "bsbf_container_hosts",
        "mptcp_servers",
    ):
        assert needle in inv, needle


def test_rollback_leaves_omr_alone() -> None:
    rb = read("playbook-bonding-servers-rollback.yml")
    assert "systemd-nspawn@bsbf1.service" in rb
    assert "inet omr forward" in rb
    assert "nft delete table ip bsbf_nat" in rb
    assert "systemctl stop omr" not in rb
    assert "systemctl restart omr" not in rb


def test_no_secrets_in_git() -> None:
    for path in (
        "inventory/bsbf-servers.yml",
        "playbook-bonding-servers.yml",
        "roles/bsbf_container/tasks/main.yml",
    ):
        text = read(path)
        assert "PRIVATE KEY" not in text


def test_health_expects_the_configured_server() -> None:
    script = read("scripts/e750-health.sh")
    assert "/etc/e750/expected-egress" in script
    tasks = read("roles/bsbf/tasks/main.yml")
    assert "expected-egress" in tasks
    assert "bsbf_server_ipv4" in tasks
