#!/usr/bin/env python3
"""Offline tests for diag_ui.Obd2Adapter — the generic SAE J1979 K-line
adapter added for OBD-II-only cars (e.g. the Porsche 996) that have no
manufacturer-specific module map.

Same hardware-free approach as test_windows_backend.py: swap power_diag's
transport (_make_io) for an in-memory K-line-echo stand-in, so the real
KLine framing/checksum/fast-init logic runs end to end against canned
module responses, no cable or car needed.
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import diag_ui
import obd2
import power_diag


class FakeIO:
    """K-line-echo stand-in for power_diag._make_io()'s real backend.

    write() appends straight to the RX buffer (the K-line echoes every TX
    byte) followed by the *next* queued module reply, if any -- a FIFO so a
    test can queue the StartCommunication (0xC1) reply fast_init() needs
    ahead of the actual command reply that follows it, same two-request
    shape every real adapter call makes (fast_init, then the request)."""

    def __init__(self):
        self.rx = bytearray()
        self._queue = collections.deque()
        self.breaks = []

    def wait_readable(self, timeout):
        return len(self.rx) > 0

    def read(self, n):
        take = bytes(self.rx[:n])
        del self.rx[:n]
        return take

    def write(self, data):
        self.rx += data
        if self._queue:
            self.rx += self._queue.popleft()

    def drain(self):
        pass

    def flush_input(self):
        pass

    def flush_io(self):
        self.rx = bytearray()

    def set_break(self, on):
        self.breaks.append(bool(on))

    def close(self):
        pass


# StartCommunication positive response (0xC1 ...) -- fast_init() only
# checks the first byte, so the rest is arbitrary key bytes.
_START_COMM_OK = bytes([0xC1, 0xEA, 0x8F])


def _frame(payload, source=0x10):
    """One ISO14230 frame carrying `payload`, as if module `source`
    answered our request."""
    resp = bytes([0x80 | len(payload), 0xF1, source]) + payload
    return resp + power_diag.cks(resp)


def _queue(io, payload, source=0x10):
    """Queue a single reply frame (for a call made without going through
    fast_init first, e.g. a raw obd_pid() probe)."""
    io._queue.append(_frame(payload, source))


def _queue_after_init(io, payload, source=0x10):
    """Queue the StartCommunication reply + the actual response, for any
    call that begins with an internal fast_init() (detect/faults/clear/
    connect all do)."""
    io._queue.append(_frame(_START_COMM_OK, source))
    io._queue.append(_frame(payload, source))


def _make_adapter():
    """An Obd2Adapter wired to a FakeIO instead of a real serial port."""
    orig_make_io = power_diag._make_io
    power_diag._make_io = lambda port, baud, parity: FakeIO()
    try:
        return diag_ui.Obd2Adapter()
    finally:
        power_diag._make_io = orig_make_io


def test_detect_and_read_vin():
    a = _make_adapter()
    try:
        # Mode 09 PID 02 positive response: SID 0x49, PID echo 0x02, then
        # 1 item-count byte + 17 ASCII VIN characters.
        _queue_after_init(a.kl.io, b"\x49\x02\x01" + b"WP0ZZZ99ZYS600603")
        assert a.detect() is True
        assert a.vin == "WP0ZZZ99ZYS600603"
        assert a.vin != a.vin_placeholder
        print("test_detect_and_read_vin OK")
    finally:
        a.close()


def test_detect_no_response_fails_cleanly():
    a = _make_adapter()
    try:
        # Nothing queued at all -- fast_init times out -> detect() is False,
        # vin stays the placeholder rather than a guessed/promoted value.
        assert a.detect() is False
        assert a.vin == a.vin_placeholder
        print("test_detect_no_response_fails_cleanly OK")
    finally:
        a.close()


def test_faults_parses_dtcs():
    a = _make_adapter()
    try:
        # Mode 03 positive response: SID 0x43, DTC count, then 2-byte
        # DTC pairs (P0301 = misfire cylinder 1).
        _queue_after_init(a.kl.io, bytes([0x43, 0x01, 0x03, 0x01]))
        res = a.faults(power_diag.OBD_FUNCTIONAL)
        assert res["ok"] is True
        assert res["count"] == 1
        assert res["entries"][0]["code"] == "P0301"
        print("test_faults_parses_dtcs OK")
    finally:
        a.close()


def test_faults_no_dtcs_stored():
    a = _make_adapter()
    try:
        _queue_after_init(a.kl.io, bytes([0x43, 0x00]))
        res = a.faults(power_diag.OBD_FUNCTIONAL)
        assert res["ok"] is True
        assert res["count"] == 0
        print("test_faults_no_dtcs_stored OK")
    finally:
        a.close()


def test_clear_reports_cleared():
    a = _make_adapter()
    try:
        # fast_init at the top of clear() gets this queued 0x44 (positive
        # response to Mode 04) as its reply; the follow-up faults() re-read
        # gets nothing queued (times out to "no response"), but clear()'s
        # own ok/status must reflect the 0x44 it actually saw.
        _queue_after_init(a.kl.io, bytes([0x44]))
        res = a.clear(power_diag.OBD_FUNCTIONAL)
        assert res["ok"] is True
        assert res["status"] == "cleared"
        print("test_clear_reports_cleared OK")
    finally:
        a.close()


def test_pid_read_over_functional_address_decodes_with_obd2():
    """Exercises the same power_diag.obd_pid() + obd2.decode_pid() combo
    live_sample() uses per channel, targeted at the functional address
    (0x33) instead of a physical DME -- the one piece that's new versus
    E87Adapter, which already proved this combo against a physical
    address."""
    a = _make_adapter()
    try:
        assert a.kl.fast_init(power_diag.OBD_FUNCTIONAL,
                              functional=True) is None  # nothing queued yet
        _queue(a.kl.io, bytes([0x41, 0x0C, 0x1A, 0xF8]))  # RPM = 1726
        d = power_diag.obd_pid(a.kl, 0x0C, power_diag.OBD_FUNCTIONAL,
                               functional=True)
        assert d is not None
        assert obd2.decode_pid(0x0C, d) == 1726.0
        print("test_pid_read_over_functional_address_decodes_with_obd2 OK")
    finally:
        a.close()


def test_vehicle_profile_registered():
    import vehicle_profiles as vp
    p = vp.get_profile("porsche_996")
    assert p and p["protocol"] == "kwp2000"
    assert not vp.validate_profile(p)
    print("test_vehicle_profile_registered OK")


def test_connect_obd2_no_response():
    """End-to-end through diag_ui.connect(proto="obd2"), same entry point
    ui.html's manual protocol override (and the auto-detect fallback) use."""
    orig_make_io = power_diag._make_io
    power_diag._make_io = lambda port, baud, parity: FakeIO()
    try:
        diag_ui.ADAPTER = None
        a = diag_ui.connect("obd2")
        assert a is None  # nothing queued -> fast_init gets no reply
        assert diag_ui.ADAPTER is None
        assert diag_ui.ADAPTER_ERR
        print("test_connect_obd2_no_response OK")
    finally:
        power_diag._make_io = orig_make_io
        if diag_ui.ADAPTER:
            diag_ui.ADAPTER.close()
        diag_ui.ADAPTER = None


def test_connect_obd2_succeeds_and_populates_status():
    """Same entry point, but the functional address answers -- ADAPTER
    should end up an Obd2Adapter with the confirmed VIN, exactly what
    /api/connect and /api/status report to ui.html."""
    orig_make_io = power_diag._make_io
    fake = FakeIO()
    power_diag._make_io = lambda port, baud, parity: fake
    try:
        diag_ui.ADAPTER = None
        _queue_after_init(fake, b"\x49\x02\x01" + b"WP0ZZZ99ZYS600603")
        a = diag_ui.connect("obd2")
        assert a is not None
        assert diag_ui.ADAPTER is a
        assert a.proto == "obd2"
        assert a.vin == "WP0ZZZ99ZYS600603"
        assert not diag_ui.ADAPTER_ERR
        print("test_connect_obd2_succeeds_and_populates_status OK")
    finally:
        power_diag._make_io = orig_make_io
        if diag_ui.ADAPTER:
            diag_ui.ADAPTER.close()
        diag_ui.ADAPTER = None


if __name__ == "__main__":
    test_detect_and_read_vin()
    test_detect_no_response_fails_cleanly()
    test_faults_parses_dtcs()
    test_faults_no_dtcs_stored()
    test_clear_reports_cleared()
    test_pid_read_over_functional_address_decodes_with_obd2()
    test_vehicle_profile_registered()
    test_connect_obd2_no_response()
    test_connect_obd2_succeeds_and_populates_status()
    print("\nAll generic-OBD-II K-line tests passed.")
