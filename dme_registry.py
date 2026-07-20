#!/usr/bin/env python3
"""E39 engine/DME registry + auto-detection (multi-car support, Phase 10-ish).

The family runs several E39s with different engines. They all speak DS2 at
0x12. The custom RAM address-list live-logging mechanism (0B 01 arm / 0B 00
read) works reliably on MS41 (car-verified) but does NOT reliably on MS43 --
tested live on a real MS43 car (part 7519308) and found to return garbage
for most non-ADC channels (fuel trims pinned at raw-value extremes, -43C
coolant, 1300 kg/h MAF, gear "24"). ms43_ram_params.json/this file's MS43
entry are kept for the RAM explorer (manual address probing) but the live
dashboard no longer uses them -- see diag_ui.py's E39Adapter._load_dme_params
and ds2_diag.MS43StatusLogger, which read MS43's own FIXED status-group
jobs (0B 03 engine params / 0B 04 digital IO) instead, reconstructed from
the factory EDIABAS SGBD MS430DS0.prg (reference_ms43_ds2_commands.ts).

Detection: the DS2 ident (service 0x00) response contains the ECU part
number as the leading digits of its ASCII (e.g. the M52 here idents as
`1429861...`). We match that against known part numbers.

Coverage today:
  - MS41  (M52,    e.g. 523i/528i '96-'98)  -> ms41_ram_params.json  [car-verified]
  - MS43  (M54,    e.g. 520i/525i/530i '00-'03) -> ms43_ram_params.json [RAM
    address-list unreliable on real hardware; live dashboard uses the SGBD
    fixed status-group reads instead, see above]
MS42 (M52TU) and ME7.2 (M62 V8) are recognised but have no param map yet
(they degrade to fault/live-block reads, which still work).

Pure stdlib, offline.
"""
import json
import os

import paths
HERE = paths.resource_dir()

# part-number prefix -> DME descriptor. Prefixes are the leading digits of
# the DS2 ident ASCII. Sources: RomRaider/ms4x.net ECU-id lists.
DME_REGISTRY = [
    {"dme": "MS41", "engine": "M52", "params": "ms41_ram_params.json",
     "evidence": "car-verified",
     "part_numbers": ["1429861", "1405854", "1406464", "1429373",
                      "1432401", "1437806", "1440176", "1430656"]},
    {"dme": "MS43", "engine": "M54", "params": "ms43_ram_params.json",
     "evidence": "RAM address-list map (RomRaider def) tested live on "
                 "part 7519308 and found unreliable for most non-ADC "
                 "channels -- live dashboard uses ds2_diag.MS43StatusLogger's "
                 "SGBD-sourced fixed status-group reads instead, not this map",
     "part_numbers": ["7511570", "7519308", "7545150", "7551615",
                      "7526753", "7532493"]},
    # Recognised, no param map yet (live block + faults still work):
    {"dme": "MS42", "engine": "M52TU", "params": None,
     "evidence": "recognised, no map",
     "part_numbers": ["7500255", "7508534"]},
    {"dme": "ME7.2", "engine": "M62TU", "params": None,
     "evidence": "recognised, no map",
     "part_numbers": ["7515777", "7526565"]},
]


def _digits(ident_ascii):
    """Leading run of digits from an ident ASCII string."""
    s = "".join(ch for ch in (ident_ascii or "") if ch.isdigit())
    return s


def detect_dme(ident_ascii):
    """Return the DME descriptor matching an ident ASCII, or an 'unknown'
    descriptor carrying the observed part number."""
    digits = _digits(ident_ascii)
    for entry in DME_REGISTRY:
        for pn in entry["part_numbers"]:
            if pn in digits:
                return {**entry, "matched_part": pn}
    return {"dme": "unknown", "engine": "unknown", "params": None,
            "evidence": "unrecognised part number",
            "part_numbers": [], "matched_part": digits[:7] or None}


def load_params(descriptor, part_number=None):
    """Load the RAM parameter list for a detected DME, or [] if none.

    Many params have firmware-specific addresses (MS41.0 vs MS41.1 etc.):
    when a param carries `addr_by_fw`, resolve `addr` to the entry matching
    the detected `part_number` so the right RAM location is read on every
    firmware. Falls back to the default `addr` when the firmware is unknown.
    """
    name = descriptor.get("params")
    if not name:
        return []
    pn = part_number or descriptor.get("matched_part")
    try:
        with open(os.path.join(HERE, name)) as f:
            params = json.load(f)
    except OSError:
        return []
    out = []
    for p in params:
        fw = p.get("addr_by_fw")
        if fw and pn and pn in fw:
            p = {**p, "addr": fw[pn], "addr_resolved_for": pn}
        out.append(p)
    return out


def all_engines():
    return [{"dme": e["dme"], "engine": e["engine"],
             "has_map": bool(e["params"]), "evidence": e["evidence"]}
            for e in DME_REGISTRY]


if __name__ == "__main__":
    # demo: identify the known M52 ident string
    sample = "142986111013021279800001158524101982711589"
    d = detect_dme(sample)
    print(f"ident {sample[:12]}... -> {d['dme']} ({d['engine']}), "
          f"map={d['params']}, {len(load_params(d))} params")
    print("\nSupported engines:")
    for e in all_engines():
        print(f"  {e['dme']:6} {e['engine']:7} "
              f"{'map' if e['has_map'] else 'no map':7} — {e['evidence']}")
