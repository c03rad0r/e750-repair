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


def run(cmd, tries=25, wait=4.0):
    best = ''
    for i in range(tries):
        s.write(b'\x03')
        time.sleep(0.15)
        s.reset_input_buffer()
        s.write((cmd + '\r').encode())
        t = drain(wait).decode('utf-8', 'replace').replace('\r', '')
        if cmd in t and '#' in t.split(cmd, 1)[-1]:
            return t, i + 1
        if len(t) > len(best):
            best = t
    return best, -1


# Extract the QCA9887 caldata from mtd2 @0x5000, 0x440 bytes, into the path ath10k probes.
CMDS = [
    "dd if=/dev/mtd2 of=/lib/firmware/ath10k/QCA9887/hw1.0/cal-pci-0000:00:00.0.bin bs=1 skip=20480 count=1088",
    "ls -l /lib/firmware/ath10k/QCA9887/hw1.0/",
    "dd if=/lib/firmware/ath10k/QCA9887/hw1.0/cal-pci-0000:00:00.0.bin bs=1 count=16 2>/dev/null | hexdump -C",
]
for c in CMDS:
    o, a = run(c)
    print("=" * 58)
    print("CMD: %s   (try %s)" % (c[:80], a))
    print(o[:900])
s.close()