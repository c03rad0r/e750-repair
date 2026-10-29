#!/usr/bin/env python3
"""Execute a shell script over the serial console with end-to-end checksums.

The console is an interactive shell, so the script is uploaded as base64 text,
verified by SHA-256 on the device, decoded, verified again, and only then run.
A corrupted upload is rejected by the device and retransmitted by the host; a
corrupted output is detected by hashing the device-side output file.

Usage:
    serial-exec.py /dev/ttyE750 -c 'uname -a'
    serial-exec.py /dev/ttyE750 -f repair.sh --dry-run
    serial-exec.py /dev/ttyE750 -f repair.sh --allow-dangerous

This is not an authentication mechanism: the serial console is root-equivalent.
It protects against typos and line noise, not against a malicious operator.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import re
import secrets
import select
import sys
import termios
import time

BAUD = {
    9600: termios.B9600,
    19200: termios.B19200,
    38400: termios.B38400,
    57600: termios.B57600,
    115200: termios.B115200,
}
PROMPT = re.compile(rb"root@[^\r\n]*#\s*$")
SHA256_RE = re.compile(rb"\b([0-9a-f]{64})\b")
DANGEROUS = (
    "mtd ",
    "mtd-",
    "sysupgrade",
    "reboot",
    "fw_setenv",
    "nand",
    "ubiformat",
    "firstboot",
    "mkfs",
    "dd if=/dev/mtd",
    "rm -rf /",
)


class Serial:
    def __init__(self, device: str, baud: int = 115200) -> None:
        self.fd = self._open(device, baud)

    @staticmethod
    def _open(device: str, baud: int) -> int:
        speed = BAUD.get(baud)
        if speed is None:
            raise SystemExit(f"unsupported baud: {baud}")
        fd = __import__("os").open(device, __import__("os").O_RDWR | __import__("os").O_NOCTTY | __import__("os").O_NONBLOCK)
        attrs = termios.tcgetattr(fd)
        attrs[0] = 0
        attrs[1] = 0
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] = 0
        attrs[4] = speed
        attrs[5] = speed
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        termios.tcflush(fd, termios.TCIOFLUSH)
        return fd

    def write(self, data: bytes) -> None:
        __import__("os").write(self.fd, data)

    def read(self, timeout: float, idle: float = 0.15) -> bytes:
        buf = b""
        end = time.time() + timeout
        last = time.time()
        while time.time() < end:
            ready, _, _ = select.select([self.fd], [], [], 0.05)
            if ready:
                try:
                    data = __import__("os").read(self.fd, 4096)
                except BlockingIOError:
                    data = b""
                if data:
                    buf += data
                    last = time.time()
            if buf and time.time() - last > idle:
                break
        return buf

    def drain(self, timeout: float = 0.2) -> bytes:
        return self.read(timeout, idle=0.05)

    def wake(self, timeout: float = 3.0) -> None:
        for _ in range(20):
            self.write(b"\r")
            time.sleep(0.15)
            out = self.read(0.2)
            if PROMPT.search(out):
                return
        raise SystemExit("no shell prompt; is the console at a login/password prompt?")

    def send_line(self, command: str, timeout: float = 2.0, retries: int = 5) -> str:
        for _ in range(retries):
            self.write(b"\x15")
            time.sleep(0.1)
            self.drain(0.2)
            for ch in command:
                self.write(ch.encode())
                time.sleep(0.01)
            self.write(b"\r")
            out = self.read(timeout).decode("utf-8", "replace")
            # The console wraps long lines; compare with whitespace removed so
            # wrapping does not look like corruption. A changed character still
            # fails the comparison.
            compact = lambda value: re.sub(r"\s+", "", value)
            if compact(command) in compact(out):
                return out
        raise SystemExit(f"command echo was not clean after retries: {command!r}")

    def wait_prompt(self, timeout: float = 5.0) -> str:
        buf = b""
        end = time.time() + timeout
        while time.time() < end:
            buf += self.read(0.3)
            if PROMPT.search(buf):
                return buf.decode("utf-8", "replace")
        raise SystemExit("timed out waiting for the shell prompt")

    def close(self) -> None:
        __import__("os").close(self.fd)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def b64_lines(data: bytes, width: int = 76) -> list[str]:
    text = base64.b64encode(data).decode()
    return [text[i : i + width] for i in range(0, len(text), width)] or [""]


def upload(serial: Serial, remote: str, data: bytes, retries: int, inject_error: bool) -> bytes:
    """Upload the script as base64 text and verify the uploaded file SHA-256."""
    lines = b64_lines(data)
    file_bytes = ("\n".join(lines) + "\n").encode()
    expected = sha256(file_bytes)
    for attempt in range(1, retries + 1):
        serial.send_line(f"rm -f {remote}")
        serial.send_line(f"cat > {remote}")
        for line in lines:
            if inject_error and attempt == 1 and line:
                # Flip one base64 character to prove the checksum catches it.
                line = ("A" if line[0] != "A" else "B") + line[1:]
            serial.write(line.encode() + b"\r")
            time.sleep(0.01)
            serial.drain(0.01)
        serial.write(b"\x04")  # EOF for cat
        time.sleep(0.2)
        serial.write(b"\x04")  # second EOF at a line start if the first raced
        serial.drain(0.3)
        serial.write(b"\r")
        serial.wait_prompt()
        got = serial.send_line(f"sha256sum {remote}")
        match = SHA256_RE.search(got.encode())
        if match and match.group(1).decode() == expected:
            return data
        print(f"payload hash mismatch on attempt {attempt}; retransmitting", file=sys.stderr)
    raise SystemExit("payload upload failed after retries")


def read_output(serial: Serial, remote: str, nonce: str, timeout: float) -> tuple[str, str]:
    begin = f"__E750_OUT_BEGIN_{nonce}__"
    end = f"__E750_OUT_END_{nonce}__"
    # The echoed command contains the marker strings; only the emitted lines
    # (marker alone on a line) are matched.
    text = serial.send_line(
        f"printf '{begin}\\n'; cat {remote}; printf '{end}\\n'",
        timeout=2.0,
    )
    end_re = re.compile(rf"(?m)^{re.escape(end)}\r?$")
    deadline = time.time() + timeout
    while not end_re.search(text) and time.time() < deadline:
        text += serial.read(0.3).decode("utf-8", "replace")
    begin_re = re.compile(rf"(?m)^{re.escape(begin)}\r?$")
    mb = begin_re.search(text)
    me = end_re.search(text)
    if not mb or not me or me.start() < mb.end():
        raise SystemExit("output markers missing or out of order")
    body = text[mb.end() : me.start()]
    body = body.replace("\r\n", "\n").lstrip("\r\n")
    return body, sha256(body.encode())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device")
    parser.add_argument("-c", "--command")
    parser.add_argument("-f", "--file")
    parser.add_argument("--dry-run", action="store_true", help="upload and verify, do not execute")
    parser.add_argument("--allow-dangerous", action="store_true", help="allow mtd/sysupgrade/reboot/...")
    parser.add_argument("--inject-error", action="store_true", help="corrupt the first upload (test)")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    if bool(args.command) == bool(args.file):
        raise SystemExit("give exactly one of -c/--command or -f/--file")
    script = args.command.encode() if args.command else open(args.file, "rb").read()
    if not script.endswith(b"\n"):
        script += b"\n"

    lower = script.decode("utf-8", "replace")
    if not args.allow_dangerous:
        hits = [token for token in DANGEROUS if token in lower]
        if hits:
            raise SystemExit(
                "refusing dangerous script without --allow-dangerous: " + ", ".join(hits)
            )

    nonce = secrets.token_hex(4)
    remote_b64 = f"/tmp/e750-serial-{nonce}.b64"
    remote_sh = f"/tmp/e750-serial-{nonce}.sh"
    remote_out = f"/tmp/e750-serial-{nonce}.out"

    serial = Serial(args.device)
    try:
        serial.wake()
        upload(serial, remote_b64, script, args.retries, args.inject_error)
        # The uploaded file is the base64 text; verify decode + script hash.
        serial.send_line(f"base64 -d {remote_b64} > {remote_sh}")
        got = serial.send_line(f"sha256sum {remote_sh}")
        match = SHA256_RE.search(got.encode())
        if not match or match.group(1).decode() != sha256(script):
            raise SystemExit("decoded script hash mismatch")
        if args.dry_run:
            print(f"script_sha256={sha256(script)} bytes={len(script)}")
            print(script.decode("utf-8", "replace"))
            return 0
        out = serial.send_line(
            f"sh {remote_sh} > {remote_out} 2>&1; echo __E750_RC_{nonce}__ $?",
            timeout=2.0,
        )
        # The marker can already be in the command-echo read; include it.
        buf = out.encode()
        end = time.time() + args.timeout
        rc_re = re.compile(rf"__E750_RC_{nonce}__ (\d+)".encode())
        rc = None
        while True:
            m = rc_re.search(buf)
            if m:
                rc = int(m.group(1))
                break
            if time.time() >= end:
                break
            buf += serial.read(0.3)
        if rc is None:
            raise SystemExit("timed out waiting for the script exit code")
        body, out_hash = read_output(serial, remote_out, nonce, args.timeout)
        got = serial.send_line(f"sha256sum {remote_out}")
        match = SHA256_RE.search(got.encode())
        if not match or match.group(1).decode() != out_hash:
            raise SystemExit(
                "output hash mismatch; the serial link corrupted the output (re-run or use a lower baud)"
            )
        print(body, end="")
        return rc
    finally:
        serial.close()


if __name__ == "__main__":
    raise SystemExit(main())
