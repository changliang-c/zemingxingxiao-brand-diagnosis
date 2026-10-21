"""Isolated synthetic verification. This suite never contacts production or mail."""
import asyncio
import copy
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import httpx
import case_store
import http_server
from case_fixtures import initial_case, follow_up_case


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "private" / "research.sqlite3")

    def test_complete_case_and_followup_retains_business_evidence(self):
        first = case_store.accept_case(initial_case(), self.db)
        second = case_store.accept_case(follow_up_case(), self.db)
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(second["version"], 2)
        records = case_store.read_cases(self.db)["items"]
        before, after = [r["case"] for r in records]
        self.assertEqual(before["observations"][0]["numerator"], 120)
        self.assertEqual(before["observations"][0]["denominator"], 1000)
        self.assertEqual(before["observations"][3]["value"], 350000.75)
        self.assertEqual(after["observations"][0]["numerator"], 170)
        self.assertEqual(after["actual_actions"][0]["investment"], 2800)
        self.assertEqual(after["outcomes"][0]["attribution"], "unestablished")
        self.assertTrue(after["objections"])
        self.assertTrue(after["outcomes"][0]["adverse_effects"])
        self.assertEqual(after["parent_submission_id"], before["submission_id"])

    def test_cleanup_preserves_numbers_dates_and_never_stores_identifiers_or_capability(self):
        payload = initial_case()
        payload["brand_name"] = "虚构示例餐厅"
        payload["source_ip"] = "192.0.2.3"
        payload["evidence"][0]["statement"] += " 联系人：示例负责人，邮箱 fake@example.invalid 电话 13800138000，网址 https://example.invalid/private 。"
        prepared = case_store.prepare_case(payload)
        self.assertEqual(prepared, case_store.prepare_case(prepared))
        case_store.accept_case(prepared, self.db)
        text = json.dumps(case_store.read_cases(self.db), ensure_ascii=False)
        for value in ("虚构示例餐厅", "示例负责人", "fake@example", "13800138000", "https://example", "source_ip", payload["case_token"], "identity_terms"):
            self.assertNotIn(value, text)
        self.assertIn("350000.75", text)
        self.assertIn("2026-06-01", text)

    def test_duplicate_returns_original_receipt_and_immutable_conflict(self):
        original = initial_case()
        first = case_store.accept_case(original, self.db)
        duplicate = case_store.accept_case(original, self.db)
        self.assertEqual(duplicate["status"], "duplicate")
        self.assertEqual(first["receipt_id"], duplicate["receipt_id"])
        original["observations"][0]["value"] = .14
        with self.assertRaises(case_store.CaseValidationError) as caught:
            case_store.accept_case(original, self.db)
        self.assertEqual(caught.exception.code, "submission_conflict")
        self.assertEqual(len(case_store.read_cases(self.db)["items"]), 1)

    def test_no_authority_confidential_and_unresolved_risk_rejected_before_database(self):
        for status in ("unknown", "not_authorized", "confidential"):
            payload = initial_case()
            payload["authorization"]["status"] = status
            with self.assertRaises(case_store.CaseValidationError) as caught:
                case_store.accept_case(payload, self.db)
            self.assertEqual(caught.exception.code, "authorization_required")
        payload = initial_case()
        payload["deidentification"]["residual_risk"] = "unresolved"
        with self.assertRaises(case_store.CaseValidationError):
            case_store.accept_case(payload, self.db)
        self.assertFalse(Path(self.db).exists())

    def test_parent_version_and_case_capability(self):
        with self.assertRaises(case_store.CaseValidationError):
            case_store.accept_case(follow_up_case(), self.db)
        case_store.accept_case(initial_case(), self.db)
        follow = follow_up_case()
        follow["case_token"] = "incorrect_capability_01234567890123456789"
        with self.assertRaises(case_store.CaseValidationError) as caught:
            case_store.accept_case(follow, self.db)
        self.assertEqual(caught.exception.code, "case_access_denied")
        follow = follow_up_case()
        follow["version"] = 3
        with self.assertRaises(case_store.CaseValidationError) as caught:
            case_store.accept_case(follow, self.db)
        self.assertEqual(caught.exception.code, "version_conflict")

    def test_failure_no_improvement_and_disagreement_are_first_class(self):
        case_store.accept_case(initial_case(), self.db)
        follow = follow_up_case()
        follow["observations"][0].update({"value": .10, "numerator": 100})
        follow["outcomes"][0].update({"result": "worsened", "interpretation": "成熟队列由120/1000下降到100/1000；原预期未实现。"})
        follow["actual_actions"][0]["status"] = "stopped"
        case_store.accept_case(follow, self.db)
        saved = case_store.read_cases(self.db)["items"][1]["case"]
        self.assertEqual(saved["outcomes"][0]["result"], "worsened")
        follow2 = copy.deepcopy(follow)
        follow2.update({"submission_id": "synthetic_followup_20261019_0002", "parent_submission_id": follow["submission_id"], "version": 3})
        follow2["outcomes"][0]["result"] = "no_change"
        follow2["observations"][0].update({"observation_id": "repeat-followup-2", "value": .12, "numerator": 120})
        follow2["outcomes"][0]["observation_id"] = "repeat-followup-2"
        self.assertEqual(case_store.accept_case(follow2, self.db)["version"], 3)

    def test_incomplete_invalid_dates_and_nonfinite_rejected(self):
        cases = []
        bad = initial_case(); bad["observations"] = []; cases.append(bad)
        bad = initial_case(); bad["observations"][0]["value"] = float("nan"); cases.append(bad)
        bad = initial_case(); bad["observations"][0]["period"]["start"] = "2026-02-31"; cases.append(bad)
        bad = initial_case(); bad["predictions"] = []; cases.append(bad)
        bad = initial_case(); bad["raw_extra_blob"] = "not allowed"; cases.append(bad)
        for bad in cases:
            with self.assertRaises(case_store.CaseValidationError):
                case_store.accept_case(bad, self.db)

    def test_incomparable_or_immature_results_are_not_established(self):
        case_store.accept_case(initial_case(), self.db)
        bad = follow_up_case()
        bad["observations"][0]["unit"] = "percent"
        with self.assertRaises(case_store.CaseValidationError) as caught:
            case_store.accept_case(bad, self.db)
        self.assertEqual(caught.exception.code, "incomparable_outcome")
        bad = follow_up_case()
        bad["observations"][0]["period"]["matured"] = False
        with self.assertRaises(case_store.CaseValidationError) as caught:
            case_store.accept_case(bad, self.db)
        self.assertEqual(caught.exception.code, "immature_outcome")
        bad["outcomes"][0]["result"] = "unknown"
        self.assertTrue(case_store.accept_case(bad, self.db)["ok"])

    def test_parallel_duplicate_is_one_row(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(lambda _: case_store.accept_case(initial_case(), self.db), range(8)))
        self.assertEqual(sum(r["status"] == "accepted" for r in receipts), 1)
        self.assertEqual(len({r["receipt_id"] for r in receipts}), 1)

    def test_legacy_is_quarantined_and_never_in_research_reads(self):
        receipt = case_store.accept_legacy_case({"industry": "真实敏感名字", "source_ip": "192.0.2.4", "prescription_direction": "客户秘密"}, self.db)
        self.assertFalse(receipt["research_eligible"])
        self.assertEqual(case_store.read_cases(self.db)["items"], [])
        conn = sqlite3.connect(self.db)
        body = conn.execute("SELECT payload FROM legacy_quarantine").fetchone()[0]
        conn.close()
        self.assertNotIn("真实敏感名字", body)
        self.assertNotIn("客户秘密", body)
        self.assertNotIn("source_ip", body)

    def test_consistent_backup_and_retention(self):
        case_store.accept_case(initial_case(), self.db)
        backup = Path(self.tmp.name) / "safe-backup.sqlite3"
        case_store.backup_store(backup, self.db)
        self.assertEqual(len(case_store.read_cases(backup)["items"]), 1)
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE records SET expires_at='2000-01-01T00:00:00+00:00'")
        conn.commit(); conn.close()
        self.assertEqual(case_store.read_cases(self.db)["items"], [])


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "research.sqlite3")
        self.admin_token = "isolated_admin_test_capability_01234567890123456789"
        self.env = patch.dict(os.environ, {"ZMXX_CASE_DB": self.db, "ZMXX_CASE_READ_TOKEN": self.admin_token})
        self.env.start(); self.addCleanup(self.env.stop)
        http_server._case_rate.clear()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=http_server.app), base_url="https://www.zmxx.work")
        self.addAsyncCleanup(self.client.aclose)

    async def test_health_old_tools_and_full_intake_http(self):
        health = await self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["notifications"]["email"]["state"], "disabled")
        self.assertTrue(health.json()["notifications"]["inbox"]["enabled"])
        self.assertTrue({"get_framework", "diagnosis_guide", "search_cases", "diagnose_brand", "generate_report", "log_case"}.issubset(set(health.json()["tools"])))
        initial = await self.client.post("/case-report", json=initial_case())
        duplicate = await self.client.post("/case-report", json=initial_case())
        follow = await self.client.post("/case-report", json=follow_up_case())
        self.assertEqual((initial.status_code, duplicate.status_code, follow.status_code), (201, 200, 201))
        self.assertEqual(initial.json()["receipt_id"], duplicate.json()["receipt_id"])
        read = await self.client.get("/case-report/list", headers={"Authorization": "Bearer " + self.admin_token})
        self.assertEqual(len(read.json()["items"]), 2)
        self.assertEqual(read.headers["cache-control"], "no-store")
        self.assertNotIn("case_token", read.text)

    async def test_admin_read_is_fail_closed_no_query_token(self):
        self.assertEqual((await self.client.get("/case-report/list")).status_code, 401)
        self.assertEqual((await self.client.get("/case-report/list", params={"token": self.admin_token})).status_code, 401)
        self.assertEqual((await self.client.get("/case-report/list?n=oops", headers={"Authorization": "Bearer " + self.admin_token})).status_code, 400)
        with patch.dict(os.environ, {"ZMXX_CASE_READ_TOKEN": ""}):
            self.assertEqual((await self.client.get("/case-report/list", headers={"Authorization": "Bearer " + self.admin_token})).status_code, 401)

    async def test_invalid_oversize_and_private_errors(self):
        self.assertEqual((await self.client.post("/case-report", content="not json")).status_code, 400)
        self.assertEqual((await self.client.post("/case-report", content="x" * (case_store.MAX_BODY + 1))).status_code, 413)
        with patch.object(http_server, "accept_case", side_effect=RuntimeError("SECRET_MUST_NOT_LEAK")):
            response = await self.client.post("/case-report", json=initial_case())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("SECRET", response.text)

    async def test_legacy_receipt_not_false_research_success(self):
        result = await self.client.post("/case-report", json={"industry": "餐饮"})
        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.json()["status"], "legacy_quarantined")
        self.assertFalse(result.json()["research_eligible"])

    async def test_rate_limit_and_no_persistent_ip(self):
        for _ in range(20):
            result = await self.client.post("/case-report", json=initial_case(), headers={"x-forwarded-for": "spoofed"})
            self.assertIn(result.status_code, (200, 201))
        self.assertEqual((await self.client.post("/case-report", json=initial_case())).status_code, 429)
        self.assertNotIn("127.0.0.1", json.dumps(http_server._case_rate))
        self.assertNotIn("source_ip", json.dumps(case_store.read_cases(self.db)))

    async def test_cors_is_only_approved_diagnosis_origin(self):
        headers = {"Origin": "https://zhenduan-63363.app.workbuddy.host", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
        preflight = await self.client.options("/case-report", headers=headers)
        self.assertEqual(preflight.status_code, 204)
        self.assertEqual(preflight.headers["access-control-allow-origin"], headers["Origin"])
        headers["Origin"] = "https://unapproved.example"
        self.assertEqual((await self.client.options("/case-report", headers=headers)).status_code, 403)
        admin = await self.client.get("/case-report/list", headers={"Origin": "https://zhenduan-63363.app.workbuddy.host"})
        self.assertNotIn("access-control-allow-origin", admin.headers)

    def test_forwarded_address_only_trusted_from_loopback(self):
        from types import SimpleNamespace
        external = SimpleNamespace(client=SimpleNamespace(host="203.0.113.8"), headers={"x-real-ip": "192.0.2.9", "x-forwarded-for": "192.0.2.10"})
        self.assertEqual(http_server._client_ip(external), "203.0.113.8")
        external.client.host = "127.0.0.1"
        self.assertEqual(http_server._client_ip(external), "192.0.2.9")

    async def test_remote_mcp_cannot_lookup_local_case_token_or_retry_local_queue(self):
        from types import SimpleNamespace
        context = SimpleNamespace(request=None)
        accepted = await http_server._call_tool(context, SimpleNamespace(name="log_case", arguments=initial_case()))
        self.assertEqual(json.loads(accepted.content[0].text)["status"], "accepted")
        missing_token = follow_up_case()
        missing_token.pop("case_token")
        result = await http_server._call_tool(context, SimpleNamespace(name="record_follow_up", arguments=missing_token))
        self.assertFalse(json.loads(result.content[0].text)["ok"])
        retry = await http_server._call_tool(context, SimpleNamespace(name="retry_case_submissions", arguments={}))
        self.assertEqual(json.loads(retry.content[0].text)["code"], "retry_on_originating_client")
        self.assertEqual(len(case_store.read_cases(self.db)["items"]), 1)


if __name__ == "__main__":
    unittest.main()
