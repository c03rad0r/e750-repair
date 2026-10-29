#!/usr/bin/env python3
"""Smoke-test the serial_console connection plugin WITHOUT hardware.

Verifies the two behaviours that matter and that are easy to regress:
  1. a clean echo is accepted on the first try
  2. a corrupted echo is retried, and the retry's clean result is returned

Runs against a fake serial object, so it needs no device and no pyserial port.
"""
import sys
import types
import os

# stub pyserial before importing the plugin
fake_serial_mod = types.ModuleType("serial")


class FakeSerial:
    """read() pops one queued response per call; write() only records."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.written = []
        self.is_open = True

    def write(self, data):
        self.written.append(data)
        return len(data)

    def read(self, n=8192):
        if self.responses:
            return self.responses.pop(0)
        return b""

    def reset_input_buffer(self):
        pass

    def close(self):
        self.is_open = False


fake_serial_mod.Serial = FakeSerial
sys.modules["serial"] = fake_serial_mod

# stub the ansible bits the plugin imports
ansible = types.ModuleType("ansible")
errors = types.ModuleType("ansible.errors")
plugins = types.ModuleType("ansible.plugins")
conn = types.ModuleType("ansible.plugins.connection")


class AnsibleConnectionFailure(Exception):
    pass


class ConnectionBase:
    def __init__(self, *a, **k):
        pass

    def exec_command(self, *a, **k):
        pass


errors.AnsibleConnectionFailure = AnsibleConnectionFailure
conn.ConnectionBase = ConnectionBase
sys.modules["ansible"] = ansible
sys.modules["ansible.errors"] = errors
sys.modules["ansible.plugins"] = plugins
sys.modules["ansible.plugins.connection"] = conn

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "connection_plugins"))
import serial_console  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS  %s" % name)
    else:
        FAIL += 1
        print("  FAIL  %s  %s" % (name, detail))


def make(responses, retries=3):
    c = serial_console.Connection.__new__(serial_console.Connection)
    c._serial = FakeSerial(responses)
    # timeout is divided by 4 to get the drain window - keep it small in tests
    c._opts = {"port": "/dev/fake", "baud": 115200, "timeout": 0.2, "retries": retries}
    c.get_option = lambda k: c._opts[k]
    c._connect = lambda: c          # no real port in a unit test
    return c


def main():
    print("test: clean echo accepted immediately")
    # responses: one per _send (the ctrl-c write is separate, so read() returns per send)
    c = make([b"echo HI\r\nHI\r\nroot@OpenWrt:~# "])
    rc, out, err = c.exec_command("echo HI")
    check("rc == 0", rc == 0, rc)
    check("output captured", "HI" in out, out[:80])

    print("test: corrupted echo is retried")
    c = make([
        b"?cho HI\r\n> ",                       # corrupted: no prompt, no clean echo
        b"echo HI\r\nHI\r\nroot@OpenWrt:~# ",   # clean on retry
    ])
    rc, out, err = c.exec_command("echo HI")
    check("rc == 0 after retry", rc == 0, rc)
    check("retry produced clean output", "root@OpenWrt" in out, out[:80])

    print("test: persistent corruption raises rather than lying")
    c = make([b"?ngarbage\r\n"] * 3, retries=3)
    try:
        c.exec_command("echo HI")
        check("raised on persistent corruption", False, "no exception")
    except AnsibleConnectionFailure:
        check("raised on persistent corruption", True)

    print()
    print("%d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)

if __name__ == "__main__":
    main()
