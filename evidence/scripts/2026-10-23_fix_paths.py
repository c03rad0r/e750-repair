import time
import serial

s = serial.Serial('/dev/ttyUSB3', 115200, timeout=0.4,
                  rtscts=False, dsrdtr=False, xonxoff=False)
time.sleep(0.5)
s.write(b'\r')
time.sleep(1.0)
s.reset_input_buffer()


def drain(w):
    t0 = time.time()
    b = b''
    while time.time() - t0 < w:
        d = s.read(8192)
        if d:
            b += d
            t0 = time.time()
    return b


def run(cmd, tries=25, wait=2.5):
    best = ''
    for i in range(tries):
        s.write(b'\x03')
        time.sleep(0.12)
        s.reset_input_buffer()
        s.write((cmd + '\r').encode())
        t = drain(wait).decode('utf-8', 'replace').replace('\r', '')
        if cmd in t and '#' in t.split(cmd, 1)[-1]:
            return t, i + 1
        if len(t) > len(best):
            best = t
    return best, -1


CMDS = [
    # confirm the two existing copies are byte-identical
    "md5sum /lib/firmware/ath10k/pre-cal-pci-0000:00:00.0.bin /lib/firmware/ath10k/QCA9887/hw1.0/cal-pci-0000:00:00.0.bin",
    # place pre-cal where the driver actually looks (nested hw dir)
    "cp /lib/firmware/ath10k/QCA9887/hw1.0/cal-pci-0000:00:00.0.bin /lib/firmware/ath10k/QCA9887/hw1.0/pre-cal-pci-0000:00:00.0.bin",
    # and a top-level cal- copy too
    "cp /lib/firmware/ath10k/QCA9887/hw1.0/cal-pci-0000:00:00.0.bin /lib/firmware/ath10k/cal-pci-0000:00:00.0.bin",
    "ls -lR /lib/firmware/ath10k",
]
for c in CMDS:
    o, a = run(c)
    print("=" * 52)
    print("CMD: %s  (try %s)" % (c[:70], a))
    print(o[:800])
s.close()