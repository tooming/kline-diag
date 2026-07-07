#!/usr/bin/env python3
"""Tests for the Protocol Explorer: operation DB + Evidence, SGBD parser,
trace parser/diff/replay."""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import operations as ops_mod
from operations import (OperationDB, make_operation, evidence_grade,
                        usable_on_car, seed_db)
import sgbd_parser
import trace as tr


# ---- Evidence model ----

def test_evidence_grade_and_usability():
    verified = make_operation("x", "DME", "read", evidence={
        "implemented": True, "tested": True, "safe": True})
    assert evidence_grade(verified) == "verified"
    assert usable_on_car(verified)

    documented_write = make_operation("y", "DME", "write", evidence={
        "documented": True})
    assert evidence_grade(documented_write) == "documented"
    assert not usable_on_car(documented_write)   # the honesty gate
    print("test_evidence_grade_and_usability OK")


def test_db_merge_ors_evidence():
    db = OperationDB([make_operation("z", "DME", "write",
                                     evidence={"documented": True})])
    db.add(make_operation("z", "DME", "write",
                          evidence={"observed": True}))
    op = db.get("DME", "z")
    assert op["evidence"]["documented"] and op["evidence"]["observed"]
    assert len(db.all()) == 1   # merged, not duplicated
    print("test_db_merge_ors_evidence OK")


def test_db_save_load_roundtrip():
    db = seed_db()
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    db.save(path)
    db2 = OperationDB.load(path)
    os.unlink(path)
    assert db2.summary()["total"] == db.summary()["total"]
    print("test_db_save_load_roundtrip OK")


# ---- SGBD parser ----

SAMPLE_SGBD = """# KOMBI39

## Jobs

### SIA_RESET

Ruecksetzen der Service-Intervall-Anzeige

#### Arguments

| Name | Type | Comment |
| --- | --- | --- |
| ARG1 | string | Oel/Weg |

#### Results

| Name | Type | Comment |
| --- | --- | --- |
| JOB_STATUS | string | |

### STATUS_NW_POSITION

Wert Nockenwellenposition auslesen

#### Results

| Name | Type | Comment |
| --- | --- | --- |
| STATUS_NW_POSITION_WERT | real | |
"""


def test_sgbd_parse_jobs():
    jobs = sgbd_parser.parse_sgbd_markdown(SAMPLE_SGBD, "IKE")
    by = {j["sgbd_job"]: j for j in jobs}
    assert "SIA_RESET" in by and by["SIA_RESET"]["kind"] == "write"
    assert by["SIA_RESET"]["args"] == ["ARG1"]
    assert by["STATUS_NW_POSITION"]["kind"] == "read"
    assert all(j["evidence"]["documented"] for j in jobs)
    assert all(not j["evidence"]["implemented"] for j in jobs)  # doc != impl
    print("test_sgbd_parse_jobs OK")


def test_sgbd_real_docs_if_present():
    ops, stats = sgbd_parser.parse_dir()
    if not stats:
        print("test_sgbd_real_docs_if_present SKIPPED (no docs)")
        return
    assert sum(stats.values()) > 100   # hundreds of jobs
    ecus = {o["ecu"] for o in ops}
    assert "DME" in ecus and "IKE" in ecus
    print(f"test_sgbd_real_docs_if_present OK ({sum(stats.values())} jobs)")


# ---- trace parser ----

SAMPLE_TRACE = """
00:00:01.100 >> 12 05 0B 03 1F
00:00:01.150 << 12 1D A0 00 11 22
00:00:02.100 >> 12 04 04 FF 11
00:00:02.200 >> 12 05 14 FF FF 33
00:00:03.000 >> 44 03 00 47
"""


def test_trace_parse_and_requests():
    frames = tr.parse_trace(SAMPLE_TRACE)
    reqs = tr.extract_requests(frames)
    # 4 unique requests (3 to DME, 1 to EWS)
    ecus = sorted({r["ecu"] for r in reqs})
    assert 0x12 in ecus and 0x44 in ecus
    print("test_trace_parse_and_requests OK")


def test_replay_excludes_writes():
    frames = tr.parse_trace(SAMPLE_TRACE)
    plan = tr.replay_plan(frames)
    payloads = [r["payload"] for r in plan["requests"]]
    # 0B 03 (read) and 04 (read faults) and 00 (ident) included; 14 (clear) excluded
    assert any(p.startswith("0B") for p in payloads)
    assert not any(p.startswith("14") for p in payloads)
    assert plan["excluded_non_read"] >= 1
    print("test_replay_excludes_writes OK")


def test_trace_diff():
    a = tr.parse_trace(SAMPLE_TRACE)
    b = tr.parse_trace("00:00:01.100 >> 12 05 0B 03 1F\n")
    d = tr.trace_diff(a, b)
    # A has extra requests b doesn't
    assert d["only_in_a"] and not d["only_in_b"]
    assert d["shared"] >= 1
    print("test_trace_diff OK")


if __name__ == "__main__":
    test_evidence_grade_and_usability()
    test_db_merge_ors_evidence()
    test_db_save_load_roundtrip()
    test_sgbd_parse_jobs()
    test_sgbd_real_docs_if_present()
    test_trace_parse_and_requests()
    test_replay_excludes_writes()
    test_trace_diff()
    print("\nAll protocol-explorer tests passed.")
