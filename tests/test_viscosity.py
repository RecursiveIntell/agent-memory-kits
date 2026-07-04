from __future__ import annotations

import json
import os
import tempfile
import unittest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared", "scripts"))

from viscosity import StrictnessLevel, ViscosityController


class TestViscosityController(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "viscosity_state.json")

    def _make_controller(self):
        return ViscosityController(self.store_path)

    # -- level tests ------------------------------------------------

    def test_fluid_when_high_success(self):
        vc = self._make_controller()
        vc.record({"success_rate": 0.99, "error_rate": 0.0,
                   "contradiction_count": 0, "elapsed_secs": 1.0})
        self.assertEqual(vc.level(), StrictnessLevel.FLUID)

    def test_normal_when_moderate(self):
        vc = self._make_controller()
        # composite = (1-0.8)*0.4 + 0.1*0.3 + 0*0.3 = 0.08+0.03 = 0.11 → too low
        # Need something in [0.3, 0.5).  Let's pick:
        # success=0.6 → (0.4)*0.4 = 0.16; error=0.4 → 0.4*0.3 = 0.12; contrad=5 → 0.5*0.3 = 0.15
        # total = 0.16+0.12+0.15 = 0.43 → NORMAL
        vc.record({"success_rate": 0.6, "error_rate": 0.4,
                   "contradiction_count": 5, "elapsed_secs": 1.0})
        score = vc.compute_signal()["composite_score"]
        self.assertGreaterEqual(score, 0.3)
        self.assertLess(score, 0.5)
        self.assertEqual(vc.level(), StrictnessLevel.NORMAL)

    def test_strict_when_errors(self):
        vc = self._make_controller()
        # Want composite in [0.5, 0.7)
        # success=0.5 → 0.5*0.4 = 0.20; error=0.7 → 0.7*0.3 = 0.21; contrad=3 → 0.3*0.3 = 0.09
        # total = 0.20+0.21+0.09 = 0.50 → STRICT
        vc.record({"success_rate": 0.5, "error_rate": 0.7,
                   "contradiction_count": 3, "elapsed_secs": 1.0})
        score = vc.compute_signal()["composite_score"]
        self.assertGreaterEqual(score, 0.5)
        self.assertLess(score, 0.7)
        self.assertEqual(vc.level(), StrictnessLevel.STRICT)

    def test_frozen_when_everything_bad(self):
        vc = self._make_controller()
        # Want composite >= 0.7
        # success=0.2 → 0.8*0.4 = 0.32; error=0.9 → 0.9*0.3 = 0.27; contrad=10 → 1.0*0.3 = 0.30
        # total = 0.32+0.27+0.30 = 0.89 → FROZEN
        vc.record({"success_rate": 0.2, "error_rate": 0.9,
                   "contradiction_count": 10, "elapsed_secs": 1.0})
        score = vc.compute_signal()["composite_score"]
        self.assertGreaterEqual(score, 0.7)
        self.assertEqual(vc.level(), StrictnessLevel.FROZEN)

    # -- threshold tests --------------------------------------------

    def test_thresholds_return_correct_values(self):
        vc = self._make_controller()
        expected = {
            StrictnessLevel.FLUID: {"mintop": 0.58, "max_hits": 4, "min_overlap": 1},
            StrictnessLevel.NORMAL: {"mintop": 0.62, "max_hits": 3, "min_overlap": 1},
            StrictnessLevel.STRICT: {"mintop": 0.68, "max_hits": 2, "min_overlap": 2},
            StrictnessLevel.FROZEN: {"mintop": 0.75, "max_hits": 1, "min_overlap": 2},
        }
        for level, exp in expected.items():
            with self.subTest(level=level):
                self.assertEqual(vc.thresholds(level), exp)

    # -- persistence test -------------------------------------------

    def test_persistence(self):
        vc1 = self._make_controller()
        vc1.record({"success_rate": 0.95, "error_rate": 0.05,
                    "contradiction_count": 1, "elapsed_secs": 2.0})
        vc1.record({"success_rate": 0.90, "error_rate": 0.10,
                    "contradiction_count": 0, "elapsed_secs": 3.0})
        self.assertEqual(len(vc1.history), 2)

        # New instance, same store file — should load prior history
        vc2 = self._make_controller()
        self.assertEqual(len(vc2.history), 2)
        self.assertEqual(vc2.history[0]["success_rate"], 0.95)
        self.assertEqual(vc2.history[1]["contradiction_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)