#!/usr/bin/env python3
"""Submit reviewed research records. The outbox contains private write capabilities."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
from research_contract import prepare_case, CaseValidationError

DEFAULT_ENDPOINT = "https://www.zmxx.work/case-report"
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{16,128}")
RETRYABLE_HTTP = {429, 500, 502, 503, 504}
SUCCESS_STATES = {"accepted", "duplicate"}
ERROR_CATEGORIES = {
    "network_timeout", "network_unavailable", "receiver_temporary",
    "receiver_rejected", "invalid_receipt", "redirect_refused",
    "invalid_pending", "authorization_required", "deidentification_required",
    "invalid_schema", "local_storage", "submission_conflict", "invalid_endpoint",
    "dependency_pending",
}


class SubmissionError(Exception):
    def __init__(self, message, category="invalid_pending", retryable=False, http_status=None):
        super().__init__(message)
        self.category = category
        self.retryable = retryable
        self.http_status = http_status


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_status(value, submission_id):
    """Only protocol metadata may leave the outbox through status commands."""
    value = value if isinstance(value, dict) else {}
    result = {
        "submission_id": submission_id,
        "status": value.get("status") if value.get("status") in SUCCESS_STATES | {"pending", "blocked"} else "pending",
        "attempt_count": value.get("attempt_count") if type(value.get("attempt_count")) is int and value["attempt_count"] >= 0 else 0,
        "retryable": value.get("retryable") is True,
    }
    for key in ("created_at", "updated_at", "last_attempt_at", "last_error_at"):
        stamp = value.get(key)
        if isinstance(stamp, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", stamp):
            result[key] = stamp
    if value.get("last_error_category") in ERROR_CATEGORIES:
        result["last_error_category"] = value["last_error_category"]
    if type(value.get("http_status")) is int and 100 <= value["http_status"] <= 599:
        result["http_status"] = value["http_status"]
    receipt_id = value.get("receipt_id")
    if result["status"] in SUCCESS_STATES and isinstance(receipt_id, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", receipt_id):
        result["receipt_id"] = receipt_id
    return result


def _read_status(outbox, submission_id):
    path = Path(outbox) / (submission_id + ".status.json")
    try:
        return _safe_status(json.loads(path.read_text(encoding="utf-8")), submission_id)
    except (OSError, ValueError, TypeError):
        return _safe_status({}, submission_id)


def _save_status(outbox, submission_id, **changes):
    state = _read_status(outbox, submission_id)
    state.update(changes)
    state.setdefault("created_at", utc_now())
    state["updated_at"] = utc_now()
    state = _safe_status(state, submission_id)
    write_private(Path(outbox) / (submission_id + ".status.json"), state)
    return state


def _record_failure(outbox, submission_id, error):
    return _save_status(
        outbox, submission_id, status="pending" if error.retryable else "blocked",
        retryable=error.retryable, last_error_category=error.category,
        last_error_at=utc_now(), http_status=error.http_status,
    )


def _validated_receipt(receipt, case_id, submission_id):
    if (
        not isinstance(receipt, dict) or receipt.get("ok") is not True
        or receipt.get("status") not in SUCCESS_STATES
        or not isinstance(receipt.get("receipt_id"), str)
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", receipt["receipt_id"])
        or receipt.get("case_id") != case_id
        or receipt.get("submission_id") != submission_id
    ):
        raise SubmissionError("No matching accepted/duplicate receipt; pending copy retained.", "invalid_receipt")
    return {key: receipt[key] for key in ("ok", "status", "case_id", "submission_id", "receipt_id")}


def write_private(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(path.parent, 0o700)
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if os.name != "nt":
        os.chmod(temp, 0o600)
    temp.replace(path)


def prepare(record: dict, outbox: Path):
    if not isinstance(record, dict):
        raise SubmissionError("Expected a JSON object.")
    payload = copy.deepcopy(record)
    for field in ("case_id", "submission_id"):
        if not isinstance(payload.get(field), str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", payload[field]):
            raise SubmissionError(f"{field} must be a stable random identifier.")
    key_file = outbox / (payload["case_id"] + ".case-token.json")
    saved = json.loads(key_file.read_text(encoding="utf-8")) if key_file.exists() else {}
    if not isinstance(saved, dict):
        raise SubmissionError("Invalid private case token file.")
    provided = payload.get("case_token")
    if provided and saved.get("case_token") and provided != saved["case_token"]:
        raise SubmissionError("Case token conflicts with the original private outbox.")
    if not provided and not saved.get("case_token") and payload.get("record_type") == "follow_up":
        raise SubmissionError("Follow-up needs the original case token; use the original private outbox.")
    payload["case_token"] = provided or saved.get("case_token") or secrets.token_urlsafe(32)
    # Full shared schema validation and deidentification happen before local persistence or network access.
    payload = prepare_case(payload)
    payload["deidentification"]["identity_terms"] = []
    pending = outbox / (payload["submission_id"] + ".pending.json")
    if pending.exists() and json.loads(pending.read_text(encoding="utf-8")) != payload:
        raise SubmissionError("This submission ID already has different pending content; resolve the version first.", "submission_conflict")
    write_private(key_file, {"case_id": payload["case_id"], "case_token": payload["case_token"]})
    write_private(pending, payload)
    return payload, pending


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SubmissionError("Redirect refused: use the receiver's final HTTPS address.", "redirect_refused")


def _pending_order(path):
    """Send earlier case versions first, regardless of arbitrary submission names."""
    try:
        record = json.loads(path.read_text(encoding="utf-8-sig"))
        case_id, version = record.get("case_id"), record.get("version")
        if isinstance(case_id, str) and type(version) is int and version >= 1:
            return case_id, version, path.name
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return "\uffff", 0, path.name


def _has_pending_dependency(record, outbox):
    """A locally unfinished parent or lower version must precede this record."""
    parent = record.get("parent_submission_id")
    if isinstance(parent, str) and IDENTIFIER.fullmatch(parent):
        if (Path(outbox) / (parent + ".pending.json")).exists():
            return True
    version, case_id = record.get("version"), record.get("case_id")
    if type(version) is not int or version <= 1 or not isinstance(case_id, str):
        return False
    for path in Path(outbox).glob("*.pending.json"):
        if path.name == record.get("submission_id", "") + ".pending.json":
            continue
        try:
            previous = json.loads(path.read_text(encoding="utf-8-sig"))
            if (isinstance(previous, dict) and previous.get("case_id") == case_id
                    and type(previous.get("version")) is int and previous["version"] < version):
                return True
        except (OSError, ValueError, TypeError):
            continue
    return False


def submit(record, outbox, endpoint=DEFAULT_ENDPOINT, prepare_only=False, retries=2, timeout=15):
    target = urlsplit(endpoint)
    local = target.hostname in {"localhost", "127.0.0.1", "::1"}
    if not target.hostname or target.username or target.password or target.fragment or (target.scheme != "https" and not (target.scheme == "http" and local)):
        raise SubmissionError("Use HTTPS; HTTP is permitted only for isolated localhost tests.", "invalid_endpoint")
    if type(retries) is not int or not 0 <= retries <= 5 or not isinstance(timeout, (int, float)) or not 0 < timeout <= 120:
        raise SubmissionError("Use retries from 0 to 5 and a timeout above 0 and at most 120 seconds.")
    outbox = Path(outbox)
    payload, pending = prepare(record, outbox)
    submission_id = payload["submission_id"]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    archive = {k: v for k, v in payload.items() if k != "case_token"}
    receipt_path = outbox / (submission_id + ".receipt.json")
    # A genuine local receipt makes replay safe even after a crash left a pending file.
    if receipt_path.exists():
        try:
            stored = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt = _validated_receipt(stored["receipt"], payload["case_id"], submission_id)
            if stored.get("payload_sha256") != digest or stored.get("record") != archive:
                raise SubmissionError("This submission ID already has different accepted content.", "submission_conflict")
            # Complete a partially written export after a crash without sending again.
            write_private(outbox / (submission_id + ".private-receipt.json"), {"case": payload, "receipt": receipt})
            _save_status(outbox, submission_id, status=receipt["status"], retryable=False, receipt_id=receipt["receipt_id"],
                         last_error_category=None, last_error_at=None, http_status=None)
            pending.unlink(missing_ok=True)
            return receipt
        except (OSError, ValueError, TypeError, KeyError):
            error = SubmissionError("Cannot verify the stored receipt; pending copy retained.", "invalid_receipt")
            _record_failure(outbox, submission_id, error)
            raise error from None
        except SubmissionError as error:
            _record_failure(outbox, submission_id, error)
            raise
    _save_status(outbox, submission_id, status="pending", retryable=True,
                 last_error_category=None, last_error_at=None, http_status=None)
    if prepare_only:
        return {"ok": False, "status": "pending", "pending_file": str(pending)}
    if _has_pending_dependency(payload, outbox):
        error = SubmissionError("An earlier case record is still pending; submit it first.", "dependency_pending", True)
        _record_failure(outbox, submission_id, error)
        raise error
    opener = build_opener(NoRedirect())
    for attempt in range(retries + 1):
        state = _read_status(outbox, submission_id)
        _save_status(outbox, submission_id, attempt_count=state["attempt_count"] + 1, last_attempt_at=utc_now())
        try:
            request = Request(endpoint, data=encoded, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
            with opener.open(request, timeout=timeout) as response:
                receipt = json.loads(response.read(65537))
            receipt = _validated_receipt(receipt, payload["case_id"], submission_id)
        except HTTPError as exc:
            status_code = exc.code
            exc.close()
            temporary = status_code in RETRYABLE_HTTP
            error = SubmissionError(f"Receiver HTTP {status_code}; pending copy retained.",
                                    "receiver_temporary" if temporary else "receiver_rejected",
                                    temporary, status_code)
        except (TimeoutError, ConnectionError, URLError, OSError) as exc:
            timed_out = isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)
            error = SubmissionError("Network unavailable; pending copy retained. Report delivery can continue.",
                                    "network_timeout" if timed_out else "network_unavailable", True)
        except (ValueError, TypeError):
            error = SubmissionError("Invalid receiver response; pending copy retained.", "invalid_receipt")
        except SubmissionError as exc:
            error = exc
        else:
            # Disk failures must not be misclassified as network retries.
            try:
                write_private(receipt_path, {"receipt": receipt, "record": archive, "payload_sha256": digest})
                # This private capability-bearing bundle can be imported by the official feedback page.
                write_private(outbox / (submission_id + ".private-receipt.json"), {"case": payload, "receipt": receipt})
                _save_status(outbox, submission_id, status=receipt["status"], retryable=False, receipt_id=receipt["receipt_id"],
                             last_error_category=None, last_error_at=None, http_status=None)
                pending.unlink(missing_ok=True)
            except OSError:
                error = SubmissionError("Receiver replied, but local receipt storage is incomplete.", "local_storage")
                try:
                    _record_failure(outbox, submission_id, error)
                except OSError:
                    pass
                raise error from None
            return receipt
        _record_failure(outbox, submission_id, error)
        if not error.retryable or attempt == retries:
            raise error from None
        time.sleep(min(2 ** attempt, 2))
    raise SubmissionError("Submission incomplete; pending copy retained.")


def get_status(outbox, submission_id=None):
    """Read sanitized local delivery state without network access or record contents."""
    outbox = Path(outbox)
    if submission_id is not None and not IDENTIFIER.fullmatch(submission_id):
        raise SubmissionError("Invalid submission identifier.")
    identifiers = {submission_id} if submission_id else set()
    if submission_id is None and outbox.exists():
        for suffix in (".pending.json", ".receipt.json", ".status.json"):
            for path in outbox.glob("*" + suffix):
                candidate = path.name[:-len(suffix)]
                if IDENTIFIER.fullmatch(candidate):
                    identifiers.add(candidate)
    entries = []
    for identifier in sorted(identifiers, key=lambda value: _pending_order(outbox / (value + ".pending.json"))):
        pending = outbox / (identifier + ".pending.json")
        receipt_path = outbox / (identifier + ".receipt.json")
        status_path = outbox / (identifier + ".status.json")
        if not any(path.exists() for path in (pending, receipt_path, status_path)):
            continue
        state = _read_status(outbox, identifier)
        if receipt_path.exists():
            try:
                stored = json.loads(receipt_path.read_text(encoding="utf-8"))
                receipt = _validated_receipt(stored["receipt"], stored["record"]["case_id"], identifier)
                if pending.exists():
                    pending_record = json.loads(pending.read_text(encoding="utf-8-sig"))
                    pending_digest = hashlib.sha256(json.dumps(pending_record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
                    if pending_digest != stored.get("payload_sha256"):
                        raise SubmissionError("Pending content conflicts with the accepted record.", "submission_conflict")
                state.update(status=receipt["status"], retryable=False, receipt_id=receipt["receipt_id"])
                for key in ("last_error_category", "last_error_at", "http_status"):
                    state.pop(key, None)
            except SubmissionError as exc:
                state.update(status="blocked", retryable=False, last_error_category=exc.category)
                state.pop("receipt_id", None)
            except (OSError, ValueError, TypeError, KeyError):
                state.update(status="blocked", retryable=False, last_error_category="invalid_receipt")
                state.pop("receipt_id", None)
        elif state["status"] in SUCCESS_STATES:
            state.update(status="blocked", retryable=False, last_error_category="invalid_receipt")
            state.pop("receipt_id", None)
        elif not status_path.exists():
            state.update(status="pending", retryable=True)
        if not pending.exists() and not receipt_path.exists():
            state.update(status="blocked", retryable=False, last_error_category="invalid_pending")
        state["pending"] = pending.exists()
        state["ready_to_retry"] = False
        if state["status"] == "pending" and state["pending"] and state["retryable"]:
            try:
                record = prepare_case(json.loads(pending.read_text(encoding="utf-8-sig")))
                if record.get("submission_id") != identifier:
                    raise SubmissionError("Pending record does not match its filename.")
                state["ready_to_retry"] = not _has_pending_dependency(record, outbox)
                if state["ready_to_retry"] and state.get("last_error_category") == "dependency_pending":
                    state.pop("last_error_category", None)
                    state.pop("last_error_at", None)
            except CaseValidationError as exc:
                category = exc.code if exc.code in ERROR_CATEGORIES else "invalid_schema"
                state.update(status="blocked", retryable=False, last_error_category=category)
            except (OSError, ValueError, TypeError, SubmissionError):
                state.update(status="blocked", retryable=False, last_error_category="invalid_pending")
        entries.append(state)
    return {"ok": True, "status": "local_status", "count": len(entries), "records": entries}


def retry_pending(outbox, endpoint=DEFAULT_ENDPOINT, submission_id=None, retries=2, timeout=15):
    """Explicitly retry only existing validated pending records; never create consent."""
    outbox = Path(outbox)
    if submission_id is not None and not IDENTIFIER.fullmatch(submission_id):
        raise SubmissionError("Invalid submission identifier.")
    paths = [outbox / (submission_id + ".pending.json")] if submission_id else sorted(outbox.glob("*.pending.json"), key=_pending_order)
    attempted = completed = blocked = invalid_filenames = deferred = 0
    for path in paths:
        if not path.exists():
            continue
        identifier = path.name[:-len(".pending.json")]
        if not IDENTIFIER.fullmatch(identifier):
            invalid_filenames += 1
            continue
        state = _read_status(outbox, identifier)
        if state["status"] == "blocked" and not (outbox / (identifier + ".receipt.json")).exists():
            blocked += 1
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(record, dict) or record.get("submission_id") != identifier:
                raise SubmissionError("Pending record does not match its filename.")
            record = prepare_case(record)
            # Do not let a transient parent failure turn a follow-up into a permanent 409.
            if _has_pending_dependency(record, outbox) and not (outbox / (identifier + ".receipt.json")).exists():
                _record_failure(outbox, identifier, SubmissionError(
                    "An earlier case record is still pending; submit it first.", "dependency_pending", True))
                deferred += 1
                continue
            attempted += 1
            submit(record, outbox, endpoint, retries=retries, timeout=timeout)
            completed += 1
        except CaseValidationError as exc:
            category = getattr(exc, "code", "")
            if category not in {"authorization_required", "deidentification_required", "invalid_schema"}:
                category = "invalid_schema"
            _record_failure(outbox, identifier, SubmissionError("Pending record failed validation.", category))
            blocked += 1
        except SubmissionError as exc:
            _record_failure(outbox, identifier, exc)
            blocked += not exc.retryable
        except (OSError, ValueError, TypeError, KeyError):
            _record_failure(outbox, identifier, SubmissionError("Cannot read the pending record.", "invalid_pending"))
            blocked += 1
    status = get_status(outbox, submission_id)
    remaining = sum(entry["pending"] for entry in status["records"]) + invalid_filenames
    blocked = sum(entry["status"] == "blocked" for entry in status["records"]) + invalid_filenames
    return {
        "ok": remaining == 0 and blocked == 0, "status": "retry_complete" if remaining == 0 and blocked == 0 else "pending_or_blocked",
        "attempted": attempted, "completed": completed, "remaining": remaining,
        "blocked": blocked, "deferred": deferred, "invalid_filenames": invalid_filenames, "records": status["records"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--input", type=Path)
    action.add_argument("--status", action="store_true", help="Show local delivery metadata; never contacts the receiver.")
    action.add_argument("--retry-pending", action="store_true", help="Explicitly retry existing authorized pending records.")
    parser.add_argument("--submission-id", help="Limit status or retries to a submission identifier.")
    parser.add_argument("--outbox", type=Path, default=Path.home() / ".zemingxingxiao" / "outbox")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--retries", type=int, choices=range(6), default=2)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    if (args.prepare_only and not args.input) or (args.submission_id and args.input):
        parser.error("--prepare-only requires --input; --submission-id is for --status or --retry-pending.")
    try:
        if args.status:
            result = get_status(args.outbox, args.submission_id)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.retry_pending:
            result = retry_pending(args.outbox, args.endpoint, args.submission_id, args.retries, args.timeout)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["ok"] else 1
        source = json.loads(args.input.read_text(encoding="utf-8-sig"))
        receipt = submit(source, args.outbox, args.endpoint, args.prepare_only, args.retries, args.timeout)
        print(json.dumps(receipt, ensure_ascii=False))
        return 0 if receipt.get("ok") or args.prepare_only else 1
    except (SubmissionError, CaseValidationError, ValueError, OSError) as exc:
        reason = str(exc) if isinstance(exc, (SubmissionError, CaseValidationError)) else "Cannot read/store local record; check private paths."
        print(json.dumps({"ok": False, "status": "pending_or_rejected", "message": reason}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
