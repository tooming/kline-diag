#!/usr/bin/env python3
"""Tests for multi-engine DME detection and parameter maps."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import dme_registry


def test_detect_m52_from_real_ident():
    # the actual E39 523i ident ASCII captured from the car
    d = dme_registry.detect_dme("142986111013021279800001158524101982711589")
    assert d["dme"] == "MS41" and d["engine"] == "M52", d
    assert d["matched_part"] == "1429861"
    print("test_detect_m52_from_real_ident OK")


def test_detect_m54_ms43():
    # an M54 part number (from the MS43 RomRaider definition ECU-id list)
    d = dme_registry.detect_dme("7551615 hw sw 20 05 07")
    assert d["dme"] == "MS43" and d["engine"] == "M54", d
    print("test_detect_m54_ms43 OK")


def test_unknown_part_number():
    d = dme_registry.detect_dme("9999999 nonsense")
    assert d["dme"] == "unknown"
    assert d["matched_part"] == "9999999"
    print("test_unknown_part_number OK")


def test_param_maps_load_and_have_core_channels():
    for dme in ("MS41", "MS43"):
        entry = [e for e in dme_registry.DME_REGISTRY if e["dme"] == dme][0]
        params = dme_registry.load_params(entry)
        assert params, f"{dme} params empty"
        ids = {p["id"] for p in params}
        # core driveability channels present in both
        for core in ("P8", "P13", "E2", "E11", "P2"):
            assert core in ids, f"{dme} missing {core}"
        # every param has an address + formula
        for p in params:
            assert p.get("addr") and p.get("expr")
    print("test_param_maps_load_and_have_core_channels OK")


def test_ms43_has_real_vanos_position():
    """M54 exposes a genuine intake-cam VANOS position (unlike M52's two-
    position system) — the E11 address differs from MS41's."""
    ms41 = {p["id"]: p for p in dme_registry.load_params(
        {"params": "ms41_ram_params.json"})}
    ms43 = {p["id"]: p for p in dme_registry.load_params(
        {"params": "ms43_ram_params.json"})}
    assert ms41["E11"]["addr"] != ms43["E11"]["addr"]
    print(f"test_ms43_has_real_vanos_position OK "
          f"(M52 E11@{ms41['E11']['addr']}, M54 E11@{ms43['E11']['addr']})")


def test_supported_list():
    eng = dme_registry.all_engines()
    dmes = {e["dme"] for e in eng}
    assert {"MS41", "MS43", "MS42", "ME7.2"} <= dmes
    with_map = [e for e in eng if e["has_map"]]
    assert len(with_map) >= 2
    print("test_supported_list OK")


if __name__ == "__main__":
    test_detect_m52_from_real_ident()
    test_detect_m54_ms43()
    test_unknown_part_number()
    test_param_maps_load_and_have_core_channels()
    test_ms43_has_real_vanos_position()
    test_supported_list()
    print("\nAll DME registry tests passed.")
