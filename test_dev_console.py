#!/usr/bin/env python3
"""Tests for Developer Mode raw console safety (Phase 8)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import dev_console as dc


def test_read_services_allowed():
    for p in ([0x1A, 0x80], [0x21, 0x5A], [0x18, 0x02], [0x00]):
        ok, _ = dc.check_request(p, "ds2")
        assert ok, p
    print("test_read_services_allowed OK")


def test_write_services_blocked():
    for p in ([0x14, 0xFF, 0xFF], [0x2E, 0x10], [0x31, 0x01],
              [0x30, 0x01], [0x43], [0x05]):
        ok, reason = dc.check_request(p, "ds2")
        assert not ok and "blocked" in reason, (p, reason)
    print("test_write_services_blocked OK")


def test_unknown_service_denied():
    ok, reason = dc.check_request([0x99], "ds2")
    assert not ok and "whitelist" in reason
    print("test_unknown_service_denied OK")


def test_empty_denied():
    ok, _ = dc.check_request([], "ds2")
    assert not ok
    print("test_empty_denied OK")


def test_send_raw_blocks_before_bus():
    """A denied request must never reach the adapter."""
    class SpyAdapter:
        name = "E39 (DS2)"
        proto = "e39"

        class _ds2:
            def request(self, *a, **k):
                raise AssertionError("write request reached the bus!")
        ds2 = _ds2()
    r = dc.send_raw(SpyAdapter(), [0x14, 0xFF, 0xFF])
    assert r["blocked"] is True
    print("test_send_raw_blocks_before_bus OK")


def test_demo_passes_check_without_sending():
    class DemoLike:
        name = "DEMO — simulated 523i"
        proto = "e39"
        ds2 = None
    r = dc.send_raw(DemoLike(), [0x1A, 0x80])
    assert r["ok"] and r.get("demo") is True
    print("test_demo_passes_check_without_sending OK")


if __name__ == "__main__":
    test_read_services_allowed()
    test_write_services_blocked()
    test_unknown_service_denied()
    test_empty_denied()
    test_send_raw_blocks_before_bus()
    test_demo_passes_check_without_sending()
    print("\nAll dev console tests passed.")
