#!/usr/bin/env python3
"""Tests for the recording comparison engine (Phase 6)."""
import csv
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from compare import compare_recordings, parse_csv, _vanos_engaged_frac


def _write_log(rows, cols):
    """Write a temp CSV with the given per-channel value lists."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    header = ["time", "epoch", "event", "pull_id", "event_data"] + cols
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i in range(rows):
            row = [f"00:00:{i:02d}", str(1000 + i), "", "", "{}"]
            for c in cols:
                row.append(VALUES[c][i % len(VALUES[c])])
            w.writerow(row)
    return path


VALUES = {}


def test_trim_regression():
    """Rising fuel trims should be flagged as a fueling regression."""
    global VALUES
    VALUES = {"P8": [2000], "E13": [2.0], "E14": [2.0]}
    a = _write_log(20, ["P8", "E13", "E14"])
    VALUES = {"P8": [2000], "E13": [4.0], "E14": [4.0]}
    b = _write_log(20, ["P8", "E13", "E14"])
    r = compare_recordings(a, b)
    os.unlink(a); os.unlink(b)
    subsystems = {f["subsystem"] for f in r["findings"]}
    assert "fueling" in subsystems, r["findings"]
    reg = [f for f in r["findings"] if f["channel"] == "E13"][0]
    assert reg["type"] == "regression", reg
    print("test_trim_regression OK:", reg["description"])


def test_knock_improvement():
    """Falling knock retard magnitude = ignition improvement."""
    global VALUES
    VALUES = {"P8": [3000], "E217": [-6.0]}
    a = _write_log(20, ["P8", "E217"])
    VALUES = {"P8": [3000], "E217": [-2.0]}
    b = _write_log(20, ["P8", "E217"])
    r = compare_recordings(a, b)
    os.unlink(a); os.unlink(b)
    f = [x for x in r["findings"] if x["channel"] == "E217"][0]
    assert f["type"] == "improvement", f
    print("test_knock_improvement OK:", f["description"])


def test_vanos_frozen_note():
    """Cam frozen at rest in both runs -> informational VANOS note."""
    global VALUES
    VALUES = {"P8": [2500], "E11": [26.59]}
    a = _write_log(30, ["P8", "E11"])
    b = _write_log(30, ["P8", "E11"])
    r = compare_recordings(a, b)
    os.unlink(a); os.unlink(b)
    notes = [f for f in r["findings"] if f["subsystem"] == "vanos"]
    assert notes and notes[0]["type"] == "note", r["findings"]
    print("test_vanos_frozen_note OK:", notes[0]["description"])


def test_vanos_engagement_metric():
    """Engaged fraction computed from departure past threshold."""
    global VALUES
    VALUES = {"E11": [26.6, 26.6, 48.0, 48.0]}  # half engaged
    p = _write_log(40, ["E11"])
    cols = parse_csv(p)["channels"]
    os.unlink(p)
    frac = _vanos_engaged_frac(cols)
    assert abs(frac - 0.5) < 0.01, frac
    print("test_vanos_engagement_metric OK: frac=%.2f" % frac)


def test_no_change_no_findings():
    """Identical data yields no significant findings."""
    global VALUES
    VALUES = {"P8": [2000], "E13": [3.0]}
    a = _write_log(20, ["P8", "E13"])
    b = _write_log(20, ["P8", "E13"])
    r = compare_recordings(a, b)
    os.unlink(a); os.unlink(b)
    real = [f for f in r["findings"] if f["type"] != "note"]
    assert not real, real
    print("test_no_change_no_findings OK")


if __name__ == "__main__":
    test_trim_regression()
    test_knock_improvement()
    test_vanos_frozen_note()
    test_vanos_engagement_metric()
    test_no_change_no_findings()
    print("\nAll compare tests passed.")
