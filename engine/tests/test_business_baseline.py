"""Financial fit and contextual report regressions; synthetic data, no uploads."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import server
from business_baseline import assess_service_fit, DIAGNOSTIC_REVISION, FIRST_QUESTION


def intake(**changes):
    result = {"entity": "Synthetic enterprise", "period": "2025", "currency": "CNY", "unit": "million",
              "basis": "consolidated revenue/gross profit/after-tax net profit", "data_status": "actual",
              "income": 100, "gross": 40, "net": 5}
    result.update(changes)
    return result


class ServiceFitTests(unittest.TestCase):
    def test_exact_boundary_and_no_net_upper_limit(self):
        for net in (5, 17, 60):  # Net may exceed gross because of non-operating income.
            with self.subTest(net=net):
                result = assess_service_fit(intake(net=net))
                self.assertEqual(result["status"], "within_policy_reference")
                self.assertFalse(result["reminder_required"])
                self.assertIsNone(result["policy"]["net_upper_limit"])

    def test_soft_reminders_low_three_and_contribution_category(self):
        cases = [(40.01, 5, ["gross_above_40"], None),
                 (40, 3, ["net_below_5"], None),
                 (60, 3, ["gross_above_40", "net_below_5"], "contribution")]
        for gross, net, reasons, category in cases:
            with self.subTest(gross=gross, net=net):
                result = assess_service_fit(intake(gross=gross, net=net))
                self.assertEqual(result["status"], "fit_reminder")
                self.assertEqual(result["reminder_reasons"], reasons)
                self.assertEqual(result["internal_category"], category)
                self.assertTrue(result["can_continue"])
                self.assertFalse(result["automatic_rejection"])

    def test_informed_user_continues_and_estimates_do_not_become_verified(self):
        data = intake(gross=60, net=3, informed_continuation=True)
        self.assertEqual(assess_service_fit(data)["status"], "proceed_informed")
        data["data_status"] = "estimate"
        result = assess_service_fit(data)
        self.assertEqual(result["status"], "pending_verification")
        self.assertTrue(result["can_continue"])
        self.assertTrue(result["informed_continuation"])
        self.assertIsNone(result["internal_category"])

    def test_missing_nonfinite_zero_and_bad_shapes_never_divide_or_reject(self):
        invalid = [None, {}, [], intake(income=0), intake(income=-100), intake(gross=None),
                   intake(income=float("inf")), intake(net=float("nan")), intake(net=True),
                   intake(gross="40"), intake(period="2025Q1"), intake(currency=""),
                   intake(income=1e-310, gross=1e-310, net=1e308)]
        for data in invalid:
            with self.subTest(data=data):
                result = assess_service_fit(data)
                self.assertEqual(result["status"], "pending_verification")
                self.assertTrue(result["can_continue"])
                json.dumps(result, allow_nan=False)
        self.assertIsNone(assess_service_fit(intake(income=0))["rates"]["net_margin"])

    def test_mismatched_period_currency_units_and_rates_are_withheld(self):
        for field, value in (("entity", "Other entity"), ("period", "2024"), ("currency", "USD"),
                             ("unit", "yuan"), ("basis", "parent only")):
            data = intake(gross={"value": 40, field: value})
            result = assess_service_fit(data)
            self.assertIn("inconsistent_" + field, result["issues"])
            self.assertEqual(result["rates"], {"gross_margin": None, "net_margin": None})
        for rates in ({"gross_margin": 45}, {"net_margin": 17}, {"gross_margin": float("inf")}, []):
            result = assess_service_fit(intake(provided_rates=rates))
            self.assertEqual(result["status"], "pending_verification")
            self.assertIsNone(result["rates"]["net_margin"])
        rounded = assess_service_fit(intake(provided_rates={"gross_margin": 40.09, "net_margin": 5.0}))
        self.assertEqual(rounded["status"], "within_policy_reference")

    def test_metric_metadata_and_source_do_not_substitute_industry_mean(self):
        full = intake()
        data = {key: {**{k: full[k] for k in ("entity", "period", "currency", "unit", "basis", "data_status")}, "value": full[key]} for key in ("income", "gross", "net")}
        before = copy.deepcopy(data)
        self.assertEqual(assess_service_fit(data)["status"], "within_policy_reference")
        self.assertEqual(data, before)
        result = assess_service_fit(intake(source_type="industry_average"))
        self.assertEqual(result["status"], "pending_verification")
        self.assertIsNone(result["rates"]["gross_margin"])

    def test_bank_does_not_require_or_evaluate_merchandise_gross(self):
        for industry in ("银行", "banking", "Commercial bank"):
            data = intake(industry=industry)
            del data["gross"]
            result = assess_service_fit(data)
            self.assertEqual(result["status"], "pending_verification")
            self.assertIn("gross_not_applicable_product_fit_required", result["issues"])
            self.assertFalse(result["gross_applicable"])
            self.assertIsNone(result["rates"]["gross_margin"])
        self.assertEqual(assess_service_fit(intake(industry="bank", net=3))["reminder_reasons"], ["net_below_5"])

    def test_other_profit_definitions_do_not_impersonate_after_tax_net_profit(self):
        for definition in ("pre_tax", "attributable", "adjusted", "segment", "unknown"):
            result = assess_service_fit(intake(net_definition=definition))
            self.assertEqual(result["status"], "pending_verification")
            self.assertIsNone(result["rates"]["net_margin"])
        self.assertIn("net_definition_unverified", assess_service_fit(intake(basis="归母净利润"))["issues"])


class BaselineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"ZMXX_REPORT_DIR": str(Path(self.tmp.name)/"reports"),
                                          "ZMXX_RESEARCH_ENDPOINT": "", "ZMXX_PUBLIC_BASE_URL": ""})
        self.env.start()
        self.network = patch("socket.create_connection", side_effect=AssertionError("No network during diagnosis/report tests"))
        self.network.start()

    def tearDown(self):
        self.network.stop()
        self.env.stop()
        self.tmp.cleanup()

    def test_schema_and_first_question_are_exposed_without_version_bump(self):
        tools = {t["name"]: t for t in server.TOOLS}
        for name in ("diagnose_brand", "generate_report"):
            self.assertIn("financial_intake", tools[name]["inputSchema"]["properties"])
            self.assertIn("operational_context", tools[name]["inputSchema"]["properties"])
        self.assertEqual(server.DIAGNOSIS_GUIDE["利润入口"]["首问"], FIRST_QUESTION)
        result = server.call_tool("assess_service_fit", {"financial_intake": intake(net=17)})
        self.assertEqual(result["status"], "within_policy_reference")

    def test_legacy_diagnosis_and_bilingual_reports_keep_unknowns_visible(self):
        diagnosis = server.diagnose({"brand_name": "Synthetic", "water_growth": 25, "fire_state": "strong"})
        self.assertEqual(diagnosis["skill_version"], "2.6.0")
        self.assertEqual(diagnosis["diagnostic_revision"], DIAGNOSTIC_REVISION)
        self.assertEqual(diagnosis["four_xiang"]["xiang"], "老阳")
        self.assertTrue(diagnosis["four_xiang"]["requires_context_verification"])
        self.assertEqual(diagnosis["service_fit"]["status"], "pending_verification")
        for language, needles in (("zh-CN", ["利润适配待核实", "四象初筛", "因果循环: 未提供", "关键门槛: 未提供"]),
                                  ("en", ["pending verification", "initial screen", "Causal loop: Not provided", "Saddle point and action timing: Not provided"])):
            # A pre-patch saved diagnosis has none of the new keys.
            legacy = {k: v for k, v in diagnosis.items() if k not in ("financial_intake", "service_fit", "operational_context")}
            report = server.generate_report({"diagnosis": legacy, "report_language": language, "format": "html"})
            for needle in needles:
                self.assertIn(needle, report["html"])
            self.assertEqual(report["version"], "2.6.0")
            self.assertTrue(Path(report["report_file"]).is_file())

    def test_informed_continuation_context_and_escape_in_both_languages(self):
        context = {"causal_loop": {"links": "Promise -> delivery -> renewal", "evidence": "Cohort A"},
                   "three_powers": {"heaven": "Window", "earth": "Market", "people": "Capacity"},
                   "critical_thresholds": [{"metric": "Cash contribution", "value": "> 0", "window": "One contract cycle"}],
                   "four_xiang_stage": "Transition under review", "four_xiang_transition": {"trigger": "Renewal evidence"},
                   "isomorphic_comparison": {"similarity": "Delivery bottleneck", "difference": "Payment period"},
                   "saddle_point": {"action": "Small reversible trial", "timing": "After acceptance", "stop_condition": "Cash loss"}}
        diagnosis = server.diagnose({"brand_name": "Synthetic", "financial_intake": intake(gross=60, net=3, informed_continuation=True), "operational_context": context})
        for language, phrase in (("en", "user understands the boundary"), ("zh-CN", "用户已知情并坚持继续")):
            report = server.generate_report({"diagnosis": diagnosis, "report_language": language, "format": "html"})
            for expected in (phrase, "Promise -&gt; delivery", "Cohort A", "Cash contribution", "Small reversible trial"):
                self.assertIn(expected, report["html"])
            self.assertNotIn("59.9", report["html"])
            self.assertNotIn("贡献型", report["html"])
            self.assertEqual(report["service_fit"]["status"], "proceed_informed")
        context["saddle_point"] = "<script>alert(1)</script>"
        report = server.generate_report({"diagnosis": diagnosis, "operational_context": context, "format": "html"})
        self.assertNotIn("<script>", report["html"])
        self.assertIn("&lt;script&gt;", report["html"])

    def test_report_recomputes_finance_and_keeps_estimated_data_provisional(self):
        diagnosis = server.diagnose({"brand_name": "Synthetic", "financial_intake": intake()})
        report = server.generate_report({"diagnosis": diagnosis, "financial_intake": intake(net=3, data_status="estimate", informed_continuation=True), "report_language": "en"})
        self.assertEqual(report["service_fit"]["status"], "pending_verification")
        self.assertIn("estimates", report["markdown"])
        self.assertIn("wishes to continue", report["markdown"])
        diagnosis = server.diagnose({"brand_name": "Synthetic", "financial_intake": intake(net=float("nan"))})
        json.dumps(diagnosis, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
