"""Isolated v2.5.0 regression tests: no production requests or notifications."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import server
import research_client
from case_store import accept_case, CaseValidationError


class EngineReportsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.directory=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{
            "ZMXX_REPORT_DIR":str(self.directory/"reports"),
            "ZMXX_CLIENT_STATE_DIR":str(self.directory/"client"),
            "ZMXX_CASE_DB":str(self.directory/"research.sqlite3"),
            "ZMXX_RESEARCH_ENDPOINT":"", "ZMXX_PUBLIC_BASE_URL":"",
            "PYTHONUTF8":"1",
        })
        self.env.start()
        self.diagnosis=server.diagnose({"brand_name":"Synthetic cafe", "industry":"restaurant", "jin_clarity":"clear", "shui_source":"mixed", "water_growth":8,"mu_asset":"yes", "fire_state":"weak", "fire_returns":"unknown", "tu_natural":12})
        self.initial=json.loads((BASE/"examples/diagnosis-v3.synthetic.json").read_text(encoding="utf-8"))
        self.follow=json.loads((BASE/"examples/follow-up-v3.synthetic.json").read_text(encoding="utf-8"))

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_language_precedence_and_both_formats(self):
        for language,conversation in (("en","zh-CN"),("zh-CN","en")):
            r=server.generate_report({"brand_name":"Synthetic cafe","diagnosis":self.diagnosis,"report_language":language,"conversation_language":conversation,"format":"html"})
            self.assertEqual(r["report_language"],language)
            self.assertIn('lang="'+language+'"',r["html"])
            self.assertEqual(r["html"].count('<svg '),3)
            self.assertTrue(Path(r["report_file"]).is_file())
            self.assertEqual(r["report_url"],"")
            if language=="en":
                for label in ("Business Diagnosis Report","Diagnostic summary","Repair priorities","Verification and conclusion","Outcome feedback","Free Commercial Use License"):
                    self.assertIn(label,r["html"])
                self.assertNotIn("品牌诊断报告",r["html"])
            else:
                self.assertIn("修复无固定顺序",r["html"])
                self.assertIn("免费商用许可",r["html"])
        conversation=server.generate_report({"diagnosis":self.diagnosis,"conversation_language":"en"})
        self.assertEqual(conversation["report_language"],"en")
        self.assertIn("markdown",conversation)
        self.assertEqual(server.generate_report({"diagnosis":self.diagnosis})["report_language"],"zh-CN")

    def test_html_svg_markdown_escape_and_unpredictable_filenames(self):
        brand='<script>alert("x")</script>![leak](https://invalid.example)'
        r=server.generate_report({"brand_name":brand,"diagnosis":self.diagnosis,"format":"html","report_language":"en"})
        self.assertNotIn('<script>',r["html"])
        self.assertIn('&lt;script&gt;',r["html"])
        self.assertNotIn("alert",Path(r["report_file"]).name)
        m=server.generate_report({"brand_name":brand,"diagnosis":self.diagnosis,"report_language":"en"})
        self.assertNotIn('![leak]',m["markdown"])
        self.assertNotEqual(r["report_file"],m["report_file"])
        for f in (self.directory/"reports").glob('*.svg'):
            self.assertNotIn('<script>',f.read_text(encoding="utf-8"))

    def test_public_url_only_when_configured_and_local_write_failure(self):
        with patch.dict(os.environ,{"ZMXX_PUBLIC_BASE_URL":"https://reports.example"}):
            r=server.generate_report({"diagnosis":self.diagnosis})
            self.assertTrue(r["report_url"].startswith('https://reports.example/static/'))
            self.assertEqual(r["markdown"].count('![chain]'),1)
        blocker=self.directory/"not-a-directory"; blocker.write_text('blocked')
        with patch.dict(os.environ,{"ZMXX_REPORT_DIR":str(blocker)}):
            r=server.generate_report({"diagnosis":self.diagnosis})
            self.assertEqual(r["artifact_status"],"inline_only")
            self.assertTrue(r["markdown"])
            self.assertFalse(r["report_url"])

    def test_original_tools_and_missing_evidence(self):
        self.assertEqual(self.diagnosis["five_elements"]["火"]["status"],"待验证")
        legacy={"get_framework","diagnosis_guide","search_cases","diagnose_brand","generate_report","log_case"}
        self.assertTrue(legacy.issubset({t["name"] for t in server.TOOLS}))
        self.assertTrue(server.call_tool('get_framework',{}))
        self.assertTrue(server.call_tool('diagnosis_guide',{}))
        self.assertIsInstance(server.call_tool('search_cases',{"query":"餐饮"}),dict)
        before=copy.deepcopy(server.CASE_INDEX)
        result=server.call_tool('log_case',{"industry":"餐饮","five_elements":{"土":"泄"}})
        self.assertEqual(result["status"],"legacy_quarantined")
        self.assertFalse(result["research_eligible"])
        self.assertEqual(before,server.CASE_INDEX)

    def test_english_industry_synonyms_preserve_chinese_observation_period(self):
        for english,chinese in [('restaurant','餐饮'),('retail','零售'),('e-commerce','电商'),('automotive','汽车'),('consumer electronics','消费电子'),('real estate','房地产'),('furniture','家具'),('healthcare','医疗'),('manufacturing','制造')]:
            self.assertEqual(server.infer_period(english),server.infer_period(chinese),(english,chinese))
        self.assertEqual(server.infer_period('unknown novel industry'),6)
        self.assertEqual(server.infer_period('restaurant-like speculative market'),6)

    def _serve(self):
        captured=[]; db=self.directory/"remote.sqlite3"
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                raw=self.rfile.read(int(self.headers['Content-Length']))
                payload=json.loads(raw); captured.append(payload)
                try:
                    result=accept_case(payload,store_path=db); status=201
                except CaseValidationError as exc:
                    result={"ok":False,"code":exc.code}; status=exc.status_code
                encoded=json.dumps(result).encode()
                self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(encoded))); self.end_headers(); self.wfile.write(encoded)
        httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True); thread.start()
        self.addCleanup(httpd.server_close); self.addCleanup(httpd.shutdown)
        return 'http://127.0.0.1:'+str(httpd.server_port)+'/case-report',captured

    def test_real_local_http_receipt_dedup_followup_and_pretransport_deidentification(self):
        endpoint,captured=self._serve()
        self.initial.pop('case_token')
        self.follow.pop('case_token')
        with patch.dict(os.environ,{"ZMXX_RESEARCH_ENDPOINT":endpoint}):
            first=server.call_tool('log_case',self.initial)
            self.assertEqual(first["status"],"accepted",first)
            self.assertEqual(first["destination"],"remote")
            repeat=server.call_tool('log_case',self.initial)
            self.assertEqual(repeat["status"],"duplicate",repeat)
            follow=server.call_tool('record_follow_up',self.follow)
            self.assertEqual(follow["status"],"accepted",follow)
            self.assertEqual(first["case_id"],follow["case_id"])
        wire=json.dumps(captured,ensure_ascii=False)
        self.assertNotIn('虚构示例餐厅',wire)
        self.assertNotIn('示例负责人',wire)
        self.assertEqual(captured[0]['deidentification'].get('identity_terms',[]),[])
        self.assertTrue(any(o.get('denominator')==1000 and o.get('numerator')==120 for o in captured[0]['observations']))
        self.assertTrue(any(o.get('denominator')==1000 and o.get('numerator')==170 for o in captured[-1]['observations']))
        self.assertNotIn('case_token',first)
        self.assertFalse(list((self.directory/'client').glob('*.pending.json')))

    def test_failed_transport_queues_deidentified_record_and_retries(self):
        endpoint,captured=self._serve()
        with patch.dict(os.environ,{"ZMXX_RESEARCH_ENDPOINT":endpoint}):
            with patch('research_client._send',return_value={"ok":False,"status":"pending_retry","code":"transport_unavailable"}):
                pending=server.call_tool('log_case',self.initial)
            self.assertFalse(pending['ok'])
            self.assertEqual(pending['status'],'pending_retry')
            files=list((self.directory/'client').glob('*.pending.json'))
            self.assertEqual(len(files),1)
            self.assertNotIn('虚构示例餐厅',files[0].read_text(encoding='utf-8'))
            report=server.generate_report({'diagnosis':self.diagnosis})
            self.assertTrue(report['markdown'])
            retry=server.call_tool('retry_case_submissions',{})
            self.assertTrue(retry['ok'],retry)
            self.assertEqual(retry['pending'],0)
            self.assertEqual(captured[0]['submission_id'],self.initial['submission_id'])

    def test_invalid_authorization_never_sent_or_queued(self):
        self.initial['authorization']['status']='unknown'
        with patch.dict(os.environ,{"ZMXX_RESEARCH_ENDPOINT":"https://invalid.example/case-report"}), patch('research_client._send') as send:
            result=server.log_case(self.initial)
            self.assertFalse(result['ok'])
            send.assert_not_called()
            self.assertFalse(list((self.directory/'client').glob('*.pending.json')))

    def test_remote_mcp_cannot_borrow_local_token_or_inspect_retry_queue(self):
        initial=copy.deepcopy(self.initial); initial.pop('case_token')
        accepted=server.call_tool('log_case',initial)
        self.assertEqual(accepted['status'],'accepted')
        follow=copy.deepcopy(self.follow); follow.pop('case_token')
        result=server.call_tool('record_follow_up',follow,remote=True)
        self.assertFalse(result['ok'])
        self.assertEqual(result['code'],'invalid_schema')
        retry=server.call_tool('retry_case_submissions',{},remote=True)
        self.assertFalse(retry['ok'])
        self.assertEqual(retry['code'],'retry_on_originating_client')

    def test_redirect_is_not_followed(self):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                received.append(self.path)
                self.send_response(302); self.send_header('Location','/unexpected-destination'); self.end_headers()
            def do_GET(self):
                received.append(self.path); self.send_response(200); self.end_headers()
        httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=httpd.serve_forever,daemon=True).start()
        try:
            result=research_client._send(self.initial,'http://127.0.0.1:'+str(httpd.server_port)+'/case-report')
        finally:
            httpd.shutdown(); httpd.server_close()
        self.assertEqual(received,['/case-report'])
        self.assertFalse(result['ok'])
        self.assertEqual(result['http_status'],302)

    def test_stdio_initialization_and_tool_list(self):
        messages=[{"jsonrpc":"2.0","id":1,"method":"initialize"},{"jsonrpc":"2.0","id":2,"method":"tools/list"}]
        result=subprocess.run([sys.executable,str(BASE/'server.py')],input='\n'.join(json.dumps(x) for x in messages)+'\n',text=True,capture_output=True,encoding='utf-8',check=True)
        lines=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(lines[0]['result']['serverInfo']['version'],'2.5.0')
        self.assertEqual(len(lines[1]['result']['tools']),8)


if __name__=='__main__': unittest.main()
