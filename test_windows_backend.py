#!/usr/bin/env python3
"""Exercise the Windows (pyserial) transport backend on any OS.

The real Windows serial I/O can only be validated on Windows with the
cable, but this forces `power_diag` down its Windows branch with a mocked
pyserial device so the *logic* — backend selection, port discovery, the
echo-strip + frame-parse path, and break signalling — is verified without
hardware. Run on macOS/Linux; it patches sys.platform + injects a fake
`serial` module, then restores.
"""
import importlib
import sys
import types

HERE = __file__


class FakeSerial:
    """Minimal pyserial.Serial stand-in with a K-line echo loopback.

    write() appends the bytes to the RX buffer (the K-line echoes every TX
    byte, exactly as the real cable does), then appends any queued module
    response — so a request() sees echo followed by the answer, like the
    wire.
    """

    def __init__(self):
        self.is_open = False
        self.rx = bytearray()
        self._resp = bytearray()
        self.breaks = []           # record of break_condition toggles
        self.port = self.baudrate = self.bytesize = None
        self.parity = self.stopbits = self.timeout = self.write_timeout = None
        self._bc = False

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    @property
    def in_waiting(self):
        return len(self.rx)

    def read(self, n):
        take = bytes(self.rx[:n])
        del self.rx[:n]
        return take

    def write(self, data):
        self.rx += data            # echo
        if self._resp:
            self.rx += self._resp  # then the module's reply
            self._resp = bytearray()
        return len(data)

    def flush(self):
        pass

    def reset_input_buffer(self):
        self.rx = bytearray()

    def reset_output_buffer(self):
        pass

    @property
    def break_condition(self):
        return self._bc

    @break_condition.setter
    def break_condition(self, v):
        self._bc = bool(v)
        self.breaks.append(bool(v))


def _install_fake_serial():
    serial = types.ModuleType("serial")
    serial.EIGHTBITS = 8
    serial.PARITY_EVEN = "E"
    serial.PARITY_NONE = "N"
    serial.STOPBITS_ONE = 1

    class SerialException(Exception):
        pass

    serial.SerialException = SerialException
    serial.Serial = FakeSerial

    tools = types.ModuleType("serial.tools")
    lp = types.ModuleType("serial.tools.list_ports")

    class _P:
        def __init__(self, device, vid, pid):
            self.device, self.vid, self.pid = device, vid, pid

    lp.comports = lambda: [_P("COM1", None, None),
                           _P("COM3", 0x0403, 0x6001)]   # the FTDI cable
    tools.list_ports = lp
    sys.modules["serial"] = serial
    sys.modules["serial.tools"] = tools
    sys.modules["serial.tools.list_ports"] = lp


def load_windows_power_diag():
    _install_fake_serial()
    sys.platform = "win32"
    import power_diag
    importlib.reload(power_diag)     # re-run top-level under the win branch
    return power_diag


def restore_posix():
    sys.platform = _REAL_PLATFORM
    for m in ("serial", "serial.tools", "serial.tools.list_ports"):
        sys.modules.pop(m, None)
    import power_diag
    importlib.reload(power_diag)


_REAL_PLATFORM = sys.platform


def test_windows_branch_selected():
    pd = load_windows_power_diag()
    try:
        assert pd.IS_WINDOWS is True
        # the win branch imported pyserial and folded its exception in
        assert sys.modules["serial"].SerialException in pd.PORT_ERRORS
        assert pd._make_io.__module__ == "power_diag"
        print("test_windows_branch_selected OK")
    finally:
        restore_posix()


def test_find_port_picks_ftdi_com():
    pd = load_windows_power_diag()
    try:
        assert pd.find_port() == "COM3"   # 0403:6001, not COM1
        print("test_find_port_picks_ftdi_com OK")
    finally:
        restore_posix()


def test_open_configures_serial():
    pd = load_windows_power_diag()
    try:
        kl = pd.KLine(port="COM3", baud=10400, parity="E")
        s = kl.io.ser
        assert s.is_open and s.baudrate == 10400
        assert s.parity == "E" and s.bytesize == 8 and s.timeout == 0
        print("test_open_configures_serial OK")
    finally:
        restore_posix()


def test_request_roundtrip_via_pyserial():
    pd = load_windows_power_diag()
    try:
        kl = pd.KLine(port="COM3")
        pl = b"\x61\x9A\x01\x02"                       # a positive reply
        resp = bytes([0x80 | len(pl), 0xF1, 0x12]) + pl
        resp += pd.cks(resp)
        kl.io.ser._resp = bytearray(resp)             # queue module answer
        frames = kl.request(b"\x21\x9A", 0x12, timeout=0.5)
        assert frames, "no frame parsed through the Windows backend"
        assert pd.frame_payload(frames[0]) == pl
        print("test_request_roundtrip_via_pyserial OK")
    finally:
        restore_posix()


def test_fast_init_uses_break_and_parses_c1():
    pd = load_windows_power_diag()
    try:
        kl = pd.KLine(port="COM3")
        pl = b"\xC1\xEA\x8F"                            # StartComm positive
        resp = bytes([0x80 | len(pl), 0xF1, 0x12]) + pl
        resp += pd.cks(resp)
        kl.io.ser._resp = bytearray(resp)
        f = kl.fast_init(0x12)
        assert f is not False and f is not None, "fast_init did not accept C1"
        # break was asserted then released (25 ms low pulse)
        assert True in kl.io.ser.breaks and False in kl.io.ser.breaks
        print("test_fast_init_uses_break_and_parses_c1 OK")
    finally:
        restore_posix()


if __name__ == "__main__":
    test_windows_branch_selected()
    test_find_port_picks_ftdi_com()
    test_open_configures_serial()
    test_request_roundtrip_via_pyserial()
    test_fast_init_uses_break_and_parses_c1()
    print("\nAll Windows-backend tests passed (logic verified without hardware).")
