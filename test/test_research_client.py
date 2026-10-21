"""Isolated HTTP tests: never contact production or send notifications."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import subprocess
import tempfile
from threading import Thread
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from submit_case import submit, get_status, retry_pending, SubmissionError
from research_contract import prepare_case, CaseValidationError


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.outbox = Path(self.tmp.name)
        self.records = []
        self.status = 201
        self.bad_receipt = False
        self.response_delay = 0
        self.enforce_versions = False
        self.accepted_records = {}
        owner = self

        class Receiver(BaseHTTPRequestHandler):
            def do_POST(self):
                record = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.records.append(record)
                prepare_case(record)
                previous = [r for r in owner.records[:-1] if r["submission_id"] == record["submission_id"]]
                data = {"ok": True, "status": "duplicate" if previous else "accepted", "case_id": record["case_id"], "submission_id": "wrong" if owner.bad_receipt else record["submission_id"], "receipt_id": "local-receipt-1"}
                status = owner.status
                if owner.enforce_versions and record["submission_id"] not in owner.accepted_records:
                    versions = [r["version"] for r in owner.accepted_records.values() if r["case_id"] == record["case_id"]]
                    expected = max(versions, default=0) + 1
                    if record["version"] != expected or (expected > 1 and record.get("parent_submission_id") not in owner.accepted_records):
                        status = 409
                        data = {"ok": False, "error": "version_conflict"}
                if 200 <= status < 300:
                    owner.accepted_records[record["submission_id"]] = record
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                if owner.response_delay:
                    time.sleep(owner.response_delay)
                try:
                    self.wfile.write(json.dumps(data).encode())
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/case-report"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def fixture(self, follow=False):
        name = "research-follow-up.synthetic.json" if follow else "research-diagnosis.synthetic.json"
        return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))

    def test_complete_case_is_cleaned_before_http_and_business_values_survive(self):
        case = self.fixture()
        case["evidence"][0]["statement"] += " 电话: 13912345678；邮箱: private@example.com"
        result = submit(case, self.outbox, self.url)
        self.assertEqual(result["status"], "accepted")
        received = self.records[0]
        serialized = json.dumps(received, ensure_ascii=False)
        for clue in ("虚构示例餐厅", "示例负责人", "13912345678", "private@example.com"):
            self.assertNotIn(clue, serialized)
        self.assertEqual(received["deidentification"]["identity_terms"], [])
        baseline = received["observations"][0]
        self.assertEqual((baseline["numerator"], baseline["denominator"]), (120, 1000))
        self.assertEqual(received["observations"][3]["value"], 350000.75)
        self.assertTrue(baseline["period"]["matured"])
        receipt_path = self.outbox / (case["submission_id"] + ".receipt.json")
        receipt_archive = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertNotIn("case_token", receipt_archive["record"])
        bridge = json.loads((self.outbox / (case["submission_id"] + ".private-receipt.json")).read_text(encoding="utf-8"))
        self.assertEqual(bridge["case"]["case_token"], received["case_token"])
        self.assertEqual(bridge["receipt"]["receipt_id"], result["receipt_id"])
        self.assertFalse(list(self.outbox.glob("*.pending.json")))

    def test_follow_up_reuses_capability_and_preserves_relation_and_result(self):
        initial, follow = self.fixture(), self.fixture(True)
        submit(initial, self.outbox, self.url)
        submit(follow, self.outbox, self.url)
        a, b = self.records
        self.assertEqual(a["case_token"], b["case_token"])
        self.assertEqual(a["submission_id"], b["parent_submission_id"])
        self.assertEqual(b["case_id"], a["case_id"])
        self.assertTrue(b["actual_actions"] and b["outcomes"])
        self.assertIn(170, [o["numerator"] for o in b["observations"]])

    def test_temporary_failure_keeps_same_payload_and_retry_receives_duplicate(self):
        case = self.fixture()
        self.status = 503
        with self.assertRaises(SubmissionError):
            submit(case, self.outbox, self.url, retries=0)
        path = self.outbox / (case["submission_id"] + ".pending.json")
        pending = json.loads(path.read_text(encoding="utf-8"))
        self.status = 200
        result = submit(pending, self.outbox, self.url, retries=0)
        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(self.records[0], self.records[1])
        self.assertFalse(path.exists())

    def test_wrong_receipt_never_marks_success(self):
        self.bad_receipt = True
        case = self.fixture()
        with self.assertRaises(SubmissionError):
            submit(case, self.outbox, self.url, retries=0)
        self.assertTrue(list(self.outbox.glob("*.pending.json")))
        self.assertFalse(list(self.outbox.glob("*.receipt.json")))

    def test_authority_or_review_failure_never_leaves_device(self):
        for field, key, value in [("authorization", "status", "unknown"), ("deidentification", "reviewed", False)]:
            case = self.fixture()
            case[field][key] = value
            with self.assertRaises(CaseValidationError):
                submit(case, self.outbox, self.url)
        self.assertEqual(self.records, [])
        self.assertEqual(list(self.outbox.iterdir()), [])

    def test_follow_up_without_original_capability_stays_local(self):
        with self.assertRaises(SubmissionError):
            submit(self.fixture(True), self.outbox, self.url)
        self.assertEqual(self.records, [])

    def test_prepare_only_and_plain_http_restriction(self):
        result = submit(self.fixture(), self.outbox, self.url, prepare_only=True)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(self.records, [])
        with self.assertRaises(SubmissionError):
            submit(self.fixture(), self.outbox, "http://example.com/case-report")

    def test_timeout_keeps_metadata_then_explicit_retry_receives_duplicate(self):
        case = self.fixture()
        self.response_delay = 0.15
        with self.assertRaises(SubmissionError):
            submit(case, self.outbox, self.url, retries=0, timeout=0.03)
        failed = get_status(self.outbox)["records"][0]
        self.assertEqual(failed["status"], "pending")
        self.assertEqual(failed["last_error_category"], "network_timeout")
        self.assertEqual(failed["attempt_count"], 1)
        self.assertTrue(failed["retryable"] and failed["pending"])
        self.assertIn("last_error_at", failed)
        self.response_delay = 0
        result = retry_pending(self.outbox, self.url, retries=0)
        self.assertTrue(result["ok"])
        self.assertEqual((result["attempted"], result["completed"], result["remaining"]), (1, 1, 0))
        self.assertEqual(self.records[0], self.records[1])
        state = result["records"][0]
        self.assertEqual((state["status"], state["attempt_count"]), ("duplicate", 2))
        self.assertEqual(state["receipt_id"], "local-receipt-1")
        self.assertNotIn("last_error_category", state)

    def test_accepted_submission_is_not_sent_again_even_with_stale_pending(self):
        case = self.fixture()
        result = submit(case, self.outbox, self.url)
        pending = self.outbox / (case["submission_id"] + ".pending.json")
        private_receipt = self.outbox / (case["submission_id"] + ".private-receipt.json")
        private_receipt.unlink()
        pending.write_text(json.dumps(self.records[0]), encoding="utf-8")
        replay = retry_pending(self.outbox, self.url)
        self.assertTrue(replay["ok"])
        self.assertEqual(len(self.records), 1)
        self.assertEqual(replay["records"][0]["status"], "accepted")
        self.assertFalse(pending.exists())
        self.assertTrue(private_receipt.exists())
        self.assertEqual(submit(case, self.outbox, self.url), result)
        self.assertEqual(len(self.records), 1)
        self.assertTrue(retry_pending(self.outbox, self.url)["ok"])
        self.assertEqual(len(self.records), 1)

    def test_accepted_identifier_cannot_be_reused_for_changed_content(self):
        case = self.fixture()
        submit(case, self.outbox, self.url)
        case["context"]["goal"] = "Changed research goal"
        with self.assertRaises(SubmissionError) as failure:
            submit(case, self.outbox, self.url)
        self.assertEqual(failure.exception.category, "submission_conflict")
        self.assertEqual(len(self.records), 1)
        state = get_status(self.outbox)["records"][0]
        self.assertEqual((state["status"], state["last_error_category"]), ("blocked", "submission_conflict"))
        self.assertNotIn("receipt_id", state)

    def test_403_is_visible_and_not_retried_automatically(self):
        self.status = 403
        with self.assertRaises(SubmissionError):
            submit(self.fixture(), self.outbox, self.url, retries=2)
        state = get_status(self.outbox)["records"][0]
        self.assertEqual((state["status"], state["last_error_category"], state["http_status"]), ("blocked", "receiver_rejected", 403))
        self.assertFalse(state["retryable"])
        self.assertEqual((len(self.records), state["attempt_count"]), (1, 1))
        result = retry_pending(self.outbox, self.url)
        self.assertFalse(result["ok"])
        self.assertEqual((result["attempted"], result["blocked"]), (0, 1))
        self.assertEqual(len(self.records), 1)

    def test_retry_without_pending_and_status_do_not_connect_or_create_directories(self):
        absent = self.outbox / "does-not-exist"
        with patch("submit_case.build_opener", side_effect=AssertionError("No network expected")):
            self.assertEqual(get_status(absent)["count"], 0)
            result = retry_pending(absent, self.url)
        self.assertTrue(result["ok"])
        self.assertEqual((result["attempted"], result["remaining"]), (0, 0))
        self.assertFalse(absent.exists())

    def test_corrupt_and_unauthorized_pending_do_not_block_other_items(self):
        valid = self.fixture()
        submit(valid, self.outbox, self.url, prepare_only=True)
        bad_id = "submission_bad_json_0001"
        (self.outbox / (bad_id + ".pending.json")).write_text('{"broken":', encoding="utf-8")
        unauthorized = self.fixture()
        unauthorized["submission_id"] = "submission_unauthorized_0001"
        unauthorized["authorization"]["status"] = "unknown"
        (self.outbox / (unauthorized["submission_id"] + ".pending.json")).write_text(json.dumps(unauthorized), encoding="utf-8")
        result = retry_pending(self.outbox, self.url, retries=0)
        self.assertFalse(result["ok"])
        self.assertEqual(result["completed"], 1)
        self.assertEqual(len(self.records), 1)
        by_id = {entry["submission_id"]: entry for entry in result["records"]}
        self.assertEqual(by_id[bad_id]["last_error_category"], "invalid_pending")
        self.assertEqual(by_id[unauthorized["submission_id"]]["last_error_category"], "authorization_required")
        self.assertEqual(by_id[unauthorized["submission_id"]]["attempt_count"], 0)

    def test_status_and_retry_outputs_never_include_record_content_or_tokens(self):
        case = self.fixture()
        self.status = 503
        with self.assertRaises(SubmissionError):
            submit(case, self.outbox, self.url, retries=0)
        state_path = self.outbox / (case["submission_id"] + ".status.json")
        stored = json.loads(state_path.read_text(encoding="utf-8"))
        token = self.records[0]["case_token"]
        stored.update(case_token=token, authorization=case["authorization"], message="private@example.com",
                      receipt_id=token, last_error_category="private@example.com")
        state_path.write_text(json.dumps(stored), encoding="utf-8")
        result = get_status(self.outbox)
        serialized = json.dumps(result, ensure_ascii=False)
        for clue in (token, "private@example.com", "case_token", "authorization", "evidence", "context"):
            self.assertNotIn(clue, serialized)
        self.assertEqual(len(self.records), 1)

    def test_retry_can_target_one_pending_submission(self):
        first = self.fixture()
        second = self.fixture()
        second["case_id"] = "case_second_independent_0001"
        second["submission_id"] = "submission_second_independent_0001"
        submit(first, self.outbox, self.url, prepare_only=True)
        submit(second, self.outbox, self.url, prepare_only=True)
        result = retry_pending(self.outbox, self.url, submission_id=second["submission_id"])
        self.assertTrue(result["ok"])
        self.assertEqual([entry["submission_id"] for entry in self.records], [second["submission_id"]])
        self.assertTrue((self.outbox / (first["submission_id"] + ".pending.json")).exists())

    def test_cli_status_is_read_only_and_legacy_input_still_works(self):
        source = self.outbox / "input.json"
        source.write_text(json.dumps(self.fixture()), encoding="utf-8")
        command = [sys.executable, str(ROOT / "scripts" / "submit_case.py"), "--outbox", str(self.outbox), "--endpoint", self.url]
        prepared = subprocess.run(command + ["--input", str(source), "--prepare-only"], text=True, capture_output=True)
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        status = subprocess.run(command + ["--status"], text=True, capture_output=True)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["records"][0]["attempt_count"], 0)
        self.assertEqual(self.records, [])
        retried = subprocess.run(command + ["--retry-pending", "--retries", "0"], text=True, capture_output=True)
        self.assertEqual(retried.returncode, 0, retried.stderr)
        self.assertTrue(json.loads(retried.stdout)["ok"])
        self.assertEqual(len(self.records), 1)

    def test_temporary_errors_have_a_bounded_attempt_count(self):
        self.status = 503
        with patch("submit_case.time.sleep"):
            with self.assertRaises(SubmissionError):
                submit(self.fixture(), self.outbox, self.url, retries=2)
        self.assertEqual(len(self.records), 3)
        self.assertEqual(get_status(self.outbox)["records"][0]["attempt_count"], 3)

    def test_status_requires_a_matching_receipt_before_reporting_success(self):
        case = self.fixture()
        submit(case, self.outbox, self.url, prepare_only=True)
        state_path = self.outbox / (case["submission_id"] + ".status.json")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.update(status="accepted", receipt_id="made-up-receipt")
        state_path.write_text(json.dumps(state), encoding="utf-8")
        result = get_status(self.outbox)["records"][0]
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["last_error_category"], "invalid_receipt")
        self.assertNotIn("receipt_id", result)
        self.assertEqual(self.records, [])

    def queue_three_versions_with_reversed_names(self):
        initial = self.fixture()
        initial["submission_id"] = "zzz_initial_submission_0001"
        follow = self.fixture(True)
        follow["submission_id"] = "mmm_second_submission_0002"
        follow["parent_submission_id"] = initial["submission_id"]
        third = copy.deepcopy(follow)
        third["submission_id"] = "aaa_third_submission_0003"
        third["parent_submission_id"] = follow["submission_id"]
        third["version"] = 3
        for record in (initial, follow, third):
            submit(record, self.outbox, self.url, prepare_only=True)
        return initial, follow, third

    def test_batch_retries_follow_case_version_order_not_filename_order(self):
        self.enforce_versions = True
        initial, follow, third = self.queue_three_versions_with_reversed_names()
        queued = get_status(self.outbox)["records"]
        self.assertEqual([record["submission_id"] for record in queued],
                         [initial["submission_id"], follow["submission_id"], third["submission_id"]])
        self.assertEqual([record["ready_to_retry"] for record in queued], [True, False, False])
        result = retry_pending(self.outbox, self.url, retries=0)
        self.assertTrue(result["ok"])
        self.assertEqual((result["completed"], result["remaining"], result["deferred"]), (3, 0, 0))
        self.assertEqual([record["version"] for record in self.records], [1, 2, 3])
        self.assertEqual([record["submission_id"] for record in self.records],
                         [initial["submission_id"], follow["submission_id"], third["submission_id"]])

    def test_failed_parent_defers_followups_without_network_attempts_then_recovers(self):
        self.enforce_versions = True
        initial, follow, third = self.queue_three_versions_with_reversed_names()
        self.status = 503
        failed = retry_pending(self.outbox, self.url, retries=0)
        self.assertFalse(failed["ok"])
        self.assertEqual((failed["attempted"], failed["deferred"], failed["blocked"]), (1, 2, 0))
        self.assertEqual([record["version"] for record in self.records], [1])
        states = {record["submission_id"]: record for record in failed["records"]}
        for dependent in (follow, third):
            state = states[dependent["submission_id"]]
            self.assertEqual((state["status"], state["attempt_count"], state["last_error_category"]),
                             ("pending", 0, "dependency_pending"))
            self.assertTrue(state["retryable"])
            self.assertFalse(state["ready_to_retry"])
        self.status = 201
        recovered = retry_pending(self.outbox, self.url, retries=0)
        self.assertTrue(recovered["ok"])
        self.assertEqual([record["version"] for record in self.records], [1, 1, 2, 3])

    def test_selected_followup_waits_for_parent_and_direct_submit_also_stays_local(self):
        initial, follow, _ = self.queue_three_versions_with_reversed_names()
        result = retry_pending(self.outbox, self.url, submission_id=follow["submission_id"], retries=0)
        self.assertEqual((result["attempted"], result["deferred"], result["blocked"]), (0, 1, 0))
        self.assertEqual(self.records, [])
        with self.assertRaises(SubmissionError) as failure:
            submit(follow, self.outbox, self.url, retries=0)
        self.assertEqual(failure.exception.category, "dependency_pending")
        self.assertEqual(self.records, [])
        state = get_status(self.outbox, follow["submission_id"])["records"][0]
        self.assertEqual(state["attempt_count"], 0)
        self.assertTrue((self.outbox / (initial["submission_id"] + ".pending.json")).exists())
        submit(initial, self.outbox, self.url, retries=0)
        ready = get_status(self.outbox, follow["submission_id"])["records"][0]
        self.assertTrue(ready["ready_to_retry"])
        self.assertNotIn("last_error_category", ready)

    def test_unexplained_409_remains_blocked_and_is_not_blindly_retried(self):
        self.status = 409
        with self.assertRaises(SubmissionError):
            submit(self.fixture(), self.outbox, self.url, retries=2)
        result = retry_pending(self.outbox, self.url, retries=2)
        self.assertEqual(len(self.records), 1)
        self.assertEqual(result["blocked"], 1)
        self.assertEqual((result["records"][0]["http_status"], result["records"][0]["status"]), (409, "blocked"))


if __name__ == "__main__":
    unittest.main()
