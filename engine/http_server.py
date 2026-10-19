#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""择命行效 2.5.0: existing MCP transport + private evidence research intake.
No hardcoded credential, no mail notification, no public research read endpoint.
"""
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import sys
import threading
import time
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from mcp.server.lowlevel import Server
from mcp import types
from mcp.server.transport_security import TransportSecuritySettings

_BASE = os.path.dirname(os.path.abspath(__file__))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)
from server import TOOLS, call_tool
from case_store import (CASE_SCHEMA, MAX_BODY, VERSION, CaseValidationError,
                        accept_case, accept_legacy_case, read_cases)

def _to_tool(t):
    return types.Tool(name=t["name"], title=t.get("title", t["name"]),
                      description=t.get("description", ""),
                      input_schema=t.get("inputSchema", {"type": "object", "properties": {}}))

TOOLS_TYPED = [_to_tool(t) for t in TOOLS]

async def _list_tools(ctx, params):
    return types.ListToolsResult(tools=TOOLS_TYPED)

async def _call_tool(ctx, params):
    try:
        if params.name in ("log_case", "record_follow_up"):
            request = getattr(ctx, "request", None)
            if not _rate_ok(_client_ip(request) if request is not None else "mcp-no-http-context"):
                raise CaseValidationError("rate_limited", "Retry later with the same submission_id.", 429)
        result = await run_in_threadpool(call_tool, params.name, params.arguments or {}, remote=True)
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))],
                                    is_error=isinstance(result, dict) and (result.get("ok") is False or "error" in result))
    except CaseValidationError as exc:
        result = {"ok": False, "error": exc.code, "message": exc.message}
    except Exception:
        result = {"ok": False, "error": "tool_failed", "message": "The tool could not complete. The report or case may be retried locally."}
    return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))], is_error=True)

async def _health(request):
    return JSONResponse({"status": "ok", "service": "zemingxingxiao-engine", "version": VERSION,
                         "case_schema_version": "3.0", "notifications": "disabled", "tools": [t["name"] for t in TOOLS]})

CASE_MAX_BODY = MAX_BODY
CASE_RATE_LIMIT = 20
_case_rate = {}
_rate_lock = threading.Lock()
_rate_salt = secrets.token_bytes(32)
_ALLOWED_ORIGINS = frozenset({"https://zhenduan-63363.app.workbuddy.host"})

def _client_ip(request):
    """Trust Nginx X-Real-IP only on the loopback reverse-proxy hop."""
    peer = request.client.host if request.client else "unknown"
    try:
        loopback = ipaddress.ip_address(peer).is_loopback
    except ValueError:
        loopback = False
    if loopback:
        forwarded = request.headers.get("x-real-ip", "")
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return peer

def _rate_ok(ip):
    """Ephemeral salted buckets only; no source IP is persisted in research."""
    key = hmac.new(_rate_salt, ip.encode(), hashlib.sha256).hexdigest()
    now = time.monotonic()
    with _rate_lock:
        expired = [k for k, hits in _case_rate.items() if not hits or now - hits[-1] >= 3600]
        for k in expired:
            del _case_rate[k]
        if key not in _case_rate and len(_case_rate) >= 10000:
            return False
        hits = [t for t in _case_rate.get(key, []) if now - t < 3600]
        if len(hits) >= CASE_RATE_LIMIT:
            _case_rate[key] = hits
            return False
        _case_rate[key] = hits + [now]
        return True

def _reply(request, payload, status=200):
    headers = {"Cache-Control": "no-store"}
    origin = request.headers.get("origin", "")
    if origin in _ALLOWED_ORIGINS:
        headers.update({"Access-Control-Allow-Origin": origin, "Vary": "Origin"})
    return JSONResponse(payload, status_code=status, headers=headers)

async def _case_options(request):
    origin = request.headers.get("origin", "")
    requested = {h.strip().lower() for h in request.headers.get("access-control-request-headers", "").split(",") if h.strip()}
    if origin not in _ALLOWED_ORIGINS or request.headers.get("access-control-request-method", "").upper() != "POST" or not requested.issubset({"content-type"}):
        return Response(status_code=403)
    return Response(status_code=204, headers={"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "POST",
        "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "600", "Vary": "Origin", "Cache-Control": "no-store"})

async def _limited_json(request):
    length = request.headers.get("content-length")
    if length:
        try:
            parsed_length = int(length)
        except ValueError:
            raise CaseValidationError("invalid_json", "Invalid content length.")
        if parsed_length < 0 or parsed_length > CASE_MAX_BODY:
            raise CaseValidationError("payload_too_large", "Record exceeds 256 KiB.", 413)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > CASE_MAX_BODY:
            raise CaseValidationError("payload_too_large", "Record exceeds 256 KiB.", 413)
        body.extend(chunk)
    try:
        def no_constant(value):
            raise ValueError()
        payload = json.loads(body.decode("utf-8"), parse_constant=no_constant)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise CaseValidationError("invalid_json", "A finite JSON object is required.")
    if not isinstance(payload, dict):
        raise CaseValidationError("invalid_schema", "A JSON object is required.")
    return payload

async def _case_report(request):
    if not _rate_ok(_client_ip(request)):
        return _reply(request, {"ok": False, "error": "rate_limited", "message": "Retry later with the same submission_id."}, 429)
    try:
        data = await _limited_json(request)
        if "schema_version" in data:
            receipt = await run_in_threadpool(accept_case, data)
            status = 201 if receipt["status"] == "accepted" else 200
        else:
            receipt = await run_in_threadpool(accept_legacy_case, data)
            status = 202
        return _reply(request, receipt, status)
    except CaseValidationError as exc:
        return _reply(request, {"ok": False, "error": exc.code, "message": exc.message}, exc.status_code)
    except Exception:
        return _reply(request, {"ok": False, "error": "storage_unavailable", "message": "Keep the sanitized local submission and retry with the same submission_id."}, 503)

async def _case_report_list(request):
    """Private admin read. Query tokens intentionally unsupported (URL log leaks)."""
    expected = os.environ.get("ZMXX_CASE_READ_TOKEN", "")
    provided = request.headers.get("authorization", "")
    if len(expected) < 32 or not hmac.compare_digest(provided.encode("utf-8"), ("Bearer " + expected).encode("utf-8")):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401, headers={"Cache-Control": "no-store"})
    try:
        limit = int(request.query_params.get("n", "50"))
        after = int(request.query_params.get("after", "0"))
        result = await run_in_threadpool(read_cases, limit=limit, after=after, case_id=request.query_params.get("case_id"))
        return JSONResponse(result, headers={"Cache-Control": "no-store"})
    except (ValueError, CaseValidationError):
        return JSONResponse({"ok": False, "error": "invalid_pagination"}, status_code=400, headers={"Cache-Control": "no-store"})
    except Exception:
        return JSONResponse({"ok": False, "error": "storage_unavailable"}, status_code=503, headers={"Cache-Control": "no-store"})

async def _case_schema(request):
    return JSONResponse(CASE_SCHEMA, headers={"Cache-Control": "public, max-age=3600"})

server = Server(name="zemingxingxiao-engine", version=VERSION, title="择命行效-五行商业诊断引擎",
    description="基于择命行效五行商业诊断理论体系（理论创立：常亮）的确定性诊断引擎。只修链，不修命。",
    on_list_tools=_list_tools, on_call_tool=_call_tool)
_MODE = os.environ.get("MCP_MODE", "stateful").strip().lower()
app = server.streamable_http_app(streamable_http_path="/mcp", json_response=_MODE == "stateless", stateless_http=_MODE == "stateless",
    custom_starlette_routes=[Route("/health", _health, methods=["GET"]),
        Route("/case-report", _case_report, methods=["POST"]), Route("/case-report", _case_options, methods=["OPTIONS"]),
        Route("/case-report/list", _case_report_list, methods=["GET"]), Route("/case-report/schema", _case_schema, methods=["GET"])],
    transport_security=TransportSecuritySettings(allowed_hosts=["zmxx.work", "zmxx.work:*", "www.zmxx.work", "www.zmxx.work:*"]))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8000")), log_level="info", proxy_headers=False)

