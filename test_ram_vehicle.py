#!/usr/bin/env python3
"""Tests for RAM explorer offline functions (Phase 7) and vehicle profiles
(Phase 10)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ds2_diag
import vehicle_profiles as vp


def test_ram_diff_ranks_by_magnitude():
    a = {0xE9E6: 71, 0xDAA4: 0, 0xDA2A: 800, 0xDA50: 100}
    b = {0xE9E6: 130, 0xDAA4: 22, 0xDA2A: 3200, 0xDA50: 100}
    d = ds2_diag.ram_diff(a, b, min_delta=1)
    assert d[0]["addr"] == 0xDA2A          # rpm change biggest
    assert all(x["addr"] != 0xDA50 for x in d)  # unchanged excluded
    vanos = [x for x in d if x["addr"] == 0xE9E6][0]
    assert vanos["delta"] == 59
    print("test_ram_diff_ranks_by_magnitude OK")


def test_ram_diff_threshold():
    a = {0x10: 100, 0x11: 100}
    b = {0x10: 101, 0x11: 150}
    d = ds2_diag.ram_diff(a, b, min_delta=10)
    assert len(d) == 1 and d[0]["addr"] == 0x11
    print("test_ram_diff_threshold OK")


def test_profiles_valid():
    for key in ("e39", "e87"):
        p = vp.get_profile(key)
        assert p is not None
        assert vp.validate_profile(p) == [], vp.validate_profile(p)
    print("test_profiles_valid OK")


def test_profile_lookup():
    assert "DME" in vp.module_name("e39", 0x12)
    assert vp.get_profile("nonexistent") is None
    assert len(vp.list_profiles()) == 2
    print("test_profile_lookup OK")


def test_validate_catches_bad_profile():
    bad = {"chassis": "X", "name": "y", "protocol": "carb",
           "modules": {999: "oops"}}
    probs = vp.validate_profile(bad)
    assert any("protocol" in p for p in probs)
    assert any("address" in p for p in probs)
    print("test_validate_catches_bad_profile OK")


if __name__ == "__main__":
    test_ram_diff_ranks_by_magnitude()
    test_ram_diff_threshold()
    test_profiles_valid()
    test_profile_lookup()
    test_validate_catches_bad_profile()
    print("\nAll RAM/vehicle tests passed.")
