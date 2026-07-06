#!/usr/bin/env python3
"""Recording comparison & analysis engine (Phase 6).

Loads two drive-log CSVs (produced by diag_ui recording) and auto-generates
findings: which subsystems improved or regressed between the two runs. Pure
stdlib, no car needed — works entirely on saved logs, so it is safe to run
offline and is independent of diag_ui.py / ui.html.

Design note: channel IDs are RomRaider MS41 param ids (P8=RPM, P12=MAF,
E11=cam position, E13/E14 short-term trims, E217 knock retard, etc.). The
metric direction (higher-is-better vs lower-is-better) is declared per
channel so findings read in plain language.

CLI:  python3 compare.py before.csv after.csv [--json]
API:  compare_recordings(path_a, path_b) -> dict
"""
import csv
import json
import math
import os
import sys

# channel id -> (label, unit, direction)
#   direction: "high" better, "low" better (abs), or "neutral" (report only)
CHANNELS = {
    "P8":  ("RPM", "rpm", "neutral"),
    "P9":  ("Vehicle speed", "km/h", "neutral"),
    "P13": ("Throttle", "%", "neutral"),
    "E2":  ("Engine load", "mg/stroke", "neutral"),
    "P12": ("MAF", "kg/h", "neutral"),
    "P18": ("MAF voltage", "V", "neutral"),
    "P21": ("Injector PW", "ms", "neutral"),
    "E13": ("Short-term trim B1", "%", "low"),
    "E14": ("Short-term trim B2", "%", "low"),
    "E21": ("Long-term trim B1", "%", "low"),
    "E22": ("Long-term trim B2", "%", "low"),
    "P10": ("Ignition advance", "deg", "neutral"),
    "E217": ("Knock retard", "deg", "low"),
    "E24": ("Global knock retard", "deg", "low"),
    "E11": ("Cam position (VANOS)", "deg", "neutral"),
    "S23": ("VANOS command", "on/off", "neutral"),
    "E210": ("VANOS adjust angle", "raw", "high"),
    "P2":  ("Coolant temp", "C", "neutral"),
    "P11": ("Intake temp", "C", "neutral"),
    "P17": ("Battery", "V", "neutral"),
}

VANOS_REST = 26.6      # single-VANOS cam rest position (deg)
VANOS_MOVE = 4.0       # departure that counts as engaged


def parse_csv(path):
    """Return {channel_id: [float,...]} plus meta (events, row count)."""
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    cols = {}
    for cid in CHANNELS:
        vals = []
        for r in rows:
            v = r.get(cid, "")
            if v not in ("", None):
                try:
                    vals.append(float(v))
                except ValueError:
                    pass
        if vals:
            cols[cid] = vals
    events = [r for r in rows if r.get("event")]
    return {"channels": cols, "events": events, "rows": len(rows),
            "name": os.path.basename(path)}


def _stats(vals):
    n = len(vals)
    if not n:
        return None
    s = sorted(vals)
    mean = sum(vals) / n
    var = sum((x - mean) ** 2 for x in vals) / n
    return {"n": n, "mean": mean, "min": s[0], "max": s[-1],
            "median": s[n // 2], "std": math.sqrt(var),
            "mean_abs": sum(abs(x) for x in vals) / n}


def _pct(a, b):
    return (b - a) / abs(a) * 100 if a else 0.0


def _vanos_engaged_frac(cols):
    """Fraction of samples where the cam departed from rest — the direct
    'is VANOS actually moving' metric from the earlier investigation."""
    cam = cols.get("E11")
    if not cam:
        return None
    moved = sum(1 for v in cam if abs(v - VANOS_REST) >= VANOS_MOVE)
    return moved / len(cam)


def compare_recordings(path_a, path_b):
    a = parse_csv(path_a)
    b = parse_csv(path_b)
    findings = []
    metrics = {}

    for cid, (label, unit, direction) in CHANNELS.items():
        va, vb = a["channels"].get(cid), b["channels"].get(cid)
        if not va or not vb:
            continue
        # trims/knock judged on magnitude; others on mean
        sa, sb = _stats(va), _stats(vb)
        key = "mean_abs" if direction == "low" else "mean"
        ma, mb = sa[key], sb[key]
        metrics[cid] = {"label": label, "unit": unit,
                        "a": round(ma, 2), "b": round(mb, 2),
                        "a_stats": {k: round(v, 2) for k, v in sa.items()},
                        "b_stats": {k: round(v, 2) for k, v in sb.items()}}
        if direction == "neutral":
            continue
        change = _pct(ma, mb)
        # meaningful threshold: 5% and at least a small absolute move
        if abs(mb - ma) < 0.1 or abs(change) < 5:
            continue
        if direction == "low":       # lower magnitude = better
            improved = mb < ma
            verb = "reduced" if improved else "increased"
            findings.append({
                "type": "improvement" if improved else "regression",
                "subsystem": _subsystem(cid), "channel": cid,
                "description": f"{label} {verb} "
                               f"{abs(change):.0f}% "
                               f"({ma:.2f} -> {mb:.2f} {unit})"})
        else:                        # high better
            improved = mb > ma
            verb = "improved" if improved else "dropped"
            findings.append({
                "type": "improvement" if improved else "regression",
                "subsystem": _subsystem(cid), "channel": cid,
                "description": f"{label} {verb} "
                               f"{abs(change):.0f}% "
                               f"({ma:.2f} -> {mb:.2f} {unit})"})

    # VANOS engagement (special: the whole point of the E39 debug)
    fa, fb = _vanos_engaged_frac(a["channels"]), _vanos_engaged_frac(b["channels"])
    if fa is not None and fb is not None:
        metrics["vanos_engaged"] = {"label": "VANOS engaged fraction",
                                    "unit": "%", "a": round(fa * 100, 1),
                                    "b": round(fb * 100, 1)}
        if fa < 0.02 and fb < 0.02:
            findings.append({
                "type": "note", "subsystem": "vanos", "channel": "E11",
                "description": "VANOS never departed rest position in either "
                               "run — cam stayed at ~26.6 deg (consistent "
                               "with a non-actuating single-VANOS)."})
        elif fb > fa + 0.05:
            findings.append({
                "type": "improvement", "subsystem": "vanos", "channel": "E11",
                "description": f"VANOS engaged more of the time "
                               f"({fa*100:.0f}% -> {fb*100:.0f}% of samples)"})
        elif fa > fb + 0.05:
            findings.append({
                "type": "regression", "subsystem": "vanos", "channel": "E11",
                "description": f"VANOS engaged less of the time "
                               f"({fa*100:.0f}% -> {fb*100:.0f}% of samples)"})

    findings.sort(key=lambda f: {"regression": 0, "improvement": 1,
                                 "note": 2}.get(f["type"], 3))
    return {"a": {"name": a["name"], "rows": a["rows"],
                  "events": len(a["events"])},
            "b": {"name": b["name"], "rows": b["rows"],
                  "events": len(b["events"])},
            "metrics": metrics, "findings": findings}


def _subsystem(cid):
    if cid in ("E13", "E14", "E21", "E22", "P21"):
        return "fueling"
    if cid in ("E217", "E24", "P10"):
        return "ignition"
    if cid in ("E11", "S23", "E210"):
        return "vanos"
    if cid in ("P12", "P18"):
        return "airflow"
    return "engine"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit("usage: compare.py before.csv after.csv [--json]")
    result = compare_recordings(args[0], args[1])
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2))
        return
    print(f"A: {result['a']['name']}  ({result['a']['rows']} rows)")
    print(f"B: {result['b']['name']}  ({result['b']['rows']} rows)\n")
    if not result["findings"]:
        print("No significant differences (>5%) between the runs.")
    for f in result["findings"]:
        mark = {"improvement": "[+]", "regression": "[-]",
                "note": "[i]"}.get(f["type"], "[ ]")
        print(f"  {mark} ({f['subsystem']}) {f['description']}")


if __name__ == "__main__":
    main()
