#!/usr/bin/env python3
"""Safety and integration checks for the host-side E750 activation script."""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/e750-esim-activate.sh"

FAKE_SSH = r"""#!/bin/sh
printf '%s\n' "$*" >> "$FAKE_SSH_ARGV"
cmd=
for a in "$@"; do cmd=$a; done
case "$cmd" in
  *"/tmp/sysinfo/board_name"*) echo glinet,gl-e750 ;;
  *"e750-esim port"*) echo /dev/ttyUSB3 ;;
  *"e750-esim chip info"*)
    echo "EID: 89000000000000000000000000000000"
    echo "testProfileSupport: true"
    ;;
  *"e750-esim profile list"*)
    echo "ICCID: 8944000000000000000"
    echo "State: disabled"
    ;;
  *"e750-esim notification list"*) echo "no notifications" ;;
  *"profile download"*)
    cat >> "$FAKE_SSH_STDIN"
    echo "ICCID: 8944000000000000001"
    echo "download: OK"
    ;;
  *"profile enable"*) echo "enable: OK" ;;
  *"ifstatus"*) echo '{"up": true}' ;;
  *"uci -q get"*) echo internet ;;
  *"uci set"*) : ;;
  *"test -x /usr/bin/e750-esim"*) exit 0 ;;
  *"test -x /usr/bin/e750-modem-diag.sh"*) exit 0 ;;
  *) : ;;
esac
"""


def make_env(tmp: Path) -> dict[str, str]:
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "ssh"
    fake.write_text(FAKE_SSH)
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["E750_ESIM_STATE_DIR"] = str(tmp / "state")
    env["E750_SSH_KEY"] = str(tmp / "key")
    env["FAKE_SSH_ARGV"] = str(tmp / "ssh.argv")
    env["FAKE_SSH_STDIN"] = str(tmp / "ssh.stdin")
    return env


def run(tmp: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(SCRIPT), *args],
        env=make_env(tmp),
        text=True,
        capture_output=True,
        check=False,
    )


def make_lpa(tmp: Path, mode: int = 0o600) -> Path:
    path = tmp / "silentlink.lpa"
    path.write_text("LPA:1$smdp.example$ABC123\n")
    path.chmod(mode)
    return path


def marker(tmp: Path) -> None:
    state = tmp / "state"
    state.mkdir(exist_ok=True)
    (state / "rehearsal-ok").write_text("2026-11-04T00:00:00Z\n")


def test_script_contract() -> None:
    text = SCRIPT.read_text()
    for needle in (
        "--confirm-paid",
        "rehearsal-ok",
        "mode 0600",
        "IFS= read -r LPA",
        "QRF-SPEEDTEST",
        "profile enable",
        "network.$WWAN.apn",
    ):
        assert needle in text, needle
    # A profile operation must never trigger a modem reset.
    assert "CFUN" not in text
    subprocess.run(["sh", "-n", str(SCRIPT)], check=True)


def test_docs_document_secure_activation() -> None:
    doc = (ROOT / "docs/E750-ESIM.md").read_text()
    for needle in (
        "e750-esim-activate.sh",
        "--confirm-paid",
        "0600",
        "stdin",
        "rehearsal-ok",
        "paid-ok",
    ):
        assert needle in doc, needle
    readme = (ROOT / "README.md").read_text()
    assert "e750-esim-activate.sh" in readme


def test_rehearsal_passes_and_marks(tmp_path: Path) -> None:
    proc = run(tmp_path, ["--rehearsal"])
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "state/rehearsal-ok").is_file()
    argv = (tmp_path / "ssh.argv").read_text()
    stdin = (tmp_path / "ssh.stdin").read_text()
    assert "QRF-SPEEDTEST" in stdin
    assert "QRF-SPEEDTEST" not in argv
    assert "QRF-SPEEDTEST" not in proc.stdout + proc.stderr


def test_paid_requires_confirmation(tmp_path: Path) -> None:
    lpa = make_lpa(tmp_path)
    marker(tmp_path)
    proc = run(tmp_path, ["--paid", "--lpa-file", str(lpa)])
    assert proc.returncode != 0
    assert "confirm-paid" in proc.stdout + proc.stderr
    assert "LPA:1$" not in (tmp_path / "ssh.argv").read_text()


def test_paid_requires_rehearsal(tmp_path: Path) -> None:
    lpa = make_lpa(tmp_path)
    proc = run(tmp_path, ["--paid", "--lpa-file", str(lpa), "--confirm-paid"])
    assert proc.returncode != 0
    assert "rehearsal" in proc.stdout + proc.stderr
    assert "LPA:1$" not in (tmp_path / "ssh.argv").read_text()


def test_paid_rejects_insecure_file(tmp_path: Path) -> None:
    lpa = make_lpa(tmp_path, 0o644)
    marker(tmp_path)
    proc = run(tmp_path, ["--paid", "--lpa-file", str(lpa), "--confirm-paid"])
    assert proc.returncode != 0
    assert "0600" in proc.stdout + proc.stderr
    assert "LPA:1$" not in (tmp_path / "ssh.argv").read_text()


def test_paid_sends_lpa_on_stdin_only(tmp_path: Path) -> None:
    lpa = make_lpa(tmp_path)
    marker(tmp_path)
    proc = run(
        tmp_path,
        ["--paid", "--lpa-file", str(lpa), "--confirm-paid"],
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "state/paid-ok").is_file()
    argv = (tmp_path / "ssh.argv").read_text()
    stdin = (tmp_path / "ssh.stdin").read_text()
    assert "LPA:1$smdp.example$ABC123" in stdin
    assert "LPA:1$smdp.example$ABC123" not in argv
    assert "LPA:1$smdp.example$ABC123" not in proc.stdout + proc.stderr
