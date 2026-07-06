#!/usr/bin/env python3
"""K-line trace parser, diff and replay (Protocol Explorer).

Turns the raw wire log (kline_raw.log, or any OEM-tool capture in the same
"ts dir hex" shape) into structured frames, so a captured OEM session can be
diffed against ours and unknown operations identified. This is the bridge
that upgrades a documented job to `observed`: once a job's request bytes are
seen in a trace, they can be attached to the operation database.

Frame line format (as written by KLine.log):
    HH:MM:SS.mmm >> 12 05 0B 03 1F
    HH:MM:SS.mmm << 12 1D A0 ...

Functions:
    parse_trace(path|lines)  -> [ {t, dir, ecu, hex, bytes, service} ]
    trace_diff(a, b)         -> requests in one trace but not the other
    extract_requests(frames) -> unique tester->ECU request payloads
    replay_plan(frames)      -> ordered read-only requests safe to replay

Pure stdlib, offline. Replay planning REFUSES to include write/actuate
requests (same service whitelist as dev_console) — replay is read-only.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

_LINE = re.compile(r'(\d{2}:\d{2}:\d{2}\.\d{3})\s+(>>|<<)\s+([0-9A-Fa-f ]+)')

# read-only DS2 service IDs (mirror dev_console)
READ_SERVICES = {0x00, 0x04, 0x0B, 0x1A, 0x17, 0x18, 0x21, 0x22, 0x06, 0x3E}


def _bytes(hexs):
    return [int(x, 16) for x in hexs.split()]


def parse_trace(source):
    """source = path, file-like, or list of lines. Returns frame dicts.

    DS2 frame is [ecu, len, data..., xor]; the service byte is data[0].
    A request (>>) to ECU E has service at index 2.
    """
    if isinstance(source, str) and os.path.isfile(source):
        lines = open(source, encoding="utf-8", errors="replace").read().splitlines()
    elif isinstance(source, str):
        lines = source.splitlines()
    else:
        lines = list(source)
    frames = []
    for ln in lines:
        m = _LINE.search(ln)
        if not m:
            continue
        ts, dirn, hexs = m.group(1), m.group(2), m.group(3).strip()
        try:
            b = _bytes(hexs)
        except ValueError:
            continue
        if len(b) < 3:
            continue
        service = b[2] if dirn == ">>" else (b[2] if len(b) > 2 else None)
        frames.append({"t": ts, "dir": dirn, "ecu": b[0],
                       "hex": hexs.upper(), "bytes": b, "service": service})
    return frames


def extract_requests(frames):
    """Unique request payloads (service + args), keyed by (ecu, payload)."""
    seen = {}
    for f in frames:
        if f["dir"] != ">>":
            continue
        payload = tuple(f["bytes"][2:-1])   # drop ecu,len and checksum
        key = (f["ecu"], payload)
        if key not in seen:
            seen[key] = {"ecu": f["ecu"],
                         "payload": " ".join(f"{x:02X}" for x in payload),
                         "service": f["service"], "count": 0}
        seen[key]["count"] += 1
    return list(seen.values())


def trace_diff(a, b):
    """Requests present in trace A but not B, and vice versa. Useful to spot
    what an OEM tool does that we don't (candidate new operations)."""
    ra = {(r["ecu"], r["payload"]) for r in extract_requests(a)}
    rb = {(r["ecu"], r["payload"]) for r in extract_requests(b)}
    only_a = [{"ecu": e, "payload": p} for (e, p) in sorted(ra - rb)]
    only_b = [{"ecu": e, "payload": p} for (e, p) in sorted(rb - ra)]
    return {"only_in_a": only_a, "only_in_b": only_b,
            "shared": len(ra & rb)}


def replay_plan(frames):
    """Ordered, de-duplicated READ-ONLY requests safe to replay. Write and
    actuate services are excluded — replay never mutates the car."""
    plan, seen = [], set()
    excluded = 0
    for r in extract_requests(frames):
        svc = None
        if r["payload"]:
            svc = int(r["payload"].split()[0], 16)
        if svc not in READ_SERVICES:
            excluded += 1
            continue
        key = (r["ecu"], r["payload"])
        if key in seen:
            continue
        seen.add(key)
        plan.append({"ecu": r["ecu"], "payload": r["payload"]})
    return {"requests": plan, "excluded_non_read": excluded}


def annotate_with_db(frames, db):
    """Match each request's service against the operation DB to label it."""
    out = []
    for r in extract_requests(frames):
        ecu_ops = db.all() if hasattr(db, "all") else []
        label = None
        for op in ecu_ops:
            if op.get("request") and r["payload"].startswith(
                    op["request"].split(" /")[0].upper()):
                label = op["name"]
                break
        out.append({**r, "operation": label})
    return out


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join(HERE, "kline_raw.log")
    frames = parse_trace(path)
    reqs = extract_requests(frames)
    plan = replay_plan(frames)
    print(f"parsed {len(frames)} frames, {len(reqs)} unique requests")
    print(f"replay-safe (read-only) requests: {len(plan['requests'])}, "
          f"excluded {plan['excluded_non_read']} write/actuate")
    for r in reqs[:12]:
        print(f"  ecu 0x{r['ecu']:02X}  {r['payload']:<24} x{r['count']}")
