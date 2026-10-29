#!/usr/bin/env python3
"""Measure host->device serial TX reliability with read-only echo commands.

Sends CR wake bytes, then `echo SERIAL_<nonce>` char-by-char. A command counts
as clean only when the nonce appears at least twice (the console echo and the
command output), so a corrupted command that merely echoes the nonce is not a
false pass.

The E750 console is behind `askfirst`; without a valid CR the console stays
silent. This test reports the wake output and the clean/corrupt count.
"""
from __future__ import annotations

import argparse
import os
import select
import termios
import time


BAUD_RATES = {
    9600: termios.B9600,
    19200: termios.B19200,
    38400: termios.B38400,
    57600: termios.B57600,
    115200: termios.B115200,
}


def open_port(device: str, baud: int) -> int:
    speed = BAUD_RATES.get(baud)
    if speed is None:
        raise SystemExit(f"unsupported baud rate: {baud}")
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
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


def read_for(fd: int, seconds: float, idle: float = 0.2) -> str:
    buf = b""
    end = time.time() + seconds
    last = time.time()
    while time.time() < end:
        ready, _, _ = select.select([fd], [], [], 0.05)
        if ready:
            try:
                data = os.read(fd, 4096)
            except BlockingIOError:
                data = b""
            if data:
                buf += data
                last = time.time()
        if buf and time.time() - last > idle:
            break
    return buf.decode("utf-8", "replace").replace("\r", "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--wake-crs", type=int, default=10)
    parser.add_argument("--pacing", type=float, default=0.02)
    parser.add_argument("--timeout", type=float, default=1.5)
    args = parser.parse_args()

    fd = open_port(args.device, args.baud)

    wake = ""
    for _ in range(args.wake_crs):
        os.write(fd, b"\r")
        time.sleep(0.2)
        wake += read_for(fd, 0.1, 0.05)
    print(f"wake_output={wake[:300]!r}")

    clean = 0
    failures: list[tuple[int, str]] = []
    for i in range(args.count):
        nonce = f"SERIAL_{os.getpid()}_{i}"
        command = f"echo {nonce}"
        for ch in command:
            os.write(fd, ch.encode())
            time.sleep(args.pacing)
        os.write(fd, b"\r")
        out = read_for(fd, args.timeout)
        # The console echoes the command and the echo command prints the nonce.
        ok = out.count(nonce) >= 2
        print(f"[{i}] {'OK' if ok else 'FAIL'} {out[:160]!r}")
        if ok:
            clean += 1
        else:
            failures.append((i, out))
    os.close(fd)

    print(f"summary clean={clean}/{args.count} corrupt={args.count - clean}")
    if failures:
        print(f"first_failure={failures[0][1][:160]!r}")
    return 0 if clean == args.count else 1


if __name__ == "__main__":
    raise SystemExit(main())
