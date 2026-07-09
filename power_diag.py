#!/usr/bin/env python3
"""BMW E87 K-line power-supply diagnostics over a K+DCAN (FTDI) cable on macOS.

Talks raw ISO 14230 / KWP2000 at 10400 baud via termios + IOSSIOSPEED
(pyserial does not open this port under Apple's DriverKit FTDI driver).

Modes:
  pids            show which Mode-01 PIDs the DME supports (incl. 0x42 voltage)
  monitor         continuous voltage + RPM logging to CSV, Ctrl+C to stop
  scan            fast-init known BMW module addresses, read + decode DTCs
  sweep           fast-init every address 0x00-0xE8, read DTCs from responders
  dtc ADDR        init one module (hex addr) and read its DTCs
  detail ADDR     DTCs plus per-fault environment/freeze-frame data (svc 17/12)
  probe-voltage   hunt KWP readDataByLocalIdentifier records for a voltage value

Use --raw to print every frame on the wire. All traffic is also appended to
kline_raw.log next to this script.
"""
import argparse
import csv
import datetime
import glob
import os
import struct
import sys
import time

# Platform-specific serial I/O. macOS/Linux use a raw fd + termios + the
# IOSSIOSPEED ioctl (pyserial can't open the port under Apple's DriverKit
# FTDI driver). Windows uses pyserial, which opens FTDI VCP COM ports
# cleanly and supports the nonstandard 10400 baud directly — so none of the
# DriverKit workarounds are needed there. The two backends live in
# _PosixKLineIO / _WindowsKLineIO below; nothing OS-specific runs at import
# time on the wrong platform.
IS_WINDOWS = sys.platform.startswith("win")
if IS_WINDOWS:
    import serial
    from serial.tools import list_ports
    PORT_ERRORS = (OSError, serial.SerialException)
else:
    import fcntl
    import select
    import termios
    PORT_ERRORS = (OSError, termios.error)

PORT_DEFAULT = "/dev/cu.usbserial-A6000001"
IOSSIOSPEED = 0x80045402
TIOCSBRK = 0x2000747B
TIOCCBRK = 0x2000747A
BAUD = 10400
TESTER = 0xF1
OBD_FUNCTIONAL = 0x33
DME = 0x12

# Candidate diagnostic addresses on the E87 K-line (pre-03/2007 cars expose
# all modules on OBD pin 7).
MODULES = {
    # verified present on this car (WBAXXXXXXXXXXXXXX):
    0x00: "JBE/SPEG (junction box / power distribution)",
    0x01: "MRS (airbag / restraint system)",
    0x12: "DME (engine)",
    0x29: "DSC (stability control / ABS)",
    0x40: "CAS (car access system)",
    0x60: "KOMBI (instrument cluster; refuses init but talks anyway)",
    0x63: "SZL? (steering column module 'KA')",
    0x64: "PDC (park distance control)",
    0x72: "LM (light module)",
    0x78: "IHKA (climate control)",
    # not fitted / silent on this car:
    0x17: "EKPS (fuel pump control)",
    0x18: "EGS (automatic transmission)",
    0x30: "EPS (electric power steering)",
    0x68: "RAD (radio)",
}
# 0xE9-0xEF answer as aliases of other modules — excluded from scans.


def hexs(b):
    return " ".join(f"{x:02X}" for x in b)


def cks(b):
    return bytes([sum(b) & 0xFF])


def now():
    return time.time()


def frame_payload(frame):
    fmt = frame[0]
    i = 3 if (fmt & 0xC0) in (0x80, 0xC0) else 1
    if (fmt & 0x3F) == 0:
        i += 1
    return frame[i:-1]


def frame_source(frame):
    if (frame[0] & 0xC0) in (0x80, 0xC0):
        return frame[2]
    return None


def _usb_reset():
    """Reset the FTDI cable at USB level. Recovers the wedged DriverKit
    state (tcsetattr/IOSSIOSPEED failing) that follows a bus dropout,
    without physically replugging. Needs pyusb + Homebrew libusb.

    macOS-specific: the wedge is a DriverKit behaviour. On Windows the VCP
    driver doesn't exhibit it, so this is a no-op there."""
    if IS_WINDOWS:
        return False
    try:
        import usb.core
        import usb.backend.libusb1
        be = usb.backend.libusb1.get_backend(
            find_library=lambda x: "/opt/homebrew/lib/libusb-1.0.dylib")
        dev = usb.core.find(idVendor=0x0403, idProduct=0x6001, backend=be)
        if dev is not None:
            dev.reset()
            time.sleep(2.0)
            return True
    except Exception:
        pass
    return False


def find_port():
    """Locate the FTDI K+DCAN cable's port for this OS.

    macOS/Linux: the /dev/cu.usbserial* device (the suffix can change on
    re-enumeration). Windows: the COM port whose USB VID:PID is FTDI's
    0403:6001, else the first COM port present. Returns None if nothing is
    found on Windows, or PORT_DEFAULT as a last resort on POSIX.
    """
    if IS_WINDOWS:
        ftdi = [p.device for p in list_ports.comports()
                if (p.vid, p.pid) == (0x0403, 0x6001)]
        if ftdi:
            return ftdi[0]
        allp = [p.device for p in list_ports.comports()]
        return allp[0] if allp else None
    cands = glob.glob("/dev/cu.usbserial*")
    return cands[0] if cands else PORT_DEFAULT


class _PosixKLineIO:
    """macOS/Linux backend: raw fd + termios + IOSSIOSPEED. This is the
    original transport, unchanged — pyserial can't drive Apple's DriverKit
    FTDI port at a nonstandard baud, so we set the speed via the ioctl."""

    def __init__(self, port, baud, parity):
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        a = termios.tcgetattr(self.fd)
        a[0] = a[1] = a[3] = 0
        a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        if parity == "E":
            a[2] |= termios.PARENB  # even parity (PARODD clear)
        # A leftover nonstandard speed (10400) makes tcsetattr fail EINVAL;
        # set a standard one first, then switch via IOSSIOSPEED.
        a[4] = a[5] = termios.B9600
        a[6][termios.VMIN] = 0
        a[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, a)
        fcntl.ioctl(self.fd, IOSSIOSPEED, struct.pack("Q", baud))

    def wait_readable(self, timeout):
        r, _, _ = select.select([self.fd], [], [], max(0.0, timeout))
        return bool(r)

    def read(self, n):
        try:
            return os.read(self.fd, n)
        except BlockingIOError:
            return b""

    def write(self, data):
        os.write(self.fd, data)

    def drain(self):
        termios.tcdrain(self.fd)

    def flush_input(self):
        termios.tcflush(self.fd, termios.TCIFLUSH)

    def flush_io(self):
        termios.tcflush(self.fd, termios.TCIOFLUSH)

    def set_break(self, on):
        fcntl.ioctl(self.fd, TIOCSBRK if on else TIOCCBRK)

    def close(self):
        os.close(self.fd)


class _WindowsKLineIO:
    """Windows backend: pyserial. Windows' serial stack supports the
    nonstandard 10400 baud directly and opens FTDI VCP COM ports without
    the DriverKit workarounds, so this is a straight pyserial wrapper.
    Reads are non-blocking (timeout=0) to mirror O_NONBLOCK; break
    signalling for fast-init / 5-baud init uses `break_condition`."""

    def __init__(self, port, baud, parity):
        self.ser = serial.Serial()
        self.ser.port = port
        self.ser.baudrate = baud
        self.ser.bytesize = serial.EIGHTBITS
        self.ser.parity = (serial.PARITY_EVEN if parity == "E"
                           else serial.PARITY_NONE)
        self.ser.stopbits = serial.STOPBITS_ONE
        self.ser.timeout = 0        # non-blocking reads
        self.ser.write_timeout = 2
        self.ser.open()

    def wait_readable(self, timeout):
        end = time.time() + max(0.0, timeout)
        while True:
            if self.ser.in_waiting:
                return True
            if time.time() >= end:
                return self.ser.in_waiting > 0
            time.sleep(0.001)

    def read(self, n):
        return self.ser.read(n)      # timeout=0 -> up to n available bytes

    def write(self, data):
        self.ser.write(data)

    def drain(self):
        self.ser.flush()             # block until the OS buffer is written

    def flush_input(self):
        self.ser.reset_input_buffer()

    def flush_io(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def set_break(self, on):
        self.ser.break_condition = bool(on)

    def close(self):
        self.ser.close()


def _make_io(port, baud, parity):
    backend = _WindowsKLineIO if IS_WINDOWS else _PosixKLineIO
    return backend(port, baud, parity)


class KLine:
    def __init__(self, port=None, show_raw=False, rawlog_path=None,
                 baud=BAUD, parity=None):
        self.port = port or find_port()
        self.show_raw = show_raw
        self.baud = baud
        self.parity = parity  # None (8N1) or "E" (8E1, used by DS2 on E39)
        self.rawlog = open(rawlog_path, "a") if rawlog_path else None
        try:
            self._open(self.port)
        except PORT_ERRORS:
            print("!! port not opening cleanly — trying USB-level reset of "
                  "the adapter")
            if not _usb_reset():
                raise
            self._open(self.port)

    def _open(self, port):
        self.io = _make_io(port, self.baud, self.parity)
        self.buf = b""

    def reopen(self, wait=None):
        """Wait for the FTDI cable to (re)appear and reopen it.

        The adapter can re-enumerate with a different name, so re-discover
        it. Returns True once reopened, False if `wait` seconds elapse.
        """
        try:
            self.io.close()
        except PORT_ERRORS:
            pass
        deadline = None if wait is None else now() + wait
        last_reset = 0.0
        while deadline is None or now() < deadline:
            cand = find_port()
            if cand:
                try:
                    self._open(cand)
                    self.port = cand
                    return True
                except PORT_ERRORS:
                    # enumerated but driver wedged — reset it (rate-limited)
                    if now() - last_reset > 5.0:
                        last_reset = now()
                        _usb_reset()
                    continue
            time.sleep(0.5)
        return False

    def close(self):
        if self.rawlog:
            self.rawlog.close()
        self.io.close()

    def log(self, dirn, data, note=""):
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"{ts} {dirn} {hexs(data)}{(' ' + note) if note else ''}"
        if self.show_raw:
            print(f"    {line}")
        if self.rawlog:
            self.rawlog.write(line + "\n")
            self.rawlog.flush()

    def flush(self):
        self.io.flush_io()
        self.buf = b""

    def _pump(self, wait):
        if self.io.wait_readable(max(0.0, wait)):
            chunk = self.io.read(256)
            if chunk:
                self.buf += chunk
                return True
        return False

    def write_raw(self, data):
        """Write bytes straight to the wire (used by DS2's own framing)."""
        self.io.write(data)

    def drain(self):
        """Block until the OS TX buffer is flushed to the wire."""
        self.io.drain()

    def _try_parse(self):
        while self.buf[:1] == b"\x00":
            self.buf = self.buf[1:]
        if len(self.buf) < 2:
            return None
        fmt = self.buf[0]
        ln = fmt & 0x3F
        i = 3 if (fmt & 0xC0) in (0x80, 0xC0) else 1
        if ln == 0:
            if len(self.buf) < i + 1:
                return None
            ln = self.buf[i]
            i += 1
        need = i + ln + 1
        if need > 260:
            self.buf = self.buf[1:]
            return self._try_parse()
        if len(self.buf) < need:
            return None
        frame = self.buf[:need]
        if (sum(frame[:-1]) & 0xFF) != frame[-1]:
            self.buf = self.buf[1:]  # resync
            return self._try_parse()
        self.buf = self.buf[need:]
        return frame

    def read_frames(self, deadline, want=1):
        frames = []
        while now() < deadline:
            f = self._try_parse()
            if f:
                self.log("<<", f)
                frames.append(f)
                if len(frames) >= want:
                    break
                continue
            self._pump(min(0.04, deadline - now()))
        while len(frames) < want:
            f = self._try_parse()
            if not f:
                break
            self.log("<<", f)
            frames.append(f)
        return frames

    def request(self, payload, target, functional=False, timeout=0.6, want=1,
                retries=0):
        fmtbase = 0xC0 if functional else 0x80
        msg = bytes([fmtbase | len(payload), target, TESTER]) + payload
        msg += cks(msg)
        for attempt in range(retries + 1):
            if attempt:
                time.sleep(0.06)  # P3 idle before retransmit
            self.io.flush_input()
            self.buf = b""
            self.log(">>", msg, "(retry)" if attempt else "")
            self.io.write(msg)
            self.io.drain()
            deadline = now() + timeout
            # consume our own K-line echo
            while len(self.buf.lstrip(b"\x00")) < len(msg) and now() < deadline:
                self._pump(0.02)
            b = self.buf.lstrip(b"\x00")
            if b[: len(msg)] == msg:
                self.buf = b[len(msg):]
            frames = self.read_frames(deadline, want)
            # 7F <svc> 78 = requestCorrectlyReceived-ResponsePending:
            # the real answer follows, wait for it (bounded)
            waited = 0
            while (frames and waited < 5
                   and frame_payload(frames[-1])[:1] == b"\x7F"
                   and frame_payload(frames[-1])[2:3] == b"\x78"):
                frames = frames[:-1] + self.read_frames(now() + 3.0, want)
                waited += 1
            if frames:
                return frames
        return []

    def fast_init(self, target, functional=False, timeout=0.7):
        """Returns the response frame on success, False if the module
        answered but refused (e.g. KOMBI's 7F — the session usually works
        anyway), None on silence."""
        self.flush()
        time.sleep(0.3)  # W5 bus idle
        self.io.set_break(True)
        time.sleep(0.025)
        self.io.set_break(False)
        time.sleep(0.023)
        frames = self.request(b"\x81", target, functional, timeout)
        for f in frames:
            p = frame_payload(f)
            if p[:1] == b"\xC1":
                return f
        return False if frames else None

    def slow_init(self, addr):
        """ISO 9141 / KWP 5-baud init: bit-bang the address with break timing."""
        self.flush()
        time.sleep(0.3)
        bits = [0]  # start bit
        bits += [(addr >> i) & 1 for i in range(8)]
        bits += [1]  # stop bit
        for bit in bits:
            self.io.set_break(not bit)   # bit 0 -> break asserted (line low)
            time.sleep(0.2)
        self.io.set_break(False)
        deadline = now() + 1.5
        while now() < deadline:
            self._pump(0.05)
            b = self.buf.lstrip(b"\x00")
            if len(b) >= 3:  # sync 0x55 + two key bytes
                break
        b = self.buf.lstrip(b"\x00")
        self.log("<<", b, "(5-baud init reply)")
        if len(b) >= 3 and b[0] == 0x55:
            kb2 = b[2]
            time.sleep(0.03)
            self.io.write(bytes([kb2 ^ 0xFF]))  # ack: inverted KB2
            self.io.drain()
            time.sleep(0.05)
            self.buf = b""
            self.io.flush_input()
            return (b[1], b[2])
        return None

    def stop_comm(self, target):
        self.request(b"\x82", target, timeout=0.3)


# ---------------------------------------------------------------- decoding

def dtc_text(hi, lo):
    letter = "PCBU"[hi >> 6]
    return f"{letter}{(hi >> 4) & 0x3}{hi & 0xF:X}{lo >> 4:X}{lo & 0xF:X}"


STATUS_BITS = [
    (0x80, "warning-lamp"),
    (0x40, "confirmed"),
    (0x20, "test-incomplete-this-cycle"),
    (0x10, "test-incomplete-since-clear"),
    (0x08, "history"),
    (0x04, "pending"),
    (0x02, "current"),
    (0x01, "test-failed"),
]


def decode_dtc_payload(p, is_dme=False):
    """p = 58 n [hi lo status]*n"""
    out = []
    n = p[1]
    body = p[2:]
    for k in range(min(n, len(body) // 3)):
        hi, lo, st = body[3 * k], body[3 * k + 1], body[3 * k + 2]
        bits = ",".join(name for bit, name in STATUS_BITS if st & bit)
        label = f"0x{hi:02X}{lo:02X}"
        if is_dme:
            label += f" ({dtc_text(hi, lo)})"
        out.append(f"{label}  status=0x{st:02X} [{bits}]")
    return out


def read_dtcs(kl, target):
    for req in (b"\x18\x02\xFF\xFF", b"\x18\x00\xFF\x00", b"\x18\x02\x00\x00"):
        frames = kl.request(req, target, timeout=0.9)
        for f in frames:
            p = frame_payload(f)
            if p[:1] == b"\x58":
                return p
            if p[:2] == b"\x7F\x18":
                break  # negative; try next variant
    return None


def read_ident_parts(kl, target):
    """KWP readECUIdentification (service 1A), tried across the common
    identifiers (0x80 ident, 0x86/0x87 part numbers). Returns
    (identifier, hex_str, ascii_str) for the first one that answers, or
    None. Split out from read_ident() so callers that want the ASCII
    (e.g. the dashboard's part-number column) don't have to re-parse its
    formatted string."""
    for ident in (0x80, 0x86, 0x87):
        frames = kl.request(bytes([0x1A, ident]), target, timeout=0.6)
        for f in frames:
            p = frame_payload(f)
            if p[:1] == b"\x5A":
                asc = "".join(chr(c) if 32 <= c < 127 else "." for c in p[2:])
                return ident, hexs(p[2:]), asc
    return None


def read_ident(kl, target):
    parts = read_ident_parts(kl, target)
    if not parts:
        return None
    ident, hexstr, asc = parts
    return f"1A{ident:02X}: {hexstr}  |{asc}|"


# ---------------------------------------------------------------- modes

def obd_pid(kl, pid, target=DME, functional=False, timeout=0.4, retries=0):
    frames = kl.request(bytes([0x01, pid]), target, functional, timeout,
                        retries=retries)
    for f in frames:
        p = frame_payload(f)
        if len(p) >= 2 and p[0] == 0x41 and p[1] == pid:
            return p[2:]
    return None


def mode_pids(kl):
    if not kl.fast_init(DME):
        sys.exit("No response from DME (ignition on?)")
    supported = set()
    base = 0x00
    while True:
        data = obd_pid(kl, base)
        if not data or len(data) < 4:
            break
        mask = int.from_bytes(data[:4], "big")
        for i in range(32):
            if mask & (1 << (31 - i)):
                supported.add(base + 1 + i)
        if not (mask & 1) or base >= 0xE0:
            break
        base += 0x20
    print("Supported Mode-01 PIDs:", " ".join(f"{p:02X}" for p in sorted(supported)))
    print(f"PID 0x42 (control module voltage): "
          f"{'SUPPORTED' if 0x42 in supported else 'NOT supported'}")
    kl.stop_comm(DME)
    return supported


def scan_addr(kl, addr, name=""):
    f = kl.fast_init(addr)
    if f is None:
        return False
    if f is False:
        # answered but refused StartCommunication (KOMBI does this);
        # the module usually serves requests regardless — carry on.
        print(f"\n== 0x{addr:02X} {name or MODULES.get(addr, '?')} "
              f"(refused init, continuing anyway)")
    else:
        print(f"\n== 0x{addr:02X} {name or MODULES.get(addr, '?')} "
              f"(responded as 0x{frame_source(f):02X})")
    ident = read_ident(kl, addr)
    if ident:
        print(f"   ident {ident}")
    p = read_dtcs(kl, addr)
    if p is None:
        print("   DTC read: no positive response")
    elif p[1] == 0:
        print("   DTCs: none stored")
    else:
        print(f"   DTCs ({p[1]}):")
        for line in decode_dtc_payload(p, is_dme=(addr == DME)):
            print(f"     {line}")
    kl.stop_comm(addr)
    return True


def mode_scan(kl, addrs):
    found = []
    for addr in addrs:
        if addr in (OBD_FUNCTIONAL, TESTER):
            continue
        if scan_addr(kl, addr):
            found.append(addr)
        time.sleep(0.05)
    print(f"\nResponding modules: "
          f"{', '.join(f'0x{a:02X}' for a in found) or 'none'}")
    return found


def mode_clear(kl, addrs):
    """Clear fault memory (KWP clearDiagnosticInformation, service 0x14),
    then re-read to verify. Faults whose cause is still present (e.g. the
    MRS BST code with a damaged cable) will refuse to clear or return."""
    for addr in addrs:
        r = kl.fast_init(addr)
        if r is None:
            print(f"0x{addr:02X}: no response, skipped")
            continue
        cleared = False
        for req in (b"\x14\xFF\xFF", b"\x14\xFF\xFF\x00", b"\x14\x00\x00"):
            frames = kl.request(req, addr, timeout=1.5)
            neg = None
            for f in frames:
                p = frame_payload(f)
                if p[:1] == b"\x54":
                    cleared = True
                elif p[:2] == b"\x7F\x14":
                    neg = p[2]
            if cleared:
                break
            if neg is not None and neg != 0x12:  # 12 = subFunc unsupported
                break
        p = read_dtcs(kl, addr)
        remaining = p[1] if p else "?"
        name = MODULES.get(addr, "?").split(" (")[0]
        if cleared:
            print(f"0x{addr:02X} {name}: cleared, {remaining} DTC(s) remain")
        else:
            print(f"0x{addr:02X} {name}: clear REFUSED"
                  + (f" (7F 14 {neg:02X})" if neg is not None else ""),
                  f"— {remaining} DTC(s) remain")
        if p and p[1]:
            for line in decode_dtc_payload(p, is_dme=(addr == DME)):
                print(f"     still stored: {line}")
        kl.stop_comm(addr)
        time.sleep(0.1)


def annotate_voltages(data):
    return [f"byte[{i}]={b} -> {b / 10:.1f}V?"
            for i, b in enumerate(data) if 95 <= b <= 160]


def mode_detail(kl, addr):
    """Read fault memory, then per-DTC environment/freeze-frame records.

    BMW KWP2000 modules of this era vary in which service carries the
    environment data (0x17 readStatusOfDTC, 0x12 readFreezeFrameData), so
    try each and show raw payloads with plausible-voltage annotations.
    """
    kl.fast_init(addr)  # negative init tolerated (KOMBI)
    p = read_dtcs(kl, addr)
    if p is None:
        print(f"0x{addr:02X}: no response to fault-memory read")
        return
    if p[1] == 0:
        print(f"0x{addr:02X}: no DTCs stored")
        return
    n = p[1]
    body = p[2:]
    print(f"0x{addr:02X} {MODULES.get(addr, '?')}: {n} DTC(s)")
    for k in range(min(n, len(body) // 3)):
        hi, lo, st = body[3 * k], body[3 * k + 1], body[3 * k + 2]
        print(f"\n-- DTC 0x{hi:02X}{lo:02X} (status 0x{st:02X})")
        for req in (bytes([0x17, hi, lo]),
                    bytes([0x12, hi, lo]),
                    bytes([0x12, hi, lo, 0x00]),
                    bytes([0x12, hi, lo, 0x01])):
            frames = kl.request(req, addr, timeout=0.7)
            for f in frames:
                pl = frame_payload(f)
                if pl[:1] == b"\x7F":
                    print(f"   {hexs(req)} -> negative "
                          f"(7F {pl[1]:02X} {pl[2]:02X})")
                    break
                print(f"   {hexs(req)} -> {hexs(pl)}")
                for note in annotate_voltages(pl[1:]):
                    print(f"        {note}")
    kl.stop_comm(addr)


def mode_probe_voltage(kl, target):
    if kl.fast_init(target) is None:
        sys.exit(f"No response from 0x{target:02X}")
    hits = {}
    for rid in range(0x00, 0x100):
        frames = kl.request(bytes([0x21, rid]), target, timeout=0.25)
        for f in frames:
            p = frame_payload(f)
            if p[:1] == b"\x61":
                hits[rid] = p[2:]
    print(f"{len(hits)} local-identifier records answered.")
    print("\nBytes that look like a plausible system voltage (9.0-15.5 V):")
    for rid, data in hits.items():
        notes = []
        for i, b in enumerate(data):
            if 90 <= b <= 155:
                notes.append(f"byte[{i}]={b} -> {b / 10:.1f}V?")
        for i in range(len(data) - 1):
            v = (data[i] << 8) | data[i + 1]
            if 9000 <= v <= 15500:
                notes.append(f"be16[{i}]={v} -> {v / 1000:.2f}V?")
        if notes:
            print(f"  21 {rid:02X}: {hexs(data)}")
            for n in notes:
                print(f"        {n}")
    kl.stop_comm(target)


def mode_monitor(kl, args):
    functional = False
    if not kl.fast_init(DME):
        print("Physical init to DME failed; falling back to functional OBD init")
        if not kl.fast_init(OBD_FUNCTIONAL, functional=True):
            sys.exit("No response from DME (ignition on?)")
        functional = True
    tgt = OBD_FUNCTIONAL if functional else DME

    use_pid42 = obd_pid(kl, 0x42, tgt, functional) is not None
    kwp_rid = args.local_id
    if not use_pid42 and kwp_rid is None:
        # Verified on this car (ME9 DME): record 0x5A byte 0 = battery
        # voltage in 0.1 V steps (12.3 V ignition-on -> 15.0 V charging).
        kwp_rid = 0x5A
        print("PID 0x42 unsupported; using KWP local id 21 5A "
              "(DME battery voltage, x0.1 V)")
    print(f"Voltage source: "
          f"{'OBD PID 0x42' if use_pid42 else f'KWP 21 {kwp_rid:02X} byte[{args.offset}] x{args.scale}'}")

    csv_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"power_log_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv")
    fcsv = open(csv_path, "w", newline="")
    w = csv.writer(fcsv)
    w.writerow(["iso_time", "epoch", "voltage_V", "rpm", "event"])

    def get_voltage():
        if use_pid42:
            d = obd_pid(kl, 0x42, tgt, functional, timeout=args.timeout,
                        retries=1)
            if d and len(d) >= 2:
                return ((d[0] << 8) | d[1]) / 1000.0
            return None
        frames = kl.request(bytes([0x21, kwp_rid]), tgt, functional,
                            timeout=args.timeout, retries=1)
        for f in frames:
            p = frame_payload(f)
            if p[:1] == b"\x61" and len(p) > 2 + args.offset:
                return p[2 + args.offset] * args.scale
        return None

    def get_rpm():
        d = obd_pid(kl, 0x0C, tgt, functional, timeout=args.timeout,
                    retries=1)
        if d and len(d) >= 2:
            return ((d[0] << 8) | d[1]) / 4.0
        return None

    rpm = get_rpm()
    misses = 0
    lost = False
    reinit_fails = 0
    samples = []
    warn_counts = {"undervolt": 0, "overvolt": 0, "comm": 0}
    start = now()
    i = 0
    print(f"Logging to {csv_path}  (Ctrl+C to stop)\n")
    try:
        while args.duration is None or now() - start < args.duration:
            i += 1
            try:
                v = get_voltage()
                if i % 3 == 0:
                    r = get_rpm()
                    if r is not None:
                        rpm = r
            except PORT_ERRORS:
                # USB adapter dropped off the bus — diagnostic in itself if
                # it coincides with the car's power dipping.
                ts = datetime.datetime.now()
                print(f"{ts:%H:%M:%S.%f}"[:-3],
                      "!! WARNING: USB adapter dropped off the bus — waiting "
                      "for it to re-enumerate (check hub/cable)")
                w.writerow([ts.isoformat(), f"{ts.timestamp():.3f}", "",
                            rpm or "", "usb_dropout"])
                fcsv.flush()
                warn_counts["comm"] += 1
                kl.reopen()
                ts = datetime.datetime.now()
                ok = kl.fast_init(tgt, functional=functional)
                print(f"{ts:%H:%M:%S.%f}"[:-3],
                      f">> adapter back on {kl.port}; "
                      f"ECU {'re-initialised' if ok else 'NOT responding yet'}")
                w.writerow([ts.isoformat(), f"{ts.timestamp():.3f}", "",
                            rpm or "", "usb_restored"])
                continue
            ts = datetime.datetime.now()
            event = ""
            if v is None:
                misses += 1
                if misses >= 3 and not lost:
                    lost = True
                    warn_counts["comm"] += 1
                    event = "comm_lost"
                    print(f"{ts:%H:%M:%S.%f}"[:-3],
                          "!! WARNING: communication with ECU lost — "
                          "re-initialising")
                if lost:
                    if kl.fast_init(tgt, functional=functional):
                        lost = False
                        misses = 0
                        reinit_fails = 0
                        event = "comm_restored"
                        print(f"{ts:%H:%M:%S.%f}"[:-3], ">> communication restored")
                    else:
                        reinit_fails += 1
                        if reinit_fails % 4 == 0:
                            # ECU init keeps failing — suspect the adapter,
                            # not the car: reset/reopen it at USB level.
                            print(f"{ts:%H:%M:%S.%f}"[:-3],
                                  "!! re-init failing; recovering adapter "
                                  "at USB level")
                            kl.reopen(wait=15)
                        time.sleep(0.5)
                w.writerow([ts.isoformat(), f"{ts.timestamp():.3f}", "",
                            rpm or "", event])
                continue
            misses = 0
            samples.append(v)
            running = rpm is not None and rpm > 400
            warns = []
            if v > 15.0:
                warns.append("OVERVOLTAGE >15.0V — suspect regulator")
                warn_counts["overvolt"] += 1
            if running and v < 12.5:
                warns.append("UNDERVOLTAGE while engine running — "
                             "alternator/connection")
                warn_counts["undervolt"] += 1
            event = ";".join(x.split(" ")[0] for x in warns)
            w.writerow([ts.isoformat(), f"{ts.timestamp():.3f}",
                        f"{v:.2f}", rpm if rpm is not None else "", event])
            line = (f"{ts:%H:%M:%S.%f}"[:-3] +
                    f"  {v:6.2f} V  " +
                    (f"{rpm:5.0f} rpm" if rpm is not None else "  ?  rpm"))
            for wtext in warns:
                line += f"   !! {wtext}"
            print(line)
            fcsv.flush()
            dt = args.interval - 0.0  # pacing
            time.sleep(max(0.0, dt))
    except KeyboardInterrupt:
        pass
    finally:
        fcsv.close()
        if samples:
            print(f"\n--- summary: {len(samples)} samples, "
                  f"min {min(samples):.2f} V, max {max(samples):.2f} V, "
                  f"avg {sum(samples) / len(samples):.2f} V")
            print(f"    warnings: undervolt={warn_counts['undervolt']} "
                  f"overvolt={warn_counts['overvolt']} "
                  f"comm-loss={warn_counts['comm']}")
        print(f"    CSV: {csv_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=None,
                    help="serial port (auto-detected if omitted)")
    ap.add_argument("--raw", action="store_true",
                    help="print raw frames on the wire")
    sub = ap.add_subparsers(dest="mode", required=True)
    sub.add_parser("pids")
    sub.add_parser("scan")
    sub.add_parser("sweep")
    p = sub.add_parser("dtc")
    p.add_argument("addr", type=lambda s: int(s, 16))
    p.add_argument("--slow", action="store_true", help="use 5-baud init")
    p = sub.add_parser("detail",
                       help="DTCs + per-fault environment/freeze-frame data")
    p.add_argument("addr", type=lambda s: int(s, 16))
    p = sub.add_parser("clear", help="clear fault memory and verify")
    p.add_argument("addrs", nargs="+", type=lambda s: int(s, 16))
    p = sub.add_parser("probe-voltage")
    p.add_argument("--addr", type=lambda s: int(s, 16), default=DME)
    p = sub.add_parser("monitor")
    p.add_argument("--interval", type=float, default=0.06,
                   help="pause between polls, seconds")
    p.add_argument("--timeout", type=float, default=0.35)
    p.add_argument("--duration", type=float, default=None,
                   help="stop after N seconds (default: run until Ctrl+C)")
    p.add_argument("--local-id", type=lambda s: int(s, 16), default=None,
                   help="KWP local identifier for voltage if PID 42 unsupported")
    p.add_argument("--offset", type=int, default=0,
                   help="byte offset of voltage within the KWP record")
    p.add_argument("--scale", type=float, default=0.1,
                   help="multiplier for the voltage byte")
    args = ap.parse_args()

    rawlog = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "kline_raw.log")
    kl = KLine(args.port, show_raw=args.raw, rawlog_path=rawlog)

    def dispatch():
        if args.mode == "pids":
            mode_pids(kl)
        elif args.mode == "scan":
            mode_scan(kl, list(MODULES))
        elif args.mode == "sweep":
            mode_scan(kl, [a for a in range(0x00, 0xE9)])
        elif args.mode == "dtc":
            if args.slow:
                kb = kl.slow_init(args.addr)
                print(f"5-baud init key bytes: "
                      f"{('%02X %02X' % kb) if kb else 'no response'}")
                if kb:
                    scan_addr(kl, args.addr)
            else:
                if not scan_addr(kl, args.addr):
                    print(f"0x{args.addr:02X}: no response to fast init")
        elif args.mode == "detail":
            mode_detail(kl, args.addr)
        elif args.mode == "clear":
            mode_clear(kl, args.addrs)
        elif args.mode == "probe-voltage":
            mode_probe_voltage(kl, args.addr)
        elif args.mode == "monitor":
            mode_monitor(kl, args)

    try:
        try:
            dispatch()
        except PORT_ERRORS as e:
            # adapter dropped or driver wedged mid-run: recover once and
            # rerun the mode (monitor recovers internally and won't get here
            # unless the port is truly gone)
            print(f"!! adapter/port error ({e}) — attempting recovery")
            if not kl.reopen(wait=30):
                raise
            print(f">> adapter recovered on {kl.port}; re-running")
            dispatch()
    finally:
        kl.close()


if __name__ == "__main__":
    main()
