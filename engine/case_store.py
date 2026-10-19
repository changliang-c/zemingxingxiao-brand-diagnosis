#!/usr/bin/env python3
"""Private, de-identified research records. Standard library only; no notifications.

The caller must review identity clues BEFORE network transmission. Pattern cleanup
is defence in depth, not a claim that arbitrary text is anonymous.
"""
import copy
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

VERSION = "2.5.0"
SCHEMA_VERSION = "3.0"
MAX_BODY = 256 * 1024
RETENTION_DAYS = 730


class CaseValidationError(ValueError):
    def __init__(self, code, message, status_code=400):
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


def _string(max_length=12000, min_length=1):
    return {"type": "string", "minLength": min_length, "maxLength": max_length}


def _enum(*items):
    return {"type": "string", "enum": list(items)}


def _array(item=None, minimum=0):
    return {"type": "array", "items": item or _string(), "minItems": minimum, "maxItems": 200}


def _object(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


NUMBER = {"type": ["number", "null"]}
EVIDENCE_TYPE = _enum("measured", "user_reported", "estimate", "model_inference")
IDENTIFIER = {"type": "string", "pattern": r"^[A-Za-z0-9_-]{16,128}$"}
PERIOD = _object({"start": _string(10), "end": _string(10),
                  "window_days": {"type": "integer", "minimum": 1}, "matured": {"type": "boolean"}})
OBSERVATION = _object({
    "observation_id": _string(128), "metric": _string(300), "value": NUMBER,
    "unit": _string(100), "numerator": NUMBER, "denominator": NUMBER,
    "period": PERIOD, "definition": _string(), "source": _string(),
    "evidence_type": EVIDENCE_TYPE, "population": _string(), "missing": _array(),
})
EVIDENCE = _object({
    "evidence_id": _string(128), "statement": _string(), "evidence_type": EVIDENCE_TYPE,
    "source": _string(), "observation_refs": _array(_string(128)), "limitations": _array(),
})
ACTION = _object({
    "action_id": _string(128), "description": _string(),
    "status": _enum("planned", "not_started", "in_progress", "completed", "stopped"),
    "start_date": _string(10, 0), "end_date": _string(10, 0),
    "investment": NUMBER, "investment_unit": _string(100), "scope": _string(),
    "execution_extent": _string(), "concurrent_changes": _array(), "evidence_refs": _array(_string(128)),
})
DIAGNOSIS = _object({
    "primary_break": _string(), "secondary_breaks": _array(), "reasoning": _string(),
    "supporting_evidence": _array(_string(128)), "counter_evidence": _array(),
    "alternative_explanations": _array(), "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "missing_evidence": _array(), "theory_version": _string(100),
})
PREDICTION = _object({
    "prediction_id": _string(128), "action_ids": _array(_string(128), 1),
    "metric": _string(300), "baseline_observation_id": _string(128), "expected_change": _string(),
    "deadline": _string(10), "falsification": _string(),
})
OUTCOME = _object({
    "observation_id": _string(128), "baseline_observation_id": _string(128),
    "result": _enum("improved", "no_change", "worsened", "mixed", "unknown"),
    "sample_size": {"type": ["integer", "null"], "minimum": 0}, "observation_window": _string(),
    "control": _string(), "confounders": _array(), "attribution": _enum("unestablished", "supported", "contradicted"),
    "interpretation": _string(), "adverse_effects": _array(),
})
CASE_SCHEMA = _object({
    "schema_version": {"const": SCHEMA_VERSION}, "record_type": _enum("diagnosis", "follow_up"),
    "case_id": IDENTIFIER, "submission_id": IDENTIFIER,
    "case_token": {"type": "string", "pattern": r"^[A-Za-z0-9_-]{32,256}$", "writeOnly": True},
    "version": {"type": "integer", "minimum": 1}, "parent_submission_id": IDENTIFIER,
    "source_platform": _string(100), "skill_version": _string(100), "report_language": _enum("zh-CN", "en"),
    "authorization": _object({"status": _enum("authorized", "not_authorized", "confidential", "unknown"),
                               "purpose": {"const": "internal_research"}, "basis": _string(2000)}),
    "deidentification": _object({"reviewed": {"type": "boolean"}, "identity_terms": _array(_string(300)),
                                  "residual_risk": _enum("low", "unresolved")}, ["reviewed", "residual_risk"]),
    "context": _object({"industry": _string(300), "business_model": _string(), "stage": _string(300),
                         "scale_band": _string(300), "customer_segment": _string(), "purchase_scenario": _string(),
                         "channels": _array(), "goal": _string(), "constraints": _array()}),
    "observations": _array(OBSERVATION, 1), "evidence": _array(EVIDENCE, 1), "diagnosis": DIAGNOSIS,
    "predictions": _array(PREDICTION), "recommended_actions": _array(ACTION), "actual_actions": _array(ACTION),
    "outcomes": _array(OUTCOME), "objections": _array(),
}, ["schema_version", "record_type", "case_id", "submission_id", "case_token", "version", "source_platform",
    "skill_version", "report_language", "authorization", "deidentification", "context", "observations", "evidence",
    "diagnosis", "predictions", "recommended_actions", "actual_actions", "outcomes", "objections"])
CASE_SCHEMA["$schema"] = "https://json-schema.org/draft/2020-12/schema"
CASE_SCHEMA["title"] = "择命行效 private research case v3"
CASE_SCHEMA["allOf"] = [
    {"if": {"properties": {"record_type": {"const": "follow_up"}}},
     "then": {"required": ["parent_submission_id"], "properties": {
         "actual_actions": {"minItems": 1}, "outcomes": {"minItems": 1}, "version": {"minimum": 2}}}},
    {"if": {"properties": {"record_type": {"const": "diagnosis"}}},
     "then": {"properties": {"recommended_actions": {"minItems": 1}, "predictions": {"minItems": 1}}}},
]

_DROP_KEYS = frozenset({"brand", "brand_name", "company", "company_name", "business_name", "person", "person_name",
    "customer_name", "customer_id", "name", "contact", "email", "phone", "mobile", "address", "exact_location",
    "latitude", "longitude", "id_card", "identity_number", "source_ip", "ip", "raw_conversation", "transcript",
    "品牌", "品牌名", "公司名", "姓名", "负责人", "客户明细", "地址", "电话", "邮箱", "身份证"})
_EMAIL = re.compile(r"(?i)[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")
_URL = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\]\[\"']+")
_IDCARD = re.compile(r"(?<!\d)\d{6}(?:19|20)\d{2}(?:0[1-9]|1[012])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?!\d)")
_PHONE = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")
_CONTACT = re.compile(r"(?i)(?:电话|手机|微信|联系人|负责人|地址|门店地址|姓名|品牌名称|公司名称|phone|contact|address)\s*[:：]\s*[^\n，,；;。]+")


def _validate(value, schema, path="case", depth=0):
    if depth > 14:
        raise CaseValidationError("invalid_schema", "Record nesting exceeds limit.")
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    checks = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
              "string": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool),
              "number": lambda v: type(v) is int or (type(v) is float and math.isfinite(v)),
              "integer": lambda v: type(v) is int, "null": lambda v: v is None}
    if kind and not any(checks[k](value) for k in kinds):
        raise CaseValidationError("invalid_schema", "Invalid type at " + path)
    if "const" in schema and value != schema["const"]:
        raise CaseValidationError("invalid_schema", "Unsupported value at " + path)
    if "enum" in schema and value not in schema["enum"]:
        raise CaseValidationError("invalid_schema", "Unsupported value at " + path)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 12000):
            raise CaseValidationError("invalid_schema", "Invalid length at " + path)
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise CaseValidationError("invalid_schema", "Invalid identifier at " + path)
    if type(value) in (int, float):
        if value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf):
            raise CaseValidationError("invalid_schema", "Number out of range at " + path)
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if any(k not in value for k in schema.get("required", [])):
            missing = [k for k in schema.get("required", []) if k not in value]
            raise CaseValidationError("invalid_schema", "Missing fields at " + path + ": " + ", ".join(missing))
        if schema.get("additionalProperties") is False and any(k not in properties for k in value):
            raise CaseValidationError("invalid_schema", "Unexpected fields at " + path)
        for key, item in value.items():
            _validate(item, properties.get(key, {}), path + "." + key, depth + 1)
    if isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 200):
            raise CaseValidationError("invalid_schema", "Invalid item count at " + path)
        for item in value:
            _validate(item, schema.get("items", {}), path + "[]", depth + 1)


def _sanitize(value, terms, depth=0):
    if depth > 14:
        raise CaseValidationError("invalid_schema", "Record nesting exceeds limit.")
    if isinstance(value, dict):
        return {k: _sanitize(v, terms, depth + 1) for k, v in value.items()
                if k.lower() not in _DROP_KEYS and k != "identity_terms"}
    if isinstance(value, list):
        return [_sanitize(v, terms, depth + 1) for v in value]
    if isinstance(value, str):
        for term in terms:
            value = re.sub(re.escape(term), "[identity removed]", value, flags=re.IGNORECASE)
        for pattern in (_EMAIL, _URL, _IDCARD, _PHONE, _CONTACT):
            value = pattern.sub("[identity removed]", value)
        return value
    return value


def prepare_case(payload):
    """Validate authority, remove direct identifiers, preserve business measurements.

    Returns a stable transport object INCLUDING the case write capability. Do not
    put this object in public reports. identity_terms are never returned/stored.
    """
    if not isinstance(payload, dict):
        raise CaseValidationError("invalid_schema", "A JSON object is required.")
    try:
        if len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_BODY:
            raise CaseValidationError("payload_too_large", "Record exceeds 256 KiB.", 413)
    except CaseValidationError:
        raise
    except (ValueError, TypeError, RecursionError):
        raise CaseValidationError("invalid_schema", "Record must contain finite JSON values.")
    auth = payload.get("authorization")
    if not isinstance(auth, dict) or auth.get("status") != "authorized" or auth.get("purpose") != "internal_research" or not str(auth.get("basis", "")).strip():
        raise CaseValidationError("authorization_required", "Current internal research use must be authorized; confidential or unauthorized material must stay local.", 403)
    review = payload.get("deidentification")
    if not isinstance(review, dict) or review.get("reviewed") is not True or review.get("residual_risk") != "low":
        raise CaseValidationError("deidentification_required", "Review direct and combination identity clues before submission.", 403)
    terms = review.get("identity_terms", [])
    if not isinstance(terms, list) or len(terms) > 200 or any(not isinstance(t, str) or not 1 <= len(t) <= 300 for t in terms):
        raise CaseValidationError("invalid_schema", "identity_terms must be a short list of strings.")
    # Protocol IDs, write capabilities and version fields are not prose and must
    # remain byte stable. Review terms apply to substantive record content only.
    protocol_keys = {"schema_version", "case_id", "submission_id", "case_token", "parent_submission_id", "version", "record_type"}
    clean = _sanitize({k: v for k, v in payload.items() if k not in protocol_keys}, sorted(terms, key=len, reverse=True))
    clean.update({k: copy.deepcopy(v) for k, v in payload.items() if k in protocol_keys})
    _validate(clean, CASE_SCHEMA)
    if clean["record_type"] == "follow_up" and (not clean.get("parent_submission_id") or not clean["outcomes"] or not clean["actual_actions"]):
        raise CaseValidationError("invalid_schema", "Follow-up requires parent_submission_id, actual_actions (including not_started when applicable), and outcomes.")
    if clean["record_type"] == "diagnosis" and (not clean["recommended_actions"] or not clean["predictions"]):
        raise CaseValidationError("invalid_schema", "Diagnosis requires recommended actions and falsifiable predictions.")
    for observation in clean["observations"]:
        period = observation["period"]
        try:
            start = datetime.strptime(period["start"], "%Y-%m-%d")
            end = datetime.strptime(period["end"], "%Y-%m-%d")
            if start > end:
                raise ValueError()
        except ValueError:
            raise CaseValidationError("invalid_schema", "Observation periods require valid ordered ISO dates.")
        if observation["denominator"] is not None and observation["denominator"] < 0:
            raise CaseValidationError("invalid_schema", "Denominator cannot be negative.")
        if observation["value"] is None and not observation["missing"]:
            raise CaseValidationError("invalid_schema", "Missing values require a missing-data explanation.")
    for key, id_key in (("observations", "observation_id"), ("evidence", "evidence_id"), ("predictions", "prediction_id")):
        ids = [v[id_key] for v in clean[key]]
        if len(set(ids)) != len(ids):
            raise CaseValidationError("invalid_schema", "Duplicate identifiers within " + key)
    for action in clean["recommended_actions"] + clean["actual_actions"]:
        for field in ("start_date", "end_date"):
            if action[field]:
                try:
                    datetime.strptime(action[field], "%Y-%m-%d")
                except ValueError:
                    raise CaseValidationError("invalid_schema", "Action dates require ISO dates or an empty string when unknown.")
        if action["start_date"] and action["end_date"] and action["start_date"] > action["end_date"]:
            raise CaseValidationError("invalid_schema", "Action end date precedes its start date.")
    for prediction in clean["predictions"]:
        try:
            datetime.strptime(prediction["deadline"], "%Y-%m-%d")
        except ValueError:
            raise CaseValidationError("invalid_schema", "Prediction deadline requires a valid ISO date.")
    return clean


sanitize_case = prepare_case


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _db_path(store_path=None):
    return Path(store_path or os.environ.get("ZMXX_CASE_DB") or Path(__file__).resolve().parent / "private" / "research.sqlite3")


def _connect(store_path=None):
    path = _db_path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(path.parent, 0o700)
    conn = sqlite3.connect(str(path), timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA secure_delete=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cases(case_id TEXT PRIMARY KEY, token_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS records(
            id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL REFERENCES cases(case_id),
            submission_id TEXT UNIQUE NOT NULL, version INTEGER NOT NULL, record_type TEXT NOT NULL,
            parent_submission_id TEXT, payload_hash TEXT NOT NULL, payload TEXT NOT NULL,
            receipt_id TEXT UNIQUE NOT NULL, received_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            UNIQUE(case_id,version));
        CREATE INDEX IF NOT EXISTS records_case ON records(case_id,version);
        CREATE TABLE IF NOT EXISTS legacy_quarantine(
            id INTEGER PRIMARY KEY AUTOINCREMENT, payload_hash TEXT UNIQUE NOT NULL,
            payload TEXT NOT NULL, receipt_id TEXT NOT NULL, received_at TEXT NOT NULL, expires_at TEXT NOT NULL);
    """)
    if os.name != "nt":
        os.chmod(path, 0o600)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(path) + suffix)
            if sidecar.exists():
                os.chmod(sidecar, 0o600)
    return conn


def _receipt(row, status="accepted"):
    return {"ok": True, "status": status, "research_eligible": True,
            **{k: row[k] for k in ("case_id", "submission_id", "version", "record_type", "receipt_id", "received_at")}}


def _purge(conn):
    now = _utc_now().isoformat()
    conn.execute("DELETE FROM records WHERE expires_at < ?", (now,))
    conn.execute("DELETE FROM cases WHERE case_id NOT IN (SELECT case_id FROM records)")
    conn.execute("DELETE FROM legacy_quarantine WHERE expires_at < ?", (now,))


def _check_references(clean, prior_payloads):
    all_payloads = prior_payloads + [clean]
    for collection, key in (("observations", "observation_id"), ("evidence", "evidence_id")):
        previous_items = {item[key]: item for p in prior_payloads for item in p[collection]}
        if any(item[key] in previous_items and previous_items[item[key]] != item for item in clean[collection]):
            raise CaseValidationError("evidence_version_conflict", "Changed evidence or observations require a new identifier; prior evidence stays immutable.", 409)
    obs = {o["observation_id"] for p in all_payloads for o in p["observations"]}
    evidence = {e["evidence_id"] for p in all_payloads for e in p["evidence"]}
    actions = {a["action_id"] for p in all_payloads for k in ("recommended_actions", "actual_actions") for a in p[k]}
    checks = [(ref, obs) for e in clean["evidence"] for ref in e["observation_refs"]]
    checks += [(ref, evidence) for ref in clean["diagnosis"]["supporting_evidence"]]
    checks += [(ref, evidence) for k in ("recommended_actions", "actual_actions") for a in clean[k] for ref in a["evidence_refs"]]
    checks += [(p["baseline_observation_id"], obs) for p in clean["predictions"]]
    checks += [(ref, actions) for p in clean["predictions"] for ref in p["action_ids"]]
    checks += [(o[k], obs) for o in clean["outcomes"] for k in ("observation_id", "baseline_observation_id")]
    if any(ref not in known for ref, known in checks):
        raise CaseValidationError("invalid_reference", "Evidence, metric or action reference does not exist in this case.")
    measurements = {o["observation_id"]: o for p in all_payloads for o in p["observations"]}
    for outcome in clean["outcomes"]:
        current = measurements[outcome["observation_id"]]
        baseline = measurements[outcome["baseline_observation_id"]]
        if current["metric"] != baseline["metric"] or current["unit"] != baseline["unit"] or current["period"]["window_days"] != baseline["period"]["window_days"]:
            raise CaseValidationError("incomparable_outcome", "Outcome comparisons require the same metric, unit and observation window; retain different measures as observations.")
        if (not current["period"]["matured"] or not baseline["period"]["matured"]) and (outcome["result"] != "unknown" or outcome["attribution"] != "unestablished"):
            raise CaseValidationError("immature_outcome", "An immature observation window cannot be recorded as an established result.")


def accept_case(payload, store_path=None):
    clean = prepare_case(payload)
    token_hash = hashlib.sha256(clean.pop("case_token").encode()).hexdigest()
    serialized = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    payload_hash = hashlib.sha256(serialized.encode()).hexdigest()
    conn = _connect(store_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        _purge(conn)
        owner = conn.execute("SELECT token_hash FROM cases WHERE case_id=?", (clean["case_id"],)).fetchone()
        if owner and not hmac.compare_digest(owner["token_hash"], token_hash):
            raise CaseValidationError("case_access_denied", "Case write capability does not match.", 403)
        existing = conn.execute("SELECT * FROM records WHERE submission_id=?", (clean["submission_id"],)).fetchone()
        if existing:
            if existing["payload_hash"] != payload_hash or existing["case_id"] != clean["case_id"]:
                raise CaseValidationError("submission_conflict", "submission_id already belongs to a different immutable record.", 409)
            conn.commit()
            return _receipt(existing, "duplicate")
        previous = conn.execute("SELECT * FROM records WHERE case_id=? ORDER BY version", (clean["case_id"],)).fetchall()
        expected_version = previous[-1]["version"] + 1 if previous else 1
        if clean["version"] != expected_version:
            raise CaseValidationError("version_conflict", "Use the next sequential case version.", 409)
        parent_id = clean.get("parent_submission_id")
        if not previous and (clean["record_type"] != "diagnosis" or parent_id):
            raise CaseValidationError("unknown_parent", "Create the initial diagnosis before follow-up.", 409)
        if previous and not any(r["submission_id"] == parent_id for r in previous):
            raise CaseValidationError("unknown_parent", "A subsequent version must reference an existing record in the same case.", 409)
        _check_references(clean, [json.loads(row["payload"]) for row in previous])
        now = _utc_now()
        expires = (now + timedelta(days=RETENTION_DAYS)).isoformat()
        if not owner:
            conn.execute("INSERT INTO cases VALUES(?,?)", (clean["case_id"], token_hash))
        receipt_id = "rcpt_" + secrets.token_urlsafe(24)
        conn.execute("INSERT INTO records(case_id,submission_id,version,record_type,parent_submission_id,payload_hash,payload,receipt_id,received_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (clean["case_id"], clean["submission_id"], clean["version"], clean["record_type"], parent_id, payload_hash, serialized, receipt_id, now.isoformat(), expires))
        conn.execute("UPDATE records SET expires_at=? WHERE case_id=?", (expires, clean["case_id"]))
        row = conn.execute("SELECT * FROM records WHERE submission_id=?", (clean["submission_id"],)).fetchone()
        conn.commit()
        return _receipt(row)
    finally:
        conn.close()


LEGACY_FIELDS = ("industry", "lifecycle_stage", "five_elements", "four_xiang", "break_chain", "degree_bias",
                 "prescription_direction", "data_source", "sample_value", "report_month", "skill_version", "platform")


def accept_legacy_case(payload, store_path=None):
    """Compatibility only: never evidence of authorized research or a real user.

    Legacy clients lack authorization/deidentification metadata. A receipt records
    only categorical usage metadata; arbitrary legacy prose is not retained.
    """
    if not isinstance(payload, dict) or not any(payload.get(k) for k in ("industry", "five_elements")):
        raise CaseValidationError("invalid_legacy", "Legacy case requires industry or five_elements.")
    # No unseen legacy free text crosses into storage. Preserve existing public
    # APIs while clearly separating the old, research-ineligible usage stream.
    clean = {"legacy": True, "research_eligible": False, "reason": "no_v3_authorization_or_evidence",
             "has_industry": bool(payload.get("industry")), "has_five_elements": bool(payload.get("five_elements"))}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    now = _utc_now()
    conn = _connect(store_path)
    try:
        with conn:
            _purge(conn)
            conn.execute("INSERT OR IGNORE INTO legacy_quarantine(payload_hash,payload,receipt_id,received_at,expires_at) VALUES(?,?,?,?,?)",
                (digest, json.dumps(clean), "legacy_" + secrets.token_urlsafe(24), now.isoformat(), (now + timedelta(days=90)).isoformat()))
            row = conn.execute("SELECT receipt_id,received_at FROM legacy_quarantine WHERE payload_hash=?", (digest,)).fetchone()
        return {"ok": True, "status": "legacy_quarantined", "research_eligible": False,
                "receipt_id": row["receipt_id"], "received_at": row["received_at"],
                "message": "Legacy compatibility receipt only. Submit schema v3 for a research case."}
    finally:
        conn.close()


def read_cases(store_path=None, limit=50, after=0, case_id=None):
    """Private local API. HTTP callers MUST authenticate before invoking it."""
    if type(limit) is not int or not 1 <= limit <= 200 or type(after) is not int or after < 0:
        raise CaseValidationError("invalid_pagination", "limit must be 1..200 and after must be nonnegative.")
    conn = _connect(store_path)
    try:
        with conn:
            _purge(conn)
        sql = "SELECT * FROM records WHERE id>?"
        params = [after]
        if case_id:
            sql += " AND case_id=?"
            params.append(case_id)
        rows = conn.execute(sql + " ORDER BY id LIMIT ?", params + [limit]).fetchall()
        return {"ok": True, "items": [{"cursor": r["id"], "receipt": _receipt(r), "case": json.loads(r["payload"]),
                                        "expires_at": r["expires_at"]} for r in rows],
                "next_cursor": rows[-1]["id"] if rows else after,
                "retention": "730 days after the latest accepted case version; private internal research only"}
    finally:
        conn.close()


def backup_store(destination, store_path=None):
    """Consistent SQLite backup, including committed WAL data; destination private."""
    dest = Path(destination)
    if dest.exists():
        raise ValueError("Backup destination already exists.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = _connect(store_path)
    target = sqlite3.connect(str(dest))
    try:
        source.backup(target)
    finally:
        source.close()
        target.close()
    if os.name != "nt":
        os.chmod(dest, 0o600)
    return str(dest)


def purge_expired(store_path=None):
    conn = _connect(store_path)
    try:
        before = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        with conn:
            _purge(conn)
        after = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return {"ok": True, "research_records_removed": before - after}
    finally:
        conn.close()


def migrate_legacy_file(source, store_path=None):
    """Explicit local migration to quarantine; never asserts real use/authority."""
    imported = invalid = 0
    with open(source, encoding="utf-8-sig") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                accept_legacy_case(json.loads(line), store_path)
                imported += 1
            except (ValueError, TypeError):
                invalid += 1
    return {"ok": True, "processed_legacy_lines": imported, "invalid_lines": invalid,
            "research_records_created": 0, "source_unchanged": True}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Private local research-store maintenance; prints counts only.")
    parser.add_argument("command", choices=("backup", "purge", "migrate-legacy", "export"))
    parser.add_argument("path", nargs="?")
    parser.add_argument("--database")
    parser.add_argument("--case-id")
    args = parser.parse_args()
    try:
        if args.command == "purge":
            result = purge_expired(args.database)
        elif args.command == "backup":
            if not args.path:
                parser.error("backup requires a private destination path")
            backup_store(args.path, args.database)
            result = {"ok": True, "backup_created": True}
        elif args.command == "migrate-legacy":
            if not args.path:
                parser.error("migrate-legacy requires an existing JSONL path")
            result = migrate_legacy_file(args.path, args.database)
        else:
            if not args.path:
                parser.error("export requires a private destination path")
            target = Path(args.path)
            if target.exists():
                raise ValueError("Export target exists")
            target.parent.mkdir(parents=True, exist_ok=True)
            count, cursor = 0, 0
            with open(target, "x", encoding="utf-8") as stream:
                if os.name != "nt":
                    os.chmod(target, 0o600)
                while True:
                    page = read_cases(args.database, limit=200, after=cursor, case_id=args.case_id)
                    if not page["items"]:
                        break
                    for item in page["items"]:
                        stream.write(json.dumps(item, ensure_ascii=False) + "\n")
                        count += 1
                    cursor = page["next_cursor"]
            result = {"ok": True, "exported_research_records": count}
        print(json.dumps(result, ensure_ascii=False))
    except Exception:
        print(json.dumps({"ok": False, "error": "maintenance_failed", "message": "Verify private paths and local permissions; original records were not overwritten."}))
        raise SystemExit(1)
