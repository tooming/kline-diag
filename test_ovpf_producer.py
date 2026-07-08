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

    def test_workshop_profile_set_get_clear(self):
        self.assertIsNone(prod.get_workshop())
        prod.set_workshop("Skoor Garage", "skoor.ee")
        self.assertEqual(prod.get_workshop(), {"name": "Skoor Garage", "domain": "skoor.ee"})
        prod.clear_workshop()
        self.assertIsNone(prod.get_workshop())

    def test_workshop_profile_attributes_diagnostic_and_manual_events(self):
        prod.set_workshop("Skoor Garage", "skoor.ee")
        fault_ev = prod.record_faults(self.vin, 0x12, "DME", {
            "ok": True, "entries": [{"code": "0x71", "text": "O2", "status": "s",
                                     "raw": "71"}]})
        service_ev = prod.record_service(self.vin, "Changed engine oil")
        for ev in (fault_ev, service_ev):
            self.assertEqual(ev["producer"]["type"], "Workshop")
            self.assertEqual(ev["producer"]["name"], "Skoor Garage")
            self.assertEqual(ev["producer"]["domain"], "skoor.ee")
            self.assertNotIn("verified", ev["producer"])  # self-asserted, never claims verification

    def test_workshop_profile_without_domain_omits_domain_field(self):
        prod.set_workshop("Garage With No Website")
        ev = prod.record_service(self.vin, "Changed engine oil")
        self.assertEqual(ev["producer"]["type"], "Workshop")
        self.assertNotIn("domain", ev["producer"])

    def test_no_workshop_profile_keeps_existing_producers(self):
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
