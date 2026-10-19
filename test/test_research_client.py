"""Isolated HTTP tests: never contact production or send notifications."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from submit_case import submit, SubmissionError
from research_contract import prepare_case, CaseValidationError


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.outbox = Path(self.tmp.name)
        self.records = []
        self.status = 201
        self.bad_receipt = False
        owner = self

        class Receiver(BaseHTTPRequestHandler):
            def do_POST(self):
                record = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.records.append(record)
                prepare_case(record)
                previous = [r for r in owner.records[:-1] if r["submission_id"] == record["submission_id"]]
                data = {"ok": True, "status": "duplicate" if previous else "accepted", "case_id": record["case_id"], "submission_id": "wrong" if owner.bad_receipt else record["submission_id"], "receipt_id": "local-receipt-1"}
                self.send_response(owner.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

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


if __name__ == "__main__":
    unittest.main()
