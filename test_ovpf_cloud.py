#!/usr/bin/env python3
"""Tests for ovpf_cloud.py (stdlib unittest). Mocks the HTTP layer
(_request) so this never touches the real passport.skoor.ee provider --
uses a temp data dir so it never touches real session/passport files.
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ovpf_cloud as cloud
import ovpf_producer as prod


class FakeHttp:
    """Programs canned (status, body) responses per call, in order, and
    records every call made so assertions can check what was sent."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, path, body=None, token=None, timeout=10.0):
        self.calls.append({"method": method, "path": path, "body": body,
                           "token": token})
        return self.responses.pop(0)


class CloudTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        prod.paths.data_dir = lambda: self.tmp
        cloud.paths.data_dir = lambda: self.tmp
        self.vin = "TESTVIN0000000001"
        self._orig_request = cloud._request

    def tearDown(self):
        cloud._request = self._orig_request

    def test_session_roundtrip(self):
        self.assertIsNone(cloud.get_user_session())
        cloud.set_user_session("a@b.com", "tok1")
        self.assertEqual(cloud.get_user_session(),
                         {"email": "a@b.com", "token": "tok1"})
        cloud.clear_user_session()
        self.assertIsNone(cloud.get_user_session())

        cloud.set_workshop_session("shop.example", "tok2", {"role": "owner"})
        self.assertEqual(cloud.get_workshop_session(),
                         {"domain": "shop.example", "token": "tok2",
                          "role": "owner"})
        cloud.clear_workshop_session()
        self.assertIsNone(cloud.get_workshop_session())

    def test_best_auth_session_prefers_matching_workshop(self):
        cloud.set_user_session("a@b.com", "user-tok")
        cloud.set_workshop_session("shop.example", "ws-tok")
        self.assertEqual(cloud.best_auth_session("shop.example")["token"],
                         "ws-tok")
        self.assertEqual(cloud.best_auth_session("other.example")["token"],
                         "user-tok")
        self.assertEqual(cloud.best_auth_session(None)["token"], "user-tok")

    def test_best_auth_session_falls_back_to_workshop_only(self):
        cloud.set_workshop_session("shop.example", "ws-tok")
        self.assertEqual(cloud.best_auth_session(None)["token"], "ws-tok")

    def test_best_auth_session_none_when_signed_out(self):
        self.assertIsNone(cloud.best_auth_session("shop.example"))

    def test_verify_otp_stores_session_on_success(self):
        cloud._request = FakeHttp([(200, {"token": "abc123"})])
        cloud.verify_otp("me@example.com", "111111")
        self.assertEqual(cloud.get_user_session(),
                         {"email": "me@example.com", "token": "abc123"})

    def test_verify_otp_raises_on_error(self):
        cloud._request = FakeHttp([(401, {"error": "bad code"})])
        with self.assertRaises(cloud.CloudError):
            cloud.verify_otp("me@example.com", "000000")
        self.assertIsNone(cloud.get_user_session())

    def test_bare_id_strips_urn_prefix(self):
        self.assertEqual(cloud._bare_id("urn:ovpf:abc-123"), "abc-123")
        self.assertEqual(cloud._bare_id("already-bare"), "already-bare")

    def test_push_passport_no_local_data(self):
        r = cloud.push_passport("NEVER_SEEN_VIN")
        self.assertEqual(r["pushed"], 0)
        self.assertIn("note", r)

    def test_push_passport_requires_sign_in(self):
        prod.ensure_passport(self.vin)
        with self.assertRaises(cloud.CloudError):
            cloud.push_passport(self.vin)

    def test_push_passport_sends_and_tracks_synced(self):
        prod.ensure_passport(self.vin)
        prod.record_odometer(self.vin, 123456)
        cloud.set_user_session("me@example.com", "tok")

        fake = FakeHttp([
            (201, {"ok": True}),                    # POST /v1/passports
            (200, {"id": "ev1"}),                    # PassportOpened event
            (200, {"id": "ev2"}),                    # OdometerReading event
        ])
        cloud._request = fake
        result = cloud.push_passport(self.vin)
        self.assertEqual(result["pushed"], 2)
        self.assertEqual(result["errors"], [])

        # registration call used the bare uuid, not the urn:ovpf: form
        register_call = fake.calls[0]
        self.assertEqual(register_call["path"], "/v1/passports")
        self.assertFalse(register_call["body"]["id"].startswith("urn:"))

        # second push with nothing new queued is a no-network no-op
        fake2 = FakeHttp([])
        cloud._request = fake2
        result2 = cloud.push_passport(self.vin)
        self.assertEqual(result2["pushed"], 0)
        self.assertEqual(result2["skipped"], 2)
        self.assertEqual(fake2.calls, [])

    def test_push_passport_stops_on_auth_error(self):
        prod.ensure_passport(self.vin)
        prod.record_odometer(self.vin, 111)
        prod.record_odometer(self.vin, 222)
        cloud.set_user_session("me@example.com", "tok")

        fake = FakeHttp([
            (201, {"ok": True}),                  # register
            (401, {"error": "expired"}),          # first event fails
        ])
        cloud._request = fake
        result = cloud.push_passport(self.vin)
        self.assertEqual(result["pushed"], 0)
        self.assertEqual(len(result["errors"]), 1)

    def test_sync_status_reports_pending_count(self):
        prod.ensure_passport(self.vin)
        prod.record_odometer(self.vin, 1000)
        status = cloud.sync_status(self.vin)
        self.assertEqual(status["total"], 2)  # PassportOpened + Odometer
        self.assertEqual(status["pending"], 2)
        self.assertFalse(status["signed_in"])
        cloud.set_user_session("me@example.com", "tok")
        self.assertTrue(cloud.sync_status(self.vin)["signed_in"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
