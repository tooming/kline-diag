#!/usr/bin/env python3
"""Evidence promotion: sourced -> car-verified (answers "does connecting a
car auto-verify?").

No. Connecting a car only loads the matching DME map. A parameter map is
"verified" only when (a) its live readings pass plausibility checks on a
real running engine AND (b) a human confirms the values match the physical
gauges. This module implements that gate and records the result per VIN+DME
in verified_maps.json, so a genuinely-confirmed map stays verified across
sessions — but nothing is ever auto-promoted just by plugging in.

Plausibility checks catch a wrong-address map (which would read out-of-range
or dead values). Passing them is necessary but not sufficient: the final
promotion requires user_confirmed=True (they eyeballed coolant vs the gauge,
RPM vs the tach). This keeps "verified" honest.

Pure stdlib, offline.
"""
import datetime
import json
import os

import paths
VERIFIED_PATH = os.path.join(paths.data_dir(), "verified_maps.json")

# Per-channel plausibility ranges for a warm, running engine. A correct map
# reads inside these; a wrong-address map typically won't.
PLAUSIBILITY = {
    "P8":  (400, 7200, "RPM"),
    "P2":  (-40, 130, "Coolant C"),
    "P11": (-40, 90, "Intake C"),
    "P17": (10.0, 15.5, "Battery V"),
    "P13": (0, 100, "Throttle %"),
    "E11": (0, 120, "Cam pos deg"),
}


def plausibility_check(values, require_running=True):
    """Return {checks:[...], passed:bool}. Each check reports the channel,
    value, range and pass/fail. `require_running` insists RPM looks like a
    live engine (guards against verifying from a key-on-only sample)."""
    checks = []
    for cid, (lo, hi, label) in PLAUSIBILITY.items():
        if cid not in values or values[cid] in (None, ""):
            continue
        try:
            v = float(values[cid])
        except (TypeError, ValueError):
            continue
        ok = lo <= v <= hi
        checks.append({"channel": cid, "label": label, "value": v,
                       "range": [lo, hi], "ok": ok})
    running = any(c["channel"] == "P8" and c["value"] > 400 for c in checks)
    passed = bool(checks) and all(c["ok"] for c in checks)
    if require_running:
        passed = passed and running
    return {"checks": checks, "passed": passed, "running": running}


def _load_verified():
    try:
        with open(VERIFIED_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def is_verified(vin, dme):
    return _load_verified().get(f"{vin}:{dme}", {}).get("verified", False)


def record_verification(vin, dme, engine, values, user_confirmed=False,
                        note=""):
    """Attempt to promote a DME map to verified for this VIN.

    Promotion requires BOTH plausibility AND user_confirmed. Otherwise the
    result explains what's missing; nothing is written unless promoted.
    """
    pc = plausibility_check(values)
    promoted = bool(pc["passed"] and user_confirmed)
    result = {"vin": vin, "dme": dme, "engine": engine,
              "plausibility": pc, "user_confirmed": user_confirmed,
              "verified": promoted}
    if not promoted:
        reason = []
        if not pc["passed"]:
            reason.append("live readings not plausible (map may be wrong or "
                          "engine not warm/running)")
        if not user_confirmed:
            reason.append("needs your confirmation that values match the "
                          "physical gauges")
        result["blocked_reason"] = "; ".join(reason)
        return result
    db = _load_verified()
    db[f"{vin}:{dme}"] = {
        "verified": True, "engine": engine,
        "when": datetime.datetime.now().isoformat(timespec="seconds"),
        "note": note,
        "evidence_sample": {c["channel"]: c["value"] for c in pc["checks"]}}
    with open(VERIFIED_PATH, "w") as f:
        json.dump(db, f, indent=1)
    result["saved"] = True
    return result


def dme_evidence(vin, dme, base_evidence):
    """Overlay verified status onto a DME's base evidence string."""
    if is_verified(vin, dme):
        return "car-verified"
    return base_evidence


if __name__ == "__main__":
    # demo: a plausible running sample vs a wrong-address sample
    good = {"P8": 820, "P2": 91, "P11": 24, "P17": 14.1, "P13": 2}
    print("plausible sample:", plausibility_check(good)["passed"])
    bad = {"P8": 820, "P2": 250, "P17": 2.0}   # coolant/battery impossible
    print("wrong-address sample:", plausibility_check(bad)["passed"])
    print("auto-promote without confirm:",
          record_verification("TESTVIN", "MS43", "M54", good,
                              user_confirmed=False)["verified"])
