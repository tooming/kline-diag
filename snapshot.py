#!/usr/bin/env python3
"""Full-vehicle snapshot system (Phase 5).

A snapshot captures the whole car in one timestamped record: every module's
ident, part/software info, fault memory and (where known) coding — as a
read-only forensic baseline. Distinct from `transaction.py`'s per-operation
backups, which cover a single write.

Read-only: this module never writes to a module, so it does not need the
transaction layer. It is adapter-agnostic — it drives whatever object it is
given, needing only `.scan()` and `.faults(addr)` (the diag_ui adapters and
the demo adapter all satisfy this). Coding is captured when a decoder for
that module exists in coding.py.

Layout (matches ROADMAP Phase 5):
  backups/<VIN>/snapshots/<timestamp>_<slug>/metadata.json

CLI:  python3 snapshot.py --list [VIN]
      python3 snapshot.py --diff <snapshot_dir_a> <snapshot_dir_b>
"""
import datetime
import json
import os
import re
import sys

import paths
BACKUP_ROOT = os.path.join(paths.data_dir(), "backups")


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", (text or "snapshot").lower()).strip("_")


def _safe_vin(vin):
    """Sanitize a VIN before it's joined into a filesystem path -- it can
    come straight from an HTTP query param (diag_ui.py's
    /api/snapshots?vin=), and an unsanitized ".." there is a path-traversal
    primitive out of BACKUP_ROOT. Case-preserving (real VINs are
    uppercase), unlike _slug()."""
    s = re.sub(r"[^A-Za-z0-9._-]", "_", vin or "")
    return s if s not in ("", ".", "..") else "_"


def _try_coding(addr):
    """Return a coding decoder result for a module if coding.py knows it."""
    try:
        import coding
    except Exception:
        return None
    fn = getattr(coding, "read_coding_for_addr", None)
    if callable(fn):
        try:
            return fn(addr)
        except Exception:
            return None
    return None


def create_snapshot(adapter, vin=None, description="", mileage_km=None):
    """Read every responding module and persist one snapshot record.

    adapter: object exposing .scan() -> [{addr,name,ident,...}] and
             .faults(addr) -> {ok,count,entries,...}
    Returns the snapshot dict (also written to disk).
    """
    vin = vin or getattr(adapter, "vin", None) or "UNKNOWN_VIN"
    ts = datetime.datetime.now()
    modules = {}
    for m in adapter.scan():
        addr = m["addr"]
        rec = {"addr": addr, "name": m.get("name", ""),
               "ident": m.get("ident", ""),
               "ident_ascii": m.get("ident_ascii", "")}
        try:
            f = adapter.faults(addr)
            rec["faults"] = {"count": f.get("count", 0),
                             "entries": f.get("entries", [])} if f.get("ok") \
                else {"error": f.get("error")}
        except Exception as e:
            rec["faults"] = {"error": str(e)}
        coding = _try_coding(addr)
        if coding is not None:
            rec["coding"] = coding
        modules[m.get("name", f"0x{addr:02X}").split(" (")[0]] = rec

    snapshot = {
        "type": "snapshot",
        "vin": vin,
        "timestamp": ts.isoformat(timespec="seconds"),
        "description": description,
        "mileage_km": mileage_km,
        "protocol": getattr(adapter, "proto", None),
        "module_count": len(modules),
        "total_faults": sum(mm.get("faults", {}).get("count", 0)
                            for mm in modules.values()),
        "modules": modules,
    }

    outdir = os.path.join(BACKUP_ROOT, _safe_vin(vin), "snapshots",
                          f"{ts:%Y%m%d_%H%M%S}_{_slug(description)}")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "metadata.json"), "w") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    snapshot["_dir"] = outdir
    return snapshot


def list_snapshots(vin=None):
    """List snapshots, newest first. If vin is None, scan all VINs."""
    out = []
    if not os.path.isdir(BACKUP_ROOT):
        return out
    vins = [_safe_vin(vin)] if vin else [d for d in os.listdir(BACKUP_ROOT)
                              if os.path.isdir(os.path.join(BACKUP_ROOT, d))]
    for v in vins:
        sdir = os.path.join(BACKUP_ROOT, v, "snapshots")
        if not os.path.isdir(sdir):
            continue
        for name in sorted(os.listdir(sdir), reverse=True):
            meta = os.path.join(sdir, name, "metadata.json")
            if os.path.isfile(meta):
                try:
                    with open(meta) as f:
                        d = json.load(f)
                    out.append({"id": name, "vin": v,
                                "timestamp": d.get("timestamp"),
                                "description": d.get("description", ""),
                                "module_count": d.get("module_count"),
                                "total_faults": d.get("total_faults"),
                                "dir": os.path.join(sdir, name)})
                except (OSError, ValueError):
                    pass
    return out


def load_snapshot(path):
    """Load a snapshot's metadata.json by path. `path` reaches here
    straight from a client-supplied value (diag_ui.py's /api/snapshot/diff
    passes POST body fields through unchanged) -- without a containment
    check this is an arbitrary-file-read (any *.json path, or any
    <dir>/metadata.json). Resolve symlinks/".." and require the real path
    to stay under BACKUP_ROOT before opening anything."""
    meta = path if path.endswith(".json") else os.path.join(path, "metadata.json")
    real_root = os.path.realpath(BACKUP_ROOT)
    real_meta = os.path.realpath(meta)
    if os.path.commonpath([real_root, real_meta]) != real_root:
        raise ValueError(f"snapshot path outside backup root: {path}")
    with open(real_meta) as f:
        return json.load(f)


def diff_snapshots(a, b):
    """Structural diff of two snapshot dicts (or dirs/paths).

    Reports modules added/removed and, per shared module, changes in fault
    count, fault set, ident and coding.
    """
    if isinstance(a, str):
        a = load_snapshot(a)
    if isinstance(b, str):
        b = load_snapshot(b)
    ma, mb = a.get("modules", {}), b.get("modules", {})
    changes = {"added": sorted(set(mb) - set(ma)),
               "removed": sorted(set(ma) - set(mb)),
               "modules": {}}
    for name in sorted(set(ma) & set(mb)):
        da, db = ma[name], mb[name]
        mod = {}
        fa = da.get("faults", {}).get("count", 0)
        fb = db.get("faults", {}).get("count", 0)
        if fa != fb:
            mod["fault_count"] = {"a": fa, "b": fb}
        codes_a = {e["code"] for e in da.get("faults", {}).get("entries", [])}
        codes_b = {e["code"] for e in db.get("faults", {}).get("entries", [])}
        if codes_a != codes_b:
            mod["faults_new"] = sorted(codes_b - codes_a)
            mod["faults_cleared"] = sorted(codes_a - codes_b)
        if da.get("ident") != db.get("ident"):
            mod["ident_changed"] = True
        if da.get("coding") != db.get("coding"):
            mod["coding_changed"] = True
        if mod:
            changes["modules"][name] = mod
    return changes


def _demo_adapter():
    sys.path.insert(0, HERE)
    import diag_ui
    diag_ui.KLine = lambda *a, **k: type("K", (), {"log": lambda *a: None,
                                                   "close": lambda s: None})()
    return diag_ui.DemoAdapter()


def main():
    if "--list" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--list"]
        for s in list_snapshots(rest[0] if rest else None):
            print(f"{s['timestamp']}  {s['vin']}  "
                  f"{s['module_count']} modules, {s['total_faults']} faults  "
                  f"{s['description']}")
        return
    if "--diff" in sys.argv:
        i = sys.argv.index("--diff")
        d = diff_snapshots(sys.argv[i + 1], sys.argv[i + 2])
        print(json.dumps(d, indent=2, ensure_ascii=False))
        return
    if "--demo" in sys.argv:
        snap = create_snapshot(_demo_adapter(), vin="WBADM12345_DEMO",
                               description="demo baseline")
        print(f"snapshot written: {snap['_dir']}")
        print(f"  {snap['module_count']} modules, "
              f"{snap['total_faults']} faults")
        return
    print(__doc__)


if __name__ == "__main__":
    main()
