#!/usr/bin/env python3
"""Vehicle profile abstraction (Phase 10 scaffold).

Turns per-vehicle knowledge — protocol, module address map, live-data
source — into DATA so a new chassis (E46, E90, …) can be added as a dict
entry rather than new code. The existing E39/E87 adapters are described
here declaratively; future vehicles slot in beside them.

This is a scaffold: it centralizes the vehicle metadata the adapters and
UI already rely on, and provides lookup/detection helpers. It does not by
itself talk to new cars — that still needs the physical vehicle to verify
addresses — but it removes the code changes from that future work.

Pure stdlib, offline, no car needed to load or test.
"""

# Each profile is self-describing. `modules` maps hex address -> label.
# `voltage` documents where battery voltage comes from (for the dashboard).
PROFILES = {
    "e39": {
        "chassis": "E39",
        # Two real E39s share this DS2 code path with different DMEs --
        # a 1998 523i (M52/MS41, manual, no EGS on the bus) and a 2003
        # 520i (M54B22/MS43, automatic, EGS present). detect() reads the
        # DME's own ident (dme_registry.py) at connect time so the right
        # RAM param map and live-data profile load per car -- see
        # diag_ui.py's PROFILES_BY_DME. Don't hardcode a single model/
        # engine/gearbox here as if only one exists (this entry used to,
        # and it was wrong for the second car -- e.g. don't assume "no
        # EGS": it's model/gearbox dependent, not chassis-wide).
        "name": "E39 (M52/MS41 or M54/MS43, detected live)",
        "protocol": "ds2",
        "baud": 9600,
        "parity": "E",
        "vin_source": {"module": 0x80, "job": "C_FG_LESEN"},
        "voltage": {"kind": "ds2_status", "addr": 0x12,
                    "job": "0B 03", "byte": 16, "scale": 0.1},
        # Mirrors ds2_diag.E39_MODULES (the map E39Adapter.scan() actually
        # uses) -- kept in sync rather than a stale subset.
        "modules": {
            0x00: "GM/ZKE (general body module)",
            0x08: "SZM (switch center, console)",
            0x12: "DME (engine)", 0x18: "CDC (CD changer)",
            0x32: "EGS (transmission)", 0x44: "EWS (immobiliser)",
            0x50: "MFL (wheel controls)", 0x56: "ABS/ASC/DSC",
            0x5B: "IHKA (climate)", 0x60: "PDC (park distance)",
            0x68: "RADIO", 0x6A: "DSP (audio)",
            0x80: "IKE (instrument cluster)", 0xA4: "MRS (airbag)",
            0xC0: "MID (multi-info display)", 0xC8: "TEL (telephone)",
            0xD0: "LCM (lights)", 0xE8: "FBZV (remote)",
        },
        "notes": "Engine/DME/gearbox vary by car — see comment above; "
                 "detect() resolves the specifics live, don't assume.",
    },
    "e87": {
        "chassis": "E87",
        "name": "2005 116i (N45)",
        "protocol": "kwp2000",
        "baud": 10400,
        "parity": None,
        "vin_source": {"module": 0x12, "job": "1A 86"},
        "voltage": {"kind": "kwp_record", "addr": 0x12,
                    "record": 0x5A, "byte": 0, "scale": 0.1},
        "modules": {
            0x00: "JBE (junction box)", 0x01: "MRS (airbag)",
            0x12: "DME (engine)", 0x29: "DSC", 0x40: "CAS",
            0x60: "KOMBI", 0x63: "steering column", 0x64: "PDC",
            0x72: "LM (lights)", 0x78: "IHKA (climate)",
        },
        "notes": "KWP2000 fast-init. PID 0x42 unsupported; use record 21 5A.",
    },
    "octavia_mk3": {
        "chassis": "MQB (Typ 5E facelift)",
        "name": "2019 Octavia",
        "protocol": "uds_can",
        "bitrate": 500000,
        "vin_source": {"mode": 0x09, "pid": 0x02},
        "voltage": {"kind": "obd_pid", "pid": 0x42, "scale": 1.0},
        "modules": {
            0x7E0: "engine (guaranteed present, legislated OBD-II)",
        },
        "notes": "CAN bus, not K-line — the K+DCAN cable cannot reach this "
                 "car (no CAN transceiver); needs a slcan-firmware "
                 "USB-CAN adapter (e.g. CANable 2.0). Module map beyond "
                 "the engine ECU is NOT hardcoded here: VAG's non-emissions "
                 "diagnostic addressing is typically routed through the "
                 "J533 gateway and varies by options/model year, so use "
                 "`vag_diag.py sweep` on the real car to discover it rather "
                 "than trusting a guessed table.",
    },
    "porsche_996": {
        "chassis": "996.1",
        "name": "2000 Porsche 911 Carrera (M96.01, Motronic ME7.2)",
        "protocol": "kwp2000",
        "baud": 10400,
        "parity": None,
        "vin_source": {"mode": 0x09, "pid": 0x02},
        "voltage": {"kind": "obd_pid", "pid": 0x42, "scale": 1.0},
        "modules": {
            0x33: "Engine control (SAE J1979 OBD-II functional broadcast)",
        },
        "notes": "Legislated OBD-II only (diag_ui.py's Obd2Adapter): Mode "
                 "01 live data, Mode 03/04 stored/clear DTCs, Mode 09 VIN, "
                 "over KWP2000 fast-init at the standard functional address "
                 "0x33 -- no Porsche-specific addressing needed since this "
                 "is the legislated layer every OBD-II car exposes. Unlike "
                 "the E39/E87 entries above there is no manufacturer module "
                 "map here (no PIWIS-equivalent per-module fault memory or "
                 "coding) -- that would need the physical car to discover "
                 "Porsche's proprietary K-line addressing, same caveat as "
                 "octavia_mk3's CAN module map above.",
    },
    # --- Template for adding a new chassis (needs the physical car to
    #     verify addresses before use). Kept commented so it is inert. ---
    # "e46": {
    #     "chassis": "E46", "name": "...", "protocol": "ds2",
    #     "baud": 9600, "parity": "E", "modules": {...},
    # },
}


def get_profile(key):
    """Return a profile by protocol key (e39/e87/...) or None."""
    return PROFILES.get(key)


def list_profiles():
    """Summaries for a vehicle picker UI."""
    return [{"key": k, "chassis": p["chassis"], "name": p["name"],
             "protocol": p["protocol"], "module_count": len(p["modules"])}
            for k, p in PROFILES.items()]


def module_name(profile_key, addr):
    p = PROFILES.get(profile_key, {})
    return p.get("modules", {}).get(addr, f"0x{addr:02X}")


def validate_profile(p):
    """Structural check for a profile dict — used when adding a new car so
    mistakes surface before it reaches the bus. Returns list of problems."""
    problems = []
    for field in ("chassis", "name", "protocol", "modules"):
        if field not in p:
            problems.append(f"missing required field: {field}")
    if p.get("protocol") not in ("ds2", "kwp2000", "uds_can"):
        problems.append(f"unknown protocol: {p.get('protocol')}")
    if not isinstance(p.get("modules"), dict) or not p.get("modules"):
        problems.append("modules must be a non-empty {addr: name} dict")
    # K-line addresses are one byte; CAN IDs (uds_can) are 11-bit.
    addr_max = 0x7FF if p.get("protocol") == "uds_can" else 0xFF
    for a in (p.get("modules") or {}):
        if not isinstance(a, int) or not 0 <= a <= addr_max:
            problems.append(f"invalid module address: {a!r}")
    return problems


if __name__ == "__main__":
    import json
    print(json.dumps(list_profiles(), indent=2))
    for k, p in PROFILES.items():
        probs = validate_profile(p)
        print(f"{k}: {'OK' if not probs else probs}")
