#!/usr/bin/env python3
"""Tests for the OVPF producer + vendored core (stdlib unittest).

Uses a temp data dir so it never touches real passport logs.
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ovpf_core
import ovpf_producer as prod

# Wire-format fingerprint — MUST equal the ovp reference's golden hash, or the
# vendored core has drifted and logs are no longer cross-compatible.
GOLDEN_EVENT = {
    "@context": ovpf_core.CONTEXT,
    "id": "urn:uuid:018f3a1b-0000-7000-8000-0000000000aa",
    "type": "PassportOpened", "specVersion": "0.1", "vehicle": "urn:ovpf:x",
    "occurredAt": "2026-01-01T00:00:00Z", "recordedAt": "2026-01-01T00:00:00Z",
    "producer": {"type": "Manual", "name": "t"},
    "data": {"vehicle": {"type": "Vehicle", "vin": "ABC"}}}
GOLDEN_HASH = "sha256:d0ffd8834939e26b423e12111dfbd606b0c228907c1268cc24c9c8f51335734f"


class ProducerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # redirect the passport dir into the temp dir
        prod.paths.data_dir = lambda: self.tmp
        self.vin = "TESTVIN0000000001"

    def test_wire_format_golden_hash(self):
        self.assertEqual(ovpf_core.event_hash(dict(GOLDEN_EVENT)), GOLDEN_HASH)

    def test_auto_mint_passport_is_anonymous_uuid(self):
        path, urn = prod.ensure_passport(self.vin)
        self.assertTrue(urn.startswith("urn:ovpf:"))
        self.assertTrue(os.path.exists(path))
        # genesis carries VIN as data, not identity
        first = ovpf_core.load(path)[0]
        self.assertEqual(first["type"], "PassportOpened")
        self.assertEqual(first["data"]["vehicle"]["vin"], self.vin)

    def test_ensure_passport_reuses_cloud_pulled_file_by_vin(self):
        """A passport pulled from the cloud (ovpf_cloud.pull_passport) is
        cached under the provider's own uuid, not the VIN. Reconnecting to
        that same car locally must reuse it, not mint a duplicate."""
        urn = "urn:ovpf:019f485f-e91a-7000-bf55-5a9558b26ac5"
        path = os.path.join(prod._passports_dir(),
                            "019f485f-e91a-7000-bf55-5a9558b26ac5.ovpf.ndjson")
        ovpf_core.append(path, ovpf_core.envelope(
            urn, "PassportOpened",
            {"vehicle": {"type": "Vehicle", "vin": self.vin}}, prod.MANUAL))

        result_path, result_urn = prod.ensure_passport(self.vin)

        self.assertEqual(result_urn, urn)
        self.assertEqual(result_path, path)
        self.assertEqual(len(os.listdir(prod._passports_dir())), 1)

    def test_stale_fault_drops_off_on_a_clean_reread_without_an_explicit_clear(self):
        """Real bug found live on the E39: a code read once, then absent
        from every subsequent read of that same module, stayed "open"
        forever because nothing ever explicitly cleared it -- a fault can
        legitimately self-resolve (e.g. after enough healthy drive cycles)
        without the user ever running the clear command on it specifically.
        A fresh full read of a module must supersede that module's prior
        state, not just accumulate into it."""
        prod.record_faults(self.vin, 0x12, "DME", {
            "ok": True, "entries": [{"code": "0x71", "text": "O2", "status": "s",
                                     "raw": "71"}]})
        prod.record_faults(self.vin, 0x12, "DME", {"ok": True, "entries": []})
        state = prod.passport_state(self.vin)
        self.assertEqual(state["open_faults"], [])

        # A different module's fault is untouched by another module's reread.
        prod.record_faults(self.vin, 0x60, "IKE", {
            "ok": True, "entries": [{"code": "0x99", "text": "lamp", "status": "s",
                                     "raw": "99"}]})
        prod.record_faults(self.vin, 0x12, "DME", {"ok": True, "entries": []})
        state = prod.passport_state(self.vin)
        self.assertEqual([f["code"] for f in state["open_faults"]], ["0x99"])

    def test_faults_then_clear_reduces_to_zero_open(self):
        prod.record_faults(self.vin, 0x12, "DME", {
            "ok": True, "entries": [{"code": "0x71", "text": "O2", "status": "s",
                                     "raw": "71"}]})
        prod.record_clear(self.vin, 0x12, "DME")
        state = prod.passport_state(self.vin)
        self.assertEqual(state["open_faults"], [])
        self.assertTrue(state["chain_ok"])

    def test_faults_deduped(self):
        r = {"ok": True, "entries": [{"code": "0x71", "text": "O2",
                                      "status": "s", "raw": "71"}]}
        self.assertIsNotNone(prod.record_faults(self.vin, 0x12, "DME", r))
        self.assertIsNone(prod.record_faults(self.vin, 0x12, "DME", r))  # same -> skip

    def test_faults_text_correction_is_not_deduped(self):
        """A DTC table gaining a translation that was blank when the code
        was first captured (the PDC 9E3x codes on the E87 passport, in
        practice) must still reach the passport on a rescan, even though
        the code set itself hasn't changed."""
        blank = {"ok": True, "entries": [{"code": "0x9E33", "text": "",
                                          "status": "s", "raw": "9E33"}]}
        self.assertIsNotNone(prod.record_faults(self.vin, 0x64, "PDC", blank))
        corrected = {"ok": True, "entries": [{"code": "0x9E33",
                                              "text": "PDC: rear left sensor wire fault",
                                              "status": "s", "raw": "9E33"}]}
        self.assertIsNotNone(prod.record_faults(self.vin, 0x64, "PDC", corrected))
        state = prod.passport_state(self.vin)
        self.assertEqual(state["open_faults"][0]["text"],
                         "PDC: rear left sensor wire fault")

    def test_vehicle_identified_deduped(self):
        f = {"vin": self.vin, "engine": "M52B25"}
        self.assertIsNotNone(prod.record_vehicle_identified(self.vin, f))
        self.assertIsNone(prod.record_vehicle_identified(self.vin, f))

    def test_coding_change_recorded(self):
        prod.record_coding_change(self.vin, 0x80, "IKE", "4a0300", "4a0301",
                                  preset="enable_12h")
        state = prod.passport_state(self.vin)
        self.assertEqual(len(state["coding_changes"]), 1)
        self.assertEqual(state["coding_changes"][0]["after"], "4a0301")

    def test_record_service_is_manual_producer(self):
        ev = prod.record_service(self.vin, "Changed engine oil",
                                  odometer=210500, price=45.0, currency="EUR")
        self.assertEqual(ev["producer"]["type"], "Manual")
        state = prod.passport_state(self.vin)
        self.assertEqual(len(state["service_history"]), 1)
        self.assertEqual(state["service_history"][0]["type"], "Changed engine oil")
        self.assertEqual(state["mileage"], {"value": 210500, "unit": "KMT"})

    def test_chain_is_maintained_across_appends(self):
        prod.record_vehicle_identified(self.vin, {"vin": self.vin})
        prod.record_faults(self.vin, 0x12, "DME", {
            "ok": True, "entries": [{"code": "0x10", "text": "x", "status": "s",
                                     "raw": "10"}]})
        path = prod._log_path(self.vin)
        self.assertEqual(ovpf_core.verify_chain(ovpf_core.load(path)), [])

    def test_faults_and_service_use_default_producers(self):
        fault_ev = prod.record_faults(self.vin, 0x12, "DME", {
            "ok": True, "entries": [{"code": "0x71", "text": "O2", "status": "s",
                                     "raw": "71"}]})
        service_ev = prod.record_service(self.vin, "Changed engine oil")
        self.assertEqual(fault_ev["producer"]["type"], "Diagnostic")
        self.assertEqual(service_ev["producer"]["type"], "Manual")

    def test_list_passports_includes_all_known_vehicles(self):
        prod.record_vehicle_identified(self.vin, {"vin": self.vin})
        prod.record_vehicle_identified("OTHERVIN00000002", {"vin": "OTHERVIN00000002"})
        vins = {s["vehicle"].get("vin") for s in prod.list_passports()}
        self.assertEqual(vins, {self.vin, "OTHERVIN00000002"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
