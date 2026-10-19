"""Local/MCP research submission with deidentification before transport."""
import hashlib
import json
import os
import secrets
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlsplit

_LOCK = threading.RLock()

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def _valid_endpoint(endpoint):
    try:
        parsed=urlsplit(endpoint)
        return bool(parsed.hostname and not parsed.username and not parsed.password and not parsed.fragment and (parsed.scheme=='https' or (parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1','::1'))))
    except ValueError:
        return False

def _directory():
    directory=Path(os.environ.get("ZMXX_CLIENT_STATE_DIR") or Path(__file__).resolve().parent/"private"/"research-client")
    directory.mkdir(parents=True,exist_ok=True)
    try: directory.chmod(0o700)
    except OSError: pass
    return directory

def _write(path,value):
    temporary=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    try: temporary.chmod(0o600)
    except OSError: pass
    temporary.replace(path)

def _context(payload):
    payload=dict(payload)
    payload.setdefault("schema_version","3.0")
    payload.setdefault("record_type","diagnosis")
    payload.setdefault("case_id","case_"+uuid.uuid4().hex)
    payload.setdefault("submission_id","sub_"+uuid.uuid4().hex)
    payload.setdefault("version",1)
    payload.setdefault("skill_version","2.5.0")
    payload.setdefault("source_platform",os.environ.get("ZMXX_SOURCE_PLATFORM","mcp"))
    payload.setdefault("report_language","zh-CN")
    context_file=_directory()/(hashlib.sha256(str(payload["case_id"]).encode()).hexdigest()+".context.json")
    stored={}
    if context_file.exists():
        stored=json.loads(context_file.read_text(encoding="utf-8"))
    if not payload.get("case_token"):
        payload["case_token"]=stored.get("case_token") or (secrets.token_urlsafe(32) if payload["record_type"]=="diagnosis" else "")
    return payload,context_file

def _queue_path(payload):
    identifier=hashlib.sha256(str(payload["submission_id"]).encode()).hexdigest()
    return _directory()/(identifier+".pending.json")

def _send(payload,endpoint):
    request=urllib.request.Request(endpoint,data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),headers={"Content-Type":"application/json","User-Agent":"Zemingxingxiao/2.5.0"},method="POST")
    try:
        with urllib.request.build_opener(_NoRedirect).open(request,timeout=15) as response:
            result=json.loads(response.read(128*1024).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code >= 500 or exc.code == 429:
            exc.close()
            return {"ok":False,"status":"pending_retry","code":"remote_temporarily_unavailable"}
        try:
            body=json.loads(exc.read(32*1024).decode("utf-8"))
            code=body.get("code")
            if not code and isinstance(body.get("error"),dict): code=body["error"].get("code")
        except (ValueError,TypeError,AttributeError): code=None
        status_code=exc.code
        exc.close()
        return {"ok":False,"status":"rejected","code":code or "remote_rejected","http_status":status_code}
    except (OSError,ValueError,urllib.error.URLError):
        return {"ok":False,"status":"pending_retry","code":"transport_unavailable"}
    if not isinstance(result,dict) or result.get("ok") is not True or result.get("status") not in ("accepted","duplicate") or not result.get("receipt_id") or result.get("submission_id") != payload["submission_id"] or result.get("case_id") != payload["case_id"]:
        return {"ok":False,"status":"pending_retry","code":"invalid_remote_receipt"}
    return result

def log_case(args):
    from case_store import accept_case, accept_legacy_case, prepare_case, CaseValidationError
    if not isinstance(args,dict):
        return {"ok":False,"status":"rejected","code":"invalid_schema"}
    payload=args.get("case") if isinstance(args.get("case"),dict) else args
    if not any(k in payload for k in ("schema_version","record_type","observations","context","authorization")):
        return accept_legacy_case(payload)
    if os.environ.get("ZMXX_SERVER_MODE")=="remote":
        try:
            return accept_case(payload)
        except CaseValidationError as exc:
            return {"ok":False,"status":"rejected","code":exc.code,"message":exc.message}
    with _LOCK:
        try:
            payload,context_file=_context(payload)
            clean=prepare_case(payload)
        except CaseValidationError as exc:
            return {"ok":False,"status":"rejected","code":exc.code,"message":exc.message}
        except (OSError,ValueError,TypeError):
            return {"ok":False,"status":"rejected","code":"local_state_unavailable"}
        _write(context_file,{"case_id":clean["case_id"],"case_token":clean["case_token"]})
        endpoint=os.environ.get("ZMXX_RESEARCH_ENDPOINT","").strip()
        if endpoint:
            if not _valid_endpoint(endpoint):
                return {"ok":False,"status":"rejected","code":"invalid_research_endpoint"}
            queued=_queue_path(clean)
            if queued.exists() and json.loads(queued.read_text(encoding="utf-8")) != clean:
                return {"ok":False,"status":"rejected","code":"submission_conflict"}
            # Persist a deidentified, stable submission before networking so a crash is recoverable.
            _write(queued,clean)
            result=_send(clean,endpoint)
            if result.get("ok"):
                queued.unlink(missing_ok=True)
            elif result.get("status")=="rejected":
                queued.replace(queued.with_suffix(".rejected"))
            result.setdefault("case_id",clean["case_id"])
            result.setdefault("submission_id",clean["submission_id"])
            result["destination"]="remote"
            result["case_recovery_file"]=str(context_file.resolve())
            if result.get("status")=="pending_retry":
                result["retry_tool"]="retry_case_submissions"
                result["message"]="Research submission is queued locally; remote receipt has not been confirmed. Report delivery is unaffected."
            return result
        try:
            result=accept_case(clean)
            result["destination"]="local"
            result["message"]="Stored in the local internal research store; this is not confirmation of remote delivery."
            return result
        except CaseValidationError as exc:
            return {"ok":False,"status":"rejected","code":exc.code,"message":exc.message}

def record_follow_up(args):
    payload=dict(args.get("case") if isinstance(args.get("case"),dict) else args)
    payload["record_type"]="follow_up"
    return log_case(payload)

def retry_case_submissions(args=None):
    from case_store import prepare_case, CaseValidationError
    endpoint=os.environ.get("ZMXX_RESEARCH_ENDPOINT","").strip()
    if not endpoint:
        return {"ok":False,"status":"not_configured","code":"remote_endpoint_required"}
    if not _valid_endpoint(endpoint) or os.environ.get("ZMXX_SERVER_MODE")=="remote":
        return {"ok":False,"status":"rejected","code":"client_retry_unavailable"}
    results=[]
    with _LOCK:
        # Initial diagnosis is normally written before its follow-up; preserve creation order.
        files=sorted(_directory().glob("*.pending.json"),key=lambda p:p.stat().st_mtime)
        for path in files[:20]:
            try:
                payload=prepare_case(json.loads(path.read_text(encoding="utf-8")))
                result=_send(payload,endpoint)
                if result.get("ok"): path.unlink(missing_ok=True)
                elif result.get("status")=="rejected": path.replace(path.with_suffix(".rejected"))
                results.append({"submission_id":payload["submission_id"],"status":result.get("status"),"receipt_id":result.get("receipt_id"),"code":result.get("code")})
            except (OSError,ValueError,CaseValidationError):
                results.append({"status":"rejected","code":"invalid_local_queue"})
    pending=len(list(_directory().glob("*.pending.json")))
    return {"ok":pending==0 and all(x["status"] in ("accepted","duplicate") for x in results),"status":"complete" if pending==0 else "pending_retry","results":results,"pending":pending}
