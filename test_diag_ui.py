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


if __name__ == "__main__":
    unittest.main(verbosity=2)
