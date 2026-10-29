"""Ansible connection plugin: talk to an OpenWrt console over a serial UART.

WHY THIS EXISTS
---------------
The GL-E750 in scope has no network access (br-lan NO-CARRIER, radio dead), so the
only way to reach it is its UART. Ansible has no built-in serial transport. This
plugin makes the repair reproducible as a normal playbook instead of a pile of
ad-hoc pyserial scripts.

THE TX-CORRUPTION PROBLEM (measured, not theoretical)
-----------------------------------------------------
On the bench host's FTDI *clone* adapters, TX corrupts roughly one character per
command line while RX is byte-perfect (the boot log reads clean at 115200). Symptoms:

    echo PING_OK        ->  ?cho PING_OK        (first char mangled)
    cat /sys/...        ->  ?at /sys/...        (same)
    long heredocs       ->  multiple corruptions, shell syntax errors

Ruled out: a second process holding the port (/proc/*/fd scan: free), XON/XOFF
(disabled), wrong baud (115200 correct - the device answers), latency_timer
(lowered 16 -> 1 ms), character pacing (no effect at 20 ms/char).

So this plugin does what actually worked: it sends the command, verifies the
echo, and RETRIES on corruption. A genuine FTDI/CP2102 cable would not need this,
but the retry costs nothing and makes the transport reliable on bad hardware.

Also handled: a corrupted byte can leave the shell in a continuation prompt
(`>`), where subsequent commands silently become text inside a quote. The plugin
sends Ctrl-C + Ctrl-U before every command to guarantee a clean line.
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
import time

from ansible.errors import AnsibleConnectionFailure
from ansible.plugins.connection import ConnectionBase

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

DOCUMENTATION = """
    name: serial_console
    short_description: Run commands on an OpenWrt console over a serial UART
    description:
      - Connects to a device console over a serial port and executes commands.
      - Retries commands whose echo comes back corrupted (known FTDI-clone TX issue).
    options:
      port:
        description: Serial device path.
        default: /dev/ttyUSB0
        vars:
          - name: ansible_serial_port
      baud:
        description: Baud rate.
        default: 115200
        vars:
          - name: ansible_serial_baud
      timeout:
        description: Per-command read timeout in seconds.
        default: 15
        vars:
          - name: ansible_serial_timeout
      retries:
        description: How many times to resend a command whose echo is corrupted.
        default: 20
        vars:
          - name: ansible_serial_retries
      verify_checksum:
        description: >-
          Run each command through a base64 + SHA-256 wrapper so the device
          executes it only if the payload arrived intact. Falls back to the
          echo check when base64/sha256sum are missing.
        default: true
        vars:
          - name: ansible_serial_verify_checksum
"""


class Connection(ConnectionBase):
    transport = "serial_console"
    has_pipelining = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._serial = None
        self._checksum_supported = None

    # ── lifecycle ────────────────────────────────────────────────────────────
    def _connect(self):
        if not HAS_SERIAL:
            raise AnsibleConnectionFailure(
                "pyserial is required for the serial_console transport: pip install pyserial"
            )
        if self._serial is not None and self._serial.is_open:
            return self

        port = self.get_option("port")
        baud = int(self.get_option("baud"))
        try:
            self._serial = serial.Serial(
                port, baud, timeout=0.4,
                rtscts=False, dsrdtr=False, xonxoff=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise AnsibleConnectionFailure(
                f"cannot open serial port {port}: {exc}"
            ) from exc

        time.sleep(0.5)
        self._serial.write(b"\r")
        time.sleep(1.0)
        self._serial.reset_input_buffer()
        return self

    def close(self):
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:  # noqa: BLE001
                pass
            self._serial = None

    # ── transport primitives ──────────────────────────────────────────────────
    def _drain(self, window: float) -> bytes:
        """Read until `window` seconds pass with no new data."""
        end = time.time() + window
        buf = b""
        while time.time() < end:
            chunk = self._serial.read(8192)
            if chunk:
                buf += chunk
                end = time.time() + window
        return buf

    def _send(self, cmd: str) -> None:
        # Ctrl-C abandons a continuation prompt; Ctrl-U kills a partial line.
        # Without this, a corrupted byte from a previous command can leave the
        # shell quoting everything that follows.
        self._serial.write(b"\x03\x15")
        time.sleep(0.2)
        self._serial.reset_input_buffer()
        self._serial.write((cmd + "\r").encode())

    def exec_command(self, cmd, in_data=None, sudoable=True):
        """Run `cmd` on the console.

        With `verify_checksum` the command travels as base64 and the device
        hashes it before running, so a mangled byte can only cause a retry,
        never a different command.
        """
        super().exec_command(cmd, in_data=in_data, sudoable=sudoable)
        self._connect()

        if bool(self.get_option("verify_checksum")):
            if self._checksum_supported is None:
                self._checksum_supported = self._probe_checksum()
            if self._checksum_supported:
                rc, out, err = self._exec_checksum(cmd)
                return (rc, out.encode(), err.encode())

        rc, out, err = self._exec_legacy(cmd)
        return (rc, out.encode(), err.encode())

    def _probe_checksum(self) -> bool:
        """Check once whether the device can decode base64 and hash it."""
        try:
            rc, out, _ = self._exec_legacy(
                "command -v base64 >/dev/null 2>&1 && "
                "command -v sha256sum >/dev/null 2>&1 && echo __CKSUM_OK__"
            )
        except AnsibleConnectionFailure:
            return False
        return rc == 0 and "__CKSUM_OK__" in out

    @staticmethod
    def _build_checksum_line(cmd: str, nonce: str) -> str:
        payload = cmd.encode()
        b64 = base64.b64encode(payload).decode()
        sha = hashlib.sha256(payload).hexdigest()
        b = f"B64_{nonce}"
        g = f"G_{nonce}"
        r = f"RC_{nonce}"
        return (
            f"{b}='{b64}'; "
            f"printf '%s' \"${b}\" | base64 -d > /tmp/.ansible-cmd 2>/dev/null; "
            f"{g}=$(sha256sum /tmp/.ansible-cmd 2>/dev/null | cut -d' ' -f1); "
            f"if [ \"${g}\" = '{sha}' ]; then "
            f"echo __BEGIN_{nonce}__; sh /tmp/.ansible-cmd; {r}=$?; "
            f"echo __END_{nonce}__; else {r}=97; fi; "
            f"rm -f /tmp/.ansible-cmd; echo __DONE_{nonce}__ ${{{r}}}"
        )

    @staticmethod
    def _parse_checksum(text: str, nonce: str):
        m = re.search(rf"__DONE_{nonce}__ (\d+)", text)
        if not m:
            return None
        rc = int(m.group(1))
        begin = f"__BEGIN_{nonce}__"
        end = f"__END_{nonce}__"
        bi = text.rfind(begin)
        ei = text.find(end, bi + 1) if bi >= 0 else -1
        if bi < 0 or ei < 0:
            return None
        return rc, text[bi + len(begin):ei]

    def _exec_checksum(self, cmd: str):
        retries = int(self.get_option("retries"))
        window = float(self.get_option("timeout")) / 4.0
        best = ""

        # Very long commands would need a wrapper the console line discipline
        # may truncate; fall back to the echo path for those.
        if len(base64.b64encode(cmd.encode())) > 2000:
            return self._exec_legacy(cmd)

        for _ in range(retries):
            nonce = secrets.token_hex(4)
            self._send(self._build_checksum_line(cmd, nonce))
            raw = self._drain(window)
            text = raw.decode("utf-8", errors="replace").replace("\r", "")
            parsed = self._parse_checksum(text, nonce)
            if parsed is not None:
                rc, body = parsed
                if rc != 97:  # 97 = payload hash mismatch on the device
                    return (rc, body, "")
                best = text
            else:
                if len(text) > len(best):
                    best = text
            time.sleep(0.2)

        raise AnsibleConnectionFailure(
            "serial transport could not deliver this command intact after "
            f"{retries} attempts (checksum/echo failed). Last output:\n{best[-500:]}"
        )

    def _exec_legacy(self, cmd: str):
        """Run `cmd` on the console, retrying until its echo is clean."""
        retries = int(self.get_option("retries"))
        window = float(self.get_option("timeout")) / 4.0
        best = ""

        for _ in range(retries):
            self._send(cmd)
            raw = self._drain(window)
            text = raw.decode("utf-8", errors="replace").replace("\r", "")

            # A clean run: the exact command echoed back, and a prompt returned
            # after it. Anything else means a byte was mangled in flight.
            if cmd in text and "#" in text.split(cmd, 1)[-1]:
                return (0, text, "")

            if len(text) > len(best):
                best = text
            time.sleep(0.2)

        # Never claim success we did not observe - surface the corruption.
        raise AnsibleConnectionFailure(
            "serial transport could not get a clean echo of this command after "
            f"{retries} attempts (TX corruption). Last output:\n{best[-500:]}"
        )

    def put_file(self, in_path, out_path):
        raise AnsibleConnectionFailure(
            "serial_console has no file transfer: fetch with `command: wget` or "
            "use the ansible.builtin.copy module with content= (rendered inline)."
        )

    def fetch_file(self, in_path, out_path):
        raise AnsibleConnectionFailure(
            "serial_console has no file transfer: read with `command: cat ...` instead."
        )

    def _reset(self):
        pass
