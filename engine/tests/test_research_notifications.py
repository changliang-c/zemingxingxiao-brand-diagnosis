"""Synthetic SQLite + mock SMTP only. Never send mail or contact production."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import smtplib
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import httpx
import case_store
import http_server
import research_notifications as notifications
from case_fixtures import initial_case, follow_up_case


SMTP_ENV = {
    "ZMXX_NOTIFY_EMAIL_ENABLED": "1",
    "ZMXX_SMTP_HOST": "smtp.example.invalid",
    "ZMXX_SMTP_PORT": "465",
    "ZMXX_SMTP_SECURITY": "ssl",
    "ZMXX_SMTP_USER": "sender@example.invalid",
    "ZMXX_SMTP_PASSWORD": "SYNTHETIC_SMTP_PASSWORD",
    "ZMXX_SMTP_FROM": "sender@example.invalid",
    "ZMXX_SMTP_TO": "owner@example.invalid",
}


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "research.sqlite3")
        self.env = patch.dict(os.environ, {"ZMXX_CASE_DB": self.db, "ZMXX_NOTIFY_EMAIL_ENABLED": ""})
        self.env.start()
        self.addCleanup(self.env.stop)
        # Every test blocks both SMTP transports unless it provides a mock.
        self.smtp = patch.object(notifications.smtplib, "SMTP_SSL", side_effect=AssertionError("Real SMTP forbidden"))
        self.smtp.start()
        self.addCleanup(self.smtp.stop)
        self.smtp_plain = patch.object(notifications.smtplib, "SMTP", side_effect=AssertionError("Real SMTP forbidden"))
        self.smtp_plain.start()
        self.addCleanup(self.smtp_plain.stop)

    def status(self):
        return notifications.read_status(self.db)

    def execute(self, sql, params=()):
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def test_default_inbox_duplicate_and_atomic_failure(self):
        first = case_store.accept_case(initial_case(), self.db)
        duplicate = case_store.accept_case(initial_case(), self.db)
        status = self.status()
        self.assertEqual(status["notification_counts"], {"inbox_only": 1})
        self.assertEqual(status["recent_notifications"][0]["receipt_id"], first["receipt_id"])
        self.assertEqual(first["receipt_id"], duplicate["receipt_id"])
        self.assertEqual(notifications.run_once(self.db)["state"], "email_disabled")
        with patch.object(notifications, "enqueue", side_effect=sqlite3.OperationalError("test queue failure")):
            with self.assertRaises(sqlite3.OperationalError):
                case_store.accept_case(follow_up_case(), self.db)
        self.assertEqual(self.status()["counts"]["records"], 1)
        self.assertEqual(case_store.read_cases(self.db)["items"][0]["receipt"]["receipt_id"], first["receipt_id"])

    def test_existing_rows_backfill_inbox_only_even_when_email_enabled(self):
        case_store.accept_case(initial_case(), self.db)
        self.execute("DROP TABLE research_notifications")
        self.execute("DROP TABLE research_notification_worker")
        with patch.dict(os.environ, SMTP_ENV):
            for _ in range(2):
                case_store._connect(self.db).close()
            self.assertEqual(self.status()["notification_counts"], {"inbox_only": 1})
            case_store.accept_case(follow_up_case(), self.db)
            self.assertEqual(self.status()["notification_counts"], {"inbox_only": 1, "pending": 1})

    def test_concurrent_workers_send_once_and_mail_is_metadata_only(self):
        smtp = MagicMock()
        smtp.send_message.return_value = {}
        with patch.dict(os.environ, SMTP_ENV), patch.object(notifications.smtplib, "SMTP_SSL", return_value=smtp):
            case_store.accept_case(initial_case(), self.db)
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _: notifications.run_once(self.db), range(8)))
            self.assertEqual(smtp.send_message.call_count, 1)
            msg = smtp.send_message.call_args.args[0]
            body = msg.get_content()
            for excluded in ("350000.75", "120", "SYNTHETIC_ONLY", "case_token", "observations", "reasoning", "SYNTHETIC_SMTP_PASSWORD"):
                self.assertNotIn(excluded, body)
            self.assertIn("source_platform", body)
            self.assertIn("receipt_id", body)
            self.assertIn("case_id", body)
            self.assertEqual(self.status()["notification_counts"], {"sent": 1})
            self.assertEqual(notifications.notification_health(self.db)["email"]["state"], "ready")
            conn = case_store._connect(self.db)
            try:
                self.assertIsNone(notifications._claim(conn))
            finally:
                conn.close()

    def test_failures_retry_bounded_with_safe_categories_and_no_case_loss(self):
        failure = smtplib.SMTPAuthenticationError(535, b"PRIVATE_CREDENTIAL_MESSAGE")
        with patch.dict(os.environ, SMTP_ENV), patch.object(notifications.smtplib, "SMTP_SSL", side_effect=failure):
            first = case_store.accept_case(initial_case(), self.db)
            for attempt in range(notifications.MAX_ATTEMPTS):
                notifications.run_once(self.db)
                status = self.status()
                item = status["recent_notifications"][0]
                self.assertEqual(item["attempts"], attempt + 1)
                self.assertEqual(item["last_error_code"], "smtp_authentication_failed")
                self.assertNotIn("PRIVATE_CREDENTIAL_MESSAGE", json.dumps(status))
                if attempt < notifications.MAX_ATTEMPTS - 1:
                    self.assertEqual(item["state"], "retry")
                    self.assertGreater(item["next_attempt_at"], item["updated_at"])
                    self.execute("UPDATE research_notifications SET next_attempt_at='2000-01-01T00:00:00+00:00'")
            self.assertEqual(self.status()["notification_counts"], {"failed": 1})
            notifications.run_once(self.db)
            self.assertEqual(self.status()["recent_notifications"][0]["attempts"], notifications.MAX_ATTEMPTS)
            self.assertEqual(case_store.read_cases(self.db)["items"][0]["receipt"]["receipt_id"], first["receipt_id"])

    def test_missing_config_does_not_claim_and_public_health_hides_settings(self):
        with patch.dict(os.environ, {"ZMXX_NOTIFY_EMAIL_ENABLED": "1", "ZMXX_SMTP_PASSWORD": "", "ZMXX_SMTP_HOST": ""}):
            case_store.accept_case(initial_case(), self.db)
            self.assertEqual(notifications.run_once(self.db)["state"], "config_missing")
            status = self.status()
            self.assertEqual(status["recent_notifications"][0]["attempts"], 0)
            self.assertEqual(status["notifications"]["email"]["state"], "config_missing")
            self.assertIn("ZMXX_SMTP_PASSWORD", status["notifications"]["email"]["missing_or_invalid_settings"])
            health = json.dumps(notifications.notification_health(self.db))
            self.assertNotIn("ZMXX_SMTP_PASSWORD", health)
            self.assertNotIn("@", health)

    def test_uncertain_data_delivery_is_not_automatically_resent(self):
        smtp = MagicMock()
        smtp.send_message.side_effect = TimeoutError("private transport detail")
        with patch.dict(os.environ, SMTP_ENV), patch.object(notifications.smtplib, "SMTP_SSL", return_value=smtp):
            case_store.accept_case(initial_case(), self.db)
            notifications.run_once(self.db)
            self.assertEqual(self.status()["notification_counts"], {"delivery_uncertain": 1})
            notifications.run_once(self.db)
            self.assertEqual(smtp.send_message.call_count, 1)

    def test_interrupted_send_and_pre_send_lease_recovery(self):
        smtp = MagicMock()
        smtp.send_message.return_value = {}
        with patch.dict(os.environ, SMTP_ENV), patch.object(notifications.smtplib, "SMTP_SSL", return_value=smtp):
            case_store.accept_case(initial_case(), self.db)
            case_store.accept_case(follow_up_case(), self.db)
            self.execute("UPDATE research_notifications SET state='sending',lease_until='2000-01-01T00:00:00+00:00' WHERE record_id=1")
            self.execute("UPDATE research_notifications SET state='leased',lease_until='2000-01-01T00:00:00+00:00' WHERE record_id=2")
            notifications.run_once(self.db)
            self.assertEqual(self.status()["notification_counts"], {"delivery_uncertain": 1, "sent": 1})
            self.assertEqual(smtp.send_message.call_count, 1)

    def test_retention_cascades_and_status_is_read_only(self):
        case_store.accept_case(initial_case(), self.db)
        self.execute("UPDATE records SET expires_at='2000-01-01T00:00:00+00:00'")
        self.assertEqual(self.status()["counts"]["records"], 1)  # no purging in reads
        case_store.purge_expired(self.db)
        self.assertEqual(self.status()["notification_counts"], {})


class NotificationHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "research.sqlite3")
        self.token = "ISOLATED_ADMIN_CAPABILITY_012345678901234567890"
        self.env = patch.dict(os.environ, {"ZMXX_CASE_DB": self.db, "ZMXX_CASE_READ_TOKEN": self.token,
                                          "ZMXX_NOTIFY_EMAIL_ENABLED": ""})
        self.env.start()
        self.addCleanup(self.env.stop)
        http_server._case_rate.clear()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=http_server.app), base_url="https://www.zmxx.work")
        self.addAsyncCleanup(self.client.aclose)

    async def test_http_and_mcp_share_atomic_inbox_and_private_read(self):
        from types import SimpleNamespace
        initial = await self.client.post("/case-report", json=initial_case())
        follow = await http_server._call_tool(SimpleNamespace(request=None),
            SimpleNamespace(name="record_follow_up", arguments=follow_up_case()))
        self.assertEqual(initial.status_code, 201)
        self.assertEqual(json.loads(follow.content[0].text)["status"], "accepted")
        for path in ("/case-report/status", "/case-report/status?token=" + self.token):
            self.assertEqual((await self.client.get(path)).status_code, 401)
        headers = {"Authorization": "Bearer " + self.token}
        result = await self.client.get("/case-report/status", headers=headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["counts"]["records"], 2)
        self.assertEqual(result.json()["notification_counts"], {"inbox_only": 2})
        self.assertEqual(result.headers["cache-control"], "no-store")
        for excluded in ("case_token", "observations", "350000.75", "SYNTHETIC_ONLY", "token_hash"):
            self.assertNotIn(excluded, result.text)
        self.assertEqual((await self.client.get("/case-report/status?n=0", headers=headers)).status_code, 400)
        self.assertEqual((await self.client.get("/health")).json()["version"], "2.6.0")


if __name__ == "__main__":
    unittest.main()
