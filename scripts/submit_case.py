#!/usr/bin/env python3
"""Submit reviewed research records. The outbox contains private write capabilities."""
from __future__ import annotations
import argparse
import copy
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


class SubmissionError(Exception):
    pass


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
        raise SubmissionError("This submission ID already has different pending content; resolve the version first.")
    write_private(key_file, {"case_id": payload["case_id"], "case_token": payload["case_token"]})
    write_private(pending, payload)
    return payload, pending


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SubmissionError("Redirect refused: use the receiver's final HTTPS address.")


def submit(record, outbox, endpoint=DEFAULT_ENDPOINT, prepare_only=False, retries=2, timeout=15):
    target = urlsplit(endpoint)
    local = target.hostname in {"localhost", "127.0.0.1", "::1"}
    if target.username or target.password or target.fragment or (target.scheme != "https" and not (target.scheme == "http" and local)):
        raise SubmissionError("Use HTTPS; HTTP is permitted only for isolated localhost tests.")
    payload, pending = prepare(record, Path(outbox))
    if prepare_only:
        return {"ok": False, "status": "pending", "pending_file": str(pending)}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    opener = build_opener(NoRedirect())
    for attempt in range(retries + 1):
        try:
            request = Request(endpoint, data=encoded, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
            with opener.open(request, timeout=timeout) as response:
                receipt = json.loads(response.read(65537))
            if not isinstance(receipt, dict) or receipt.get("ok") is not True or receipt.get("status") not in {"accepted", "duplicate"} or not isinstance(receipt.get("receipt_id"), str) or not receipt["receipt_id"].strip() or receipt.get("case_id") != payload["case_id"] or receipt.get("submission_id") != payload["submission_id"]:
                raise SubmissionError("No matching accepted/duplicate receipt; pending copy retained.")
            archive = {k: v for k, v in payload.items() if k != "case_token"}
            write_private(Path(outbox) / (payload["submission_id"] + ".receipt.json"), {"receipt": receipt, "record": archive, "payload_sha256": hashlib.sha256(encoded).hexdigest()})
            # This private capability-bearing bundle can be imported by the official feedback page.
            write_private(Path(outbox) / (payload["submission_id"] + ".private-receipt.json"), {"case": payload, "receipt": receipt})
            pending.unlink(missing_ok=True)
            return receipt
        except HTTPError as exc:
            status_code = exc.code
            exc.close()
            if status_code not in {429, 500, 502, 503, 504} or attempt == retries:
                raise SubmissionError(f"Receiver HTTP {status_code}; pending copy retained.") from None
        except (URLError, TimeoutError, ConnectionError, OSError):
            if attempt == retries:
                raise SubmissionError("Network unavailable; pending copy retained. Report delivery can continue.") from None
        except (ValueError, TypeError):
            raise SubmissionError("Invalid receiver response; pending copy retained.") from None
        if attempt < retries:
            time.sleep(min(2 ** attempt, 2))
    raise SubmissionError("Submission incomplete; pending copy retained.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--outbox", type=Path, default=Path.home() / ".zemingxingxiao" / "outbox")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    try:
        source = json.loads(args.input.read_text(encoding="utf-8-sig"))
        receipt = submit(source, args.outbox, args.endpoint, args.prepare_only)
        print(json.dumps(receipt, ensure_ascii=False))
        return 0 if receipt.get("ok") or args.prepare_only else 1
    except (SubmissionError, CaseValidationError, ValueError, OSError) as exc:
        reason = str(exc) if isinstance(exc, (SubmissionError, CaseValidationError)) else "Cannot read/store local record; check private paths."
        print(json.dumps({"ok": False, "status": "pending_or_rejected", "message": reason}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
