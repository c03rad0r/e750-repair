#!/usr/bin/env python3
"""Contract tests for the BSBF client + server IaC. No hardware required."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_bsbf_files_exist() -> None:
    for path in (
        "playbook-bsbf-client.yml",
        "playbook-bsbf-server.yml",
        "inventory/e750-ssh.yml",
        "inventory/bsbf-servers.yml",
        "group_vars/bsbf_servers.yml",
        "roles/bsbf/defaults/main.yml",
        "roles/bsbf/tasks/main.yml",
        "roles/bsbf/files/bsbf-bonding-nft",
        "roles/verify_bsbf/tasks/main.yml",
        "roles/bsbf_server/tasks/main.yml",
        "roles/bsbf_server/defaults/main.yml",
        "roles/bsbf_server/handlers/main.yml",
        "docs/BSBF-BONDING.md",
        "docs/BSBF-SERVER.md",
    ):
        assert (ROOT / path).is_file(), path


def test_client_is_raw_and_python_free() -> None:
    playbook = read("playbook-bsbf-client.yml")
    assert "gather_facts: false" in playbook
    role = read("roles/bsbf/tasks/main.yml")
    assert "ansible.builtin.raw" in role
    assert "ansible.builtin.shell" not in role
    assert "ansible.builtin.command" not in role


def test_client_uses_apn_mbim_and_backup() -> None:
    defaults = read("roles/bsbf/defaults/main.yml")
    assert "internet.eplus.de" in defaults
    assert "kmod-usb-net-cdc-mbim" in defaults
    assert "kmod-nft-tproxy" in defaults
    assert "bsbf-bonding" in defaults
    assert "wwan0" in defaults
    tasks = read("roles/bsbf/tasks/main.yml")
    assert "network.{{ bsbf_cellular_uci }}.proto='mbim'" in tasks
    assert "bsbf-bonding --enable" in tasks
    assert "bsbf-mptcp-subflow-backup" in tasks
    assert "nft_tproxy" in tasks
    assert "ip mp e | grep" in tasks


def test_client_credentials_have_no_defaults() -> None:
    defaults = read("roles/bsbf/defaults/main.yml")
    assert 'bsbf_server_ipv4: ""' in defaults
    assert "bsbf_client_uuid: \"\"" in defaults
    playbook = read("playbook-bsbf-client.yml")
    assert "bsbf_server_ipv4 | length > 0" in playbook
    assert "bsbf_client_uuid | length > 0" in playbook


def test_server_is_pinned_and_checksummed() -> None:
    group = read("group_vars/bsbf_servers.yml")
    defaults = read("roles/bsbf_server/defaults/main.yml")
    tasks = read("roles/bsbf_server/tasks/main.yml")
    for text in (group, defaults):
        assert re.search(r'bsbf_server_commit: "[0-9a-f]{40}"', text)
        assert re.search(r'bsbf_server_installer_sha256: "[0-9a-f]{64}"', text)
    assert "checksum: \"sha256:{{ bsbf_server_installer_sha256 }}\"" in tasks
    assert "ufw allow" in tasks
    assert "bsbf-mptcp-configuration.service.d" in tasks
    assert "state/bsbf" in group
    assert "bsbf_server_credentials_dir" in tasks


def test_verify_refuses_a_false_pass() -> None:
    verify = read("roles/verify_bsbf/tasks/main.yml")
    assert "tproxy" in verify
    assert "backup dev" in verify
    assert "ifconfig.me" in verify
    assert "_vbsbf_egress.stdout | trim == bsbf_server_ipv4" in verify


def test_no_credentials_are_committed() -> None:
    gitignore = read(".gitignore")
    assert "state/bsbf" in gitignore
    scan = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix not in {".yml", ".yaml", ".md", ".py", ".sh", ".txt"}:
            continue
        scan.append(path)
    for path in scan:
        text = path.read_text(errors="ignore")
        assert not UUID_RE.search(text), f"UUID-shaped string in {path}"
        assert ("c03rad0r" + "123") not in text, f"hardcoded STA PSK in {path}"


def test_docs_cover_topology_and_caveats() -> None:
    client_doc = read("docs/BSBF-BONDING.md")
    for needle in (
        "192.168.8.1",
        "hermes-lan",
        "internet.eplus.de",
        "backup",
        "5 GHz",
        "Rollback",
    ):
        assert needle in client_doc, needle
    server_doc = read("docs/BSBF-SERVER.md")
    for needle in ("16384", "hermes-nvme", "ufw", "uninstall", "AGPL"):
        assert needle in server_doc, needle


def test_playbooks_target_the_right_groups() -> None:
    assert "hosts: e750_ssh" in read("playbook-bsbf-client.yml")
    assert "hosts: bsbf_servers" in read("playbook-bsbf-server.yml")
    assert "name: bsbf" in read("playbook-bsbf-client.yml")
    assert "name: verify_bsbf" in read("playbook-bsbf-client.yml")
    assert "role: bsbf_server" in read("playbook-bsbf-server.yml")
