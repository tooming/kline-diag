#!/usr/bin/env python3
"""Tests for the correlation engine (Phase 7.2)."""
import csv
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from correlate import pearson, correlate_channels, correlate_ram


def test_pearson_basic():
    assert abs(pearson([1, 2, 3, 4], [2, 4, 6, 8]) - 1.0) < 1e-9
    assert abs(pearson([1, 2, 3, 4], [8, 6, 4, 2]) + 1.0) < 1e-9
    assert pearson([1, 1, 1], [1, 2, 3]) == 0.0   # flat -> 0
    print("test_pearson_basic OK")


def test_correlate_channels():
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "epoch", "event", "pull_id", "event_data",
                    "P8", "P9", "NOISE"])
        for i in range(20):
            # P9 tracks P8 exactly; NOISE is inverse
            w.writerow([f"t{i}", i, "", "", "{}", 1000 + i * 50,
                        20 + i, 500 - i * 3])
    res = correlate_channels(path, "P8")
    os.unlink(path)
    top = res[0]
    assert top["channel"] == "P9" and top["r"] > 0.99, top
    noise = [r for r in res if r["channel"] == "NOISE"][0]
    assert noise["r"] < -0.99, noise
    print("test_correlate_channels OK:", top["channel"], top["r"])


def test_ram_discovery():
    """RAM offset that tracks the target must be found with a type guess."""
    # target parameter ramps 0..19; build dumps where offset 5 tracks it,
    # offset 2 is constant, offset 8 is inverse.
    target = list(range(20))
    dumps = []
    for v in target:
        d = bytearray(16)
        d[5] = v * 3          # tracks target (uint8)
        d[2] = 99             # constant
        d[8] = 200 - v * 2    # inverse
        dumps.append(bytes(d))
    cands = correlate_ram(target, dumps, threshold=0.85)
    offsets = {c["offset"] for c in cands}
    assert 5 in offsets, cands
    assert 8 in offsets, cands       # strong inverse counts
    assert 2 not in offsets, cands   # constant excluded
    best = [c for c in cands if c["offset"] == 5][0]
    assert best["r"] > 0.99 and best["type"] in ("uint8", "uint16-be"), best
    print("test_ram_discovery OK: found offsets", sorted(offsets))


def test_ram_uint16():
    """A 16-bit big-endian value spanning two bytes is detected."""
    target = [100, 300, 700, 1500, 3000, 90, 40000, 12345]
    dumps = []
    for v in target:
        d = bytearray(8)
        d[3] = (v >> 8) & 0xFF
        d[4] = v & 0xFF
        dumps.append(bytes(d))
    cands = correlate_ram(target, dumps, threshold=0.9)
    u16 = [c for c in cands if c["type"] == "uint16-be" and c["offset"] == 3]
    assert u16 and u16[0]["r"] > 0.99, cands
    print("test_ram_uint16 OK")


if __name__ == "__main__":
    test_pearson_basic()
    test_correlate_channels()
    test_ram_discovery()
    test_ram_uint16()
    print("\nAll correlate tests passed.")
