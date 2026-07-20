#!/usr/bin/env python3
"""Tests for the generic body-module registry (ecu_registry.py)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ecu_registry


def test_unregistered_module_reports_unmatched_with_observed_part():
    # No real ident has been captured for any body module yet (only the
    # DME, via dme_registry.py) -- every address must come back unmatched,
    # never a guessed match.
    d = ecu_registry.detect_variant(0x00, "88371234560405...9826980107")
    assert d["matched"] is False
    assert d["sgbd"] is None
    assert d["observed_part"] == "88371234"
    print("test_unregistered_module_reports_unmatched_with_observed_part OK")


def test_unmatched_module_surfaces_its_candidates():
    d = ecu_registry.detect_variant(0x00, "88371234560405")
    assert d["sgbd_candidates"] == ["ZKE3_GM1"]
    d2 = ecu_registry.detect_variant(0xC0, "anything")  # MID: no candidates
    assert d2["sgbd_candidates"] == []
    print("test_unmatched_module_surfaces_its_candidates OK")


def test_registered_module_matches_by_part_number():
    # Exercise the matching algorithm itself against a fabricated entry
    # (MODULE_REGISTRY has no real entries yet -- this only tests the
    # mechanism dme_registry.py's real DME matching already proved works).
    saved = ecu_registry.MODULE_REGISTRY.get(0x99)
    ecu_registry.MODULE_REGISTRY[0x99] = [
        {"sgbd": "TESTDOC", "name": "Test Module", "part_numbers": ["12345"]}]
    try:
        d = ecu_registry.detect_variant(0x99, "1234567 hw sw 20 05 07")
        assert d["matched"] is True and d["sgbd"] == "TESTDOC"
        assert d["matched_part"] == "12345"
    finally:
        if saved is None:
            del ecu_registry.MODULE_REGISTRY[0x99]
        else:
            ecu_registry.MODULE_REGISTRY[0x99] = saved
    print("test_registered_module_matches_by_part_number OK")


def test_sgbd_candidates_exist_in_the_submodule_if_checked_out():
    # Not a hard failure if sgbd_full isn't initialized (submodules aren't
    # auto-cloned) -- but if it IS present, every candidate stem referenced
    # here must be a real doc, or the hint is useless/stale.
    sgbd_dir = os.path.join(HERE, "sgbd_full", "docs", "sgbd")
    if not os.path.isdir(sgbd_dir):
        print("test_sgbd_candidates_exist_in_the_submodule_if_checked_out "
              "SKIPPED (sgbd_full not checked out)")
        return
    present = set(os.listdir(sgbd_dir))
    for addr, stems in ecu_registry.SGBD_CANDIDATES.items():
        for stem in stems:
            assert f"{stem}.md" in present, \
                f"0x{addr:02X} candidate {stem}.md not found in sgbd_full"
    print("test_sgbd_candidates_exist_in_the_submodule_if_checked_out OK")


if __name__ == "__main__":
    test_unregistered_module_reports_unmatched_with_observed_part()
    test_unmatched_module_surfaces_its_candidates()
    test_registered_module_matches_by_part_number()
    test_sgbd_candidates_exist_in_the_submodule_if_checked_out()
    print("\nAll ecu_registry tests passed.")
