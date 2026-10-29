#!/usr/bin/env python3
"""Wake a serial console and optionally send a command with echo verification.

The E750's console runs `askfirst`, so it stays silent until it receives a
valid Enter. A lossy host TX can corrupt every CR; this tool sends a burst and
then types a command with per-character echo checks and retries.

Usage:
    serial-wake.py /dev/ttyE750
    serial-wake.py /dev/ttyE750 'id'
    serial-wake.py /dev/ttyE750 --crs 30 --retries 8 'uname -a'
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


def drain(fd: int, seconds: float, idle: float = 0.2) -> str:
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
    parser.add_argument("command", nargs="?", default="")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--crs", type=int, default=20)
    parser.add_argument("--retries", type=int, default=6)
    parser.add_argument("--pacing", type=float, default=0.1)
    args = parser.parse_args()

    fd = open_port(args.device, args.baud)

    wake = ""
    for _ in range(args.crs):
        os.write(fd, b"\r")
        time.sleep(0.2)
        wake += drain(fd, 0.1, 0.05)
    print("=== wake ===")
    print(wake[:1000] or "(no output)")

    if not args.command:
        os.close(fd)
        return 0

    print("=== command ===")
    for attempt in range(1, args.retries + 1):
        os.write(fd, b"\x15")  # kill line
        time.sleep(0.15)
        drain(fd, 0.15, 0.1)
        for ch in args.command:
            os.write(fd, ch.encode())
            time.sleep(args.pacing)
        time.sleep(0.3)
        echo = drain(fd, 0.3, 0.15)
        if args.command in echo:
            os.write(fd, b"\r")
            out = drain(fd, 1.5, 0.25)
            print(f"attempt={attempt} clean echo")
            print(out or "(no output)")
            os.close(fd)
            return 0
        print(f"attempt={attempt} corrupted echo: {echo[-160:]!r}")
    print("command not accepted after retries; the TX line is not reliable")
    os.close(fd)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
