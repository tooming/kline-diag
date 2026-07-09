#!/usr/bin/env python3
"""ISO-TP (ISO 15765-2) segmentation/reassembly on top of raw CAN frames.

Carries UDS (ISO 14229) request/response payloads longer than a single
8-byte CAN frame. Works against anything with `send_frame(id, data,
extended=False)` / `recv_frame(timeout) -> (id, data, extended) | None`
(can_transport.SlcanPort, or a mock for tests).

PCI (first payload byte) formats:
    0x0L        single frame, L = length (0-7)
    0x1L LL     first frame, 12-bit length, 6 data bytes follow
    0x2N        consecutive frame, N = sequence number 1-15 wrapping to 0
    0x3S BS ST  flow control, S = status (0 continue / 1 wait / 2 overflow)
"""
import time

SF, FF, CF, FC = 0x0, 0x1, 0x2, 0x3


class IsoTpError(Exception):
    pass


class IsoTpChannel:
    """One request/response pair of CAN IDs (tester -> ECU on tx_id, ECU ->
    tester on rx_id). Physical addressing only — no functional/broadcast
    (see obd2.py for that, which only ever needs single-frame requests)."""

    def __init__(self, port, tx_id, rx_id, extended=False):
        self.port = port
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.extended = extended

    def send(self, payload):
        if len(payload) <= 7:
            frame = bytes([SF << 4 | len(payload)]) + payload
            frame += b"\x00" * (8 - len(frame))  # pad to 8, common practice
            self.port.send_frame(self.tx_id, frame, self.extended)
            return
        if len(payload) > 4095:
            raise IsoTpError("payload too long for ISO-TP (max 4095 bytes)")
        first = bytes([FF << 4 | (len(payload) >> 8), len(payload) & 0xFF])
        first += payload[:6]
        self.port.send_frame(self.tx_id, first, self.extended)
        fc = self._wait_flow_control()
        bs, stmin = fc
        rest = payload[6:]
        seq = 1
        sent_since_fc = 0
        while rest:
            chunk, rest = rest[:7], rest[7:]
            frame = bytes([CF << 4 | seq]) + chunk
            frame += b"\x00" * (8 - len(frame))
            self.port.send_frame(self.tx_id, frame, self.extended)
            seq = (seq + 1) & 0x0F
            sent_since_fc += 1
            if stmin:
                time.sleep(stmin / 1000.0)
            if bs and sent_since_fc >= bs and rest:
                bs, stmin = self._wait_flow_control()
                sent_since_fc = 0

    def _wait_flow_control(self, timeout=1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            f = self.port.recv_frame(deadline - time.time())
            if not f:
                break
            can_id, data, _ = f
            if can_id != self.rx_id or not data:
                continue
            pci = data[0] >> 4
            if pci != FC:
                continue
            status = data[0] & 0x0F
            if status == 1:  # wait
                continue
            if status == 2:
                raise IsoTpError("flow control: overflow")
            bs = data[1] if len(data) > 1 else 0
            st_raw = data[2] if len(data) > 2 else 0
            stmin = st_raw if st_raw <= 0x7F else (
                (st_raw - 0xF0) * 0.1 if 0xF1 <= st_raw <= 0xF9 else 0)
            return bs, stmin
        raise IsoTpError("no flow control response from ECU")

    def recv(self, timeout=1.0):
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            f = self.port.recv_frame(remaining)
            if not f:
                return None
            can_id, data, _ = f
            if can_id != self.rx_id or not data:
                continue
            pci = data[0] >> 4
            if pci == SF:
                length = data[0] & 0x0F
                return data[1:1 + length]
            if pci == FF:
                total = ((data[0] & 0x0F) << 8) | data[1]
                payload = bytearray(data[2:8])
                self.port.send_frame(self.tx_id, bytes([FC << 4, 0x00, 0x00])
                                      + b"\x00" * 5, self.extended)
                expect_seq = 1
                cf_deadline = time.time() + timeout
                while len(payload) < total:
                    cf = self.port.recv_frame(max(0.0, cf_deadline - time.time()))
                    if not cf:
                        raise IsoTpError("timed out waiting for consecutive frame")
                    cid, cdata, _ = cf
                    if cid != self.rx_id or not cdata:
                        continue
                    if (cdata[0] >> 4) != CF:
                        continue
                    seq = cdata[0] & 0x0F
                    if seq != expect_seq:
                        raise IsoTpError(
                            f"consecutive frame sequence mismatch: "
                            f"got {seq}, expected {expect_seq}")
                    payload += cdata[1:]
                    expect_seq = (expect_seq + 1) & 0x0F
                return bytes(payload[:total])
            # ignore stray FC / unknown PCI while waiting for a response
