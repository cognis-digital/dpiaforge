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

    def test_bad_path_returns_2(self):
        code = main(["assess", "/no/such/file.json"])
        self.assertEqual(code, 2)


class TestHardenedEdgeCases(unittest.TestCase):
    """Tests for hardened error paths and edge cases added during robustness pass."""

    # ------------------------------------------------------------------
    # core.assess — structural validation
    # ------------------------------------------------------------------

    def test_assess_empty_dict_raises(self):
        """An empty dict must raise ValueError, not crash silently."""
        with self.assertRaises(ValueError):
            assess({})

    def test_assess_list_raises(self):
        """A JSON array at the top level must raise ValueError."""
        with self.assertRaises(ValueError):
            assess(["item1", "item2"])

    def test_assess_flags_not_dict_tolerated(self):
        """If 'flags' is not a dict (e.g. a string), the engine should not raise."""
        activity = {"name": "broken flags", "flags": "should_be_a_dict"}
        report = assess(activity)
        self.assertIn("dpia", report)
        self.assertEqual(report["dpia"]["criteria_met"], 0)

    def test_assess_data_subjects_string_tolerated(self):
        """A non-numeric data_subjects value must be treated as 0, not raise."""
        activity = {"name": "bad subjects", "data_subjects": "many", "flags": {}}
        report = assess(activity)
        self.assertIsInstance(report["risk"]["inherent"], int)

    def test_assess_negative_data_subjects_treated_as_zero(self):
        """Negative data_subjects must not produce negative inherent scores."""
        activity = {"name": "neg subjects", "data_subjects": -50000, "flags": {}}
        report = assess(activity)
        self.assertGreaterEqual(report["risk"]["inherent"], 0)

    def test_assess_mitigations_not_list_tolerated(self):
        """If 'mitigations' is a string instead of a list, engine should not raise."""
        activity = {"name": "bad mitigations", "mitigations": "pen-tested", "flags": {}}
        report = assess(activity)
        # Should treat it as zero mitigations (no crash)
        self.assertEqual(report["risk"]["mitigations_counted"], 0)

    # ------------------------------------------------------------------
    # CLI — malformed and missing-file paths
    # ------------------------------------------------------------------

    def setUp(self):
        self._tmp_files: list = []

    def tearDown(self):
        for p in self._tmp_files:
            if os.path.exists(p):
                os.remove(p)

    def _capture(self, argv):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            code = main(argv)
        finally:
            sys.stdout = old
        return code, buf.getvalue()

    def _write_tmp(self, name: str, content: str) -> str:
        p = os.path.join(os.path.dirname(__file__), name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
        self._tmp_files.append(p)
        return p

    def test_malformed_json_returns_1(self):
        """A file with invalid JSON must exit 1 with an error message on stderr."""
        path = self._write_tmp("_tmp_bad.json", "{not valid json}")
        err_buf = io.StringIO()
        old_err = sys.stderr
        sys.stderr = err_buf
        try:
            code, _ = self._capture(["assess", path])
        finally:
            sys.stderr = old_err
        self.assertEqual(code, 1)
        self.assertIn("error", err_buf.getvalue().lower())

    def test_json_array_returns_1(self):
        """A JSON array (not object) must exit 1 with a clear error."""
        path = self._write_tmp("_tmp_array.json", '["not", "an", "object"]')
        err_buf = io.StringIO()
        old_err = sys.stderr
        sys.stderr = err_buf
        try:
            code, _ = self._capture(["assess", path])
        finally:
            sys.stderr = old_err
        self.assertEqual(code, 1)

    def test_empty_file_returns_1(self):
        """An empty file must exit 1 with a clear error, not crash."""
        path = self._write_tmp("_tmp_empty.json", "")
        err_buf = io.StringIO()
        old_err = sys.stderr
        sys.stderr = err_buf
        try:
            code, _ = self._capture(["assess", path])
        finally:
            sys.stderr = old_err
        self.assertEqual(code, 1)

    def test_missing_file_returns_2(self):
        """A non-existent file path must exit 2 (file-not-found)."""
        code = main(["assess", "/no/such/path/activity.json"])
        self.assertEqual(code, 2)

    def test_empty_activity_returns_1(self):
        """An empty JSON object {} must exit 1 (no fields to assess)."""
        path = self._write_tmp("_tmp_emptyobj.json", "{}")
        err_buf = io.StringIO()
        old_err = sys.stderr
        sys.stderr = err_buf
        try:
            code, _ = self._capture(["assess", path])
        finally:
            sys.stderr = old_err
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
