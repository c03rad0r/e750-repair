#!/usr/bin/env python3
"""Listen on ONE serial console port and log everything.

Use this once the console port is known (it is /dev/ttyUSB3 / FTDI BH00DL3M for
the bench E750). Capture the boot with this running BEFORE you power the device on.

    python3 scripts/serial-listen.py --port /dev/ttyUSB3 --seconds 600 --out boot.log
"""
import argparse
import os
import sys
import time

import serial


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=int, default=300)
    ap.add_argument("--out", required=True)
    ap.add_argument("--nudge", action="store_true",
                    help="send a bare CR every 5s to wake a quiet console")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    s = serial.Serial(a.port, a.baud, timeout=0.5,
                      rtscts=False, dsrdtr=False, xonxoff=False)
    time.sleep(0.3)
    s.reset_input_buffer()

    total = 0
    t0 = time.time()
    last_nudge = time.time()
    with open(a.out, "wb") as f:
        while time.time() - t0 < a.seconds:
            d = s.read(8192)
            if d:
                f.write(d)
                f.flush()
                total += len(d)
            elif a.nudge and time.time() - last_nudge > 5:
                s.write(b"\r")
                last_nudge = time.time()
    s.close()
    print("captured %d bytes -> %s" % (total, a.out))
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
