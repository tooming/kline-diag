#!/usr/bin/env python3
"""Correlation engine (Phase 7.2) — discover which signals track a target.

Two uses:

1. Offline (works now): given a drive-log CSV and a target channel, rank all
   other logged channels by Pearson correlation. Answers "what moves with
   throttle / RPM / load", which is how you separate cause from effect in the
   bog-down hunt.

2. RAM discovery (for when the car is present): given a target parameter's
   values sampled over time and a parallel series of RAM dumps (one per
   sample), find the byte offsets whose value tracks the parameter — i.e.
   locate an unknown sensor's RAM address, and suggest its data type. This is
   the mechanism behind the "probe 0xE9E0-0xEA00 for the real VANOS signal"
   plan.

Pure stdlib. Independent of diag_ui.py / ui.html.

CLI:  python3 correlate.py <log.csv> <target_channel>
"""
import csv
import json
import os
import sys

MIN_SAMPLES = 8


def pearson(xs, ys):
    """Pearson correlation of two equal-length numeric series; 0 if flat."""
    n = min(len(xs), len(ys))
    if n < 2:
        return 0.0
    xs, ys = xs[:n], ys[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs)
    dy = sum((y - my) ** 2 for y in ys)
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy) ** 0.5


def _load_channels(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    skip = {"time", "epoch", "event", "pull_id", "event_data"}
    cols = {}
    for key in (rows[0].keys() if rows else []):
        if key in skip:
            continue
        vals = []
        for r in rows:
            v = r.get(key, "")
            if v not in ("", None):
                try:
                    vals.append(float(v))
                except ValueError:
                    vals = None
                    break
        if vals and len(vals) >= MIN_SAMPLES:
            cols[key] = vals
    return cols


def correlate_channels(path, target, top=None):
    """Rank channels in a log by |correlation| against `target`."""
    cols = _load_channels(path)
    if target not in cols:
        raise KeyError(f"target {target!r} not in log "
                       f"(have: {', '.join(sorted(cols))})")
    tv = cols[target]
    results = []
    for cid, vals in cols.items():
        if cid == target:
            continue
        n = min(len(tv), len(vals))
        r = pearson(tv[:n], vals[:n])
        results.append({"channel": cid, "r": round(r, 3),
                        "abs_r": round(abs(r), 3),
                        "strength": _label(abs(r)),
                        "sign": "same direction" if r >= 0
                                else "opposite direction"})
    results.sort(key=lambda d: d["abs_r"], reverse=True)
    return results[:top] if top else results


def _label(ar):
    if ar >= 0.9:
        return "very strong"
    if ar >= 0.7:
        return "strong"
    if ar >= 0.4:
        return "moderate"
    if ar >= 0.2:
        return "weak"
    return "negligible"


def _suggest_type(byte_series):
    """Guess a data type from a byte's behaviour across dumps."""
    lo, hi = min(byte_series), max(byte_series)
    if hi <= 1:
        return "flag/bit"
    return "uint8"


def correlate_ram(target_values, ram_dumps, threshold=0.85):
    """Locate RAM offsets whose value tracks target_values.

    ram_dumps: list of equal-length byte sequences, one per target sample.
    Returns candidate offsets sorted by |correlation|, with a uint8 vs uint16
    (big-endian) type suggestion. This is the offline core of the on-car RAM
    discovery flow.
    """
    if not ram_dumps or len(ram_dumps) != len(target_values):
        raise ValueError("need one RAM dump per target value")
    width = min(len(d) for d in ram_dumps)
    cands = []
    for off in range(width):
        series = [d[off] for d in ram_dumps]
        r = pearson(target_values, series)
        if abs(r) >= threshold:
            cands.append({"offset": off, "hex": f"0x{off:04X}",
                          "r": round(r, 3), "type": _suggest_type(series)})
    # uint16 big-endian pairs
    for off in range(width - 1):
        series = [(d[off] << 8) | d[off + 1] for d in ram_dumps]
        r = pearson(target_values, series)
        if abs(r) >= threshold:
            cands.append({"offset": off, "hex": f"0x{off:04X}",
                          "r": round(r, 3), "type": "uint16-be"})
    cands.sort(key=lambda c: abs(c["r"]), reverse=True)
    return cands


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit("usage: correlate.py <log.csv> <target_channel>")
    path, target = args
    try:
        results = correlate_channels(path, target)
    except KeyError as e:
        sys.exit(str(e))
    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
        return
    print(f"Correlation with {target} in {os.path.basename(path)}:\n")
    for r in results:
        if r["abs_r"] < 0.2:
            continue
        bar = "#" * int(r["abs_r"] * 20)
        print(f"  {r['channel']:>5}  r={r['r']:+.3f}  {bar:<20} "
              f"{r['strength']} ({r['sign']})")


if __name__ == "__main__":
    main()
