#!/usr/bin/env python3
"""Contract checks for the E750 on-device eSIM stack."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_artifact_is_pinned() -> None:
    defaults = read("roles/e750_esim/defaults/main.yml")
    assert "7be0e679ff695d469064088ed0e69b438292e305" in defaults
    assert 'e750_esim_artifact_url: ""' in defaults
    assert 'https://github.com/Amperstrand/lpac-openwrt' not in defaults
    assert "9b7088e814d0efef8ab56d98b65263aec3199659bff633566e1f1192e24c8e99" not in defaults
    assert 'e750_esim_at_device: "auto"' in defaults
    assert 'e750_esim_apn: "internet"' in defaults


def test_role_verifies_and_installs_wrapper() -> None:
    defaults = read("roles/e750_esim/defaults/main.yml")
    tasks = read("roles/e750_esim/tasks/main.yml")
    assert "ca-certificates-gsma.crt" in defaults
    assert 'e750_esim_require_board: "glinet,gl-e750"' in defaults
    for needle in (
        "sha256sum -c -",
        "driver_apdu_at_csim.so",
        "driver_http_curl.so",
        "e750_esim_ca_bundle",
        "e750-esim.sh.j2",
        "LPAC_HTTP_CURL_CAINFO",
        "LPAC_DRIVER_HOME",
        "no pre-staged lpac bundle",
    ):
        assert needle in tasks, needle


def test_prestaged_artifact_does_not_download(tmp_path: Path) -> None:
    artifact = tmp_path / "lpac.tar.gz"
    artifact.write_bytes(b"test bundle")
    curl_called = tmp_path / "curl.called"
    command = _stage_task(artifact)
    _run_stage(command, tmp_path, curl_called)
    assert not curl_called.exists()


def test_missing_artifact_without_mirror_fails_closed(tmp_path: Path) -> None:
    curl_called = tmp_path / "curl.called"
    command = _stage_task(tmp_path / "missing.tar.gz")
    proc = _run_stage(command, tmp_path, curl_called, check=False)
    assert proc.returncode == 2
    assert "no pre-staged lpac bundle" in proc.stderr
    assert not curl_called.exists()


def _stage_task(artifact: Path) -> str:
    tasks = read("roles/e750_esim/tasks/main.yml")
    stage = tasks.split("- name: Stage the pinned lpac bundle", 1)[1]
    raw = stage.split("ansible.builtin.raw: |", 1)[1].split("\n  register:", 1)[0]
    script = "\n".join(line[4:] if line.startswith("    ") else line
                      for line in raw.splitlines())
    return (script.replace("{{ e750_esim_artifact_path }}", str(artifact))
            .replace("{{ e750_esim_artifact_url }}", ""))


def _run_stage(command: str, tmp_path: Path, curl_called: Path,
               check: bool = True) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    curl = bin_dir / "curl"
    curl.write_text("#!/bin/sh\nprintf called > \"$LPAC_TEST_CURL_CALLED\"\nexit 99\n")
    curl.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["LPAC_TEST_CURL_CALLED"] = str(curl_called)
    return subprocess.run(["sh", "-c", command], env=env, check=check,
                          text=True, capture_output=True)


def test_installer_provisions_tar_on_minimal_openwrt() -> None:
    tasks = read("roles/e750_esim/tasks/main.yml")
    assert 'if ! command -v tar >/dev/null 2>&1; then\n      apk add tar' in tasks


def test_wrapper_uses_uppercase_at_csim_and_cpin_probe() -> None:
    wrapper = read("roles/e750_esim/templates/e750-esim.sh.j2")
    for needle in (
        "LPAC_APDU=at_csim",
        "LPAC_APDU_AT_HEX=UPPER",
        "LPAC_HTTP_SSL_VERIFY=1",
        "LPAC_HTTP_CURL_CAINFO",
        "LPAC_DRIVER_HOME",
        "AT+CPIN?",
        "detect_port",
        "/dev/ttyUSB*",
    ):
        assert needle in wrapper, needle
    # The wrapper must never issue a modem reset; the usage text may forbid it.
    assert "Never run AT+CFUN=1,1" in wrapper
    assert "AT+CFUN=1,1\\r" not in wrapper
    assert "AT+CFUN=1,1'" not in wrapper


def test_playbook_and_docs_exist() -> None:
    playbook = read("playbook-e750-esim.yml")
    assert "e750_esim" in playbook
    doc = read("docs/E750-ESIM.md")
    for needle in (
        "Path B",
        "e750-esim",
        "AT+CFUN=1,1",
        "FORBIDDEN",
        "QRF-SPEEDTEST",
        "internet.eplus.de",
        "data.esim",
        "2c7c:030b",
        "MBIM",
        "tools/lpac-e750-build/",
        "pre-staged",
        "7be0e679ff695d469064088ed0e69b438292e305",
    ):
        assert needle in doc, needle


def test_modem_diag_auto_detects_port() -> None:
    defaults = read("roles/e750_modem_diag/defaults/main.yml")
    assert 'e750_modem_at_port: "auto"' in defaults
    script = read("scripts/e750-modem-diag.sh")
    assert 'AT_PORT="${AT_PORT:-auto}"' in script
    assert "detect_at_port" in script
    assert "AT+CPIN?" in script
