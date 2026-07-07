import os, time, termios, fcntl, struct, select, sys

PORT = "/dev/cu.usbserial-A6000001"
IOSSIOSPEED = 0x80045402
TIOCSBRK = 0x2000747B
TIOCCBRK = 0x2000747A
BAUD = 10400

fd = os.open(PORT, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
attrs = termios.tcgetattr(fd)
# raw mode, 8N1
attrs[0] = 0                      # iflag
attrs[1] = 0                      # oflag
attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL  # cflag
attrs[3] = 0                      # lflag
attrs[6][termios.VMIN] = 0
attrs[6][termios.VTIME] = 0
termios.tcsetattr(fd, termios.TCSANOW, attrs)
fcntl.ioctl(fd, IOSSIOSPEED, struct.pack("Q", BAUD))

def flush():
    termios.tcflush(fd, termios.TCIOFLUSH)

def read_bytes(deadline):
    buf = b""
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            chunk = os.read(fd, 64)
            if chunk:
                buf += chunk
                deadline = max(deadline, time.time() + 0.06)  # extend on activity
    return buf

def send(msg, quiet_ms=60):
    os.write(fd, msg)
    termios.tcdrain(fd)
    # K-line echoes our own bytes; read everything then strip echo
    resp = read_bytes(time.time() + 1.2)
    if resp.startswith(msg):
        resp = resp[len(msg):]
    return resp

def cks(b):
    return bytes([sum(b) & 0xFF])

def hexs(b):
    return " ".join(f"{x:02X}" for x in b)

def fast_init():
    flush()
    time.sleep(0.35)               # W5 idle time
    fcntl.ioctl(fd, TIOCSBRK)      # K-line low
    time.sleep(0.025)
    fcntl.ioctl(fd, TIOCCBRK)      # K-line high
    time.sleep(0.025)
    req = bytes([0xC1, 0x33, 0xF1, 0x81]) + cks(bytes([0xC1, 0x33, 0xF1, 0x81]))
    resp = send(req)
    print("fast-init response:", hexs(resp) if resp else "(nothing)")
    return resp

resp = fast_init()
if not resp:
    print("NO_RESPONSE")
    sys.exit(2)

# positive response to StartCommunication is service 0xC1
if 0xC1 not in resp:
    print("UNEXPECTED")
    sys.exit(3)

print("K-line session established (ISO 14230 / KWP2000)")

def obd_request(data):
    hdr = bytes([0xC0 | len(data), 0x33, 0xF1]) + data
    msg = hdr + cks(hdr)
    return send(msg)

time.sleep(0.06)
# Mode 01 PID 00 (supported PIDs) as a sanity check
r = obd_request(bytes([0x01, 0x00]))
print("0100:", hexs(r) if r else "(nothing)")
time.sleep(0.06)
# Mode 03: stored DTCs
r = obd_request(bytes([0x03]))
print("03  :", hexs(r) if r else "(nothing)")
time.sleep(0.06)
# Mode 09 PID 02: VIN (may not be supported on 2005)
r = obd_request(bytes([0x09, 0x02]))
print("0902:", hexs(r) if r else "(nothing)")

os.close(fd)
