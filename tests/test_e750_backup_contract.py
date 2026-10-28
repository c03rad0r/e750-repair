#!/usr/bin/env python3
"""Contract checks for the private E750 backup script."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/e750-backup.sh"


def test_backup_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111


def test_backup_is_private_and_covers_the_radio_state() -> None:
    text = SCRIPT.read_text()
    for needle in (
        "/dev/mtd1",
        "/dev/mtd2",
        "uci export",
        "/lib/firmware/ath10k",
        "/etc/dropbear/authorized_keys",
        "/root/.ssh/authorized_keys",
        "umask 077",
        "$HOME/.local/share",
    ):
        assert needle in text, needle


def test_backup_is_not_written_into_the_repo() -> None:
    text = SCRIPT.read_text()
    assert "evidence/" not in text
    assert "docs/" not in text
