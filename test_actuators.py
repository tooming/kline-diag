#!/usr/bin/env python3
"""Tests for actuator tests + maintenance (Phases 3/4) and their safety gate."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import actuators


class DemoLike:
    name = "DEMO — simulated 523i"
    proto = "e39"
    ds2 = None


class FakeReal:
    name = "E39 (DS2)"
    proto = "e39"
    ds2 = object()


def test_dme_tests_sourced_body_tests_gated():
    tests = {t["id"]: t for t in actuators.list_tests()}
    # DME actuators now sourced (emdzej/j2534 service 0x22); body-module gated
    assert tests["fuel_pump"]["available"] is True
    assert tests["vanos_intake_valve"]["available"] is True
    assert tests["ac_compressor"]["available"] is False  # not in DME map
    print("test_dme_tests_sourced_body_tests_gated OK")


def test_actuator_frames_are_concrete():
    """Sourced frames are concrete byte lists, never None-guessed."""
    assert actuators._cmd(0x84) == [0x22, 0x84, 0xFF]
    assert actuators.ACTUATOR_STOP == [0x0A]
    print("test_actuator_frames_are_concrete OK")


def test_real_car_body_test_still_gated():
    r = actuators.run_actuator_test(FakeReal(), "ac_compressor", confirm=True)
    assert r["ok"] is False and r.get("gated") is True, r
    print("test_real_car_body_test_still_gated OK")


def test_confirm_required():
    r = actuators.run_actuator_test(DemoLike(), "fuel_pump", confirm=False)
    assert r["ok"] is False and "confirm" in r["error"]
    print("test_confirm_required OK")


def test_demo_simulates():
    r = actuators.run_actuator_test(DemoLike(), "fuel_pump", confirm=True)
    assert r["ok"] and r.get("simulated") is True
    print("test_demo_simulates OK")


def test_real_car_gated():
    r = actuators.run_actuator_test(FakeReal(), "fuel_pump", confirm=True)
    assert r["ok"] is False and r.get("gated") is True, r
    print("test_real_car_gated OK")


def test_unknown_test():
    r = actuators.run_actuator_test(DemoLike(), "nope", confirm=True)
    assert r["ok"] is False and "unknown" in r["error"]
    print("test_unknown_test OK")


def test_maintenance_listed():
    m = {x["id"]: x for x in actuators.list_maintenance()}
    assert m["oil_service_reset"]["status"] == "gated"
    assert m["battery_registration"]["status"] == "n/a"
    print("test_maintenance_listed OK")


if __name__ == "__main__":
    test_dme_tests_sourced_body_tests_gated()
    test_actuator_frames_are_concrete()
    test_real_car_body_test_still_gated()
    test_confirm_required()
    test_demo_simulates()
    test_unknown_test()
    test_maintenance_listed()
    print("\nAll actuator/maintenance tests passed.")
