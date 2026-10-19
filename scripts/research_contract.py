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

VERSION = "2.5.1"
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

