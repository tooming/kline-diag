#!/usr/bin/env python3
"""Tests for adaptation reset (Phase 2). Verifies the software layer AND the
safety gate that blocks a real-car write until the opcode is confirmed."""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import adaptations
from transaction import get_transaction_manager


def test_mask_computation():
    assert adaptations.mask_for(["throttle"]) == 0x0800
    assert adaptations.mask_for(["knock", "idle"]) == 0x0300
    try:
        adaptations.mask_for(["bogus"])
        assert False, "should have raised"
    except ValueError:
        pass
    print("test_mask_computation OK")


def test_erase_builds_romraider_frame():
    """Opcode 0x43 (sourced from RomRaider) builds the throttle payload."""
    payload, note = adaptations.build_selective_erase(["throttle"])
    assert payload == [0x43, 0x08, 0x00], payload
    print("test_erase_builds_romraider_frame OK:", note)


def test_gate_holds_when_opcode_none():
    """If the opcode were ever cleared, the build must refuse (no guessing)."""
    saved = adaptations.ERASE_OPCODE
    try:
        adaptations.ERASE_OPCODE = None
        payload, note = adaptations.build_selective_erase(["throttle"])
        assert payload is None and "unconfirmed" in note
    finally:
        adaptations.ERASE_OPCODE = saved
    print("test_gate_holds_when_opcode_none OK")


def test_demo_flow_runs_through_transaction():
    """Demo mode exercises the whole read->backup->write->verify pipeline."""
    tmp = tempfile.mkdtemp()
    tm = get_transaction_manager(backup_root=tmp)

    class DemoLike:
        name = "DEMO — simulated 523i"
        proto = "e39"
        vin = "DEMOVIN"
        ds2 = None       # None -> demo path
    r = adaptations.reset_adaptations(DemoLike(), ["throttle", "idle"],
                                      transaction_manager=tm,
                                      user_note="unit test")
    assert r["demo"] is True
    assert r["success"] is True, r
    assert r["verified"] is True, r
    # a backup must have been created
    backups = tm.list_backups("DEMOVIN")
    assert len(backups) >= 1, backups
    shutil.rmtree(tmp)
    print("test_demo_flow_runs_through_transaction OK")


def test_confirmed_opcode_builds_frame():
    """When an opcode is set (simulating a confirmed trace), the payload is
    a concrete 3-byte frame. Restored afterward so nothing leaks."""
    saved = adaptations.ERASE_OPCODE
    try:
        adaptations.ERASE_OPCODE = 0x0C   # hypothetical, for test only
        payload, note = adaptations.build_selective_erase(["throttle"])
        assert payload == [0x0C, 0x08, 0x00], payload
    finally:
        adaptations.ERASE_OPCODE = saved
    assert adaptations.ERASE_OPCODE == 0x43   # restored to sourced value
    print("test_confirmed_opcode_builds_frame OK")


if __name__ == "__main__":
    test_mask_computation()
    test_erase_builds_romraider_frame()
    test_gate_holds_when_opcode_none()
    test_demo_flow_runs_through_transaction()
    test_confirmed_opcode_builds_frame()
    print("\nAll adaptation tests passed.")
