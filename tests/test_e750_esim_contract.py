#!/usr/bin/env python3
"""Contract checks for the E750 on-device eSIM stack."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_artifact_is_pinned() -> None:
    defaults = read("roles/e750_esim/defaults/main.yml")
    assert "mips24kc-25.12.5-r1" in defaults
    assert "9b7088e814d0efef8ab56d98b65263aec3199659bff633566e1f1192e24c8e99" in defaults
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
    ):
        assert needle in tasks, needle


def test_wrapper_uses_uppercase_at_csim_and_cpin_probe() -> None:
    wrapper = read("roles/e750_esim/templates/e750-esim.sh.j2")
    for needle in (
        "LPAC_APDU=at_csim",
        "LPAC_APDU_AT_HEX=UPPER",
        "LPAC_HTTP_SSL_VERIFY=1",
        "LPAC_HTTP_CURL_CAINFO",
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
        "9b7088e8",
    ):
        assert needle in doc, needle


def test_modem_diag_auto_detects_port() -> None:
    defaults = read("roles/e750_modem_diag/defaults/main.yml")
    assert 'e750_modem_at_port: "auto"' in defaults
    script = read("scripts/e750-modem-diag.sh")
    assert 'AT_PORT="${AT_PORT:-auto}"' in script
    assert "detect_at_port" in script
    assert "AT+CPIN?" in script
