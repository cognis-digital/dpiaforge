"""Smoke tests for DPIAFORGE (offline, stdlib-only)."""
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dpiaforge import (  # noqa: E402
    TOOL_NAME,
    TOOL_VERSION,
    assess,
    dpia_threshold,
    classify_ai_act_tier,
    risk_score,
)
from dpiaforge.cli import main  # noqa: E402


HIGH_RISK_HR = {
    "name": "HR screener",
    "is_ai_system": True,
    "role": "provider",
    "data_subjects": 250000,
    "flags": {
        "evaluation_scoring": True,
        "automated_decision": True,
        "employment": True,
    },
    "mitigations": ["human review"],
}

PROHIBITED = {
    "name": "Gov social score",
    "is_ai_system": True,
    "flags": {"social_scoring": True},
    "mitigations": ["a", "b", "c", "d", "e"],
}

MINIMAL = {
    "name": "Spam filter",
    "is_ai_system": True,
    "flags": {},
}


class TestMeta(unittest.TestCase):
    def test_version_exports(self):
        self.assertEqual(TOOL_NAME, "dpiaforge")
        self.assertTrue(TOOL_VERSION)


class TestDpiaThreshold(unittest.TestCase):
    def test_two_criteria_requires_dpia(self):
        res = dpia_threshold(HIGH_RISK_HR)
        self.assertTrue(res["dpia_required"])
        self.assertEqual(res["verdict"], "DPIA_REQUIRED")
        self.assertGreaterEqual(res["criteria_met"], 2)

    def test_zero_criteria_not_indicated(self):
        res = dpia_threshold(MINIMAL)
        self.assertFalse(res["dpia_required"])
        self.assertEqual(res["verdict"], "DPIA_NOT_INDICATED")


class TestAiActTier(unittest.TestCase):
    def test_high_risk_employment(self):
        res = classify_ai_act_tier(HIGH_RISK_HR)
        self.assertEqual(res["tier"], "HIGH_RISK")
        self.assertTrue(res["obligations"])

    def test_prohibited(self):
        res = classify_ai_act_tier(PROHIBITED)
        self.assertEqual(res["tier"], "PROHIBITED")

    def test_minimal(self):
        res = classify_ai_act_tier(MINIMAL)
        self.assertEqual(res["tier"], "MINIMAL_RISK")

    def test_non_ai(self):
        res = classify_ai_act_tier({"is_ai_system": False, "flags": {}})
        self.assertEqual(res["tier"], "NOT_AN_AI_SYSTEM")


class TestRiskScore(unittest.TestCase):
    def test_mitigations_reduce_residual(self):
        dpia = dpia_threshold(HIGH_RISK_HR)
        tier = classify_ai_act_tier(HIGH_RISK_HR)
        score = risk_score(HIGH_RISK_HR, dpia, tier)
        self.assertLessEqual(score["residual"], score["inherent"])
        self.assertIn(score["band"], ("LOW", "MEDIUM", "HIGH", "CRITICAL"))

    def test_prohibited_is_critical_no_mitigation(self):
        dpia = dpia_threshold(PROHIBITED)
        tier = classify_ai_act_tier(PROHIBITED)
        score = risk_score(PROHIBITED, dpia, tier)
        self.assertEqual(score["mitigation_reduction"], 0)
        self.assertEqual(score["band"], "CRITICAL")


class TestAssess(unittest.TestCase):
    def test_full_report_shape(self):
        report = assess(HIGH_RISK_HR)
        for key in ("dpia", "ai_act", "risk", "recommendations", "deployable"):
            self.assertIn(key, report)
        self.assertTrue(report["deployable"])

    def test_prohibited_not_deployable(self):
        report = assess(PROHIBITED)
        self.assertFalse(report["deployable"])

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            assess(["not", "a", "dict"])


class TestCli(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(os.path.dirname(__file__), "_tmp_activity.json")
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(HIGH_RISK_HR, fh)

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def _capture(self, argv):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            code = main(argv)
        finally:
            sys.stdout = old
        return code, buf.getvalue()

    def test_assess_json(self):
        code, out = self._capture(["--format", "json", "assess", self.path])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["ai_act"]["tier"], "HIGH_RISK")

    def test_assess_table(self):
        code, out = self._capture(["assess", self.path])
        self.assertEqual(code, 0)
        self.assertIn("DPIAFORGE report", out)

    def test_prohibited_nonzero_exit(self):
        p = os.path.join(os.path.dirname(__file__), "_tmp_prohibited.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(PROHIBITED, fh)
        try:
            code, _ = self._capture(["--format", "json", "assess", p])
            self.assertEqual(code, 3)
        finally:
            os.remove(p)

    def test_no_command_returns_2(self):
        code, _ = self._capture([])
        self.assertEqual(code, 2)

    def test_bad_path_returns_1(self):
        code = main(["assess", "/no/such/file.json"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
