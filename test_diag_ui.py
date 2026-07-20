#!/usr/bin/env python3
"""Tests for diag_ui.py's detect_pull() (stdlib unittest). Importing
diag_ui.py doesn't touch any hardware -- adapters are only constructed on
an explicit /api/connect, never at import time.
"""
import sys
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import diag_ui
import ds2_diag


class DetectPullTest(unittest.TestCase):
    def setUp(self):
        diag_ui.PULL_STATE.update(active=False, counter=0, rpm_history=[])
        diag_ui.PULLS_LOG.clear()
        self._orig_time = diag_ui.time.time
        self.clock = [0.0]
        diag_ui.time.time = lambda: self.clock[0]

    def tearDown(self):
        diag_ui.time.time = self._orig_time

    def _sample(self, dt, rpm, throttle):
        self.clock[0] += dt
        return diag_ui.detect_pull({"P8": rpm, "P13": throttle})

    def test_dense_small_per_sample_deltas_still_detect_a_real_pull(self):
        """Real bug found live on the E39: rpm_increasing used to compare
        only against the single previous sample (rpm > prev_rpm + 100).
        DS2's single combined list-read samples densely enough that a real
        WOT pull's per-sample delta never exceeded ~91rpm even while
        climbing 1900->6500rpm overall -- confirmed against an actual
        recorded pull -- so detect_pull() silently never fired. It only
        ever worked on the E87 by coincidence of KWP2000's slower per-PID
        round trips leaving bigger gaps between samples of the same real
        acceleration. This replays that exact cadence synthetically: ~90rpm
        per ~110ms sample, throttle pinned at 85%."""
        transitions = []
        rpm = 1900
        for _ in range(20):
            rpm += 90
            t = self._sample(0.11, rpm, 85)
            if t:
                transitions.append(t)
        self.assertTrue(any(t[0] == "start" for t in transitions),
                         "pull start never detected despite a sustained climb")

        t = self._sample(0.11, rpm, 40)  # driver lifts off
        self.assertEqual(t[0], "end")

    def test_sparse_e87_cadence_still_detects_a_real_pull(self):
        """Real bug found live on the E87: KWP2000's per-PID round trips
        sample at ~0.83-1.1s intervals -- slower than the 0.6s rpm_history
        window -- so the window's age-based trim emptied down to just the
        sample that was *just appended* every call, baseline_rpm compared
        rpm against itself, and detect_pull() silently never fired for an
        entire real recorded WOT pull (1163->6533rpm, throttle 82->100%).
        Replays that exact cadence: ~0.83s per sample, ~470rpm/sample."""
        transitions = []
        rpm = 1163
        for _ in range(12):
            rpm += 470
            t = self._sample(0.83, rpm, 100)
            if t:
                transitions.append(t)
        self.assertTrue(any(t[0] == "start" for t in transitions),
                         "pull start never detected at E87 sampling cadence")

        t = self._sample(0.83, rpm, 9)  # driver lifts off
        self.assertEqual(t[0], "end")

    def test_idle_noise_does_not_false_trigger(self):
        """Small fluctuations around a stable idle/cruise rpm, even with
        throttle occasionally blipping, must not register as a pull."""
        import random
        random.seed(0)
        rpm = 800
        transitions = []
        for _ in range(50):
            rpm = 800 + random.randint(-30, 30)
            t = self._sample(0.1, rpm, random.choice([10, 15, 20]))
            if t:
                transitions.append(t)
        self.assertEqual(transitions, [])


class MS43ProfileDataTest(unittest.TestCase):
    """MS43_PROFILES is the second E39's (2003 520i, M54B22/MS43) live-data
    table -- rebuilt from ds2_diag.MS43_ENGINE_PARAMS/MS43_DIGITAL_BITS
    (BMW's own fixed status-group reads, reconstructed from the factory
    EDIABAS SGBD MS430DS0.prg) after the original RAM-address-list-derived
    version proved wrong on a real car. These check the data is internally
    consistent without needing the real car connected."""

    def test_every_ms43_profile_id_exists_in_the_verified_sgbd_tables(self):
        verified_ids = ({p["id"] for p in ds2_diag.MS43_ENGINE_PARAMS}
                         | {b["id"] for b in ds2_diag.MS43_DIGITAL_BITS})
        for profile, channels in diag_ui.MS43_PROFILES.items():
            for pid, label, group, graph in channels:
                self.assertIn(pid, verified_ids,
                               f"{profile}: {pid} ({label}) not in the SGBD-verified tables")

    def test_ms41_expr_overrides_do_not_apply_under_ms43(self):
        # S23 means "VANOS command" on MS41 but doesn't exist at all in
        # MS43's verified status-group tables -- the MS41 bitmask override
        # must never be picked up for an MS43 car.
        self.assertNotIn("S23", diag_ui.EXPR_OVERRIDES_BY_DME.get("MS43", {}))
        self.assertIn("S23", diag_ui.EXPR_OVERRIDES_BY_DME["MS41"])


class EvaluateHealthMS43Test(unittest.TestCase):
    """evaluate_health() must not apply MS41/M52-tuned thresholds (idle MAF
    band, single-cam VANOS rest position) to a sample that carries MS43/M54
    ids, and must not fabricate a knock-retard reading MS43's verified
    status-group tables don't actually provide."""

    def test_ms43_sample_skips_m52_idle_maf_verdict(self):
        # 18 kg/h would be a "green, idle airflow OK" verdict under the M52
        # 15-22 kg/h band -- must come back as uncolored/informational once
        # an MS43-only id (E12) marks this as an M54 sample instead.
        health = diag_ui.evaluate_health({"P8": 800, "P12": 18.0, "E12": 65.0})
        self.assertEqual(health["maf"]["color"], "blue")

    def test_ms43_vanos_uses_active_ready_switches_not_m52_rest_heuristic(self):
        health = diag_ui.evaluate_health(
            {"E11": 61.0, "E12": -61.0, "VAN_AK": True, "VAN_BR": False, "P2": 90})
        self.assertEqual(health["vanos"]["color"], "green")
        self.assertIn("VANOS active", health["vanos"]["text"])
        self.assertIn("ex ", health["vanos"]["value"])

    def test_ms43_knock_tile_does_not_populate_without_a_verified_source(self):
        # Earlier versions fell back to id E24 or E27 for MS43 "knock" --
        # neither is in the verified status-group tables. Better to show
        # nothing than fabricate a reading, so the tile must stay absent
        # even when E24 happens to be present in the sample for some other
        # reason.
        health = diag_ui.evaluate_health({"E12": 0.0, "E24": 87.0})
        self.assertNotIn("timing", health)


if __name__ == "__main__":
    unittest.main(verbosity=2)
