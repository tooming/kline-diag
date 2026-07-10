#!/usr/bin/env python3
"""OVPF producer — turns diagnostic actions into Open Vehicle Passport events.

Makes the diagnostic app the first real *event producer* for the passport
ecosystem. A scan, a fault clear, a coding write, or reading the VIN appends
immutable JSON-LD events to a local, per-vehicle append-only log:

    <data_dir>/passports/<vin>.ovpf.ndjson

Local-first & anonymous-first: the log is created automatically on first
write (no account, no prompt), the passport identity is a freshly-minted
`urn:ovpf:<uuid>` (VIN is stored as data, not identity), and events are
hash-chained (tamper-evident, offline). The wire format lives in
`ovpf_core` (vendored, byte-identical to the `ovp/` reference); this module
is just the mapping from diagnostic results to events.

Stdlib only; best-effort (callers wrap in try/except so diagnostics never
break if logging fails).
"""
import json
import os
import re
import threading

import ovpf_core
import paths

# Serialize dedup-check + append within this process (the check and the write
# must be atomic, or concurrent HTTP-handler threads duplicate "de-duped"
# events). ovpf_core.append's file lock only covers cross-process writers.
_WRITE_LOCK = threading.RLock()   # reentrant: record_* call ensure_passport

VERSION = "0.1.0"
PRODUCER = {"type": "Diagnostic", "name": "opendiag", "version": VERSION,
            "device": "K+DCAN FTDI"}
MANUAL = {"type": "Manual", "name": "opendiag", "version": VERSION}


# --- log location ----------------------------------------------------------

def _passports_dir():
    d = os.path.join(paths.data_dir(), "passports")
    os.makedirs(d, exist_ok=True)
    return d


def _log_path(vin):
    key = re.sub(r"[^A-Za-z0-9._-]", "_", vin or "unknown")
    return os.path.join(_passports_dir(), f"{key}.ovpf.ndjson")


def _read_first(path):
    for ev in ovpf_core.load(path):
        return ev
    return None


def _last_event(path, etype):
    found = None
    for ev in ovpf_core.load(path):
        if ev.get("type") == etype:
            found = ev
    return found


# --- vehicle nickname (local-only, not an OVPF event) -----------------------
# A personal label ("The E39", "Mom's daily") for the garage/passport UI --
# distinct from VehicleIdentified facts (VIN/make/model/year), which are
# immutable, hash-chained, and get pushed to cloud sync. A nickname is
# neither a diagnostic fact nor something to broadcast on a shared vehicle
# passport, so it's kept in its own local file, editable/overwritable at
# will, and never touched by ovpf_cloud.

def _vehicle_names_path():
    return os.path.join(paths.data_dir(), "vehicle_names.json")


def _load_vehicle_names():
    try:
        with open(_vehicle_names_path(), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_vehicle_name(urn):
    return _load_vehicle_names().get(urn) if urn else None


def set_vehicle_name(urn, name):
    """Set (or, if name is blank, clear) the nickname for a passport urn."""
    names = _load_vehicle_names()
    name = (name or "").strip()
    if name:
        names[urn] = name
    else:
        names.pop(urn, None)
    with open(_vehicle_names_path(), "w", encoding="utf-8") as f:
        json.dump(names, f)
    return names.get(urn)


# "Remove from garage" is a hide, not a delete -- the passport itself is a
# hash-chained diagnostic log (see module docstring's tamper-evidence goal),
# so unilaterally deleting it on a UI click would be destructive and
# unrecoverable. Same local-only-JSON pattern as vehicle_names.json, just a
# set of urns instead of a name map.

def _hidden_vehicles_path():
    return os.path.join(paths.data_dir(), "hidden_vehicles.json")


def _load_hidden_vehicles():
    try:
        with open(_hidden_vehicles_path(), encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def set_vehicle_hidden(urn, hidden):
    """Hide (or unhide) a passport urn from the default garage listing."""
    hidden_set = _load_hidden_vehicles()
    if hidden:
        hidden_set.add(urn)
    else:
        hidden_set.discard(urn)
    with open(_hidden_vehicles_path(), "w", encoding="utf-8") as f:
        json.dump(sorted(hidden_set), f)
    return urn in hidden_set


def ensure_passport(vin):
    """Return (log_path, vehicle_urn), minting the passport on first use.

    The vehicle URN is a `urn:ovpf:<uuid>` (never the VIN). Auto-created with
    a `PassportOpened` genesis event — no account, no prompt.
    """
    with _WRITE_LOCK:
        path = _log_path(vin)
        first = _read_first(path)
        if first:
            return path, first["vehicle"]
        urn = "urn:ovpf:" + ovpf_core.uuid7()
        vehicle = {"type": "Vehicle"}
        if vin:
            vehicle["vin"] = vin
        ovpf_core.append(path, ovpf_core.envelope(
            urn, "PassportOpened", {"vehicle": vehicle}, MANUAL))
        return path, urn


# --- mappers: diagnostic results -> events ---------------------------------

def record_faults(vin, addr, module_name, faults_result):
    """Append a `DiagnosticTroubleCodeRead` from an adapter faults() result.
    De-dupes: unchanged code set since the last read for this module -> skip."""
    if not faults_result or not faults_result.get("ok"):
        return None
    addr_hex = f"0x{addr:02X}"
    codes = [{"code": e.get("code"), "text": e.get("text", ""),
              "status": e.get("status", ""), "rawHex": e.get("raw", "")}
             for e in faults_result.get("entries", [])]
    data = {"module": {"address": addr_hex, "name": module_name}, "codes": codes}

    with _WRITE_LOCK:
        path, urn = ensure_passport(vin)
        prev = _last_event(path, "DiagnosticTroubleCodeRead")
        if prev and prev.get("data", {}).get("module", {}).get("address") == addr_hex:
            prev_codes = sorted(c.get("code") for c in prev["data"].get("codes", []))
            if prev_codes == sorted(c["code"] for c in codes):
                return None
        return ovpf_core.append(path, ovpf_core.envelope(
            urn, "DiagnosticTroubleCodeRead", data, PRODUCER))


def record_clear(vin, addr, module_name):
    """Append a `DiagnosticTroubleCodeCleared` (module-wide, `["*"]`)."""
    path, urn = ensure_passport(vin)
    data = {"module": {"address": f"0x{addr:02X}", "name": module_name},
            "codesCleared": ["*"]}
    return ovpf_core.append(path, ovpf_core.envelope(
        urn, "DiagnosticTroubleCodeCleared", data, PRODUCER))


def record_coding_change(vin, addr, module_name, before, after, preset=None):
    """Append an `EcuCodingChanged` (transaction-layer coding write)."""
    path, urn = ensure_passport(vin)
    data = {"module": {"address": f"0x{addr:02X}", "name": module_name},
            "before": before, "after": after}
    if preset:
        data["preset"] = preset
    return ovpf_core.append(path, ovpf_core.envelope(
        urn, "EcuCodingChanged", data, PRODUCER))


def record_vehicle_identified(vin, facts):
    """Append a `VehicleIdentified` letting a passport 'learn' its car.
    De-duped: unchanged facts since the last identification -> skip."""
    facts = {k: v for k, v in (facts or {}).items() if v}
    if not facts:
        return None
    with _WRITE_LOCK:
        path, urn = ensure_passport(vin)
        vehicle = {"type": "Vehicle", **facts}
        prev = _last_event(path, "VehicleIdentified")
        if prev and prev.get("data", {}).get("vehicle", {}) == vehicle:
            return None
        return ovpf_core.append(path, ovpf_core.envelope(
            urn, "VehicleIdentified", {"vehicle": vehicle}, PRODUCER))


def record_odometer(vin, value, unit="KMT", source="obd"):
    """Append an `OdometerReading`."""
    if value is None:
        return None
    path, urn = ensure_passport(vin)
    data = {"value": value, "unit": unit, "source": source}
    return ovpf_core.append(path, ovpf_core.envelope(
        urn, "OdometerReading", data, PRODUCER))


def record_service(vin, service_type, odometer=None, odometer_unit="KMT",
                    price=None, currency=None, notes=None):
    """Append a `ServicePerformed` -- a manual maintenance fact (oil
    change, part swap, etc.), producer type Manual, not Diagnostic: this
    didn't come off the ECU, a person is asserting it happened."""
    path, urn = ensure_passport(vin)
    data = {"serviceType": service_type}
    if odometer is not None:
        data["odometer"] = {"value": odometer, "unit": odometer_unit}
    if price is not None:
        data["total"] = {"price": price, "currency": currency}
    if notes:
        data["notes"] = notes
    return ovpf_core.append(path, ovpf_core.envelope(
        urn, "ServicePerformed", data, MANUAL))


def record_live_session(vin, channels, sample_rate=None, attachment_ref=None):
    """Append a `LiveDataRecorded` summarising a logging session."""
    path, urn = ensure_passport(vin)
    data = {"channels": list(channels)}
    if sample_rate:
        data["sampleRate"] = sample_rate
    if attachment_ref:
        data["attachmentRef"] = attachment_ref
    return ovpf_core.append(path, ovpf_core.envelope(
        urn, "LiveDataRecorded", data, PRODUCER))


def record_dyno_run(vin, peaks, duration_s=None, num=None, curve_ref=None):
    """Append a `DynoRun` -- peak power/torque from a detected WOT pull,
    producer type Diagnostic since these numbers came straight off the
    ECU's live channels, not a person's claim. `peaks` is whatever numeric
    channels were tracked during the pull (channel id -> running max);
    power_kw/torque_nm map to the spec's power/torque fields when present
    (only true for the MAF-based estimate today -- other adapters/cars
    won't have them), and everything else (rpm, maf, speed_kmh, ...) goes
    under `conditions` for context, same "essentials, not exhaustive"
    latitude the spec gives every other field here.

    `curve_ref` is a plain relative-path string (e.g.
    "dyno_runs/<uuid>.json", see diag_ui.py's /api/dyno/save) pointing at
    the full RPM-binned curve, matching the spec's `curveRef` attachment
    field -- same precedent as record_live_session's attachment_ref, not
    the spec's full content-addressed attachments system (hashing etc.),
    which is bigger than this and out of scope here. Callers today are
    entirely client-driven (ui.html's computeDynoCurve -> POST
    /api/dyno/save): detect_pull() itself no longer calls this directly,
    so a pull only gets a DynoRun event once the client has actually
    computed and saved a curve for it."""
    if not peaks:
        return None
    path, urn = ensure_passport(vin)
    data = {}
    if "power_kw" in peaks:
        data["power"] = {"value": peaks["power_kw"], "unit": "kW"}
    if "torque_nm" in peaks:
        data["torque"] = {"value": peaks["torque_nm"], "unit": "Nm"}
    conditions = {k: v for k, v in peaks.items()
                  if k not in ("power_kw", "torque_nm")}
    if conditions:
        data["conditions"] = conditions
    if duration_s is not None:
        data["duration"] = {"value": round(duration_s, 1), "unit": "s"}
    if num is not None:
        data["pullNumber"] = num
    if curve_ref:
        data["curveRef"] = curve_ref
    return ovpf_core.append(path, ovpf_core.envelope(
        urn, "DynoRun", data, PRODUCER))


def passport_state(vin):
    """Derived state for the current passport (for the UI timeline)."""
    path = _log_path(vin)
    events = ovpf_core.load(path)
    state = ovpf_core.reduce(events)
    state["chain_ok"] = not ovpf_core.verify_chain(events)
    state["passport_urn"] = state.get("passport")
    state["name"] = get_vehicle_name(state["passport_urn"])
    return state


def _path_for_urn(urn):
    """Find a passport file by its vehicle urn rather than by VIN.

    A passport opened before its VIN was known keeps living under the
    "unknown" filename forever even after a later VehicleIdentified event
    fills the VIN in -- _log_path(vin) is a naive direct lookup and misses
    it. The urn (never the VIN, see module docstring) is the vehicle's
    actual stable identity, so scanning for it always finds the right file
    regardless of what it happened to be named at creation time."""
    if not urn:
        return None
    for fname in os.listdir(_passports_dir()):
        if not fname.endswith(".ovpf.ndjson"):
            continue
        path = os.path.join(_passports_dir(), fname)
        first = _read_first(path)
        if first and first.get("vehicle") == urn:
            return path
    return None


def resolve_log_path(vin=None, urn=None):
    """Resolve the right passport file for a vin and/or urn, preferring urn
    (see _path_for_urn) since a passport opened before its VIN was known
    can't be found by VIN alone. Falls back to the vin-keyed path (which
    may not exist yet -- callers already treat a missing file as "no
    events", same as before this existed). Used by ovpf_cloud too, so cloud
    sync status/push are correct for a browsed (non-connected) vehicle."""
    if urn:
        p = _path_for_urn(urn)
        if p:
            return p
    return _log_path(vin)


def passport_state_by_urn(urn):
    """Same shape as passport_state(), looked up by urn (see _path_for_urn)
    -- for browsing a garage vehicle that isn't the connected car, where a
    plain VIN lookup could silently miss it."""
    path = _path_for_urn(urn)
    if not path:
        return {"passport": None, "vehicle": {}}
    events = ovpf_core.load(path)
    state = ovpf_core.reduce(events)
    state["chain_ok"] = not ovpf_core.verify_chain(events)
    state["passport_urn"] = state.get("passport")
    state["name"] = get_vehicle_name(state["passport_urn"])
    return state


def list_passports(include_hidden=False):
    """Derived state for every local passport (one per known VIN, plus
    the anonymous "unknown" one if it exists) -- powers the workshop
    garage view: browse every vehicle worked on from this laptop, not
    just whichever one is currently connected (see _current_vin()).

    Hidden vehicles (see set_vehicle_hidden) are left out by default --
    a "remove from garage" that the workshop view still needs to be able
    to reveal and undo, so it's a filter here, not a deletion anywhere."""
    hidden = _load_hidden_vehicles()
    out = []
    for fname in sorted(os.listdir(_passports_dir())):
        if not fname.endswith(".ovpf.ndjson"):
            continue
        path = os.path.join(_passports_dir(), fname)
        events = ovpf_core.load(path)
        if not events:
            continue
        state = ovpf_core.reduce(events)
        state["chain_ok"] = not ovpf_core.verify_chain(events)
        state["passport_urn"] = state.get("passport")
        is_hidden = state["passport_urn"] in hidden
        if is_hidden and not include_hidden:
            continue
        state["name"] = get_vehicle_name(state["passport_urn"])
        state["hidden"] = is_hidden
        out.append(state)
    return out


if __name__ == "__main__":
    demo_vin = "DEMOVIN0000000001"
    if os.path.exists(_log_path(demo_vin)):
        os.remove(_log_path(demo_vin))
    record_vehicle_identified(demo_vin, {"vin": demo_vin, "engine": "M52B25",
                                         "dme": "MS41"})
    record_faults(demo_vin, 0x12, "DME (MS41)",
                  {"ok": True, "count": 1,
                   "entries": [{"code": "0x71", "status": "stored",
                                "text": "O2 sensor pre-cat aging", "raw": "71 60"}]})
    record_faults(demo_vin, 0x12, "DME (MS41)",   # de-duped
                  {"ok": True, "count": 1,
                   "entries": [{"code": "0x71", "status": "stored",
                                "text": "O2 sensor pre-cat aging", "raw": "71 60"}]})
    record_clear(demo_vin, 0x12, "DME (MS41)")
    print(f"wrote {_log_path(demo_vin)}")
