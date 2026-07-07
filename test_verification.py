#!/usr/bin/env python3
"""Tests for evidence promotion (sourced -> car-verified)."""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import verification as v


def test_plausible_running_sample_passes():
    good = {"P8": 820, "P2": 91, "P11": 24, "P17": 14.1, "P13": 2}
    assert v.plausibility_check(good)["passed"] is True
    print("test_plausible_running_sample_passes OK")


def test_wrong_address_sample_fails():
    # impossible coolant + battery = wrong-address map
    bad = {"P8": 820, "P2": 250, "P17": 2.0}
    assert v.plausibility_check(bad)["passed"] is False
    print("test_wrong_address_sample_fails OK")


def test_key_on_only_not_verified():
    # engine not running (RPM 0) must not verify even if other values sane
    keyon = {"P8": 0, "P2": 20, "P17": 12.4}
    assert v.plausibility_check(keyon)["passed"] is False
    print("test_key_on_only_not_verified OK")


def test_no_autopromote_without_confirm():
    tmp = tempfile.mkdtemp()
    v.VERIFIED_PATH = os.path.join(tmp, "verified.json")
    good = {"P8": 820, "P2": 91, "P17": 14.1}
    r = v.record_verification("VIN1", "MS43", "M54", good,
                              user_confirmed=False)
    assert r["verified"] is False
    assert "confirm" in r["blocked_reason"]
    assert not v.is_verified("VIN1", "MS43")   # nothing written
    print("test_no_autopromote_without_confirm OK")


def test_promote_with_plausible_and_confirm():
    tmp = tempfile.mkdtemp()
    v.VERIFIED_PATH = os.path.join(tmp, "verified.json")
    good = {"P8": 2500, "P2": 90, "P11": 30, "P17": 14.2, "P13": 40}
    r = v.record_verification("VIN2", "MS43", "M54", good,
                              user_confirmed=True, note="matches gauges")
    assert r["verified"] is True and r.get("saved")
    assert v.is_verified("VIN2", "MS43")           # persisted
    assert v.dme_evidence("VIN2", "MS43", "sourced") == "car-verified"
    # a DIFFERENT car is NOT verified by this
    assert not v.is_verified("VIN3", "MS43")
    print("test_promote_with_plausible_and_confirm OK")


def test_confirm_but_implausible_still_blocked():
    tmp = tempfile.mkdtemp()
    v.VERIFIED_PATH = os.path.join(tmp, "verified.json")
    bad = {"P8": 820, "P2": 250}   # impossible coolant
    r = v.record_verification("VIN4", "MS43", "M54", bad, user_confirmed=True)
    assert r["verified"] is False   # confirm alone isn't enough
    print("test_confirm_but_implausible_still_blocked OK")


if __name__ == "__main__":
    test_plausible_running_sample_passes()
    test_wrong_address_sample_fails()
    test_key_on_only_not_verified()
    test_no_autopromote_without_confirm()
    test_promote_with_plausible_and_confirm()
    test_confirm_but_implausible_still_blocked()
    print("\nAll verification tests passed.")
