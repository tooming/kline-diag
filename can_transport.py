#!/usr/bin/env python3
"""SLCAN (Lawicel ASCII) transport over a USB-CAN adapter, for the Skoda
Octavia (and other CAN/UDS cars) on macOS.

Targets CANable 2.0-class adapters running the stock slcan firmware: they
enumerate as a plain USB-CDC serial port (/dev/cu.usbmodem*), so this is a
straight termios open — none of the K+DCAN cable's DriverKit/IOSSIOSPEED
workarounds are needed (that cable is K-line only and cannot be reused for
CAN — see CLAUDE.md).

Protocol reference: Lawicel SLCAN ASCII commands over the serial line —
    S<n>   set bitrate (0=10k 1=20k 2=50k 3=100k 4=125k 5=250k 6=500k
           7=800k 8=1M), must precede O
    O      open channel (normal mode, transmit enabled)
    C      close channel
    t<id3><dlc><data>   send standard (11-bit) data frame
    T<id8><dlc><data>   send extended (29-bit) data frame
    V      report firmware version
Incoming traffic lines mirror t/T; a bare CR acks a command, BEL (0x07)
signals an error. Pure stdlib — no pyserial.
"""
import fcntl
import glob
import os
import select
import struct
import sys
import termios
import time

IS_WINDOWS = sys.platform.startswith("win")
if IS_WINDOWS:
    import serial
    from serial.tools import list_ports
    PORT_ERRORS = (OSError, serial.SerialException)
else:
    PORT_ERRORS = (OSError, termios.error)

BITRATE_CODES = {10000: "0", 20000: "1", 50000: "2", 100000: "3",
                  125000: "4", 250000: "5", 500000: "6", 800000: "7",
                  1000000: "8"}


def now():
    return time.time()


def find_port():
    """Locate the USB-CAN adapter's serial port. CANable-class devices are
    STM32 USB-CDC and enumerate as /dev/cu.usbmodem* on macOS (distinct
    from the K+DCAN cable's /dev/cu.usbserial* FTDI VCP)."""
    if IS_WINDOWS:
        allp = [p.device for p in list_ports.comports()]
        return allp[0] if allp else None
    cands = glob.glob("/dev/cu.usbmodem*")
    return cands[0] if cands else None


class _PosixSerial:
    def __init__(self, port):
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        a = termios.tcgetattr(self.fd)
        a[0] = a[1] = a[3] = 0
        a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        a[4] = a[5] = termios.B115200  # nominal only; USB-CDC ignores it
        a[6][termios.VMIN] = 0
        a[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, a)

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

    def flush_input(self):
        termios.tcflush(self.fd, termios.TCIFLUSH)

    def close(self):
        os.close(self.fd)


class _WindowsSerial:
    def __init__(self, port):
        self.ser = serial.Serial()
        self.ser.port = port
        self.ser.baudrate = 115200
        self.ser.timeout = 0
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
        return self.ser.read(n)

    def write(self, data):
        self.ser.write(data)

    def flush_input(self):
        self.ser.reset_input_buffer()

    def close(self):
        self.ser.close()


def _make_io(port):
    return _WindowsSerial(port) if IS_WINDOWS else _PosixSerial(port)


class SlcanError(Exception):
    pass


class SlcanPort:
    def __init__(self, port=None, bitrate=500000, show_raw=False,
                 rawlog_path="can_raw.log"):
        self.port = port or find_port()
        if not self.port:
            raise SlcanError(
                "no USB-CAN adapter found (looked for /dev/cu.usbmodem*) "
                "— is it plugged in? the K+DCAN cable will not work here, "
                "it has no CAN transceiver")
        self.bitrate = bitrate
        self.show_raw = show_raw
        self.rawlog = open(rawlog_path, "a") if rawlog_path else None
        self.buf = b""
        self._open(self.port)

    def _open(self, port):
        self.io = _make_io(port)
        self.buf = b""
        self.io.flush_input()
        # Adapter may already be open from a previous crashed run.
        self._cmd("C", expect_ack=False)
        code = BITRATE_CODES.get(self.bitrate)
        if not code:
            raise SlcanError(f"unsupported bitrate {self.bitrate}")
        self._cmd("S" + code)
        self._cmd("O")

    def reopen(self, wait=None):
        try:
            self.io.close()
        except PORT_ERRORS:
            pass
        deadline = None if wait is None else now() + wait
        while deadline is None or now() < deadline:
            cand = find_port()
            if cand:
                try:
                    self._open(cand)
                    self.port = cand
                    return True
                except (PORT_ERRORS, SlcanError):
                    pass
            time.sleep(0.5)
        return False

    def close(self):
        try:
            self._cmd("C", expect_ack=False)
        except PORT_ERRORS:
            pass
        if self.rawlog:
            self.rawlog.close()
        self.io.close()

    def _log(self, dirn, text):
        if self.show_raw:
            print(f"    {dirn} {text}")
        if self.rawlog:
            self.rawlog.write(f"{dirn} {text}\n")
            self.rawlog.flush()

    def _cmd(self, text, expect_ack=True, timeout=0.5):
        self.io.write((text + "\r").encode("ascii"))
        self._log(">>", text)
        if not expect_ack:
            return
        deadline = now() + timeout
        while now() < deadline:
            self._pump(min(0.05, deadline - now()))
            ack = self._consume_ack()
            if ack is not None:
                if not ack:
                    raise SlcanError(f"adapter rejected command: {text}")
                return
        raise SlcanError(f"no response to command: {text}")

    def _pump(self, wait):
        if self.io.wait_readable(wait):
            chunk = self.io.read(256)
            if chunk:
                self.buf += chunk

    def _consume_ack(self):
        """Pull a bare CR (ack) or BEL (nak) off the front of the buffer.
        Command acks always arrive as the first byte after a command, before
        any frame data, so no need to scan ahead."""
        if not self.buf:
            return None
        if self.buf[:1] == b"\r":
            self.buf = self.buf[1:]
            return True
        if self.buf[:1] == b"\x07":
            self.buf = self.buf[1:]
            return False
        return None

    def _try_parse_frame(self):
        while self.buf[:1] == b"\x07":
            self.buf = self.buf[1:]
        i = self.buf.find(b"\r")
        if i < 0:
            return None
        line = self.buf[:i]
        self.buf = self.buf[i + 1:]
        if not line or line[:1] not in (b"t", b"T"):
            return self._try_parse_frame()
        try:
            ext = line[:1] == b"T"
            idlen = 8 if ext else 3
            can_id = int(line[1:1 + idlen], 16)
            dlc = int(line[1 + idlen:2 + idlen], 16)
            data = bytes.fromhex(
                line[2 + idlen:2 + idlen + dlc * 2].decode("ascii"))
        except ValueError:
            return self._try_parse_frame()
        self._log("<<", line.decode("ascii", "replace"))
        return (can_id, data, ext)

    def send_frame(self, can_id, data, extended=False):
        if len(data) > 8:
            raise SlcanError("CAN data frame max 8 bytes")
        if extended:
            text = f"T{can_id:08X}{len(data):X}{data.hex().upper()}"
        else:
            text = f"t{can_id:03X}{len(data):X}{data.hex().upper()}"
        self._cmd(text)

    def recv_frame(self, timeout):
        deadline = now() + timeout
        while True:
            f = self._try_parse_frame()
            if f:
                return f
            remaining = deadline - now()
            if remaining <= 0:
                return None
            self._pump(min(0.02, remaining))

    def drain_rx(self):
        while self._try_parse_frame():
            pass
