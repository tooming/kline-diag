#!/usr/bin/env python3
"""Web UI for BMW K-line diagnostics — faults, clearing, live data + graphs.

Serves a single-page dashboard (ui.html) and a JSON/SSE API on top of the
existing transports:
  - E87 2005 (KWP2000 fast init, 10400 8N1)  -> power_diag.py
  - E39 1998 (DS2, 9600 8E1)                 -> ds2_diag.py

Run:  python3 diag_ui.py  [--port-http 8039]
then open http://localhost:8039

Stdlib only, same as the rest of the toolkit. The serial port has a single
owner (this server); all car I/O is serialized through one lock. Fault
memories are snapshotted to fault_snapshots.log before every clear.
"""
import argparse
import base64
import collections
import json
import math
import os
import queue
import subprocess
import urllib.parse
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import paths  # noqa: E402
import power_diag  # noqa: E402
import ds2_diag    # noqa: E402
import obd2        # noqa: E402  (shared Mode-01 PID decode formulas)
from power_diag import KLine, hexs, frame_payload, now  # noqa: E402
from transaction import get_transaction_manager  # noqa: E402
import coding  # noqa: E402
import ovpf_producer  # noqa: E402  (OVPF event log; best-effort)

# Read-only bundled resources (ui.html, *.json tables) vs. writable runtime
# data (logs, backups, snapshots). Identical to the project dir when run from
# source; they diverge only in a frozen build (see paths.py).
HERE = paths.resource_dir()
DATA = paths.data_dir()

E87_DTC = {}
try:
    with open(os.path.join(HERE, "e87_dtc.json")) as f:
        E87_DTC = json.load(f)
except OSError:
    pass

CAR_LOCK = threading.RLock()
RAW_LOG = collections.deque(maxlen=400)
RAW_SEQ = [0]


def log_hook(orig):
    def wrapped(dirn, data, note=""):
        RAW_SEQ[0] += 1
        RAW_LOG.append({"seq": RAW_SEQ[0],
                        "t": time.strftime("%H:%M:%S"),
                        "dir": dirn, "hex": hexs(data), "note": note})
        orig(dirn, data, note)
    return wrapped


# Live channel profiles for the MS41 fast logger. The MS41 firmware has a
# practical limit of ~20 parameters per address list (38 arms but responds
# with status B0; 17 streams correctly at 9-10 Hz). Groups drive the dashboard
# layout; graph=True channels chart by default. IDs = RomRaider param ids
# in ms41_ram_params.json.
MS41_PROFILES = {
    "driveability": [
        ("P8", "RPM", "Engine", True),
        ("P9", "Vehicle Speed", "Engine", True),
        ("P13", "Throttle", "Engine", True),
        ("E2", "Load", "Engine", True),
        ("P12", "MAF", "Airflow", True),
        ("P18", "MAF Voltage", "Airflow", False),
        ("P21", "Injector PW", "Fuel", True),
        ("E13", "STFT Bank 1", "Fuel Trim", True),
        ("E14", "STFT Bank 2", "Fuel Trim", True),
        ("E21", "LTFT Bank 1", "Fuel Trim", False),
        ("E22", "LTFT Bank 2", "Fuel Trim", False),
        ("P10", "Ignition Advance", "Ignition", True),
        ("E217", "Knock Retard", "Ignition", True),
        ("E11", "VANOS Angle", "VANOS", True),
        ("P2", "Coolant Temp", "Temps", False),
        ("P11", "Intake Temp", "Temps", False),
        # Real MAP sensor -- used (at WOT, as an ambient-pressure proxy) for
        # dyno SAE/DIN correction. NOT P24 ("Atmospheric Pressure" in
        # ms41_ram_params.json) -- that entry's own description literally
        # says "temporary fake entry for the Dyno tab" and its expr is a
        # hardcoded constant, not a real reading.
        ("P7", "MAP", "Engine", False),
        ("P17", "Battery", "Temps", True),
    ],
    "fuel": [
        ("P8", "RPM", "Engine", True),
        ("P13", "Throttle", "Engine", True),
        ("E2", "Load", "Engine", False),
        ("P12", "MAF", "Airflow", True),
        ("P21", "Injector PW", "Fuel", True),
        ("E13", "STFT Bank 1", "Fuel Trim", True),
        ("E14", "STFT Bank 2", "Fuel Trim", True),
        ("E21", "LTFT Bank 1", "Fuel Trim", True),
        ("E22", "LTFT Bank 2", "Fuel Trim", True),
        ("E19", "Idle FT Bank 1", "Fuel Trim", False),
        ("E20", "Idle FT Bank 2", "Fuel Trim", False),
        ("E101", "O2 Voltage #1", "O2 Sensors", True),
        ("E102", "O2 Voltage #2", "O2 Sensors", True),
        ("E15", "O2 Heater #1", "O2 Sensors", False),
        ("E16", "O2 Heater #2", "O2 Sensors", False),
        ("E202", "Purge PWM", "Fuel", False),
        ("E9", "IACV", "Idle", False),
    ],
    "knock": [
        ("P8", "RPM", "Engine", True),
        ("E2", "Load", "Engine", True),
        ("P13", "Throttle", "Engine", False),
        ("P10", "Ignition Advance", "Timing", True),
        ("E24", "Global Knock Retard", "Knock", True),
        ("E217", "Current Knock Retard", "Knock", True),
        ("E204", "Knock Cyl 1", "Cylinders", True),
        ("E205", "Knock Cyl 2", "Cylinders", True),
        ("E206", "Knock Cyl 3", "Cylinders", True),
        ("E207", "Knock Cyl 4", "Cylinders", True),
        ("E208", "Knock Cyl 5", "Cylinders", True),
        ("E209", "Knock Cyl 6", "Cylinders", True),
    ],
    "sensors": [
        ("P8", "RPM", "Engine", False),
        ("P13", "Throttle", "Engine", False),
        ("P18", "MAF Voltage", "Voltages", True),
        ("P19", "TPS Voltage", "Voltages", True),
        ("P17", "Battery Voltage", "Voltages", True),
        ("E101", "O2 Voltage #1", "O2", True),
        ("E102", "O2 Voltage #2", "O2", True),
        ("P11", "IAT", "Temps", False),
        ("P2", "ECT", "Temps", False),
        ("P12", "MAF", "Airflow", False),
        ("E9", "IACV", "Idle", False),
        ("E202", "Purge PWM", "Fuel", False),
    ],
    "vanos": [
        ("P8", "RPM", "Engine", True),
        ("P9", "Vehicle Speed", "Engine", True),
        ("P13", "Throttle", "Engine", True),
        ("E2", "Load", "Engine", True),
        ("P12", "MAF", "Airflow", True),
        ("P21", "Injector PW", "Fuel", True),
        ("P10", "Ignition Advance", "Timing", True),
        ("E217", "Knock Retard", "Timing", True),
        ("E11", "Cam Position", "VANOS", True),
        ("S23", "VANOS Command", "VANOS", True),
        ("E210", "Adjust Angle (raw)", "VANOS", False),
        ("P2", "Coolant Temp", "Temps", True),
        ("P11", "Intake Temp", "Temps", False),
    ],
}

# The RomRaider expressions for switch params use BitWise()/! which our
# safe-eval can't run — python-eval-able replacements, verified against the
# XML semantics (S23: 0xFFC1 bit4, inverted -> 1 when VANOS commanded).
EXPR_OVERRIDES = {
    "S23": ("0 if (x & 16) else 1", "cmd"),
    "E210": ("x", "raw"),
}

# Physics-based crank power/torque estimate from mass airflow -- one
# formula for every petrol engine, no per-VIN/per-engine calibration
# constant. The earlier approach (a kW-per-g/s ratio back-solved from one
# real WOT pull's peak MAF against that engine's factory-rated power)
# quietly stopped being a measurement and became "make this one car read
# its spec sheet number" -- comparing engines against each other (or a
# generic-constant car against a calibrated one) was meaningless, and any
# real deviation from spec on a *sick* engine would get calibrated away
# instead of showing up.
#
#   fuel mass flow (g/s)  = MAF (g/s) / AFR
#   chemical energy (kW)  = fuel mass flow (g/s) * gasoline LHV (kJ/g)
#   brake power (kW)      = chemical energy (kW) * brake thermal efficiency
#
# Every constant below has physical meaning and is a documented typical
# value, not a fit:
GASOLINE_LHV_KJ_PER_G = 44.0   # lower heating value of gasoline, ~44 MJ/kg
                                # (standard reference value)
WOT_AFR = 12.6                  # mass air-fuel ratio at wide-open-throttle
                                 # enrichment for a naturally-aspirated
                                 # port-injected engine -- typical range is
                                 # 12.5-13.0:1 (richer than stoichiometric
                                 # 14.7:1 for cooling/max power/detonation
                                 # margin), confirmed via web search, not
                                 # memory.
BRAKE_THERMAL_EFFICIENCY = 0.30  # typical NA gasoline engine at WOT;
                                  # general literature range is ~25-30% for
                                  # conventional (non-Atkinson/non-high-CR)
                                  # engines, confirmed via web search.
# Deliberately NOT surfaced as a "+-X%" figure: an earlier version of this
# comment did that by varying BRAKE_THERMAL_EFFICIENCY alone (+-3pp ->
# +-10%), which implies a rigorous confidence interval that doesn't exist --
# AFR, LHV, MAF sensor accuracy, and sampling all carry their own unstated
# uncertainty too. Instead, every displayed estimate states its exact inputs
# (AFR/BTE/LHV) so it's transparent and exactly reproducible, and so a
# future refinement to any one constant can be understood against what
# produced the old numbers. See ui.html's setDynoCurrent().
# If a car's estimate consistently reads high/low against its known-healthy
# factory rating, that's a signal the physics model (or these defaults) has
# a systematic bias worth investigating -- not something to paper over with
# a per-car fudge factor again.


def estimate_power_torque(maf_gps, rpm):
    """Physics-based crank power/torque estimate from mass airflow -- see
    the constants above for the formula and its assumptions. Same numbers
    for every petrol engine, deliberately: comparable across cars, and any
    systematic bias shows up as a bias instead of being silently absorbed
    into a per-car constant. Returns (power_kw, torque_nm); torque_nm is
    None below 50 rpm (avoids a division blow-up at engine-off)."""
    if not maf_gps:
        return None, None
    fuel_g_s = maf_gps / WOT_AFR
    power_kw = fuel_g_s * GASOLINE_LHV_KJ_PER_G * BRAKE_THERMAL_EFFICIENCY
    torque_nm = None
    if rpm and rpm > 50:
        omega = rpm * 2 * math.pi / 60
        torque_nm = power_kw * 1000 / omega
    return (round(power_kw, 1),
            round(torque_nm, 1) if torque_nm is not None else None)


class E39Adapter:
    """DS2 protocol (1998 523i)."""
    name = "E39 (DS2 9600 8E1)"
    proto = "e39"
    modules = ds2_diag.E39_MODULES
    vin = "WBAXXXXXXXXXXXXXX"  # placeholder until a real read is confirmed

    def read_vin(self):
        """DS2 has no confirmed standard VIN job across this ECU set, so we
        don't guess — keep the placeholder until a real read is verified.
        (Read-only stub; returning None makes the caller keep `self.vin`.)"""
        return None

    def __init__(self, profile="driveability"):
        self.kl = KLine(baud=ds2_diag.DS2_BAUD, parity="E",
                        rawlog_path=os.path.join(DATA, "kline_raw.log"))
        self.kl.log = log_hook(self.kl.log)
        self.ds2 = ds2_diag.DS2(self.kl)
        self.current_profile = profile
        # DME defaults to MS41 (M52); refined by detect() once the engine's
        # ident is read, so any family E39 loads the right parameter map.
        self.dme = {"dme": "MS41", "engine": "M52",
                    "params": "ms41_ram_params.json",
                    "evidence": "default (not yet detected)"}
        self._load_dme_params(self.dme)
        self._build_profile(profile)

    def _load_dme_params(self, descriptor):
        import dme_registry
        plist = dme_registry.load_params(
            descriptor, part_number=descriptor.get("matched_part"))
        if not plist:  # unknown/mapless DME -> fall back to MS41 ids
            try:
                with open(os.path.join(HERE, "ms41_ram_params.json")) as f:
                    plist = json.load(f)
            except OSError:
                plist = []
        self._all_params = {p["id"]: p for p in plist}

    def _build_profile(self, profile):
        """Build live_channels and logger from the given profile name."""
        if profile not in MS41_PROFILES:
            profile = "driveability"
        self.current_profile = profile
        self.live_channels = []
        params = []
        adc_count = 0
        for pid, label, group, graph in MS41_PROFILES[profile]:
            if pid not in self._all_params:
                continue
            p = self._all_params[pid]
            if pid in EXPR_OVERRIDES:
                p = dict(p)
                p["expr"], p["units"] = EXPR_OVERRIDES[pid]
            # Count ADC reads (addresses < 0x1C use ADC procedure type)
            if int(p["addr"], 16) < 0x1C:
                adc_count += 1
            self.live_channels.append(
                {"id": pid, "label": label, "group": group,
                 "unit": p["units"], "graph": graph})
            params.append(p)
        if any(p["id"] == "S23" for p in params):
            # synthetic channel computed by VanosMonitor from S23 + E11
            self.live_channels.append(
                {"id": "vanos_state", "label": "VANOS State",
                 "group": "VANOS", "unit": "", "graph": False})
        if any(p["id"] == "P12" for p in params) and any(p["id"] == "P8" for p in params):
            # synthetic channels computed by live_sample() from P12 (MAF)
            # + P8 (RPM) via estimate_power_torque(), same physics-based
            # estimate as the E87.
            self.live_channels.append(
                {"id": "power_kw", "label": "Est. Crank Power", "unit": "kW",
                 "group": "Engine", "graph": True})
            self.live_channels.append(
                {"id": "torque_nm", "label": "Est. Crank Torque", "unit": "Nm",
                 "group": "Engine", "graph": True})
        self.logger = ds2_diag.MS41Logger(self.ds2, params)
        self.profile_stats = {
            "total": len(params),
            "adc": adc_count,
            "ram": len(params) - adc_count
        }

    def set_profile(self, profile_name):
        """Switch to a different logging profile and re-arm the logger."""
        self._build_profile(profile_name)
        return {"ok": True, "profile": self.current_profile,
                "channels": self.live_channels, "profile_stats": self.profile_stats}

    def close(self):
        self.kl.close()

    def detect(self):
        f = self.ds2.ident(0x12, timeout=0.5)
        if f is None:
            return False
        # Identify the engine/DME from the ident ASCII and load its map.
        import dme_registry
        data = ds2_diag.body(f)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in data)
        dme = dme_registry.detect_dme(asc)
        if dme["dme"] != "unknown":
            self.dme = dme
            self.name = (f"E39 {dme['engine']}/{dme['dme']} (DS2 9600 8E1)")
            self._load_dme_params(dme)
            self._build_profile(self.current_profile)
        v = self.read_vin()
        if v:
            self.vin = v      # promote placeholder -> confirmed real VIN
        return True

    def engine_info(self):
        return {"dme": self.dme.get("dme"), "engine": self.dme.get("engine"),
                "evidence": self.dme.get("evidence", ""),
                "matched_part": self.dme.get("matched_part"),
                "param_count": len(self._all_params)}

    def sia_reset(self, kind=0x01):
        f = self.ds2.sia_reset(kind)
        if f is None:
            return {"ok": False, "error": "no response from cluster"}
        st = f[2]
        return {"ok": st == 0xA0,
                "status": f"0x{st:02X} "
                          f"({ds2_diag.STATUS_BYTE.get(st, '?')})"}

    def scan(self):
        out = []
        for addr, name in self.modules.items():
            f = self.ds2.ident(addr, timeout=0.3)
            if f is None:
                continue
            data = ds2_diag.body(f)
            asc = "".join(chr(c) if 32 <= c < 127 else "." for c in data)
            out.append({"addr": addr, "name": name,
                        "ident": hexs(data), "ident_ascii": asc})
        return out

    def faults(self, addr):
        f = self.ds2.faults(addr)
        if f is None:
            return {"ok": False, "error": "no response"}
        st = f[2]
        if st != 0xA0:
            return {"ok": False,
                    "error": f"status 0x{st:02X} "
                             f"({ds2_diag.STATUS_BYTE.get(st, '?')})"}
        data = ds2_diag.body(f)
        n = data[0] if data else 0
        rest = data[1:]
        entries = []
        table = ds2_diag.DTC_TABLES.get(addr, {})
        if n and rest and len(rest) % n == 0:
            size = len(rest) // n
            for k in range(n):
                e = rest[k * size:(k + 1) * size]
                if not any(e):
                    continue
                art = (ds2_diag.fault_type_text(addr, e[1])
                       if size >= 2 else "")
                entries.append({"code": f"{e[0]:02X}",
                                "raw": hexs(e),
                                "text": table.get(e[0], ""),
                                "status": art})
        elif n:
            entries.append({"code": "?", "raw": hexs(rest),
                            "text": "(unknown entry layout)", "status": ""})
        return {"ok": True, "count": n, "entries": entries,
                "raw": hexs(data)}

    def clear(self, addr):
        f = self.ds2.clear(addr)
        if f is None:
            return {"ok": False, "error": "no response to clear"}
        return {"ok": f[2] == 0xA0, "status": f"0x{f[2]:02X}",
                "after": self.faults(addr)}

    def live_sample(self):
        s = self.logger.sample() or {}
        maf_kgh = s.get("P12")
        if maf_kgh is not None:
            maf_gps = maf_kgh * 1000 / 3600
            pw, tq = estimate_power_torque(maf_gps, s.get("P8") or 0)
            if pw is not None:
                s["power_kw"] = pw
            if tq is not None:
                s["torque_nm"] = tq
        return s


class DemoAdapter(E39Adapter):
    """Simulated 523i for demoing the UI without the car connected.

    Replays the module inventory and the real fault codes recorded from the
    car, and synthesizes a repeating drive cycle: idle -> pull -> overrun.
    VANOS alternates per cycle between responding (engage event) and frozen
    (fault event) so the state tile and event log can be seen working.
    """
    name = "DEMO — simulated 523i (no car)"
    proto = "e39"
    vin = "WBADEMO5230DEMO01"          # obviously-fake demo VIN

    def read_vin(self):
        return self.vin

    # (ident hex, fault-entry-size, fault bytes) — real data from the car
    DEMO_MODULES = {
        0x12: ("31 34 32 39 38 36 31", 0, b""),
        0x44: ("88 38 24 54 02 81 81 07 26 98 04 05", 2,
               bytes.fromhex("433F410A0FFF4005")),
        0x56: ("01 16 41 30 59 06 08 00 27 98 08 01 80", 5,
               bytes.fromhex("06000102AC")),
        0x5B: ("88 37 54 53 02 03 21 08 26 98 21 07", 0, b""),
        0x60: ("88 38 52 32 01 02 01 01 26 98 14 11", 0, b""),
        0x80: ("F8 37 56 69 04 05 32 08 38 97 10 11 02 24", 3,
               bytes.fromhex("83C26EC78100")),
        0xD0: ("08 37 28 75 10 16 12 00 27 98 01 32", 0, b""),
        0xE8: ("88 38 24 68 04 00 00 00 26 98 02 13", 0, b""),
    }

    # Demo coding data (example E39 coding strings)
    DEMO_CODING = {
        0x80: bytes([0x01, 0x0F, 0x01, 0x01, 0x41]),  # IKE: US, Touring, digital speed
        0xD0: bytes([0x01, 0x3C, 0x02, 0x03]),        # LCM: US, Xenon, DRL+comfort blink
        0x00: bytes([0x01, 0x45, 0x83]),              # GM: US, auto lock, selective unlock, comfort close, crash unlock, mirror fold
        0x5B: bytes([0x01, 0x00, 0xE5]),              # IHKA: US, Celsius, auto recirc + rest + economy + solar
    }

    def __init__(self, profile="vanos"):
        self.kl = None
        self.ds2 = None
        self.current_profile = profile
        # the demo replays the real M52/MS41 car
        self.dme = {"dme": "MS41", "engine": "M52",
                    "params": "ms41_ram_params.json",
                    "evidence": "demo (simulated M52)", "matched_part": "1429861"}
        try:
            with open(os.path.join(HERE, "ms41_ram_params.json")) as f:
                self._all_params = {p["id"]: p for p in json.load(f)}
        except OSError:
            self._all_params = {}
        self._build_profile(profile)
        self.t0 = time.time()
        self._faults = {a: (size, bytes(raw))
                        for a, (_, size, raw) in self.DEMO_MODULES.items()}

    def demo_ram_dump(self, start, count):
        """Simulated RAM for the explorer demo. Most bytes are static; a few
        near the real MS41 RPM address (0xDA2A) vary with the simulated engine
        speed, so an idle-vs-rev diff reveals them — exactly the discovery
        workflow, without a car."""
        import math
        t = time.time() - self.t0
        phase = t % 24.0
        rpm = 800 if phase < 6 else (1200 + 3300 * min(1, (phase - 6) / 8)
                                     if phase < 14 else 2100)
        out = {}
        for a in range(start, start + count):
            if a in (0xDA2A, 0xDA2B):          # RPM word (hi, lo)
                rpm_raw = int(rpm)
                out[a] = (rpm_raw >> 8) if a == 0xDA2A else (rpm_raw & 0xFF)
            elif a == 0xDA34:                   # MAF-ish, tracks rpm
                out[a] = min(255, int(rpm / 16))
            elif a == 0xDA5A:                   # coolant, ~static warm
                out[a] = 0xB8
            else:                               # deterministic static filler
                out[a] = (a * 37) & 0xFF
        return out

    def close(self):
        pass

    def detect(self):
        return True

    def sia_reset(self, kind=0x01):
        return {"ok": True, "status": "0xA0 (OK) [demo]"}

    def scan(self):
        out = []
        for addr, (ident, _, _) in self.DEMO_MODULES.items():
            data = bytes.fromhex(ident.replace(" ", ""))
            asc = "".join(chr(c) if 32 <= c < 127 else "." for c in data)
            out.append({"addr": addr,
                        "name": ds2_diag.E39_MODULES.get(addr, "?"),
                        "ident": hexs(data), "ident_ascii": asc})
        return out

    def faults(self, addr):
        if addr not in self._faults:
            return {"ok": False, "error": "no response"}
        size, raw = self._faults[addr]
        entries = []
        table = ds2_diag.DTC_TABLES.get(addr, {})
        n = (len(raw) // size) if size else 0
        for k in range(n):
            e = raw[k * size:(k + 1) * size]
            art = ds2_diag.fault_type_text(addr, e[1]) if size >= 2 else ""
            entries.append({"code": f"{e[0]:02X}", "raw": hexs(e),
                            "text": table.get(e[0], ""), "status": art})
        return {"ok": True, "count": n, "entries": entries, "raw": hexs(raw)}

    def clear(self, addr):
        self._faults[addr] = (0, b"")
        return {"ok": True, "status": "cleared [demo]",
                "after": self.faults(addr)}

    def read_coding(self, addr):
        """Return demo coding data for testing."""
        time.sleep(0.05)  # simulate bus latency
        if addr in self.DEMO_CODING:
            return self.DEMO_CODING[addr]
        return None

    def live_sample(self):
        time.sleep(0.08)  # simulate bus latency (~10 Hz)
        import math
        t = time.time() - self.t0
        phase = t % 24.0                 # one drive cycle
        vanos_ok = (t % 48.0) < 24.0     # alternate healthy/faulty cycles
        if phase < 6:                    # idle
            rpm, tps = 780 + 25 * math.sin(t * 2.1), 1.5
        elif phase < 14:                 # accelerating pull
            k = (phase - 6) / 8
            rpm, tps = 1200 + 3300 * k, 82
        elif phase < 17:                 # overrun
            rpm, tps = 4500 - (phase - 14) * 1100, 2
        else:                            # cruise
            rpm, tps = 2100 + 40 * math.sin(t * 1.3), 22
        load = min(700.0, 90 + tps * 6.2 + rpm * 0.02)
        cmd = 1 if (1700 < rpm < 4600 and load > 180) else 0
        cam_rest, cam_adv = 26.6, 48.7
        cam = cam_adv if (cmd and vanos_ok) else cam_rest
        maf = round(rpm * load / 25000, 1)
        noise = math.sin(t * 3.7)
        s = {
            "P8": round(rpm), "P9": round(rpm / 48),
            "P13": round(tps, 1), "E2": round(load, 1),
            "P12": maf, "P18": round(1.0 + maf / 200, 2),
            "P21": round(1.4 + load / 120, 2),
            "E13": round(2.3 * noise, 1), "E14": round(-1.8 * noise, 1),
            "E21": 1.6, "E22": 2.4,
            "P10": round(12 + tps / 8 + noise, 1),
            "E217": 0.0, "E24": 0.0,
            "E11": round(cam + 0.2 * noise, 1),
            "S23": cmd, "E210": round(cam - cam_rest),
            "P2": 91, "P11": 24, "P17": 14.1,
            "P19": round(0.6 + tps * 0.04, 2), "E9": 28.0,
            "E101": round(0.45 + 0.4 * noise, 2),
            "E102": round(0.45 - 0.4 * noise, 2),
        }
        return {k: v for k, v in s.items()
                if any(c["id"] == k for c in self.live_channels)
                or k in ("P8",)}


class E87Adapter:
    """KWP2000 (2005 E87)."""
    name = "E87 (KWP2000 10400 8N1)"
    proto = "e87"
    vin = "WBAXXXXXXXXXXXXXX"  # placeholder — promoted to the real VIN by
                                # detect()/read_vin() once confirmed (same
                                # contract as E39Adapter), becoming the
                                # backup/passport key from then on
    vin_suffix = None          # last 7 chars of the real VIN (display-only
                                # fallback for when the full read fails —
                                # see read_vin_suffix())
    modules = {a: n for a, n in power_diag.MODULES.items()
               if a in (0x00, 0x01, 0x12, 0x29, 0x40, 0x60, 0x63, 0x64,
                        0x72, 0x78)}
    live_channels = [
        {"id": "battery_v", "label": "Battery", "unit": "V",
         "group": "Temps/V", "graph": True},
        {"id": "rpm", "label": "RPM", "unit": "rpm",
         "group": "Engine", "graph": True},
        {"id": "coolant_c", "label": "Coolant", "unit": "°C",
         "group": "Temps/V", "graph": False},
        {"id": "speed_kmh", "label": "Speed", "unit": "km/h",
         "group": "Engine", "graph": True},
        {"id": "engine_load", "label": "Engine Load", "unit": "%",
         "group": "Engine", "graph": True},
        {"id": "throttle", "label": "Throttle", "unit": "%",
         "group": "Engine", "graph": True},
        {"id": "iat_c", "label": "Intake Air", "unit": "°C",
         "group": "Temps/V", "graph": False},
        {"id": "maf", "label": "MAF", "unit": "g/s",
         "group": "Engine", "graph": True},
        {"id": "power_kw", "label": "Est. Crank Power", "unit": "kW",
         "group": "Engine", "graph": True},
        {"id": "torque_nm", "label": "Est. Crank Torque", "unit": "Nm",
         "group": "Engine", "graph": True},
        {"id": "timing_advance", "label": "Timing Advance", "unit": "°",
         "group": "Engine", "graph": False},
        {"id": "stft", "label": "Short Fuel Trim", "unit": "%",
         "group": "Fuel", "graph": False},
        {"id": "ltft", "label": "Long Fuel Trim", "unit": "%",
         "group": "Fuel", "graph": False},
        # UNVERIFIED against real hardware -- unlike the rest of this list
        # (confirmed via power_diag.py pids output), whether this DME
        # answers PID 0x0B/0x33 at all hasn't been tested on the real car.
        # Used for SAE/DIN dyno correction (manifold pressure at WOT as an
        # ambient-pressure proxy) if present; if this DME never answers,
        # they'll simply stay absent from every sample, same as any other
        # unsupported PID, and dyno curves fall back to uncorrected.
        {"id": "map_kpa", "label": "Manifold Pressure", "unit": "kPa",
         "group": "Engine", "graph": False},
        {"id": "baro_kpa", "label": "Barometric Pressure", "unit": "kPa",
         "group": "Engine", "graph": False},
        # o2_s1/o2_s2 (PIDs 0x14/0x15) confirmed responding live at idle
        # (voltage oscillating ~0.1-0.8V, healthy narrowband switching
        # behavior). o2_s3/o2_s4 (0x16/0x17) confirmed absent from the same
        # live sample -- this engine likely only has 2 O2 sensors (single
        # bank, 4-cylinder: one pre-cat, one post-cat), not the 4 some
        # multi-bank PID layouts assume. No PID here gives an actual
        # lambda/AFR number -- these are narrowband switching sensors, not
        # wideband, so voltage is all that's available (see CLAUDE.md).
        # Still labeled by raw PID slot, not by claimed bank/pre-post-cat
        # position: SAE J1979 splits O2 sensor location across two possible
        # bitmap configs (PID 0x13 vs 0x1D), and this DME's config isn't
        # confirmed. Once PID 0x13's presence bitmap is read, relabel the
        # responding ones as e.g. "O2 Bank 1 Pre-Cat" -- relevant here since
        # a DME on this code path has stored 29F4/29F5 (Bank 1/2 catalyst
        # efficiency; see that car's local backups/<VIN>/ tree), and a
        # post-cat sensor bouncing 0.1-0.9V like the pre-cat one would
        # confirm a worn catalyst rather than a sensor/fueling fault.
        {"id": "o2_s1", "label": "O2 Sensor 1 (PID 0x14)", "unit": "V",
         "group": "Fuel", "graph": False},
        {"id": "o2_s2", "label": "O2 Sensor 2 (PID 0x15)", "unit": "V",
         "group": "Fuel", "graph": False},
        {"id": "o2_s3", "label": "O2 Sensor 3 (PID 0x16)", "unit": "V",
         "group": "Fuel", "graph": False},
        {"id": "o2_s4", "label": "O2 Sensor 4 (PID 0x17)", "unit": "V",
         "group": "Fuel", "graph": False},
    ]
    # PIDs confirmed supported by this car's DME (power_diag.py pids output);
    # channel id -> Mode-01 PID, decoded via obd2.decode_pid (same SAE J1979
    # formulas the CAN/UDS Octavia code uses — PID math is transport-agnostic).
    _PID_CHANNELS = {
        "rpm": 0x0C, "coolant_c": 0x05, "speed_kmh": 0x0D,
        "engine_load": 0x04, "throttle": 0x11, "iat_c": 0x0F, "maf": 0x10,
        "timing_advance": 0x0E, "stft": 0x06, "ltft": 0x07,
        # unverified -- see the map_kpa/baro_kpa/o2_s1..4 live_channels comments above
        "map_kpa": 0x0B, "baro_kpa": 0x33,
        "o2_s1": 0x14, "o2_s2": 0x15, "o2_s3": 0x16, "o2_s4": 0x17,
    }
    def __init__(self):
        self.kl = KLine(rawlog_path=os.path.join(DATA, "kline_raw.log"))
        self.kl.log = log_hook(self.kl.log)
        self._live_init = False

    def close(self):
        self.kl.close()

    def detect(self):
        r = self.kl.fast_init(0x12)
        # r is False when the DME answers StartCommunication but refuses it
        # (same "responded-but-refused" pattern as KOMBI, see CLAUDE.md) --
        # it still serves requests, so only None (no answer at all) means
        # truly unreachable. power_diag.py's scan_addr() uses the same
        # is-None/is-False split; a plain `if r:` here previously treated
        # the refusal as no response and made the whole app miss the car.
        if r is not None:
            self.vin_suffix = self.read_vin_suffix()  # display-only partial
            v = self.read_vin()          # full VIN, if confirmed
            if v:
                self.vin = v      # promote placeholder -> confirmed real VIN
            self.kl.stop_comm(0x12)
            return True
        return False

    def read_vin(self):
        """KWP readECUIdentification, service 1A identifier 0x86 -- the
        full VIN. Same contract as E39Adapter.read_vin(): a truthy return
        here is promoted to self.vin (the backup/passport key) by detect().

        Hardware-verified on this car: the DME answers with a 38-char
        combined production record, structured as
        [serial:7][unknown:9][unknown:12][VIN-prefix:10] -- reassembling
        as prefix+serial gives exactly the real 17-char VIN (confirmed
        against the physical VIN plate). The two middle fields are still
        unidentified; this only trusts the parse when the total length
        matches what was verified, so an unexpected DME/format returns
        None rather than a wrong guess.
        """
        try:
            frames = self.kl.request(b"\x1A\x86", 0x12, timeout=1.0)
            for f in frames:
                p = power_diag.frame_payload(f)
                if p[:2] == b"\x5A\x86":     # positive response to 1A 86
                    raw = bytes(p[2:]).decode("ascii", "ignore")
                    clean = "".join(ch for ch in raw if ch.isalnum())
                    if len(clean) == 38:
                        vin = clean[28:38] + clean[0:7]
                        if len(vin) == 17:
                            return vin
        except Exception:
            pass
        return None

    def read_vin_suffix(self):
        """KWP readECUIdentification, service 1A identifier 0x90.

        Hardware-verified on this car: the DME answers with 7 ASCII
        characters that are exactly the last 7 characters of the real VIN
        (confirmed against the physical VIN plate) -- this is BMW's
        "production serial" identifier, not the full 17-character VIN.
        Display-only fallback for when read_vin() (the full VIN, service
        1A 86) doesn't resolve -- never promoted to self.vin, a 7-char
        value isn't a safe backup key on its own.
        """
        try:
            frames = self.kl.request(b"\x1A\x90", 0x12, timeout=1.0)
            for f in frames:
                p = power_diag.frame_payload(f)
                if p[:2] == b"\x5A\x90":     # positive response to 1A 90
                    raw = bytes(p[2:]).decode("ascii", "ignore")
                    vin = "".join(ch for ch in raw if ch.isalnum())
                    if 5 <= len(vin) <= 17:
                        return vin
        except Exception:
            pass
        return None

    def scan(self):
        out = []
        self._live_init = False
        for addr, name in self.modules.items():
            r = self.kl.fast_init(addr)
            if r is None:
                continue
            parts = power_diag.read_ident_parts(self.kl, addr)
            ident = f"1A{parts[0]:02X}: {parts[1]}  |{parts[2]}|" if parts else ""
            ident_ascii = parts[2].strip(".") if parts else ""
            out.append({"addr": addr, "name": name, "ident": ident,
                        "ident_ascii": ident_ascii})
            self.kl.stop_comm(addr)
        return out

    def dme_ident(self):
        """Raw DME (0x12) identification string, for vehicle-info/report
        purposes. This project has no engine-variant registry for KWP2000
        cars yet (unlike dme_registry.py's DS2/E39 one) -- the E87 code
        path is shared by more than one physical car with different
        engines (see CLAUDE.md), so returning the real ident text instead
        of a hardcoded model/engine guess is the only honest option until
        one exists."""
        self._live_init = False
        if self.kl.fast_init(0x12) is None:
            return None
        parts = power_diag.read_ident_parts(self.kl, 0x12)
        self.kl.stop_comm(0x12)
        return parts[2].strip(".") if parts else None

    def faults(self, addr, _init=True):
        if _init:
            self._live_init = False
            if self.kl.fast_init(addr) is None:
                return {"ok": False, "error": "no response to init"}
        p = power_diag.read_dtcs(self.kl, addr)
        if p is None:
            return {"ok": False, "error": "no response to fault read"}
        n = p[1]
        entries = []
        body = p[2:]
        for k in range(min(n, len(body) // 3)):
            hi, lo, st = body[3 * k], body[3 * k + 1], body[3 * k + 2]
            bits = ",".join(nm for bit, nm in power_diag.STATUS_BITS
                            if st & bit)
            code = f"{hi:02X}{lo:02X}"
            entries.append({"code": code, "raw": f"{code} {st:02X}",
                            "text": E87_DTC.get(code, ""),
                            "status": bits})
        if _init:
            self.kl.stop_comm(addr)
        return {"ok": True, "count": n, "entries": entries, "raw": hexs(p)}

    def clear(self, addr):
        self._live_init = False
        if self.kl.fast_init(addr) is None:
            return {"ok": False, "error": "no response to init"}
        cleared = False
        neg = None
        for req in (b"\x14\xFF\xFF", b"\x14\xFF\xFF\x00", b"\x14\x00\x00"):
            frames = self.kl.request(req, addr, timeout=1.5)
            for f in frames:
                p = frame_payload(f)
                if p[:1] == b"\x54":
                    cleared = True
                elif p[:2] == b"\x7F\x14":
                    neg = p[2]
            if cleared or (neg is not None and neg != 0x12):
                break
        after = self.faults(addr, _init=False)
        self.kl.stop_comm(addr)
        return {"ok": cleared,
                "status": "cleared" if cleared else
                          (f"refused 7F 14 {neg:02X}" if neg is not None
                           else "no answer"),
                "after": after}

    def live_sample(self):
        if not self._live_init:
            if self.kl.fast_init(0x12) is None:
                return {}
            self._live_init = True
        s = {}
        frames = self.kl.request(b"\x21\x5A", 0x12, timeout=0.35, retries=1)
        for f in frames:
            p = frame_payload(f)
            if p[:1] == b"\x61" and len(p) > 2:
                s["battery_v"] = round(p[2] * 0.1, 1)
        for chan_id, pid in self._PID_CHANNELS.items():
            d = power_diag.obd_pid(self.kl, pid, 0x12, retries=0, timeout=0.3)
            if d:
                s[chan_id] = round(obd2.decode_pid(pid, d), 2)
        if "maf" in s:
            pw, tq = estimate_power_torque(s["maf"], s.get("rpm") or 0)
            if pw is not None:
                s["power_kw"] = pw
            if tq is not None:
                s["torque_nm"] = tq
        if not s:
            self._live_init = False  # force re-init next time
        return s


ADAPTER = None            # current protocol adapter
ADAPTER_ERR = ""


def _open_file(path):
    """Launch the OS's default viewer for a file as its own separate
    process/window -- distinct from (and safe unlike) navigating the app's
    own pywebview/WKWebView window to the file, which has no downloads UI
    and just hijacks the whole app window with no way back (see
    /api/dyno/export-pdf)."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif sys.platform.startswith("win"):
        os.startfile(path)  # noqa: Windows-only API, guarded by the platform check
    else:
        subprocess.Popen(["xdg-open", path])


def _current_vin():
    """VIN of the connected car, or None. A passport doesn't require a live
    connection to exist or be viewed/logged to -- anonymous-first, VIN is
    optional data, not identity (see ovpf_producer.ensure_passport). None
    resolves to the single "unknown vin" passport, same as running this
    tool with no car plugged in at all."""
    return ADAPTER.vin if ADAPTER else None


def gather_vehicle_info():
    """Best-known facts about the connected car, shared by /api/vehicle and
    /api/report_metadata. Assumes ADAPTER is set; callers check that first."""
    vehicle_info = {
        "vin": ADAPTER.vin,
        # generic across adapters: vin has been promoted from the
        # placeholder once any adapter's read_vin() confirms a
        # real one (see E39Adapter/E87Adapter.detect())
        "vin_confirmed": ADAPTER.vin != "WBAXXXXXXXXXXXXXX",
        "protocol": ADAPTER.proto,
        "adapter_name": ADAPTER.name
    }

    # Try to get additional info from IKE ident (if E39)
    if ADAPTER.proto == "e39" and hasattr(ADAPTER, 'ds2') and ADAPTER.ds2:
        with CAR_LOCK:
            ike_frame = ADAPTER.ds2.ident(0x80, timeout=0.5)
            if ike_frame:
                ike_data = ds2_diag.body(ike_frame)
                ike_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in ike_data)
                vehicle_info["ike_ident"] = ike_str.strip()

                # Try to parse model from ident
                # E39 IKE ident format varies, but often contains model info
                if "523" in ike_str:
                    vehicle_info["model"] = "E39 523i"
                    vehicle_info["engine"] = "M52TU"
                elif "528" in ike_str:
                    vehicle_info["model"] = "E39 528i"
                    vehicle_info["engine"] = "M52TU"
                elif "540" in ike_str:
                    vehicle_info["model"] = "E39 540i"
                    vehicle_info["engine"] = "M62"
                else:
                    vehicle_info["model"] = "E39"

                # Parse year from VIN (10th character = year code)
                if len(ADAPTER.vin) >= 10:
                    year_char = ADAPTER.vin[9]
                    # Simplified year parsing (W=1998, X=1999, Y=2000, etc.)
                    year_map = {'W': 1998, 'X': 1999, 'Y': 2000, '1': 2001, '2': 2002, '3': 2003}
                    vehicle_info["year"] = year_map.get(year_char, "Unknown")

    elif ADAPTER.proto == "e87":
        # chassis/protocol is genuinely known (that's what selected this
        # Adapter class) -- trim/engine is NOT: this code path is shared by
        # more than one physical E87 with different engines (see
        # CLAUDE.md), and there's no KWP2000 engine-variant registry yet
        # (unlike dme_registry.py for DS2/E39). Report the real DME ident
        # text as evidence instead of a hardcoded model/engine/year guess
        # -- that guess is exactly what mixed up two different cars' data
        # in an earlier report.
        vehicle_info["model"] = "E87"
        vehicle_info["engine"] = None
        vehicle_info["engine_evidence"] = "not auto-detected"
        # vin above is now the confirmed real VIN once detect() has
        # run (see E87Adapter.read_vin); vin_suffix is a
        # display-only fallback for when only the partial read
        # succeeded.
        vehicle_info["vin_suffix"] = getattr(ADAPTER, "vin_suffix", None)
        with CAR_LOCK:
            vehicle_info["dme_ident"] = ADAPTER.dme_ident()

    # Add transmission type (default unknown, can be enhanced)
    vehicle_info["transmission"] = "Unknown"

    # TODO: Read mileage from IKE (requires specific DS2 service)
    vehicle_info["mileage_km"] = None

    return vehicle_info


def _current_operator():
    """Signed-in cloud identity's email, to stamp onto locally created
    events as producer.operator (see ovpf_producer._stamp_operator and
    OVPF.md's spec field) -- distinct from producer.name/type, which
    describe the tool/mechanism (opendiag, a Diagnostic read), not who was
    actually at the keyboard. ovpf_producer.py can't check this itself
    (ovpf_cloud imports ovpf_producer, not the other way around). None if
    nobody's signed in -- the common, fully-anonymous case, and events
    stay exactly as they were before this existed."""
    try:
        import ovpf_cloud
        ws = ovpf_cloud.get_workshop_session()
        if ws and ws.get("email"):
            return ws["email"]
        us = ovpf_cloud.get_user_session()
        if us and us.get("email"):
            return us["email"]
    except Exception:
        pass
    return None


# Serializes background pushes so two auto-push threads firing close
# together (e.g. a coding write immediately followed by a fault re-read)
# can't race on ovpf_cloud's synced-ids file (read-modify-write, no
# locking of its own).
_PUSH_LOCK = threading.Lock()


def _auto_push(vin, urn=None):
    """Fire-and-forget cloud sync right after a local OVPF event is
    recorded, so nothing sits queued waiting for someone to click the
    dashboard's manual sync button. Best-effort like the record_* calls
    themselves: no session, offline, or a provider error just leaves the
    event queued for the next auto-push or manual sync -- never surfaced
    to the caller, never blocks the request or (if called with CAR_LOCK
    held) the car. `urn` lets a garage vehicle without a VIN yet resolve
    to its passport (see ovpf_producer.resolve_log_path)."""
    if not vin and not urn:
        return

    def _run():
        with _PUSH_LOCK:
            try:
                import ovpf_cloud
                ovpf_cloud.push_passport(vin, urn=urn)
            except Exception:
                pass
    threading.Thread(target=_run, daemon=True).start()


def _passport_url(urn):
    """Public passport.skoor.ee URL for a passport urn, or None if unminted.
    Same $OVPF_BASE_URL convention as the QR code (see do_GET) -- shared here
    so the UI can render a clickable link without duplicating the base URL."""
    if not urn:
        return None
    uid = urn.replace("urn:ovpf:", "")
    base_url = os.environ.get("OVPF_BASE_URL", "https://passport.skoor.ee")
    return f"{base_url.rstrip('/')}/p/{uid}"

LIVE_CLIENTS = set()      # live SSE listeners exist -> sampler runs
LIVE_LAST = {}
# power_kw/torque_nm are synthetic channels live_sample() computes from
# maf+rpm (see estimate_power_torque()), not anything the ECU actually
# reports -- they're excluded from the CSV recorder's columns
# (record_start()) so a recording's columns are only ever raw/measured
# sensor data, never an inferred value baked in at whatever physics
# constants happened to be in effect at record time (should the AFR/LHV/
# efficiency defaults ever get refined). ui.html's Replay/Dyno tabs already
# derive them on demand from maf+rpm wherever they're needed for display,
# using the current formula.
INFERRED_CHANNELS = {"power_kw", "torque_nm"}
# CSV export column names -- the E39/DS2 side's channel ids are RomRaider-
# style opaque codes (P8, P12, E2...) straight from ms41_ram_params.json,
# meaningless without cross-referencing that file. E87/KWP2000 already
# uses plain names (rpm, maf, throttle...) since its channel set is
# hardcoded, not loaded from a RAM-address table -- this makes the E39
# match it wherever a real semantic equivalent exists (rpm, maf, throttle,
# iat_c, map_kpa -- chosen to exactly match ui.html's normalizeSample()
# fallback names, so old and new CSVs both parse without it needing to
# know which car wrote the file) and gives the rest (VANOS, knock, fuel
# trims, switches) a real name instead of a bare id. Internal channel ids
# (live_channels, live_sample()'s dict keys, SSE payloads) are completely
# unaffected -- this only renames what gets WRITTEN to a CSV's header
# row; record_row() still looks values up by the original id.
E39_CSV_COLUMN_NAMES = {
    "P8": "rpm", "P9": "speed_kmh", "P13": "throttle",
    "P11": "iat_c", "P2": "coolant_c", "P10": "timing_advance",
    "P17": "battery_v", "P7": "map_kpa", "P12": "maf",
    "P18": "maf_voltage_v", "P19": "tps_voltage_v", "P21": "injector_pw_ms",
    "P24": "atm_pressure_psi", "P58": "wbo2_afr",
    "E2": "load_mgstroke", "E9": "iacv_pct",
    "E11": "vanos_angle", "E13": "stft1", "E14": "stft2",
    "E15": "o2_heater_front1", "E16": "o2_heater_front2",
    "E17": "o2_heater_rear1", "E18": "o2_heater_rear2",
    "E19": "idle_ft1_ms", "E20": "idle_ft2_ms",
    "E21": "ltft1", "E22": "ltft2", "E23": "tps_adapt",
    "E24": "knock_retard_global", "E99": "knock_adapt_table1",
    "E100": "iat_voltage_v", "E101": "o2_front1_v", "E102": "o2_front2_v",
    "E103": "ect_voltage_v", "E105": "zsr_voltage_v",
    "E123": "knock1_voltage_v", "E124": "knock2_voltage_v",
    "E125": "o2_rear1_v", "E126": "o2_rear2_v", "E127": "fuel_tank_pressure_v",
    "E201": "iacv_alphan", "E202": "evap_pwm",
    "E203": "load_switch", "E204": "knock_cyl1", "E205": "knock_cyl2",
    "E206": "knock_cyl3", "E207": "knock_cyl4", "E208": "knock_cyl5",
    "E209": "knock_cyl6", "E210": "vanos_status",
    "E211": "geberrad_adaption", "E212": "tank_diff_pressure",
    "E213": "timer_te_diag", "E214": "lambda_counter",
    "E215": "timer_tl_sp_dte", "E216": "timer_nb_sp_dte",
    "E85": "ff_ipw_pct", "E86": "ff_ign_deg", "E87": "oil_pressure_psi",
    "E88": "fuel_pressure_psi", "E131": "ff_pct",
    "S0": "ac_compressor", "S1": "ac_high_load", "S2": "theft_deterrent",
    "S3": "torque_reduction_gearshift", "S4": "engine_drag_torque_reduction",
    "S5": "torque_reduction_request", "S6": "full_load", "S7": "part_load",
    "S8": "closed_throttle", "S9": "reg2", "S10": "reg1",
    "S11": "trailing_throttle_fuel_cutoff", "S12": "accel_enrich",
    "S13": "engine_start", "S14": "drive_engaged", "S15": "generator",
    "S16": "can_switch", "S17": "secondary_air_valve",
    "S18": "secondary_air_pump", "S19": "tank_ventilation_valve",
    "S20": "rear_defogger", "S22": "exhaust_flap", "S23": "vanos_switch",
    "S24": "compressor_relay", "S25": "fuel_pump",
}
# P12 (MAF) is kg/h on DS2/MS41 vs g/s everywhere else in this codebase
# (E87's PID 0x10, and every physics/dyno calc) -- converting at write
# time, under the "maf" name above, means a CSV never needs a reader to
# know which protocol wrote it to interpret the MAF column correctly.
E39_CSV_VALUE_TRANSFORMS = {"P12": lambda kgh: round(kgh * 1000 / 3600, 2)}


def _csv_value(chan_id, values):
    v = values.get(chan_id)
    if v is None:
        return ""
    transform = E39_CSV_VALUE_TRANSFORMS.get(chan_id)
    return transform(v) if transform else v


RECORDER = {"on": False, "path": None, "file": None, "count": 0,
            "lock": threading.Lock()}
CSV_QUEUE = queue.Queue(maxsize=1000)  # Buffer for CSV writer thread
PULL_STATE = {"active": False, "counter": 0, "rpm_history": []}
PULLS_LOG = []  # finished pulls this session: [{num, t_start, t_end, peaks}]


class VanosMonitor:
    """Correlates the VANOS solenoid command (S23) with the measured cam
    position (E11) to classify VANOS behaviour in real time.

    On this M52 single-VANOS engine the cam RESTS at ~26.6 °crank (raw 0x47)
    and should depart from that position within a few hundred ms of being
    commanded. The rest position is slow-learned while uncommanded. A fault
    event fires when the command stays on past GRACE_S with no movement —
    exactly the failure signature under investigation (frozen E11 + E210=0).
    """
    REST_DEFAULT = 26.6
    MOVE_THRESH = 4.0    # °crank departure from rest = "cam moved"
    GRACE_S = 0.7        # allowed response time after command asserts

    def __init__(self):
        self.rest = self.REST_DEFAULT
        self.cmd_since = None
        self.fault_logged = False
        self.engage_logged = False
        self.last_state = "—"

    def update(self, s, tnow=None):
        """Returns (state_string, event_or_None) for a live sample dict."""
        tnow = tnow if tnow is not None else time.time()
        cmd = s.get("S23")
        pos = s.get("E11")
        event = None
        if cmd is None or pos is None:
            self.last_state = "—"
            return self.last_state, None
        moved = abs(pos - self.rest) >= self.MOVE_THRESH
        if not cmd:
            if not moved:
                # slow-learn the true rest position while uncommanded
                self.rest += 0.02 * (pos - self.rest)
                state = "rest"
            else:
                state = "moved w/o cmd?"
            self.cmd_since = None
            self.fault_logged = False
            self.engage_logged = False
        else:
            if self.cmd_since is None:
                self.cmd_since = tnow
            if moved:
                state = "ENGAGED"
                if not self.engage_logged:
                    event = "vanos_engaged"
                    self.engage_logged = True
            elif tnow - self.cmd_since > self.GRACE_S:
                state = "FAULT"
                if not self.fault_logged:
                    event = "vanos_fault"
                    self.fault_logged = True
            else:
                state = "engaging…"
        self.last_state = state
        return state, event


VANOS_MON = VanosMonitor()


def log_vanos_event(event, s):
    """Persist a VANOS event with a telemetry snapshot; returns UI payload."""
    snap = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        "rpm": s.get("P8"), "throttle": s.get("P13"), "load": s.get("E2"),
        "cam_pos_e11": s.get("E11"), "adjust_e210": s.get("E210"),
        "cmd_s23": s.get("S23"), "rest_learned": round(VANOS_MON.rest, 2),
        "coolant": s.get("P2"),
    }
    try:
        with open(os.path.join(DATA, "vanos_events.log"), "a") as f:
            f.write(json.dumps(snap) + "\n")
    except OSError:
        pass
    return snap

# Event tracking state (for detecting transitions)
EVENT_STATE = {
    "prev_profile": None,
    "prev_knock": 0,
    "prev_vanos": 0,
    "prev_health": {},
}


def evaluate_health(values):
    """M52-specific health evaluation from live data.

    Returns dict of subsystem statuses with color (green/yellow/red/blue) and text.
    Works with both E39 (DS2) and E87 (KWP2000) parameter sets.
    """
    health = {}

    # Extract common values (handle both E39 and E87 parameter names)
    rpm = values.get("P8") or values.get("rpm")
    throttle = values.get("P13") or values.get("throttle") or 0
    coolant = values.get("P2") or values.get("coolant_c")
    v_batt = values.get("P17") or values.get("battery_v")

    # Battery / Charging
    if v_batt is not None:
        if 13.6 <= v_batt <= 14.6:
            health["charging"] = {"color": "green", "text": "Charging OK", "value": f"{v_batt:.1f}V"}
        elif 13.0 <= v_batt < 13.6 or 14.6 < v_batt <= 15.0:
            health["charging"] = {"color": "yellow", "text": "Voltage borderline", "value": f"{v_batt:.1f}V"}
        else:
            health["charging"] = {"color": "red", "text": "Voltage abnormal", "value": f"{v_batt:.1f}V"}

    # Coolant temp (P2 or E87 coolant_c)
    if coolant is not None:
        if coolant < 80:
            health["coolant"] = {"color": "blue", "text": "Warming up", "value": f"{coolant:.0f}°C"}
        elif 80 <= coolant <= 105:
            health["coolant"] = {"color": "green", "text": "Temp normal", "value": f"{coolant:.0f}°C"}
        elif 105 < coolant <= 112:
            health["coolant"] = {"color": "yellow", "text": "Running hot", "value": f"{coolant:.0f}°C"}
        else:
            health["coolant"] = {"color": "red", "text": "Overheating", "value": f"{coolant:.0f}°C"}

    # Intake air temp (P11 or E87 iat_c)
    iat = values.get("P11")
    if iat is None:
        iat = values.get("iat_c")
    if iat is not None:
        if iat < 45:
            health["iat"] = {"color": "green", "text": "IAT good", "value": f"{iat:.0f}°C"}
        elif 45 <= iat <= 65:
            health["iat"] = {"color": "yellow", "text": "IAT elevated", "value": f"{iat:.0f}°C"}
        else:
            health["iat"] = {"color": "red", "text": "IAT hot", "value": f"{iat:.0f}°C"}

    # Fuel trims (E39 RAM params E13/E14/E21/E22, or E87 OBD PID 06/07 —
    # the +/-5% / +/-10% bands are generic OBD-II tuning guidance, not
    # engine-specific, so the same thresholds apply to both).
    stft1 = values.get("E13")
    stft2 = values.get("E14")
    ltft1 = values.get("E21")
    ltft2 = values.get("E22")
    e87_stft = values.get("stft")
    e87_ltft = values.get("ltft")
    trims = [t for t in [stft1, stft2, ltft1, ltft2, e87_stft, e87_ltft]
             if t is not None]
    if trims:
        max_trim = max(abs(t) for t in trims)
        if max_trim < 5:
            health["fuel"] = {"color": "green", "text": "Fuel trim excellent", "value": f"{max_trim:.1f}%"}
        elif max_trim < 10:
            health["fuel"] = {"color": "yellow", "text": "Fuel trim compensating", "value": f"{max_trim:.1f}%"}
        else:
            health["fuel"] = {"color": "red", "text": "Fuel trim high", "value": f"{max_trim:.1f}%"}

    # MAF health (P12)
    maf = values.get("P12")
    if maf is not None and rpm is not None:
        if rpm < 1000:
            # M52 2.5L idle MAF should be ~15-22 kg/h
            if 15 <= maf <= 22:
                health["maf"] = {"color": "green", "text": "Idle airflow OK", "value": f"{maf:.1f} kg/h"}
            elif 12 <= maf < 15 or 22 < maf <= 28:
                health["maf"] = {"color": "yellow", "text": "Idle airflow off", "value": f"{maf:.1f} kg/h"}
            else:
                health["maf"] = {"color": "red", "text": "Idle airflow abnormal", "value": f"{maf:.1f} kg/h"}
        else:
            # Driving - just show value without health assessment
            health["maf"] = {"color": "blue", "text": "MAF", "value": f"{maf:.1f} kg/h"}
    elif values.get("maf") is not None:
        # E87 OBD PID 0x10 reports g/s, not kg/h, and this is a different
        # (smaller, turbocharged) engine than the M52 thresholds above are
        # tuned for — show it as informational only, no color verdict.
        health["maf"] = {"color": "blue", "text": "MAF",
                          "value": f"{values['maf']:.1f} g/s"}

    # VANOS: command-vs-response when S23 is logged, else position-only.
    # NOTE: single-VANOS cam RESTS at ~26.6° (raw 0x47) — "active" means the
    # position DEPARTS from rest, not that it is nonzero.
    vanos = values.get("E11")
    if "S23" in values and vanos is not None:
        st = VANOS_MON.last_state
        color = {"ENGAGED": "green", "rest": "green", "engaging…": "blue",
                 "FAULT": "red", "moved w/o cmd?": "yellow"}.get(st, "blue")
        text = {"ENGAGED": "VANOS engaged", "rest": "VANOS at rest",
                "engaging…": "VANOS engaging",
                "FAULT": "Commanded, cam not moving",
                "moved w/o cmd?": "Cam moved w/o command"}.get(st, "VANOS")
        health["vanos"] = {"color": color, "text": text,
                           "value": f"{vanos:.1f}° (rest {VANOS_MON.rest:.1f}°)"}
    elif vanos is not None and coolant is not None and coolant >= 70:
        departed = abs(vanos - VANOS_MON.rest) >= VanosMonitor.MOVE_THRESH
        if throttle > 20 and rpm and rpm > 1500:
            if departed:
                health["vanos"] = {"color": "green", "text": "VANOS active", "value": f"{vanos:.0f}°"}
            else:
                health["vanos"] = {"color": "yellow", "text": "VANOS not moving", "value": f"{vanos:.0f}°"}
        else:
            health["vanos"] = {"color": "green", "text": "VANOS idle", "value": f"{vanos:.0f}°"}

    # Knock retard (E217 or E24)
    knock = values.get("E217")
    if knock is None:
        knock = values.get("E24")
    if knock is not None:
        knock_abs = abs(knock)
        if knock_abs < 2:
            health["timing"] = {"color": "green", "text": "No knock", "value": f"{knock:.1f}°"}
        elif knock_abs < 5:
            health["timing"] = {"color": "yellow", "text": "Mild knock", "value": f"{knock:.1f}°"}
        else:
            health["timing"] = {"color": "red", "text": "Heavy knock", "value": f"{knock:.1f}°"}

    return health


def detect_pull(values):
    """Detect pull start/end based on throttle, load, and RPM.

    Start: throttle > 80%, RPM increasing (load deliberately NOT required
    here -- found empirically that throttle sustains ~90-100% while load is
    still ramping from ~20% to 70%+ over several seconds, so requiring
    load>70 at the start missed the first few seconds of a real WOT pull).
    End: throttle < 60% alone -- load used to also gate this (`or load <
    50`), but a real logged pull showed why that's wrong: load can still be
    climbing from ~20% past 50% several seconds into a pull with throttle
    already pinned at 100%, so "load < 50" kept firing on nearly every
    sample during that ramp-up and fragmented one continuous pull into six
    separate start/end pairs, each ending the instant it began. Load lags
    throttle by design (intake/turbo dynamics); throttle position alone is
    the reliable "did the driver lift off" signal.

    While a pull is active, tracks the running peak of every numeric channel
    (not just throttle/load/rpm) so that e.g. peak power_kw/torque_nm/maf are
    available too -- see PULL_STATE["peaks"]. On "end", the finished pull's
    peaks are snapshotted into PULLS_LOG for the UI to list per-pull, so a
    session with several pulls keeps each one's numbers instead of only the
    single session-wide max. The full curve (not just peaks) and the
    passport DynoRun event are the client's job now -- see ui.html's
    computeDynoCurve()/POST /api/dyno/save -- this function only tracks
    peaks for the lightweight in-session "Pulls this session" panel.

    Returns: ("start", pull_number) | ("end", pull_number) | None
    """
    # Extract values, handling different param IDs across profiles (E39 DS2
    # MS41 profiles use P8/P13; the E87 KWP2000 channels use the plain
    # names -- same fallback pattern already used elsewhere in this file,
    # e.g. evaluate_health()).
    throttle = values.get("P13") or values.get("throttle") or 0
    rpm = values.get("P8") or values.get("rpm") or 0

    # rpm_increasing compares against a short rolling time window (~0.6s),
    # not the single previous sample -- confirmed against a real recorded
    # E39 WOT pull (1900->6500rpm, throttle pinned >80% throughout) that a
    # single-sample delta never exceeded ~91rpm, always under the old
    # ">100rpm since the previous sample" threshold, so detect_pull()
    # silently never fired for it. That's not the car being slow to spin
    # up -- DS2's single combined list-read just samples much more densely
    # than E87's per-PID KWP2000 round trips, so consecutive-sample deltas
    # during the exact same real acceleration are far smaller. The E87
    # "worked" by coincidence of being the slower protocol, not because
    # the heuristic was actually measuring acceleration.
    now = time.time()
    hist = PULL_STATE.setdefault("rpm_history", [])
    hist.append((now, rpm))
    window_s = 0.6
    # Real bug found live on the E87: KWP2000's per-PID round trips sample
    # at ~0.83-1.1s intervals (confirmed against an actual recorded WOT
    # pull, 1163->6533rpm), slower than this 0.6s window -- so the trim
    # below emptied hist down to just the sample that was *just appended*
    # every single call, baseline_rpm ended up comparing rpm against
    # itself, and detect_pull() silently never fired for the entire pull.
    # `> 2` (not `> 1`) keeps at least one older sample around whenever the
    # sampling interval alone exceeds window_s, falling back to a plain
    # previous-sample comparison -- while leaving the dense E39 case (many
    # samples per window) governed by the age-based trim exactly as before.
    while len(hist) > 2 and now - hist[0][0] > window_s:
        hist.pop(0)
    baseline_rpm = hist[0][1]
    rpm_increasing = rpm > baseline_rpm + 150  # meaningful climb across the window

    if PULL_STATE["active"]:
        peaks = PULL_STATE.setdefault("peaks", {})
        for k, v in values.items():
            if isinstance(v, (int, float)) and (k not in peaks or v > peaks[k]):
                peaks[k] = v

    if not PULL_STATE["active"]:
        # Check for pull start
        if throttle > 80 and rpm_increasing:
            PULL_STATE["active"] = True
            PULL_STATE["counter"] += 1
            PULL_STATE["peaks"] = {}
            PULL_STATE["t_start"] = time.time()
            return ("start", PULL_STATE["counter"])
    else:
        # Check for pull end -- throttle alone, see docstring for why load
        # was dropped from this condition.
        if throttle < 60:
            PULL_STATE["active"] = False
            t_start = PULL_STATE.get("t_start")
            t_end = time.time()
            peaks = dict(PULL_STATE.get("peaks", {}))
            PULLS_LOG.append({
                "num": PULL_STATE["counter"],
                "t_start": t_start,
                "t_end": t_end,
                "peaks": peaks,
            })
            del PULLS_LOG[:-50]  # cap; a session isn't going to need more
            return ("end", PULL_STATE["counter"])

    return None


def record_start():
    with RECORDER["lock"]:
        if RECORDER["on"]:
            return RECORDER["path"]
        # Include profile name in filename for easier comparison
        profile = getattr(ADAPTER, "current_profile", None) if ADAPTER else None
        profile_str = f"_{profile}" if profile else ""
        path = os.path.join(
            DATA, f"drive_log_{time.strftime('%Y%m%d_%H%M%S')}{profile_str}.csv")
        f = open(path, "w", buffering=1)
        ids = [c["id"] for c in (ADAPTER.live_channels if ADAPTER else [])
               if c["id"] not in INFERRED_CHANNELS]
        # Tags the recording with whichever car is connected right now, so
        # a Dyno curve generated later from a Replay selection of this file
        # (generateDynoFromSelection) can attribute it correctly instead of
        # falling back to whatever's connected *at generation time* (wrong
        # car if a different one's since been plugged in) or "unknown" (no
        # connection at all) -- the exact gap that let a real E39 dyno
        # session end up orphaned under an "unknown" passport earlier this
        # project. A plain leading comment line, not a new column -- see
        # ui.html's parseCSV for the matching skip-and-parse.
        f.write(f"# vin: {ADAPTER.vin if ADAPTER else ''}\n")
        # Descriptive column names instead of opaque PID codes (P8, P12...)
        # -- see E39_CSV_COLUMN_NAMES. Falls back to the raw id for
        # anything unmapped, and (defensively -- shouldn't happen with the
        # current table) if a mapped name would collide with one already
        # used in this exact header, since duplicate CSV column names
        # would silently break header.indexOf()-style lookups downstream.
        used, csv_names = set(), []
        for i in ids:
            name = E39_CSV_COLUMN_NAMES.get(i, i)
            if name in used:
                name = i
            used.add(name)
            csv_names.append(name)
        # Event columns: event, pull_id, event_data for extensible event system
        f.write("time,epoch,event,pull_id,event_data," + ",".join(csv_names) + "\n")
        RECORDER.update(on=True, path=path, file=f, count=0, ids=ids)
        # Reset pull state when starting new recording
        PULL_STATE.update(active=False, counter=0, rpm_history=[])
        PULLS_LOG.clear()
        return path


def record_stop():
    with RECORDER["lock"]:
        if RECORDER["file"]:
            RECORDER["file"].close()
        RECORDER.update(on=False, file=None)
        return {"path": RECORDER["path"], "rows": RECORDER["count"]}


def record_row(values):
    with RECORDER["lock"]:
        if not RECORDER["on"]:
            return

        event = ""
        pull_id = ""
        event_data_obj = {}

        # Check for profile changes
        current_profile = getattr(ADAPTER, "current_profile", None) if ADAPTER else None
        if current_profile and current_profile != EVENT_STATE["prev_profile"]:
            if EVENT_STATE["prev_profile"] is not None:  # Skip first sample
                event = "profile_change"
                event_data_obj = {"profile": current_profile}
            EVENT_STATE["prev_profile"] = current_profile

        # Check for pull transitions (only if no other event)
        if not event:
            transition = detect_pull(values)
            if transition:
                event_type, num = transition
                pull_id = str(num)
                if event_type == "start":
                    event = "pull_start"
                elif event_type == "end":
                    event = "pull_end"

        # Serialize event_data as JSON (empty object if no data)
        event_data = json.dumps(event_data_obj) if event_data_obj else "{}"

        # Write data row with event columns (event, pull_id, event_data)
        t = time.time()
        ts = time.strftime("%H:%M:%S", time.localtime(t)) + f".{int(t % 1 * 1000):03d}"
        row = [ts, f"{t:.3f}", event, pull_id, event_data]
        row += [str(_csv_value(i, values)) for i in RECORDER["ids"]]
        RECORDER["file"].write(",".join(row) + "\n")
        RECORDER["count"] += 1


def connect(proto="auto"):
    global ADAPTER, ADAPTER_ERR
    with CAR_LOCK:
        if ADAPTER:
            ADAPTER.close()
            ADAPTER = None
        order = {"auto": [E39Adapter, E87Adapter],
                 "demo": [DemoAdapter],
                 "e39": [E39Adapter], "e87": [E87Adapter]}[proto]
        errs = []
        for cls in order:
            try:
                a = cls()
            except Exception as e:
                errs.append(f"{cls.proto}: port error {e}")
                continue
            if a.detect():
                ADAPTER = a
                ADAPTER_ERR = ""
                try:    # auto-mint the passport the moment we know the car
                    ovpf_producer.ensure_passport(a.vin)
                except Exception:
                    pass
                return a
            a.close()
            errs.append(f"{cls.proto}: no response")
        ADAPTER_ERR = "; ".join(errs)
        return None


def snapshot_faults(addr, faults):
    with open(os.path.join(DATA, "fault_snapshots.log"), "a") as f:
        f.write(json.dumps({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "protocol": ADAPTER.proto if ADAPTER else "?",
            "addr": f"0x{addr:02X}",
            "faults": faults}) + "\n")


# The server binds to 127.0.0.1 only, but that alone doesn't stop a
# malicious page open in the user's *browser* from reaching it: simple
# cross-origin requests (fetch with Content-Type: text/plain, or a plain
# <form> POST) skip CORS preflight entirely, and _body() parses the JSON
# payload regardless of declared content-type. Without this check, any
# website the user has open while the diag server is running could POST to
# /api/clear, /api/coding/write, /api/actuator/test (physical actuation),
# /api/coding/restore etc. with zero auth. ui.html's api() helper always
# sends this header; a custom header forces a CORS preflight, and this
# server never answers one with permissive CORS headers, so a real browser
# blocks the actual cross-origin request before it's sent. This is not a
# secret (the header name/value is visible in ui.html's source, downloadable
# by anyone) -- it works because it relies on *browser* CORS enforcement,
# not on the value being hidden. It does nothing to stop a local process
# that can already run arbitrary code on this machine -- that's a
# different, larger threat model than "a webpage tricked the browser".
_CLIENT_HEADER = "X-OpenDiag-Client"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _csrf_ok(self):
        # /api/passport/qr is loaded via a plain <img src>, which can never
        # carry a custom header -- exempt it; it's read-only and not
        # sensitive (a QR code encoding a public passport URL).
        # /api/live is opened via EventSource, which likewise can never carry
        # a custom header -- exempt it too. It's GET-only/read-only telemetry;
        # a cross-origin page can trigger the request but, same as the QR
        # endpoint, this server never sends Access-Control-Allow-Origin, so
        # the browser blocks it from reading the stream contents.
        if (not self.path.startswith("/api/")
                or self.path.startswith("/api/passport/qr")
                or self.path == "/api/live"):
            return True
        return self.headers.get(_CLIENT_HEADER) == "1"

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        # Sanity cap -- nothing legitimate here (coding writes, service
        # notes) is anywhere near this size; an unbounded read lets any
        # caller that reaches this port hand it an arbitrarily large
        # Content-Length and inflate memory.
        if n > 10_000_000:
            raise ValueError("request body too large")
        return json.loads(self.rfile.read(n) or b"{}")

    def _raw(self, body, content_type, code=200):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _qs_passport_state(self):
        """?urn= or ?vin= query override for /api/passport(/qr) -- lets the
        UI browse any garage vehicle's read-only passport view, not just the
        connected car. ?urn= is preferred (the vehicle's actual stable
        identity, see ovpf_producer.passport_state_by_urn) since a passport
        opened before its VIN was known can't be found by VIN alone. Falls
        back to the connected car's VIN (or None) when neither is given."""
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        urn = (q.get("urn") or [""])[0].strip()
        if urn:
            st = ovpf_producer.passport_state_by_urn(urn)
            if not st.get("passport"):
                # Nothing local -- e.g. a passport.skoor.ee URL pasted/
                # scanned for a car diagnosed on a different device, or a
                # cloud-only passport this one's never synced. Try pulling
                # it from the cloud before reporting "no passport" (see
                # ovpf_cloud.pull_passport) -- best-effort: offline or an
                # id the provider doesn't have just falls back to the
                # original empty state, same as before this existed.
                try:
                    import ovpf_cloud
                    ovpf_cloud.pull_passport(ovpf_cloud._bare_id(urn))
                    st = ovpf_producer.passport_state_by_urn(urn)
                except Exception:
                    pass
            return st
        vin = (q.get("vin") or [""])[0].strip()
        return ovpf_producer.passport_state(vin or _current_vin())

    def do_GET(self):
        if not self._csrf_ok():
            return self._json({"error": "forbidden"}, 403)
        if self.path.startswith("/api/passport/qr"):
            # Offline QR for the current passport (segno; graceful if absent).
            st = self._qs_passport_state()
            if not st.get("passport"):
                return self._json({"error": "no passport yet"}, 404)
            try:
                import io
                import segno
            except Exception:
                return self._json(
                    {"error": "QR unavailable (install segno)"}, 501)
            payload = _passport_url(st.get("passport_urn"))
            buf = io.BytesIO()
            segno.make(payload, error="m").save(buf, kind="svg", scale=6,
                                                border=2)
            return self._raw(buf.getvalue(), "image/svg+xml")
        if self.path.startswith("/api/passport"):
            # Derived passport state + timeline (replay of the local log).
            # No connection required to view -- see _current_vin(). Optional
            # ?urn=/?vin= lets the UI browse any garage vehicle's passport,
            # not just the connected one -- see _qs_passport_state().
            try:
                st = self._qs_passport_state()
                st["url"] = _passport_url(st.get("passport_urn"))
                return self._json(st)
            except Exception as e:
                return self._json({"error": str(e)}, 500)
        if self.path == "/api/pulls":
            # Finished pulls this session with their peak values -- see
            # detect_pull(). Client polls this right after it sees the live
            # "pull" flag drop, so a multi-pull session keeps every pull's
            # numbers rather than just one running max.
            return self._json({"pulls": PULLS_LOG})
        if self.path.startswith("/api/dyno/runs"):
            # Past dyno curves for a vehicle, read straight from its OVPF
            # passport log (DynoRun events) -- no second index to drift out
            # of sync with the log. ?vin= browses any garage vehicle, same
            # convention as _qs_passport_state(); defaults to the connected
            # car.
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            vin = (q.get("vin") or [""])[0].strip() or _current_vin()
            try:
                path = ovpf_producer._log_path(vin)
                events = ovpf_producer.ovpf_core.load(path)
            except Exception as e:
                return self._json({"error": str(e)}, 500)
            runs = []
            for e in events:
                d = e.get("data", {})
                if e.get("type") != "DynoRun" or not d.get("curveRef"):
                    continue
                runs.append({
                    "id": os.path.basename(d["curveRef"]).removesuffix(".json"),
                    "occurredAt": e.get("occurredAt"),
                    "peaks": {"power_kw": d.get("power", {}).get("value"),
                             "torque_nm": d.get("torque", {}).get("value")},
                    "duration_s": d.get("duration", {}).get("value"),
                    "pullNumber": d.get("pullNumber"),
                    "curveRef": d["curveRef"]})
            return self._json({"vin": vin, "runs": runs})
        if self.path.startswith("/api/dyno/curve/"):
            # A saved curve's full data (bins etc.), for overlay -- see
            # POST /api/dyno/save. Same path-containment check
            # snapshot.load_snapshot already does; the id is client-supplied
            # and must not be trusted as a bare path component.
            import snapshot as _snap
            parsed = urllib.parse.urlsplit(self.path)
            curve_id = parsed.path[len("/api/dyno/curve/"):]
            q = urllib.parse.parse_qs(parsed.query)
            vin = (q.get("vin") or [""])[0].strip() or _current_vin()
            curve_path = os.path.join(
                _snap.BACKUP_ROOT, _snap._safe_vin(vin), "dyno_runs",
                curve_id + ".json")
            real_root = os.path.realpath(_snap.BACKUP_ROOT)
            real_curve = os.path.realpath(curve_path)
            if os.path.commonpath([real_root, real_curve]) != real_root:
                return self._json({"error": "invalid curve id"}, 400)
            try:
                with open(real_curve) as f:
                    return self._json(json.load(f))
            except OSError:
                return self._json({"error": "no such curve"}, 404)
        if self.path.startswith("/api/cloud/session"):
            # Cloud sign-in status + how many local events are queued to
            # push. Optional ?urn=/?vin= (see _qs_passport_state()) reports
            # sync status for a browsed garage vehicle instead of the
            # connected one.
            import ovpf_cloud
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            urn = (q.get("urn") or [""])[0].strip() or None
            vin = (q.get("vin") or [""])[0].strip() or _current_vin()
            return self._json({"user": ovpf_cloud.get_user_session(),
                              "workshop": ovpf_cloud.get_workshop_session(),
                              "sync": ovpf_cloud.sync_status(vin, urn)})
        if self.path.startswith("/api/garage"):
            # Every vehicle this laptop has a passport for, not just
            # whichever one is currently connected -- the workshop's
            # "garage" view. ?include_hidden=1 also returns vehicles
            # removed from the garage (see /api/garage/hide) so the UI
            # can offer to un-hide them.
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            include_hidden = (q.get("include_hidden") or [""])[0] == "1"
            try:
                return self._json({"vehicles": ovpf_producer.list_passports(include_hidden)})
            except Exception as e:
                return self._json({"error": str(e)}, 500)
        # Query-stripped: a deep link like "/?passport=<id>" (see
        # ui.html's openPassportByRef) must still serve the page, not 404 --
        # the query string is read client-side from location.search.
        if urllib.parse.urlsplit(self.path).path in ("/", "/index.html"):
            with open(os.path.join(HERE, "ui.html"), "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/api/state":
            profile = getattr(ADAPTER, "current_profile", None) if ADAPTER else None
            profiles = list(MS41_PROFILES.keys()) if ADAPTER and ADAPTER.proto == "e39" else []
            stats = getattr(ADAPTER, "profile_stats", None) if ADAPTER else None
            vin = getattr(ADAPTER, "vin", None) if ADAPTER else None
            self._json({"connected": ADAPTER is not None,
                        "protocol": ADAPTER.proto if ADAPTER else None,
                        "name": ADAPTER.name if ADAPTER else None,
                        "vin": vin,
                        "channels": ADAPTER.live_channels if ADAPTER else [],
                        "profile": profile,
                        "profiles": profiles,
                        "profile_stats": stats,
                        "error": ADAPTER_ERR})
        elif self.path == "/api/vehicle":
            # Get vehicle information
            if not ADAPTER:
                return self._json({"error": "not connected"}, 400)
            self._json(gather_vehicle_info())
        elif self.path == "/api/report_metadata":
            # Trustworthy facts for anything (a session, a script) writing
            # up a diagnostic report -- app build identity + real vehicle
            # evidence + a live environmental snapshot, so a report is
            # self-describing instead of relying on whoever wrote it to
            # remember/guess which car and which app build it came from.
            self._json({
                "app_version": paths.app_version(),
                "generated_at": now(),
                "vehicle": gather_vehicle_info() if ADAPTER else None,
                "environment": {
                    "sampled_at": LIVE_LAST.get("t"),
                    "values": LIVE_LAST.get("values", {}),
                },
            })


        elif self.path == "/api/backups":
            # List all backups for current VIN
            if not ADAPTER:
                return self._json({"error": "not connected"}, 400)
            tm = get_transaction_manager(backup_root=os.path.join(DATA, "backups"))
            backups = tm.list_backups(ADAPTER.vin)
            self._json({"vin": ADAPTER.vin, "backups": backups})
        elif self.path.startswith("/api/backup/"):
            # Get specific backup by operation_id
            # URL format: /api/backup/{operation_id}
            if not ADAPTER:
                return self._json({"error": "not connected"}, 400)
            operation_id = self.path.split("/api/backup/")[1]
            tm = get_transaction_manager(backup_root=os.path.join(DATA, "backups"))
            backup = tm.get_backup(ADAPTER.vin, operation_id)
            if backup:
                self._json(backup)
            else:
                self._json({"error": "backup not found"}, 404)
        elif self.path.startswith("/api/coding/preview"):
            # Preview what a preset would change (without applying)
            if not ADAPTER:
                return self._json({"error": "not connected"}, 400)
            if ADAPTER.proto != "e39":
                return self._json({"error": "coding only supported on E39 (DS2) currently"}, 400)

            # Parse addr and preset_id from query string
            addr = None
            preset_id = None
            if "?" in self.path:
                for param in self.path.split("?")[1].split("&"):
                    if param.startswith("addr="):
                        addr_str = param.split("=")[1]
                        addr = int(addr_str, 16 if addr_str.startswith("0x") else 10)
                    elif param.startswith("preset_id="):
                        preset_id = param.split("=")[1]

            if addr is None or not preset_id:
                return self._json({"error": "addr and preset_id required"}, 400)

            module_name = ADAPTER.modules.get(addr, f"Module_0x{addr:02X}")
            presets = coding.get_presets_for_module(module_name)

            if preset_id not in presets:
                return self._json({"error": f"preset '{preset_id}' not found"}, 400)

            preset = presets[preset_id]
            decoder = coding.get_coding_decoder(module_name, protocol="ds2")

            if not decoder:
                return self._json({"error": "no decoder available"}, 400)

            with CAR_LOCK:
                # Read current coding
                if isinstance(ADAPTER, DemoAdapter):
                    current_coding = ADAPTER.read_coding(addr)
                else:
                    frame = ADAPTER.ds2.read_coding(addr)
                    if frame is None or frame[2] != 0xA0:
                        return self._json({"error": "failed to read coding"}, 400)
                    current_coding = ds2_diag.body(frame)

                if current_coding is None:
                    return self._json({"error": "no coding data"}, 400)

                # Apply preset to get new coding (without writing)
                new_coding = decoder.apply_preset(current_coding, preset)

                # Decode both to show diff
                before = decoder.decode_coding(current_coding)
                after = decoder.decode_coding(new_coding)

                # Find what changed
                changes = []
                for i, (b_byte, a_byte) in enumerate(zip(before["bytes"], after["bytes"])):
                    if b_byte.get("type") == "bitfield" and a_byte.get("type") == "bitfield":
                        for bit_name in b_byte["bits"]:
                            if b_byte["bits"][bit_name]["value"] != a_byte["bits"][bit_name]["value"]:
                                changes.append({
                                    "field": bit_name,
                                    "before": b_byte["bits"][bit_name]["value"],
                                    "after": a_byte["bits"][bit_name]["value"]
                                })
                    elif b_byte.get("type") == "enum" and a_byte.get("type") == "enum":
                        if b_byte["value"] != a_byte["value"]:
                            changes.append({
                                "field": b_byte["name"],
                                "before": b_byte["value"],
                                "after": a_byte["value"]
                            })

                self._json({
                    "preset": preset,
                    "before": before,
                    "after": after,
                    "changes": changes,
                    "raw_before": current_coding.hex().upper(),
                    "raw_after": new_coding.hex().upper()
                })

        elif self.path.startswith("/api/coding/presets"):
            # Get available presets for a module
            if not ADAPTER:
                return self._json({"error": "not connected"}, 400)
            if ADAPTER.proto != "e39":
                return self._json({"error": "coding only supported on E39 (DS2) currently"}, 400)

            # Parse addr from query string
            addr = None
            if "?" in self.path and "addr=" in self.path:
                addr_str = self.path.split("addr=")[1].split("&")[0]
                addr = int(addr_str, 16 if addr_str.startswith("0x") else 10)

            if addr is None:
                return self._json({"error": "addr parameter required"}, 400)

            module_name = ADAPTER.modules.get(addr, f"Module_0x{addr:02X}")
            presets = coding.get_presets_for_module(module_name)

            self._json({
                "addr": addr,
                "module": module_name,
                "presets": presets
            })

        elif self.path.startswith("/api/coding"):
            # Read coding from module
            if not ADAPTER:
                return self._json({"error": "not connected"}, 400)
            if ADAPTER.proto != "e39":
                return self._json({"error": "coding only supported on E39 (DS2) currently"}, 400)

            # Parse query string for addr
            addr = None
            if "?" in self.path and "addr=" in self.path:
                addr_str = self.path.split("addr=")[1].split("&")[0]
                addr = int(addr_str, 16 if addr_str.startswith("0x") else 10)

            if addr is None:
                return self._json({"error": "addr parameter required"}, 400)

            with CAR_LOCK:
                # Handle demo mode
                if isinstance(ADAPTER, DemoAdapter):
                    coding_data = ADAPTER.read_coding(addr)
                    if coding_data is None:
                        return self._json({"error": "no coding data for this module in demo"}, 400)
                else:
                    # Real car
                    frame = ADAPTER.ds2.read_coding(addr)
                    if frame is None:
                        return self._json({"error": "no response from module"}, 400)

                    if frame[2] != 0xA0:
                        return self._json({"error": f"module returned status 0x{frame[2]:02X}"}, 400)

                    coding_data = ds2_diag.body(frame)

                module_name = ADAPTER.modules.get(addr, f"Module_0x{addr:02X}")

                # Try to decode if we have a decoder for this module
                decoder = coding.get_coding_decoder(module_name, protocol="ds2")
                if decoder:
                    decoded = decoder.decode_coding(coding_data)
                    self._json({
                        "addr": addr,
                        "module": module_name,
                        "raw": coding_data.hex().upper(),
                        "decoded": decoded,
                        "has_decoder": True
                    })
                else:
                    self._json({
                        "addr": addr,
                        "module": module_name,
                        "raw": coding_data.hex().upper(),
                        "has_decoder": False
                    })
        elif self.path == "/api/live":
            self._sse_live()
        elif self.path.startswith("/api/log"):
            since = 0
            if "since=" in self.path:
                since = int(self.path.split("since=")[1])
            self._json([e for e in RAW_LOG if e["seq"] > since])
        # --- Additive analysis endpoints (Agent-2, Phases 5/6/7/11) ---
        # Read-only, operate on saved files; independent of live adapter.
        elif self.path == "/api/recordings/dir":
            # Where drive_log_*.csv actually lands -- surfaced so the UI
            # can tell the user, and so Replay can offer to load from
            # here instead of only an OS file-picker dialog.
            self._json({"path": DATA})
        elif self.path.startswith("/api/recordings/"):
            # Serve one recording's raw content by name, for the Replay
            # tab's server-backed picker -- same DATA dir the recorder
            # writes to (see /api/recordings/dir), basename-only so a
            # crafted name can't escape it via "../".
            name = urllib.parse.unquote(self.path[len("/api/recordings/"):])
            p = os.path.join(DATA, os.path.basename(name))
            if not os.path.isfile(p):
                return self._json({"error": "recording not found"}, 404)
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError as e:
                return self._json({"error": str(e)}, 500)
            self._json({"name": os.path.basename(p), "content": content})
        elif self.path.startswith("/api/recordings"):
            import glob as _glob
            files = sorted(_glob.glob(os.path.join(DATA, "drive_log_*.csv")),
                           reverse=True)
            out = []
            for p in files:
                try:
                    rows = sum(1 for _ in open(p)) - 1
                except OSError:
                    rows = 0
                out.append({"name": os.path.basename(p), "rows": rows})
            self._json(out)
        elif self.path.startswith("/api/snapshot/"):
            # Single snapshot's full detail (modules/faults/coding) for the
            # "Snapshots" list's click-through -- /api/snapshots above only
            # returns the summary row. Look the id up via list_snapshots()
            # rather than trusting a client-supplied path directly, so this
            # can't be pointed outside BACKUP_ROOT.
            import snapshot as _snap
            snap_id = urllib.parse.unquote(
                self.path[len("/api/snapshot/"):]).split("?")[0]
            vin = None
            if "vin=" in self.path:
                vin = self.path.split("vin=")[1].split("&")[0]
            match = next((s for s in _snap.list_snapshots(vin)
                         if s["id"] == snap_id), None)
            if not match:
                return self._json({"error": "snapshot not found"}, 404)
            try:
                data = _snap.load_snapshot(match["dir"])
            except (OSError, ValueError) as e:
                return self._json({"error": str(e)}, 500)
            data["id"] = snap_id
            self._json(data)
        elif self.path.startswith("/api/snapshots"):
            import snapshot as _snap
            vin = None
            if "vin=" in self.path:
                vin = self.path.split("vin=")[1].split("&")[0]
            self._json(_snap.list_snapshots(vin))
        elif self.path.startswith("/api/profiles"):
            import vehicle_profiles as _vp
            self._json(_vp.list_profiles())
        elif self.path.startswith("/api/actuators"):
            import actuators as _act
            self._json({"tests": _act.list_tests(),
                        "maintenance": _act.list_maintenance()})
        elif self.path.startswith("/api/adaptations"):
            import adaptations as _ad
            self._json({"groups": list(_ad.ADAPTATION_GROUPS),
                        "erase_confirmed": _ad.ERASE_OPCODE is not None})
        elif self.path.startswith("/api/engine"):
            # Detected engine/DME for the connected car + supported list.
            import dme_registry
            info = ADAPTER.engine_info() if (ADAPTER and hasattr(
                ADAPTER, "engine_info")) else None
            if ADAPTER and info:
                try:    # let the passport 'learn' the car (VehicleIdentified)
                    ovpf_producer.record_vehicle_identified(ADAPTER.vin, {
                        "vin": ADAPTER.vin,
                        "engine": info.get("engine"),
                        "dme": info.get("dme")}, operator=_current_operator())
                    _auto_push(ADAPTER.vin)
                except Exception:
                    pass
            self._json({"detected": info,
                        "supported": dme_registry.all_engines()})
        elif self.path.startswith("/api/operations/summary"):
            import operations as _ops
            try:
                self._json(_ops.OperationDB.load().summary())
            except OSError:
                self._json({"error": "operations.json not built"}, 404)
        elif self.path.startswith("/api/operations"):
            # Protocol Explorer: the operation database with evidence grades.
            import operations as _ops
            ecu = None
            if "ecu=" in self.path:
                ecu = self.path.split("ecu=")[1].split("&")[0]
            try:
                db = _ops.OperationDB.load()
            except OSError:
                return self._json({"error": "operations.json not built"}, 404)
            out = []
            for o in db.all(ecu=ecu):
                out.append({"ecu": o["ecu"], "name": o["name"],
                            "kind": o["kind"], "sgbd_job": o.get("sgbd_job"),
                            "description": o.get("description", ""),
                            "grade": _ops.evidence_grade(o),
                            "car_usable": _ops.usable_on_car(o),
                            "evidence": o["evidence"]})
            self._json({"ecus": db.ecus(), "operations": out})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._csrf_ok():
            return self._json({"error": "forbidden"}, 403)
        try:
            if self.path == "/api/connect":
                proto = self._body().get("protocol", "auto")
                a = connect(proto)
                profile = getattr(a, "current_profile", None) if a else None
                profiles = list(MS41_PROFILES.keys()) if a and a.proto == "e39" else []
                stats = getattr(a, "profile_stats", None) if a else None
                self._json({"connected": a is not None,
                            "protocol": a.proto if a else None,
                            "name": a.name if a else None,
                            "channels": a.live_channels if a else [],
                            "profile": profile,
                            "profiles": profiles,
                            "profile_stats": stats,
                            "error": ADAPTER_ERR})
            elif self.path == "/api/scan":
                if not ADAPTER:
                    return self._json({"error": "not connected"}, 400)
                with CAR_LOCK:
                    self._json({"modules": ADAPTER.scan()})
            elif self.path == "/api/faults":
                addr = int(self._body()["addr"])
                with CAR_LOCK:
                    res = ADAPTER.faults(addr)
                try:    # append an OVPF DiagnosticTroubleCodeRead event
                    ovpf_producer.record_faults(
                        ADAPTER.vin, addr,
                        ADAPTER.modules.get(addr, f"0x{addr:02X}"), res,
                        operator=_current_operator())
                    _auto_push(ADAPTER.vin)
                except Exception:
                    pass
                self._json(res)
            elif self.path == "/api/clear":
                b = self._body()
                addr = int(b["addr"])
                if not b.get("confirm"):
                    return self._json({"error": "confirm required"}, 400)

                # Use transaction layer for safe fault clear with backup
                tm = get_transaction_manager(backup_root=os.path.join(DATA, "backups"))
                module_name = ADAPTER.modules.get(addr, f"Module_0x{addr:02X}")

                with CAR_LOCK:
                    result = tm.execute(
                        vin=ADAPTER.vin,
                        module_name=module_name,
                        module_addr=addr,
                        operation="clear_faults",
                        read_fn=lambda: ADAPTER.faults(addr),
                        write_fn=lambda: ADAPTER.clear(addr),
                        verify_fn=lambda: ADAPTER.faults(addr).get("count", 0) == 0,
                        user_note=b.get("note", "")
                    )

                    # Keep old snapshot log for backwards compatibility
                    if result["success"]:
                        snapshot_faults(addr, result.get("write_result", {}))
                        try:    # append an OVPF DiagnosticTroubleCodeCleared
                            ovpf_producer.record_clear(
                                ADAPTER.vin, addr, module_name,
                                operator=_current_operator())
                            _auto_push(ADAPTER.vin)
                        except Exception:
                            pass

                    self._json(result)
            elif self.path == "/api/restore":
                # Restore from backup with verification
                b = self._body()
                operation_id = b.get("operation_id")
                if not operation_id:
                    return self._json({"error": "operation_id required"}, 400)
                if not b.get("confirm"):
                    return self._json({"error": "confirm required"}, 400)

                tm = get_transaction_manager(backup_root=os.path.join(DATA, "backups"))

                # Load the backup
                backup = tm.get_backup(ADAPTER.vin, operation_id)
                if not backup:
                    return self._json({"error": "backup not found"}, 404)

                meta = backup["metadata"]
                modules = meta.get("modules", {})

                if not modules:
                    return self._json({"error": "no modules in backup"}, 400)

                # For now, only support restoring single module
                module_name = list(modules.keys())[0]
                module_info = modules[module_name]
                addr = module_info["addr"]
                backup_data = backup["data"][module_name]

                # Restore is essentially a write operation, so use transaction layer
                # Note: This is a placeholder - actual restore depends on operation type
                # For fault memory, we can't really "restore" faults, but for coding/adaptations
                # we would write the old values back

                with CAR_LOCK:
                    if meta["operation"] == "clear_faults":
                        # Can't restore faults that were cleared
                        return self._json({
                            "error": "Cannot restore cleared faults - they must naturally return if cause is present"
                        }, 400)
                    else:
                        # Generic restore (for future coding/adaptations)
                        return self._json({
                            "error": "Restore not yet implemented for this operation type"
                        }, 400)
            elif self.path == "/api/coding/apply":
                # Apply a coding preset with transaction layer backup
                b = self._body()
                addr = b.get("addr")
                preset_id = b.get("preset_id")

                if addr is None:
                    return self._json({"error": "addr required"}, 400)
                if not preset_id:
                    return self._json({"error": "preset_id required"}, 400)
                if not b.get("confirm"):
                    return self._json({"error": "confirm required"}, 400)

                if not ADAPTER:
                    return self._json({"error": "not connected"}, 400)
                if ADAPTER.proto != "e39":
                    return self._json({"error": "coding only supported on E39 (DS2) currently"}, 400)

                addr = int(addr)
                module_name = ADAPTER.modules.get(addr, f"Module_0x{addr:02X}")

                # Get the preset
                presets = coding.get_presets_for_module(module_name)
                if preset_id not in presets:
                    return self._json({"error": f"preset '{preset_id}' not found for module"}, 400)

                preset = presets[preset_id]

                # Get decoder
                decoder = coding.get_coding_decoder(module_name, protocol="ds2")
                if not decoder:
                    return self._json({"error": "no coding decoder available for this module"}, 400)

                # Read current coding, apply preset, write with transaction layer
                def read_coding_fn():
                    with CAR_LOCK:
                        if isinstance(ADAPTER, DemoAdapter):
                            return ADAPTER.read_coding(addr)
                        else:
                            frame = ADAPTER.ds2.read_coding(addr)
                            if frame is None or frame[2] != 0xA0:
                                raise Exception("Failed to read current coding")
                            return ds2_diag.body(frame)

                def write_coding_fn(new_coding):
                    with CAR_LOCK:
                        if isinstance(ADAPTER, DemoAdapter):
                            # Update demo adapter's coding
                            ADAPTER.DEMO_CODING[addr] = new_coding
                            return {"status": "ok (demo)"}
                        else:
                            frame = ADAPTER.ds2.write_coding(addr, new_coding)
                            if frame is None or frame[2] != 0xA0:
                                raise Exception(f"Write failed: status {frame[2]:02X}" if frame else "no response")
                            return {"status": f"0x{frame[2]:02X}"}

                def verify_coding_fn(expected_coding):
                    with CAR_LOCK:
                        if isinstance(ADAPTER, DemoAdapter):
                            readback = ADAPTER.read_coding(addr)
                        else:
                            frame = ADAPTER.ds2.read_coding(addr)
                            if frame is None or frame[2] != 0xA0:
                                return False
                            readback = ds2_diag.body(frame)
                        return readback == expected_coding

                try:
                    # Read current coding
                    current_coding = read_coding_fn()

                    # Apply preset to get new coding
                    new_coding = decoder.apply_preset(current_coding, preset)

                    # Use transaction manager for safe write
                    tm = get_transaction_manager(backup_root=os.path.join(DATA, "backups"))

                    # Create serializable backup data
                    def read_for_backup():
                        return {
                            "raw_hex": current_coding.hex(),
                            "decoded": decoder.decode_coding(current_coding)
                        }

                    result = tm.execute(
                        vin=ADAPTER.vin,
                        module_name=module_name,
                        module_addr=addr,
                        operation=f"coding_preset_{preset_id}",
                        read_fn=read_for_backup,
                        write_fn=lambda: write_coding_fn(new_coding),
                        verify_fn=lambda: verify_coding_fn(new_coding),
                        user_note=f"Applied preset: {preset['name']}"
                    )

                    # Add before/after coding to result
                    result["before"] = decoder.decode_coding(current_coding)
                    result["after"] = decoder.decode_coding(new_coding)

                    if result.get("success"):
                        try:    # append an OVPF EcuCodingChanged event
                            ovpf_producer.record_coding_change(
                                ADAPTER.vin, addr, module_name,
                                current_coding.hex(), new_coding.hex(),
                                preset=preset_id, operator=_current_operator())
                            _auto_push(ADAPTER.vin)
                        except Exception:
                            pass

                    self._json(result)

                except Exception as e:
                    self._json({"error": str(e)}, 500)

            elif self.path == "/api/coding/write":
                # Manual coding write with transaction layer
                b = self._body()
                addr = b.get("addr")
                coding_hex = b.get("coding_hex")

                if addr is None:
                    return self._json({"error": "addr required"}, 400)
                if not coding_hex:
                    return self._json({"error": "coding_hex required"}, 400)
                if not b.get("confirm"):
                    return self._json({"error": "confirm required"}, 400)

                if not ADAPTER:
                    return self._json({"error": "not connected"}, 400)
                if ADAPTER.proto != "e39":
                    return self._json({"error": "coding only supported on E39 (DS2) currently"}, 400)

                addr = int(addr)
                module_name = ADAPTER.modules.get(addr, f"Module_0x{addr:02X}")

                # Parse hex string to bytes
                try:
                    new_coding = bytes.fromhex(coding_hex)
                except ValueError:
                    return self._json({"error": "invalid hex string"}, 400)

                # Get decoder
                decoder = coding.get_coding_decoder(module_name, protocol="ds2")
                if not decoder:
                    return self._json({"error": "no coding decoder available for this module"}, 400)

                # Read current coding, write new coding with transaction layer
                def read_coding_fn():
                    with CAR_LOCK:
                        if isinstance(ADAPTER, DemoAdapter):
                            return ADAPTER.read_coding(addr)
                        else:
                            frame = ADAPTER.ds2.read_coding(addr)
                            if frame is None or frame[2] != 0xA0:
                                raise Exception("Failed to read current coding")
                            return ds2_diag.body(frame)

                def write_coding_fn(coding_bytes):
                    with CAR_LOCK:
                        if isinstance(ADAPTER, DemoAdapter):
                            ADAPTER.DEMO_CODING[addr] = coding_bytes
                            return {"status": "ok (demo)"}
                        else:
                            frame = ADAPTER.ds2.write_coding(addr, coding_bytes)
                            if frame is None or frame[2] != 0xA0:
                                raise Exception(f"Write failed: status {frame[2]:02X}" if frame else "no response")
                            return {"status": f"0x{frame[2]:02X}"}

                def verify_coding_fn(expected_coding):
                    with CAR_LOCK:
                        if isinstance(ADAPTER, DemoAdapter):
                            readback = ADAPTER.read_coding(addr)
                        else:
                            frame = ADAPTER.ds2.read_coding(addr)
                            if frame is None or frame[2] != 0xA0:
                                return False
                            readback = ds2_diag.body(frame)
                        return readback == expected_coding

                try:
                    # Read current coding
                    current_coding = read_coding_fn()

                    # Create serializable backup data
                    def read_for_backup():
                        return {
                            "raw_hex": current_coding.hex(),
                            "decoded": decoder.decode_coding(current_coding)
                        }

                    # Use transaction manager for safe write
                    tm = get_transaction_manager(backup_root=os.path.join(DATA, "backups"))

                    result = tm.execute(
                        vin=ADAPTER.vin,
                        module_name=module_name,
                        module_addr=addr,
                        operation="coding_manual_edit",
                        read_fn=read_for_backup,
                        write_fn=lambda: write_coding_fn(new_coding),
                        verify_fn=lambda: verify_coding_fn(new_coding),
                        user_note=b.get("user_note", "Manual coding edit")
                    )

                    # Add before/after coding to result
                    result["before"] = decoder.decode_coding(current_coding)
                    result["after"] = decoder.decode_coding(new_coding)

                    if result.get("success"):
                        try:    # append an OVPF EcuCodingChanged event
                            ovpf_producer.record_coding_change(
                                ADAPTER.vin, addr, module_name,
                                current_coding.hex(), new_coding.hex(),
                                operator=_current_operator())
                            _auto_push(ADAPTER.vin)
                        except Exception:
                            pass

                    self._json(result)

                except Exception as e:
                    self._json({"error": str(e)}, 500)

            elif self.path == "/api/coding/restore":
                # Restore coding from a backup
                b = self._body()
                operation_id = b.get("operation_id")
                module_name = b.get("module_name")

                if not operation_id or not module_name:
                    return self._json({"error": "operation_id and module_name required"}, 400)
                if not b.get("confirm"):
                    return self._json({"error": "confirm required"}, 400)

                if not ADAPTER:
                    return self._json({"error": "not connected"}, 400)
                if ADAPTER.proto != "e39":
                    return self._json({"error": "coding only supported on E39 (DS2) currently"}, 400)

                tm = get_transaction_manager(backup_root=os.path.join(DATA, "backups"))

                # Load the backup
                backup = tm.get_backup(ADAPTER.vin, operation_id)
                if not backup:
                    return self._json({"error": "backup not found"}, 404)

                if module_name not in backup["data"]:
                    return self._json({"error": f"module '{module_name}' not in backup"}, 400)

                backup_data = backup["data"][module_name]
                if "raw_hex" not in backup_data:
                    return self._json({"error": "backup does not contain coding data"}, 400)

                # Parse module address from backup metadata
                module_info = backup["metadata"]["modules"][module_name]
                addr = module_info["addr"]

                # Get the old coding bytes to restore
                old_coding = bytes.fromhex(backup_data["raw_hex"])

                # Get decoder for this module
                decoder = coding.get_coding_decoder(module_name, protocol="ds2")
                if not decoder:
                    return self._json({"error": "no decoder available for this module"}, 400)

                # Define read/write/verify functions
                def read_coding_fn():
                    with CAR_LOCK:
                        if isinstance(ADAPTER, DemoAdapter):
                            return ADAPTER.read_coding(addr)
                        else:
                            frame = ADAPTER.ds2.read_coding(addr)
                            if frame is None or frame[2] != 0xA0:
                                raise Exception("Failed to read current coding")
                            return ds2_diag.body(frame)

                def write_coding_fn(coding_bytes):
                    with CAR_LOCK:
                        if isinstance(ADAPTER, DemoAdapter):
                            ADAPTER.DEMO_CODING[addr] = coding_bytes
                            return {"status": "ok (demo)"}
                        else:
                            frame = ADAPTER.ds2.write_coding(addr, coding_bytes)
                            if frame is None or frame[2] != 0xA0:
                                raise Exception(f"Write failed: status {frame[2]:02X}" if frame else "no response")
                            return {"status": f"0x{frame[2]:02X}"}

                def verify_coding_fn(expected_coding):
                    with CAR_LOCK:
                        if isinstance(ADAPTER, DemoAdapter):
                            readback = ADAPTER.read_coding(addr)
                        else:
                            frame = ADAPTER.ds2.read_coding(addr)
                            if frame is None or frame[2] != 0xA0:
                                return False
                            readback = ds2_diag.body(frame)
                        return readback == expected_coding

                try:
                    # Read current coding before restore
                    current_coding = read_coding_fn()

                    # Create serializable backup data
                    def read_for_backup():
                        return {
                            "raw_hex": current_coding.hex(),
                            "decoded": decoder.decode_coding(current_coding)
                        }

                    # Use transaction manager for safe restore
                    result = tm.execute(
                        vin=ADAPTER.vin,
                        module_name=module_name,
                        module_addr=addr,
                        operation="coding_restore",
                        read_fn=read_for_backup,
                        write_fn=lambda: write_coding_fn(old_coding),
                        verify_fn=lambda: verify_coding_fn(old_coding),
                        user_note=f"Restored from backup: {operation_id}"
                    )

                    # Add before/after coding to result
                    result["before"] = decoder.decode_coding(current_coding)
                    result["after"] = decoder.decode_coding(old_coding)
                    result["restored_from"] = operation_id

                    if result.get("success"):
                        try:    # append an OVPF EcuCodingChanged (restore)
                            ovpf_producer.record_coding_change(
                                ADAPTER.vin, addr, module_name,
                                current_coding.hex(), old_coding.hex(),
                                preset=f"restore:{operation_id}", operator=_current_operator())
                            _auto_push(ADAPTER.vin)
                        except Exception:
                            pass

                    self._json(result)

                except Exception as e:
                    self._json({"error": str(e)}, 500)

            elif self.path == "/api/sia-reset":
                b = self._body()
                if not b.get("confirm"):
                    return self._json({"error": "confirm required"}, 400)
                if not hasattr(ADAPTER, "sia_reset"):
                    return self._json(
                        {"error": "SIA reset only available on the E39"}, 400)
                with CAR_LOCK:
                    self._json(ADAPTER.sia_reset(int(b.get("kind", 1))))
            elif self.path == "/api/record":
                if self._body().get("on"):
                    self._json({"on": True, "path": record_start()})
                else:
                    r = record_stop()
                    self._json({"on": False, **r})
            elif self.path == "/api/profile":
                if not ADAPTER:
                    return self._json({"error": "not connected"}, 400)
                if not hasattr(ADAPTER, "set_profile"):
                    return self._json(
                        {"error": "profile switching only available on E39"}, 400)
                b = self._body()
                profile = b.get("profile")
                if not profile:
                    return self._json({"error": "profile name required"}, 400)
                if RECORDER["on"]:
                    return self._json(
                        {"error": "cannot change profile while recording"}, 400)
                with CAR_LOCK:
                    result = ADAPTER.set_profile(profile)
                self._json(result)
            # --- Additive analysis endpoints (Agent-2, Phases 5/6/7) ---
            elif self.path == "/api/correlate":
                import correlate as _corr
                b = self._body()
                p = os.path.join(DATA, os.path.basename(b.get("recording", "")))
                if not os.path.isfile(p):
                    return self._json({"error": "recording not found"}, 400)
                try:
                    self._json({"target": b.get("target"),
                                "results": _corr.correlate_channels(
                                    p, b.get("target"), top=b.get("top"))})
                except KeyError as e:
                    self._json({"error": str(e)}, 400)
            elif self.path == "/api/snapshot/create":
                if not ADAPTER:
                    return self._json({"error": "not connected"}, 400)
                import snapshot as _snap
                b = self._body()
                with CAR_LOCK:
                    snap = _snap.create_snapshot(
                        ADAPTER, vin=getattr(ADAPTER, "vin", None),
                        description=b.get("description", ""))
                snap.pop("_dir", None)
                self._json({"ok": True, "snapshot": snap})
            elif self.path == "/api/snapshot/diff":
                import snapshot as _snap
                b = self._body()
                try:
                    self._json(_snap.diff_snapshots(b["a"], b["b"]))
                except (KeyError, OSError, ValueError) as e:
                    self._json({"error": str(e)}, 400)
            elif self.path == "/api/ram/read":
                # Read-only RAM explorer (Phase 7.1). E39/MS41 only.
                b = self._body()
                if not ADAPTER or getattr(ADAPTER, "proto", None) != "e39":
                    return self._json({"error": "requires E39 (DS2) connection"}, 400)
                ds2 = getattr(ADAPTER, "ds2", None)
                width = int(b.get("width", 1))
                with CAR_LOCK:
                    if ds2 is None and hasattr(ADAPTER, "demo_ram_dump"):
                        # demo: simulated RAM so the explorer flow is usable
                        r = ADAPTER.demo_ram_dump(
                            int(b.get("start", 0xDA28)), int(b.get("count", 16)))
                    elif ds2 is None:
                        return self._json({"error": "no DS2 handle"}, 400)
                    elif "start" in b:
                        r = ds2_diag.ram_dump_range(
                            ds2, int(b["start"]), int(b.get("count", 16)), width)
                    else:
                        r = ds2_diag.ram_read(ds2, b.get("addresses", []), width)
                if r is None:
                    return self._json({"error": "no response from DME"}, 502)
                self._json({"values": {f"0x{a:04X}": v for a, v in r.items()}})
            elif self.path == "/api/ram/diff":
                # Offline (Phase 7.3): diff two RAM dumps {hexaddr: value}.
                b = self._body()
                def _parse(d):
                    return {int(k, 16) if isinstance(k, str) else k: v
                            for k, v in (d or {}).items()}
                self._json(ds2_diag.ram_diff(_parse(b.get("a")),
                                             _parse(b.get("b")),
                                             int(b.get("min_delta", 1))))
            elif self.path == "/api/adaptations/reset":
                # Phase 2. Real-car write is GATED (unconfirmed opcode);
                # demo runs the full transaction flow.
                import adaptations as _ad
                b = self._body()
                if not ADAPTER:
                    return self._json({"error": "not connected"}, 400)
                if not b.get("confirm"):
                    return self._json({"error": "confirm required"}, 400)
                with CAR_LOCK:
                    self._json(_ad.reset_adaptations(
                        ADAPTER, b.get("groups", []),
                        user_note=b.get("note", "")))
            elif self.path == "/api/actuator/test":
                # Phase 3. Gated on real car; simulated in demo.
                import actuators as _act
                b = self._body()
                if not ADAPTER:
                    return self._json({"error": "not connected"}, 400)
                with CAR_LOCK:
                    self._json(_act.run_actuator_test(
                        ADAPTER, b.get("test"), confirm=b.get("confirm")))
            elif self.path == "/api/dev/raw":
                # Phase 8. Read-only-whitelisted raw request console.
                import dev_console as _dc
                b = self._body()
                if not ADAPTER:
                    return self._json({"error": "not connected"}, 400)
                with CAR_LOCK:
                    self._json(_dc.send_raw(
                        ADAPTER, b.get("payload", []),
                        addr=int(b.get("addr", 0x12))))
            elif self.path == "/api/trace/parse":
                # Protocol Explorer: parse a K-line trace file (offline).
                import trace as _tr
                b = self._body()
                p = os.path.join(DATA, os.path.basename(b.get("file", "")))
                if not os.path.isfile(p):
                    return self._json({"error": "trace file not found"}, 400)
                frames = _tr.parse_trace(p)
                self._json({"frames": len(frames),
                            "requests": _tr.extract_requests(frames),
                            "replay": _tr.replay_plan(frames)})
            elif self.path == "/api/trace/diff":
                # Diff two traces to find OEM-only operations (offline).
                import trace as _tr
                b = self._body()
                pa = os.path.join(DATA, os.path.basename(b.get("a", "")))
                pb = os.path.join(DATA, os.path.basename(b.get("b", "")))
                if not (os.path.isfile(pa) and os.path.isfile(pb)):
                    return self._json({"error": "trace file not found"}, 400)
                self._json(_tr.trace_diff(_tr.parse_trace(pa),
                                          _tr.parse_trace(pb)))
            elif self.path == "/api/passport/service":
                # Manual maintenance fact, not diagnostic-derived (an oil
                # change, a part swap) -- the one gap ovpf_producer had:
                # everything else was ECU-observed, this is a person saying
                # "this happened." No connection required -- see
                # _current_vin().
                b = self._body()
                if not b.get("serviceType"):
                    return self._json({"error": "serviceType required"}, 400)
                ev = ovpf_producer.record_service(
                    _current_vin(), b["serviceType"],
                    odometer=b.get("odometer"),
                    odometer_unit=b.get("odometerUnit", "KMT"),
                    price=b.get("price"), currency=b.get("currency"),
                    notes=b.get("notes"), operator=_current_operator())
                _auto_push(_current_vin())
                self._json(ev)
            elif self.path == "/api/passport/create":
                # Mint a passport with no live connection -- anonymous-first:
                # "create = mint UUID -> QR -> sticker -> done." VIN is added
                # as data later (a real connection, or edited by hand), never
                # required up front.
                path, urn = ovpf_producer.ensure_passport(_current_vin())
                self._json(ovpf_producer.passport_state(_current_vin()))
            elif self.path == "/api/passport/identify":
                # Attach vehicle facts (VIN, make/model/year/engine, nickname)
                # to a passport that was created without them. Appends
                # VehicleIdentified -- reduce() merges it into state.vehicle,
                # the PassportOpened genesis event is never touched. Same
                # "person is asserting this" contract as /service: no
                # connection required, see _current_vin(). The nickname is
                # part of this permanent, hash-chained, cloud-synced fact
                # set -- there's no separate local-only label.
                b = self._body()
                facts = {k: b[k] for k in ("nickname", "vin", "make", "model", "modelYear", "engine")
                          if b.get(k)}
                if not facts:
                    return self._json({"error": "at least one vehicle fact required"}, 400)
                ev = ovpf_producer.record_vehicle_identified(
                    _current_vin(), facts, operator=_current_operator())
                _auto_push(_current_vin())
                self._json(ev or {"note": "unchanged -- same facts already recorded"})
            elif self.path == "/api/garage/identify":
                # Same as /api/passport/identify, but for a garage vehicle
                # that isn't the one currently connected -- keyed by urn
                # since it may not have a VIN yet (see
                # ovpf_producer.record_vehicle_identified_by_urn).
                b = self._body()
                urn = (b.get("urn") or "").strip()
                if not urn:
                    return self._json({"error": "urn required"}, 400)
                facts = {k: b[k] for k in ("nickname", "vin", "make", "model", "modelYear", "engine")
                          if b.get(k)}
                if not facts:
                    return self._json({"error": "at least one vehicle fact required"}, 400)
                ev = ovpf_producer.record_vehicle_identified_by_urn(
                    urn, facts, operator=_current_operator())
                _auto_push(None, urn=urn)
                self._json(ev or {"note": "unchanged -- same facts already recorded"})
            elif self.path == "/api/garage/hide":
                # "Remove from garage" -- a hide, not a delete (see
                # ovpf_producer.set_vehicle_hidden). Reversible via the
                # same endpoint with hidden=false.
                b = self._body()
                urn = (b.get("urn") or "").strip()
                if not urn:
                    return self._json({"error": "urn required"}, 400)
                hidden = bool(b.get("hidden", True))
                self._json({"urn": urn, "hidden": ovpf_producer.set_vehicle_hidden(urn, hidden)})
            elif self.path == "/api/cloud/otp/request":
                # Personal cloud identity -- any email, OTP-verified,
                # satisfies the provider's write gate (no pre-existing
                # account needed). See ovpf_cloud.py.
                import ovpf_cloud
                b = self._body()
                email = (b.get("email") or "").strip()
                if not email:
                    return self._json({"error": "email required"}, 400)
                try:
                    self._json(ovpf_cloud.request_otp(email))
                except ovpf_cloud.CloudError as e:
                    self._json({"error": str(e)}, 400)
            elif self.path == "/api/cloud/otp/verify":
                import ovpf_cloud
                b = self._body()
                email = (b.get("email") or "").strip()
                code = (b.get("code") or "").strip()
                if not (email and code):
                    return self._json({"error": "email and code required"}, 400)
                try:
                    ovpf_cloud.verify_otp(email, code)
                    self._json({"user": ovpf_cloud.get_user_session()})
                except ovpf_cloud.CloudError as e:
                    self._json({"error": str(e)}, 400)
            elif self.path == "/api/cloud/signout":
                import ovpf_cloud
                ovpf_cloud.clear_user_session()
                self._json({"user": None})
            elif self.path == "/api/cloud/workshop/verify":
                # DNS verification check for a workshop domain -- no auth,
                # this only reads DNS, doesn't grant anything.
                import ovpf_cloud
                b = self._body()
                domain = (b.get("domain") or "").strip()
                if not domain:
                    return self._json({"error": "domain required"}, 400)
                try:
                    self._json(ovpf_cloud.check_workshop_verified(domain))
                except ovpf_cloud.CloudError as e:
                    self._json({"error": str(e)}, 400)
            elif self.path == "/api/cloud/workshop/otp/request":
                import ovpf_cloud
                b = self._body()
                domain = (b.get("domain") or "").strip()
                email = (b.get("email") or "").strip()
                if not (domain and email):
                    return self._json({"error": "domain and email required"}, 400)
                try:
                    self._json(ovpf_cloud.request_workshop_otp(domain, email))
                except ovpf_cloud.CloudError as e:
                    self._json({"error": str(e)}, 400)
            elif self.path == "/api/cloud/workshop/otp/verify":
                import ovpf_cloud
                b = self._body()
                domain = (b.get("domain") or "").strip()
                email = (b.get("email") or "").strip()
                code = (b.get("code") or "").strip()
                if not (domain and email and code):
                    return self._json(
                        {"error": "domain, email and code required"}, 400)
                try:
                    ovpf_cloud.verify_workshop_otp(domain, email, code)
                    self._json({"workshop": ovpf_cloud.get_workshop_session()})
                except ovpf_cloud.CloudError as e:
                    self._json({"error": str(e)}, 400)
            elif self.path == "/api/cloud/workshop/signout":
                import ovpf_cloud
                ovpf_cloud.clear_workshop_session()
                self._json({"workshop": None})
            elif self.path == "/api/cloud/push":
                # Push the current (or an explicitly named, for the garage/
                # passport-browsing view) VIN's local passport events to the
                # cloud provider. Optional urn resolves a passport opened
                # before its VIN was known -- see ovpf_cloud.push_passport.
                import ovpf_cloud
                b = self._body()
                vin = (b.get("vin") or "").strip() or _current_vin()
                urn = (b.get("urn") or "").strip() or None
                try:
                    self._json(ovpf_cloud.push_passport(vin, urn))
                except ovpf_cloud.CloudError as e:
                    self._json({"error": str(e)}, 400)
            elif self.path == "/api/cloud/pull":
                # Merge in any events that exist on the cloud provider but
                # not locally -- the counterpart to push, for edits made
                # independently on the cloud side (e.g. a nickname changed
                # via the passport.skoor.ee web viewer, which writes
                # straight to the provider and never reaches this device
                # any other way). See ovpf_cloud.pull_and_merge_passport.
                import ovpf_cloud
                b = self._body()
                vin = (b.get("vin") or "").strip() or _current_vin()
                urn = (b.get("urn") or "").strip() or None
                try:
                    self._json(ovpf_cloud.pull_and_merge_passport(vin, urn))
                except ovpf_cloud.CloudError as e:
                    self._json({"error": str(e)}, 400)
            elif self.path == "/api/dyno/save":
                # Persist a curve computed client-side (ui.html's
                # computeDynoCurve -- see its comment for why this is the
                # one write path for a DynoRun event now, not
                # detect_pull()). Body: {vin?, curve: {...}, note?,
                # corrects?}. curve is the full shape computeDynoCurve
                # returns (bins, peaks, correction, window, ...); this
                # endpoint just adds an id, writes it to disk, and records
                # the summary event. corrects is an earlier DynoRun event id
                # to supersede (see ovpf_producer.record_dyno_run) -- e.g.
                # re-generating a pull from Replay after a fix to the power
                # estimate formula, so the stale reading drops out of the
                # timeline instead of sitting there contradicting the new one.
                import snapshot as _snap
                b = self._body()
                vin = (b.get("vin") or "").strip() or _current_vin()
                curve = b.get("curve")
                if not curve or not curve.get("bins"):
                    return self._json({"error": "curve with bins required"}, 400)
                curve_id = str(uuid.uuid4())
                vdir = os.path.join(_snap.BACKUP_ROOT, _snap._safe_vin(vin),
                                    "dyno_runs")
                os.makedirs(vdir, exist_ok=True)
                curve["id"] = curve_id
                curve["vin"] = vin
                curve["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                if b.get("note"):
                    curve["note"] = b["note"]
                with open(os.path.join(vdir, curve_id + ".json"), "w") as f:
                    json.dump(curve, f)
                pk = curve.get("peaks", {})
                # conditions (peak airflow/rpm/throttle/load, mean IAT --
                # see ui.html's computeDynoCurve) are often just as
                # diagnostically useful as the power estimate itself, so
                # they ride along in the same event under peaks/conditions
                # (record_dyno_run puts anything besides power_kw/torque_nm
                # under data.conditions).
                peaks_payload = {
                    "power_kw": pk.get("power_kw_corrected") if pk.get("power_kw_corrected") is not None else pk.get("power_kw"),
                    "torque_nm": pk.get("torque_nm_corrected") if pk.get("torque_nm_corrected") is not None else pk.get("torque_nm"),
                }
                peaks_payload.update({k: v for k, v in curve.get("conditions", {}).items()
                                       if v is not None})
                try:
                    ovpf_producer.record_dyno_run(
                        vin,
                        peaks_payload,
                        duration_s=(curve.get("window", {}).get("t_end", 0)
                                   - curve.get("window", {}).get("t_start", 0)) or None,
                        num=curve.get("pull_num"),
                        curve_ref=f"dyno_runs/{curve_id}.json",
                        operator=_current_operator(),
                        corrects=b.get("corrects"))
                    _auto_push(vin)
                except Exception:
                    pass
                self._json({"id": curve_id, "curveRef": f"dyno_runs/{curve_id}.json"})
            elif self.path == "/api/dyno/export-pdf":
                # The packaged app's window is a native WebView (pywebview
                # -> WKWebView on macOS), not a real browser -- it has no
                # downloads UI, so <a download> on a blob: URL just
                # navigates the whole app window to render the PDF inline
                # with no way back except quitting. Sidestep that entirely:
                # the client sends the already-built PDF bytes here and the
                # server writes the file directly, same as how recordings/
                # snapshots already work.
                b = self._body()
                pdf_b64 = b.get("pdf_base64")
                if not pdf_b64:
                    return self._json({"error": "pdf_base64 required"}, 400)
                try:
                    pdf_bytes = base64.b64decode(pdf_b64)
                except Exception:
                    return self._json({"error": "invalid base64"}, 400)
                export_dir = os.path.join(DATA, "dyno_exports")
                os.makedirs(export_dir, exist_ok=True)
                filename = os.path.basename(
                    b.get("filename") or f"dyno_{time.strftime('%Y%m%d_%H%M%S')}.pdf")
                if not filename.lower().endswith(".pdf"):
                    filename += ".pdf"
                path = os.path.join(export_dir, filename)
                with open(path, "wb") as f:
                    f.write(pdf_bytes)
                opened = False
                if b.get("open", True):
                    try:
                        _open_file(path)
                        opened = True
                    except Exception:
                        pass  # best-effort -- the file is saved either way
                self._json({"path": path, "opened": opened})
            elif self.path == "/api/garage/service":
                # Log a service against any vehicle in the garage, not
                # just the one currently connected (see /api/passport/service
                # for the connected-car equivalent).
                b = self._body()
                vin = (b.get("vin") or "").strip()
                if not vin:
                    return self._json({"error": "vin required"}, 400)
                if not b.get("serviceType"):
                    return self._json({"error": "serviceType required"}, 400)
                ev = ovpf_producer.record_service(
                    vin, b["serviceType"], odometer=b.get("odometer"),
                    odometer_unit=b.get("odometerUnit", "KMT"),
                    price=b.get("price"), currency=b.get("currency"),
                    notes=b.get("notes"), operator=_current_operator())
                _auto_push(vin)
                self._json(ev)
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _sse_live(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        me = object()
        LIVE_CLIENTS.add(me)
        try:
            last_sent = 0
            while True:
                if LIVE_LAST.get("t", 0) > last_sent:
                    last_sent = LIVE_LAST["t"]
                    msg = f"data: {json.dumps(LIVE_LAST)}\n\n"
                    self.wfile.write(msg.encode())
                    self.wfile.flush()
                time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            LIVE_CLIENTS.discard(me)


def csv_writer_thread():
    """Background thread: process CSV queue and write samples to disk.

    This runs independently of the sampler thread, preventing disk I/O and event
    detection from blocking live telemetry updates.
    """
    while True:
        try:
            t, values = CSV_QUEUE.get(timeout=1.0)
            record_row(values)
        except queue.Empty:
            continue
        except Exception as e:
            print(f"CSV writer error: {e}")
            time.sleep(0.1)


def sampler():
    """Background thread: poll live data while any SSE client is attached."""
    global LIVE_LAST
    while True:
        if ADAPTER and (LIVE_CLIENTS or RECORDER["on"]):
            try:
                with CAR_LOCK:
                    s = ADAPTER.live_sample()
                # Detect pull state even when not recording (for UI indication)
                pull_active = PULL_STATE["active"]
                if s and not RECORDER["on"]:
                    # Update pull detection state during live (non-recording) mode
                    detect_pull(s)
                # VANOS command-vs-response state (when S23 is in the profile)
                vanos_event = None
                if s and "S23" in s:
                    state, ev = VANOS_MON.update(s)
                    s["vanos_state"] = state
                    if ev:
                        vanos_event = log_vanos_event(ev, s)
                # Evaluate health status
                health = evaluate_health(s) if s else {}
                LIVE_LAST = {"t": time.time(), "values": s,
                             "ok": bool(s), "rec": RECORDER["count"]
                             if RECORDER["on"] else None,
                             "pull": PULL_STATE["active"],
                             "pull_num": PULL_STATE["counter"] if PULL_STATE["active"] else None,
                             "health": health,
                             "vanos_event": vanos_event}
                # Enqueue sample for CSV writer (non-blocking)
                if s and RECORDER["on"]:
                    try:
                        CSV_QUEUE.put_nowait((time.time(), s))
                    except queue.Full:
                        pass  # Drop sample if queue full (unlikely with 1000 buffer)
            except Exception as e:
                LIVE_LAST = {"t": time.time(), "values": {}, "ok": False,
                             "error": str(e)}
                time.sleep(1.0)
            time.sleep(0.02)
        else:
            time.sleep(0.3)


def serve(port=8039, connect_car=False, block=True):
    """Start the dashboard server + background threads.

    Used by the CLI (main) and, in a frozen desktop build, by desktop_app.py
    in-process (a frozen exe can't re-spawn itself as a plain interpreter).
    With block=False the HTTP server runs in a daemon thread and the bound
    server is returned so the caller can shut it down.
    """
    if connect_car:
        a = connect("auto")
        print(f"car: {a.name if a else 'not detected — connect via UI'}")
    threading.Thread(target=csv_writer_thread, daemon=True).start()
    threading.Thread(target=sampler, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"UI at http://localhost:{port}")
    if not block:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv
    srv.serve_forever()
    return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port-http", type=int, default=8039)
    ap.add_argument("--no-connect", action="store_true",
                    help="start server without touching the car")
    args = ap.parse_args()
    serve(port=args.port_http, connect_car=not args.no_connect)


if __name__ == "__main__":
    main()
