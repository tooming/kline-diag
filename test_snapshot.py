#!/usr/bin/env python3
"""Tests for the vehicle snapshot system (Phase 5)."""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import snapshot


class FakeAdapter:
    """Minimal adapter satisfying snapshot's .scan()/.faults() contract."""
    proto = "e39"

    def __init__(self, faults):
        self._faults = faults  # {addr: [codes]}

    def scan(self):
        return [{"addr": a, "name": f"MOD_{a:02X}",
                 "ident": f"IDENT{a:02X}", "ident_ascii": ""}
                for a in self._faults]

    def faults(self, addr):
        codes = self._faults[addr]
        return {"ok": True, "count": len(codes),
                "entries": [{"code": c, "raw": c, "text": "", "status": ""}
                            for c in codes]}


def test_create_and_list():
    tmp = tempfile.mkdtemp()
    snapshot.BACKUP_ROOT = tmp
    ad = FakeAdapter({0x12: [], 0x44: ["43", "41"]})
    snap = snapshot.create_snapshot(ad, vin="TESTVIN1", description="baseline")
    assert snap["module_count"] == 2
    assert snap["total_faults"] == 2
    listed = snapshot.list_snapshots("TESTVIN1")
    assert len(listed) == 1 and listed[0]["total_faults"] == 2
    shutil.rmtree(tmp)
    print("test_create_and_list OK")


def test_diff_detects_cleared():
    tmp = tempfile.mkdtemp()
    snapshot.BACKUP_ROOT = tmp
    before = snapshot.create_snapshot(
        FakeAdapter({0x44: ["43", "41"], 0x80: ["83"]}),
        vin="TESTVIN2", description="before")
    after = snapshot.create_snapshot(
        FakeAdapter({0x44: [], 0x80: ["83"]}),
        vin="TESTVIN2", description="after")
    d = snapshot.diff_snapshots(before, after)
    assert d["modules"]["MOD_44"]["faults_cleared"] == ["41", "43"]
    assert "MOD_80" not in d["modules"]  # unchanged module omitted
    shutil.rmtree(tmp)
    print("test_diff_detects_cleared OK")


def test_diff_detects_new_and_module_change():
    tmp = tempfile.mkdtemp()
    snapshot.BACKUP_ROOT = tmp
    a = snapshot.create_snapshot(FakeAdapter({0x12: []}),
                                 vin="V3", description="a")
    b = snapshot.create_snapshot(FakeAdapter({0x12: ["2C55"], 0x56: ["06"]}),
                                 vin="V3", description="b")
    d = snapshot.diff_snapshots(a, b)
    assert "MOD_56" in d["added"]
    assert d["modules"]["MOD_12"]["faults_new"] == ["2C55"]
    shutil.rmtree(tmp)
    print("test_diff_detects_new_and_module_change OK")


def test_load_snapshot_rejects_path_outside_backup_root():
    """diff_snapshots' a/b args come straight from an HTTP POST body
    (diag_ui.py's /api/snapshot/diff) -- without a containment check,
    load_snapshot would open() any *.json path the caller names."""
    tmp = tempfile.mkdtemp()
    snapshot.BACKUP_ROOT = tmp

    outside = tempfile.mkdtemp()
    secret_path = os.path.join(outside, "secret.json")
    with open(secret_path, "w") as f:
        f.write('{"modules": {"leaked": true}}')

    try:
        snapshot.load_snapshot(secret_path)
        assert False, "arbitrary file read was not blocked"
    except ValueError:
        pass
    shutil.rmtree(tmp)
    shutil.rmtree(outside)
    print("test_load_snapshot_rejects_path_outside_backup_root OK")


if __name__ == "__main__":
    test_create_and_list()
    test_diff_detects_cleared()
    test_diff_detects_new_and_module_change()
    test_load_snapshot_rejects_path_outside_backup_root()
    print("\nAll snapshot tests passed.")
