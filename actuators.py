#!/usr/bin/env python3
"""Actuator tests (Phase 3) and maintenance functions (Phase 4).

Framework for component activation tests (fuel pump, fans, lamps, locks) and
maintenance resets. Same safety model as adaptations.py: the registry,
demo-mode execution, UI-facing metadata and tests are complete; the actual
on-car actuation command for each test is GATED (`command=None`) until it is
confirmed from a real INPA/EDIABAS trace. A real car refuses any test whose
command is unconfirmed. Nothing here guesses an actuation opcode.

Actuator tests energize real hardware (relays, pumps, pyro-adjacent
circuits), so the gate matters even more than for adaptations. Demo mode
lets the whole flow — selection, confirmation modal, result display — be
built and tested without a car.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# DME actuator control (service 0x22). Frame: 12 06 22 <actuator> <value> cks;
# stop with STOP_CONTROL 0x0a. SOURCE: emdzej/j2534 examples/ds2 (ms43-jobs.ts,
# by the author of the SGBD docs) — a working DS2 command map. The same file
# independently confirms the adaptation-reset opcode 0x43 we found from
# RomRaider, which corroborates the source. These IDs are documented for MS43
# (M54); on MS41 (M52) the service is the same but some IDs may differ, so
# they stay evidence="sourced (MS43), verify per-engine" — the actual send is
# gated the same way as before (demo + explicit confirm; STOP available).
ACTUATOR_CONTROL = 0x22
ACTUATOR_STOP = [0x0A]                 # STOP_CONTROL — ends any active test
ACTUATOR_SOURCE = ("emdzej/j2534 ms43-jobs.ts (service 0x22 + actuator id); "
                   "MS43-sourced, verify per-engine")


def _cmd(actuator, value=0xFF):
    """DS2 actuator-control payload: [0x22, actuator, value]."""
    return [ACTUATOR_CONTROL, actuator, value & 0xFF]


# Each test: module address, description, safety level, activation command
# (now sourced for DME tests), and UI-suggested max activation time.
ACTUATOR_TESTS = {
    "fuel_pump": {"addr": 0x12, "desc": "Fuel pump relay (EKP)",
                  "safety": "medium", "duration_s": 5,
                  "command": _cmd(0x84), "source": ACTUATOR_SOURCE},
    "cooling_fan": {"addr": 0x12, "desc": "Electric radiator fan",
                    "safety": "medium", "duration_s": 10,
                    "command": [ACTUATOR_CONTROL, 0x92, 0xFF, 0xFF],
                    "source": ACTUATOR_SOURCE},
    "secondary_air_pump": {"addr": 0x12, "desc": "Secondary air pump",
                           "safety": "medium", "duration_s": 5,
                           "command": _cmd(0x81), "source": ACTUATOR_SOURCE},
    "evap_purge_valve": {"addr": 0x12, "desc": "EVAP purge valve (TEV)",
                         "safety": "low", "duration_s": 5,
                         "command": _cmd(0x94), "source": ACTUATOR_SOURCE},
    "vanos_intake_valve": {"addr": 0x12,
                           "desc": "VANOS intake solenoid (watch cam move!)",
                           "safety": "low", "duration_s": 5,
                           "command": _cmd(0xA6), "source": ACTUATOR_SOURCE},
    "check_engine_light": {"addr": 0x12, "desc": "MIL / check-engine lamp",
                           "safety": "low", "duration_s": 3,
                           "command": _cmd(0x8A), "source": ACTUATOR_SOURCE},
    # Body-module tests remain gated — this DME map does not cover them:
    "ac_compressor": {"addr": 0x5B, "desc": "A/C compressor clutch",
                      "safety": "medium", "duration_s": 5, "command": None},
    "central_lock": {"addr": 0x00, "desc": "Central locking",
                     "safety": "low", "duration_s": 1, "command": None},
}

# Maintenance functions (Phase 4). SIA reset is handled in ds2_diag (also
# experimental/gated). Battery registration is E87/KWP and out of DS2 scope.
MAINTENANCE = {
    "oil_service_reset": {"addr": 0x80, "desc": "Reset oil service (SIA)",
                          "impl": "ds2_diag.sia_reset (experimental)",
                          "status": "gated"},
    "battery_registration": {"addr": 0x12, "desc": "Register new battery",
                             "impl": "E87/KWP only — not on this E39",
                             "status": "n/a"},
}


def list_tests():
    return [{"id": k, **{kk: vv for kk, vv in v.items() if kk != "command"},
             "available": v["command"] is not None}
            for k, v in ACTUATOR_TESTS.items()]


def list_maintenance():
    return [{"id": k, **v} for k, v in MAINTENANCE.items()]


def run_actuator_test(adapter, test_id, confirm=False):
    """Run one actuator test. Real car refuses unless the command is
    confirmed AND the caller confirmed. Demo mode simulates activation."""
    if test_id not in ACTUATOR_TESTS:
        return {"ok": False, "error": f"unknown test: {test_id}"}
    if not confirm:
        return {"ok": False, "error": "confirm required"}
    t = ACTUATOR_TESTS[test_id]
    is_demo = getattr(adapter, "name", "").startswith("DEMO") or \
        getattr(adapter, "ds2", None) is None
    if is_demo:
        return {"ok": True, "simulated": True, "test": test_id,
                "desc": t["desc"], "activated_s": t["duration_s"]}
    if t["command"] is None:
        return {"ok": False, "gated": True, "test": test_id,
                "error": f"actuation command for {test_id!r} is unconfirmed "
                         f"— body-module test not in the sourced DME map"}
    # command sourced (emdzej/j2534). Activate, wait the suggested duration,
    # then ALWAYS send STOP_CONTROL so nothing is left energized.
    import time
    f = adapter.ds2.request(t["addr"], t["command"], timeout=2.0)
    activated = f is not None and f[2] == 0xA0
    if activated:
        time.sleep(min(t["duration_s"], 10))
    stop = adapter.ds2.request(t["addr"], ACTUATOR_STOP, timeout=2.0)
    return {"ok": activated, "test": test_id,
            "status": None if f is None else f"0x{f[2]:02X}",
            "stopped": stop is not None and stop[2] == 0xA0,
            "source": t.get("source"),
            "frame": " ".join(f"{b:02X}" for b in t["command"])}


if __name__ == "__main__":
    import json
    print("Actuator tests:")
    print(json.dumps(list_tests(), indent=2))
    print("\nMaintenance:")
    print(json.dumps(list_maintenance(), indent=2))
