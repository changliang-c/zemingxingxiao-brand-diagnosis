#!/usr/bin/env python3
"""Private durable inbox and optional SMTP worker; no credentials in source.

Run ``python research_notifications.py worker`` under systemd with the same
private EnvironmentFile as the API. The default records inbox entries only.
SMTP delivery cannot be exactly once: a crash after DATA may have delivered the
message. Such entries become delivery_uncertain and are never retried blindly.
"""
import argparse
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime
import hashlib
import json
import os
import re
import secrets
import signal
import smtplib
import socket
import sqlite3
import ssl
import threading

MAX_ATTEMPTS = 5
LEASE_SECONDS = 180
HEARTBEAT_SECONDS = 90


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def email_enabled():
    return os.environ.get("ZMXX_NOTIFY_EMAIL_ENABLED", "").lower() in ("1", "true", "yes")


def _configuration():
    """EnvironmentFile parsing belongs to the service manager, never to eval."""
    cfg = {key: os.environ.get("ZMXX_SMTP_" + key.upper(), "") for key in
           ("host", "user", "password", "from", "to")}
    cfg["security"] = os.environ.get("ZMXX_SMTP_SECURITY", "ssl").lower()
    errors = ["ZMXX_SMTP_" + key.upper() for key, value in cfg.items()
              if key != "security" and not value]
    try:
        cfg["port"] = int(os.environ.get("ZMXX_SMTP_PORT", "465" if cfg["security"] == "ssl" else "587"))
        if not 1 <= cfg["port"] <= 65535:
            raise ValueError()
    except ValueError:
        errors.append("ZMXX_SMTP_PORT")
    if cfg["security"] not in ("ssl", "starttls"):
        errors.append("ZMXX_SMTP_SECURITY")
    for key in ("from", "to"):
        # Exactly one mailbox; reject header injection and surprise recipients.
        if cfg[key] and not re.fullmatch(r"[^@\s<>,;\r\n]+@[^@\s<>,;\r\n]+\.[^@\s<>,;\r\n]+", cfg[key]):
            errors.append("ZMXX_SMTP_" + key.upper())
    if cfg["host"] and (any(c.isspace() for c in cfg["host"]) or "/" in cfg["host"]):
        errors.append("ZMXX_SMTP_HOST")
    return cfg, sorted(set(errors))


def ensure_schema(conn):
    """Called while initializing the store, before the intake transaction."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS research_notifications(
            record_id INTEGER PRIMARY KEY REFERENCES records(id) ON DELETE CASCADE,
            notification_id TEXT UNIQUE NOT NULL,
            state TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TEXT,
            lease_id TEXT,
            lease_until TEXT,
            last_error_code TEXT,
            sent_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS research_notifications_due
            ON research_notifications(state,next_attempt_at);
        CREATE TABLE IF NOT EXISTS research_notification_worker(
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            state TEXT NOT NULL, heartbeat_at TEXT NOT NULL
        );
        -- Upgrade backfill is deliberately inbox-only, including when email
        -- has been enabled for future records. Repeated migration is harmless.
        INSERT OR IGNORE INTO research_notifications(
            record_id,notification_id,state,created_at,updated_at)
        SELECT id,'notice_' || receipt_id,'inbox_only',received_at,received_at
        FROM records;
    """)


def enqueue(conn, row):
    """Must run in the SAME transaction as inserting the accepted record."""
    state = "pending" if email_enabled() else "inbox_only"
    conn.execute("""INSERT INTO research_notifications
        (record_id,notification_id,state,next_attempt_at,created_at,updated_at)
        VALUES(?,?,?,?,?,?)""",
        (row["id"], "notice_" + row["receipt_id"], state, row["received_at"],
         row["received_at"], row["received_at"]))


def _read_connection(store_path=None):
    from case_store import _db_path
    path = _db_path(store_path).resolve()
    if not path.exists():
        return None
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def notification_health(store_path=None):
    """Public operational facts only: no addresses, cases, tokens or counts."""
    enabled = email_enabled()
    _, errors = _configuration()
    result = {"inbox": {"enabled": True, "state": "not_initialized"},
              "email": {"enabled": enabled, "configured": not errors,
                        "state": "disabled" if not enabled else "config_missing" if errors else "worker_unavailable"},
              "worker": {"state": "not_seen", "heartbeat_at": None}}
    conn = None
    try:
        conn = _read_connection(store_path)
        if conn:
            conn.execute("SELECT record_id FROM research_notifications LIMIT 1").fetchone()
            result["inbox"]["state"] = "ready"
            row = conn.execute("SELECT state,heartbeat_at FROM research_notification_worker WHERE singleton=1").fetchone()
            if row:
                fresh = (_now() - datetime.fromisoformat(row["heartbeat_at"])).total_seconds() <= HEARTBEAT_SECONDS
                result["worker"] = {"state": row["state"] if fresh else "stale",
                                    "heartbeat_at": row["heartbeat_at"]}
                if enabled and not errors and fresh and row["state"] in ("idle", "processing"):
                    result["email"]["state"] = "ready"
    except (sqlite3.Error, ValueError, OSError):
        result["inbox"]["state"] = "unavailable"
    finally:
        if conn:
            conn.close()
    return result


def read_status(store_path=None, limit=50):
    """Read-only admin view. Authentication is enforced by the HTTP caller."""
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    result = {"ok": True, "notifications": notification_health(store_path),
              "counts": {"cases": 0, "records": 0, "diagnosis": 0, "follow_up": 0, "legacy_quarantined": 0},
              "notification_counts": {}, "recent_notifications": []}
    _, errors = _configuration()
    result["notifications"]["email"]["missing_or_invalid_settings"] = errors if email_enabled() else []
    conn = _read_connection(store_path)
    if conn is None:
        return result
    try:
        for key, table in (("cases", "cases"), ("records", "records"), ("legacy_quarantined", "legacy_quarantine")):
            result["counts"][key] = conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
        result["counts"].update(dict(conn.execute("SELECT record_type,COUNT(*) FROM records GROUP BY record_type")))
        result["notification_counts"] = dict(conn.execute(
            "SELECT state,COUNT(*) FROM research_notifications GROUP BY state"))
        rows = conn.execute("""SELECT n.notification_id,n.state,n.attempts,n.next_attempt_at,
            n.last_error_code,n.sent_at,n.created_at,n.updated_at,
            r.case_id,r.receipt_id,r.record_type,r.received_at,r.payload
            FROM research_notifications n JOIN records r ON r.id=n.record_id
            ORDER BY r.id DESC LIMIT ?""", (limit,)).fetchall()
        for row in rows:
            item = dict(row)
            item["source_platform"] = json.loads(item.pop("payload"))["source_platform"]
            result["recent_notifications"].append(item)
        return result
    finally:
        conn.close()


def _heartbeat(conn, state):
    conn.execute("""INSERT INTO research_notification_worker VALUES(1,?,?)
        ON CONFLICT(singleton) DO UPDATE SET state=excluded.state,heartbeat_at=excluded.heartbeat_at""",
        (state, _now().isoformat()))
    conn.commit()


def _claim(conn):
    now = _now()
    conn.execute("BEGIN IMMEDIATE")
    try:
        # A lease that expired before DATA started can safely be retried.
        conn.execute("""UPDATE research_notifications SET state=CASE WHEN attempts>=? THEN 'failed' ELSE 'retry' END,
            lease_id=NULL,lease_until=NULL,
            last_error_code='worker_interrupted_before_send',next_attempt_at=?,updated_at=?
            WHERE state='leased' AND lease_until < ?""", (MAX_ATTEMPTS, now.isoformat(), now.isoformat(), now.isoformat()))
        # SMTP may already have accepted DATA. Do not send it a second time.
        conn.execute("""UPDATE research_notifications SET state='delivery_uncertain',lease_id=NULL,
            lease_until=NULL,last_error_code='delivery_ack_unknown',updated_at=?
            WHERE state='sending' AND lease_until < ?""", (now.isoformat(), now.isoformat()))
        row = conn.execute("""SELECT n.*,r.case_id,r.receipt_id,r.record_type,r.received_at,r.payload
            FROM research_notifications n JOIN records r ON r.id=n.record_id
            WHERE n.state IN ('pending','retry') AND n.next_attempt_at <= ? AND n.attempts < ? AND r.expires_at>=?
            ORDER BY n.record_id LIMIT 1""", (now.isoformat(), MAX_ATTEMPTS, now.isoformat())).fetchone()
        if not row:
            conn.commit()
            return None
        item = dict(row)
        item["lease_id"] = secrets.token_hex(16)
        conn.execute("""UPDATE research_notifications SET state='leased',attempts=attempts+1,
            lease_id=?,lease_until=?,updated_at=? WHERE record_id=?""",
            (item["lease_id"], (now + timedelta(seconds=LEASE_SECONDS)).isoformat(),
             now.isoformat(), item["record_id"]))
        conn.commit()
        item["attempts"] += 1
        return item
    except BaseException:
        conn.rollback()
        raise


def _message(item, cfg):
    msg = EmailMessage()
    msg["Subject"] = "择命行效收到新的研究记录"
    msg["From"], msg["To"] = cfg["from"], cfg["to"]
    msg["Date"] = format_datetime(datetime.fromisoformat(item["received_at"]))
    digest = hashlib.sha256(item["notification_id"].encode()).hexdigest()
    msg["Message-ID"] = "<" + digest + "@notifications.zmxx.work>"
    payload = json.loads(item["payload"])
    # Strict metadata whitelist; never include the business report or capability.
    metadata = {"record_type": item["record_type"], "source_platform": payload["source_platform"],
                "received_at": item["received_at"], "receipt_id": item["receipt_id"],
                "case_id": item["case_id"]}
    msg.set_content("已收到研究记录，请在私有研究面板查看。\n\n" +
                    json.dumps(metadata, ensure_ascii=False, indent=2))
    return msg


def _error_code(exc):
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "smtp_authentication_failed"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "smtp_recipient_rejected"
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return "smtp_sender_rejected"
    if isinstance(exc, smtplib.SMTPDataError):
        return "smtp_data_rejected"
    if isinstance(exc, ssl.SSLError):
        return "smtp_tls_failed"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "smtp_timeout"
    if isinstance(exc, smtplib.SMTPException):
        return "smtp_protocol_failed"
    if isinstance(exc, OSError):
        return "smtp_connection_failed"
    return "notification_worker_failed"


def _deliver(conn, item, cfg):
    smtp = None
    sending = False
    error = None
    try:
        context = ssl.create_default_context()
        if cfg["security"] == "ssl":
            smtp = smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=context, timeout=20)
        else:
            smtp = smtplib.SMTP(cfg["host"], cfg["port"], timeout=20)
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(cfg["user"], cfg["password"])
        # Commit before attempting DATA, so a crash cannot silently cause retry.
        now = _now()
        changed = conn.execute("""UPDATE research_notifications SET state='sending',updated_at=?
            WHERE record_id=? AND state='leased' AND lease_id=? AND lease_until>=?""",
            (now.isoformat(), item["record_id"], item["lease_id"], now.isoformat())).rowcount
        conn.commit()
        if not changed:
            return
        sending = True
        refused = smtp.send_message(_message(item, cfg), from_addr=cfg["from"], to_addrs=[cfg["to"]])
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    except Exception as exc:
        error = exc
    finally:
        if smtp:
            try:
                smtp.close()
            except Exception:
                pass
    now = _now()
    if error is None:
        state, code, due, sent = "sent", None, None, now.isoformat()
    else:
        code = _error_code(error)
        known_rejection = isinstance(error, (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError))
        if sending and not known_rejection:
            state = "delivery_uncertain"
        else:
            state = "failed" if item["attempts"] >= MAX_ATTEMPTS else "retry"
        due = (now + timedelta(seconds=min(3600, 30 * 2 ** (item["attempts"] - 1)))).isoformat() if state == "retry" else None
        sent = None
    conn.execute("""UPDATE research_notifications SET state=?,last_error_code=?,next_attempt_at=?,
        sent_at=?,lease_id=NULL,lease_until=NULL,updated_at=? WHERE record_id=? AND lease_id=?""",
        (state, code, due, sent, now.isoformat(), item["record_id"], item["lease_id"]))
    conn.commit()


def run_once(store_path=None):
    """Process at most one row. Used by the worker and isolated tests."""
    from case_store import _connect
    conn = _connect(store_path)
    try:
        cfg, errors = _configuration()
        if not email_enabled():
            _heartbeat(conn, "email_disabled")
            return {"ok": True, "state": "email_disabled"}
        if errors:
            _heartbeat(conn, "config_missing")
            return {"ok": False, "state": "config_missing"}
        item = _claim(conn)
        _heartbeat(conn, "processing" if item else "idle")
        if item:
            _deliver(conn, item, cfg)
        _heartbeat(conn, "idle")
        return {"ok": True, "state": "processed" if item else "idle"}
    finally:
        conn.close()


def worker(store_path=None):
    from case_store import _connect
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    try:
        while not stop.is_set():
            result = run_once(store_path)
            if result["state"] != "processed":
                stop.wait(10)
    finally:
        conn = _connect(store_path)
        try:
            _heartbeat(conn, "stopped")
        finally:
            conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Private research inbox/SMTP worker; default email disabled.")
    parser.add_argument("command", choices=("worker", "migrate", "status"))
    parser.add_argument("--database")
    args = parser.parse_args()
    if args.command == "worker":
        worker(args.database)
    elif args.command == "migrate":
        from case_store import _connect
        connection = _connect(args.database)
        connection.close()
        print(json.dumps({"ok": True, "backfill": "inbox_only"}))
    else:
        print(json.dumps(read_status(args.database), ensure_ascii=False))
