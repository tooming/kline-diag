#!/usr/bin/env python3
"""Offline tests for the CAN/UDS stack (isotp.py, uds.py, obd2.py) added
for the Skoda Octavia. Pure protocol-framing tests against a mock CAN bus
— no adapter or car needed, matching the rest of this repo's test style."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import obd2
from isotp import IsoTpChannel, IsoTpError
from uds import Uds, UdsError, decode_dtc_records, dtc_to_text


class MockCanBus:
    """Records every send_frame call; recv_frame replays a pre-loaded
    queue of (can_id, data, extended) tuples, ignoring the timeout."""

    def __init__(self):
        self.sent = []
        self.rx_queue = []

    def queue(self, can_id, data, extended=False):
        self.rx_queue.append((can_id, bytes(data), extended))

    def send_frame(self, can_id, data, extended=False):
        self.sent.append((can_id, bytes(data), extended))

    def recv_frame(self, timeout):
        return self.rx_queue.pop(0) if self.rx_queue else None

    def drain_rx(self):
        self.rx_queue.clear()


def test_isotp_single_frame_send():
    bus = MockCanBus()
    chan = IsoTpChannel(bus, tx_id=0x7E0, rx_id=0x7E8)
    chan.send(bytes([0x22, 0xF1, 0x90]))
    assert len(bus.sent) == 1
    can_id, data, ext = bus.sent[0]
    assert can_id == 0x7E0 and not ext
    assert data == bytes([0x03, 0x22, 0xF1, 0x90, 0, 0, 0, 0])
    print("test_isotp_single_frame_send OK")


def test_isotp_single_frame_recv():
    bus = MockCanBus()
    chan = IsoTpChannel(bus, tx_id=0x7E0, rx_id=0x7E8)
    bus.queue(0x7E8, bytes([0x03, 0x62, 0xF1, 0x90, 0, 0, 0, 0]))
    resp = chan.recv(timeout=0.1)
    assert resp == bytes([0x62, 0xF1, 0x90]), resp
    print("test_isotp_single_frame_recv OK")


def test_isotp_multiframe_recv_sends_flow_control():
    bus = MockCanBus()
    chan = IsoTpChannel(bus, tx_id=0x7E0, rx_id=0x7E8)
    payload = bytes([0x59, 0x02, 0xFF]) + bytes(range(20))  # 23 bytes total
    # First frame: 6 payload bytes; Consecutive frames: 7 bytes each.
    bus.queue(0x7E8, bytes([0x10, len(payload)]) + payload[:6])
    rest = payload[6:]
    seq = 1
    while rest:
        chunk, rest = rest[:7], rest[7:]
        frame = bytes([0x20 | seq]) + chunk
        frame += b"\x00" * (8 - len(frame))
        bus.queue(0x7E8, frame)
        seq = (seq + 1) & 0x0F
    resp = chan.recv(timeout=0.5)
    assert resp == payload, (resp, payload)
    # We must have sent exactly one flow-control frame back to the ECU.
    fc_frames = [f for f in bus.sent if f[0] == 0x7E0 and f[1][0] >> 4 == 3]
    assert len(fc_frames) == 1, bus.sent
    assert fc_frames[0][1][0] & 0x0F == 0, "flow status should be continue"
    print("test_isotp_multiframe_recv_sends_flow_control OK")


def test_isotp_multiframe_send_respects_flow_control():
    bus = MockCanBus()
    chan = IsoTpChannel(bus, tx_id=0x7E0, rx_id=0x7E8)
    # ECU immediately grants "send all, no delay".
    bus.queue(0x7E8, bytes([0x30, 0x00, 0x00, 0, 0, 0, 0, 0]))
    payload = bytes(range(10))  # forces FF + 1 CF (6 + 4 bytes)
    chan.send(payload)
    ff = bus.sent[0]
    assert ff[0] == 0x7E0
    assert ff[1][0] >> 4 == 1 and (((ff[1][0] & 0x0F) << 8) | ff[1][1]) == 10
    assert ff[1][2:8] == payload[:6]
    cf = bus.sent[1]
    assert cf[1][0] == 0x21, "first consecutive frame must have sequence 1"
    assert cf[1][1:5] == payload[6:]
    print("test_isotp_multiframe_send_respects_flow_control OK")


def test_uds_session_control_and_dtc_read():
    bus = MockCanBus()
    bus.queue(0x7E8, bytes([0x02, 0x50, 0x03, 0, 0, 0, 0, 0]))
    u = Uds(bus, tx_id=0x7E0, rx_id=0x7E8)
    resp = u.session_control()
    assert resp == bytes([0x03]), resp
    assert bus.sent[-1][1][:3] == bytes([0x02, 0x10, 0x03])

    bus2 = MockCanBus()
    # ReadDTCInformation positive response: statusAvailMask + one 4-byte
    # record (3-byte DTC + 1 status byte).
    body = bytes([0x59, 0x02, 0xFF, 0x01, 0x23, 0x45, 0x08])
    bus2.queue(0x7E8, bytes([len(body)]) + body + b"\x00" * (7 - len(body)))
    u2 = Uds(bus2, tx_id=0x7E0, rx_id=0x7E8)
    payload = u2.read_dtc_by_status_mask()
    recs = decode_dtc_records(payload)
    assert recs == [(0x012345, 0x08)], recs
    assert dtc_to_text(0x012345) == "P0123", dtc_to_text(0x012345)
    print("test_uds_session_control_and_dtc_read OK")


def test_uds_negative_response_raises():
    bus = MockCanBus()
    bus.queue(0x7E8, bytes([0x03, 0x7F, 0x22, 0x31, 0, 0, 0, 0]))
    u = Uds(bus, tx_id=0x7E0, rx_id=0x7E8)
    try:
        u.read_data_by_identifier(0xF190)
        assert False, "expected UdsError"
    except UdsError as e:
        assert e.nrc == 0x31
    print("test_uds_negative_response_raises OK")


def test_obd2_decode_pid():
    assert obd2.decode_pid(0x0C, bytes([0x1A, 0xF8])) == 1726.0
    assert obd2.decode_pid(0x05, bytes([0x7B])) == 83
    assert obd2.decode_pid(0x42, bytes([0x2E, 0xE0])) == 12.0
    print("test_obd2_decode_pid OK")


def test_obd2_decode_dtc_2byte():
    assert obd2.decode_dtc_2byte(0x03, 0x01) == "P0301"
    assert obd2.decode_dtc_2byte(0x43, 0x02) == "C0302"
    print("test_obd2_decode_dtc_2byte OK")


def test_vehicle_profile_registered():
    import vehicle_profiles as vp
    p = vp.get_profile("octavia_mk3")
    assert p and p["protocol"] == "uds_can"
    assert not vp.validate_profile(p)
    print("test_vehicle_profile_registered OK")


if __name__ == "__main__":
    test_isotp_single_frame_send()
    test_isotp_single_frame_recv()
    test_isotp_multiframe_recv_sends_flow_control()
    test_isotp_multiframe_send_respects_flow_control()
    test_uds_session_control_and_dtc_read()
    test_uds_negative_response_raises()
    test_obd2_decode_pid()
    test_obd2_decode_dtc_2byte()
    test_vehicle_profile_registered()
    print("\nAll CAN/UDS tests passed.")
