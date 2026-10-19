"""Bilingual reports; the diagnostic rules remain in server.py (v2.5.1)."""
import html
import json
import math
import os
import re
import uuid
from pathlib import Path

VERSION = "2.5.1"
ORDER = ["金", "水", "木", "火", "土"]
COLORS = ["#ad8846", "#246b67", "#47694d", "#a94f36", "#766758"]
ELEMENTS_EN = {"金": "Metal · positioning", "水": "Water · acquisition", "木": "Wood · product assets", "火": "Fire · conversion", "土": "Earth · retention"}
STATUS_EN = {"生": "Generating", "泄": "Leaking", "中": "Intermediate", "待验证": "Unverified", "无": "Not established"}
XIANG_EN = {"老阳": "Lao Yang · strong activation / rapid acquisition", "少阳": "Shao Yang · strong activation / lower acquisition growth", "少阴": "Shao Yin · weak activation / nonnegative acquisition", "老阴": "Lao Yin · acquisition loss", "无象": "No configuration · channel not established", "待判定": "Undetermined · evidence required"}
EN_INTERPRETATION = {
 "金": {"生": "Choices and exclusions are clear; resources concentrate on a defined market position.", "泄": "Positioning is unclear or spread across too many priorities. Verify what the business has actually stopped doing.", "中": "A direction exists, but the differentiating choice needs sharper evidence.", "待验证": "Positioning evidence is missing. Record the intended customer, exclusions and actual trade-offs."},
 "水": {"生": "Customers arrive through organic demand, referrals or repeat preference. Check how much demand remains without paid acquisition.", "泄": "Acquisition relies on paid or mixed channels. Check acquisition costs and the share that survives a pause in spending; this is a rule-based signal, not proof that all demand disappears.", "中": "Organic acquisition exists but may not support the business independently.", "待验证": "The acquisition mix, costs or organic demand have not been established.", "无": "No acquisition channel is established. Build and test a channel before assigning a configuration."},
 "木": {"生": "The business controls assets that can accumulate and be reused across cycles.", "泄": "Core assets are externally controlled or fail to accumulate. Verify ownership, reuse and substitutability.", "中": "Some assets exist but do not yet form a repeatable system.", "待验证": "Ownership and reusable product or service assets need evidence."},
 "火": {"生": "Activation produces retained value. Confirm the post-campaign cohort and observation window.", "泄": "Activation has not produced retained value. Check whether repeated campaigns are masking weak conversion or retention.", "中": "Activation has occurred but sustained conversion has not been demonstrated.", "待验证": "Before-and-after activation data or mature retention results are missing."},
 "土": {"生": "An established base returns by preference. Verify repeat purchasing and organic sales using a consistent definition.", "泄": "The retained customer base is weak or dependent on external channels. Separate true repeat purchases from one-off orders and channel loading.", "中": "A retained base exists but has limited depth.", "待验证": "Repeat purchase, returning-customer sales and organic sales require measurement."},
}
EN_REPAIR = {"金": "Clarify exclusions and concentrate resources on a supported positioning choice.", "水": "Test a channel that can accumulate organic demand; track paid and organic acquisition separately.", "木": "Build a controlled, reusable product or service asset within the available resources.", "火": "Run a measurable activation only when dependencies permit; measure subsequent retained value.", "土": "Use returning-customer evidence to improve repeat purchasing and reusable customer assets."}
EN_CONFIG = {"老阳": "Rapid acquisition with strong activation requires a retention check. Do not infer durable value from visibility alone.", "少阳": "Strong activation with lower acquisition growth calls for testing whether the existing model can be expanded without weakening retention.", "少阴": "Weak activation with nonnegative acquisition calls for closer observation and, where dependencies permit, a measurable activation test.", "老阴": "Acquisition is declining under this configuration. Inspect returning-customer losses and the underlying positioning before expanding promotion.", "无象": "A channel is not yet established. Collect acquisition evidence before assigning a configuration.", "待判定": "The required acquisition-growth or activation evidence is missing. Keep the configuration undetermined."}
ZH_INTERPRETATION = {
 "金": {"生":"取舍与排除项清晰，资源集中于明确定位；需结合实际经营记录核验。", "泄":"定位不清或优先方向过多。请核验企业实际放弃了哪些业务。", "中":"已有方向，但差异化取舍仍需更明确的证据。", "待验证":"定位证据不足。请记录目标客户、排除项和已经发生的取舍。"},
 "水": {"生":"客户来自自然需求、转介绍或复指名；仍需核验暂停付费获客后能保留多少需求。", "泄":"当前依赖付费或混合获客。请核验获客成本与停投后保留的需求；这是规则信号，不能据此断言停投后新客归零。", "中":"已有自然来路，但能否独立支撑经营仍需核验。", "待验证":"获客结构、成本或自然需求尚未查明。", "无":"获客渠道尚未建立。先建立并验证渠道，再判断四象。"},
 "木": {"生":"企业掌握可跨周期积累和复用的核心资产；需以资产归属及使用记录核验。", "泄":"核心资产由外部控制，或未能形成积累。请核验归属、复用能力和可替代性。", "中":"已有部分资产，但尚未形成可重复使用的系统。", "待验证":"产品或服务资产的归属、积累和复用证据不足。"},
 "火": {"生":"集中动作带来了可留存价值；请核验活动后人群与成熟观察窗口。", "泄":"集中动作尚未沉淀为可留存价值。请检查是否依靠反复活动掩盖转化或留存问题。", "中":"已有集中动作，但持续转化尚未得到验证。", "待验证":"缺少动作前后对比或成熟留存结果，不把未统计直接判为表现差。"},
 "土": {"生":"已有主动回来的客户基本盘；请以一致口径核验复购及自然成交。", "泄":"留存客户盘偏弱或依赖外部渠道。区分真实复购、一次性订单和渠道压量。", "中":"已有沉淀，但深度有限。", "待验证":"复购、老客成交和自然成交数据尚需测量。"}
}
ZH_CONFIG = {"老阳":"获客快速增长且集中动作较强，需要检查留存；不能单凭声量推定形成了长期资产。", "少阳":"集中动作较强、获客增幅相对较低，应检验现有模式能否在不削弱留存的前提下放大。", "少阴":"集中动作较弱且获客未净减少，宜加密观察；依赖条件具备时再做可验证的集中动作试验。", "老阴":"此配置下获客正在减少。扩大推广前，应先检查老客流失和定位依据。", "无象":"渠道尚未建立，先收集获客证据再定象。", "待判定":"缺少必要获客增长或集中动作证据，四象暂不判定。"}
LICENSE_ZH = "本项目代码、技能文本、提示词、文档与模板依 MIT License 发布，可使用、修改、分发、再许可和商用；在副本或实质性部分中保留版权及许可声明。名称、标识、第三方材料与非公开研究数据不随软件授权。"
LICENSE_EN = "Project code, skill text, prompts, documentation and templates are released under the MIT License. Use, modification, distribution, sublicensing and commercial use are permitted; retain the copyright and permission notices in copies or substantial portions. Names, marks, third-party materials and non-public research data are outside the software license."

def resolve_language(args, diagnosis=None):
    """Explicit report language > conversation language > Simplified Chinese."""
    aliases = {"en": "en", "english": "en", "英文": "en", "英语": "en", "zh": "zh-CN", "zh-cn": "zh-CN", "zh-hans": "zh-CN", "chinese": "zh-CN", "中文": "zh-CN", "简体中文": "zh-CN"}
    for value in (args.get("report_language"), args.get("language"), args.get("conversation_language"), (diagnosis or {}).get("report_language")):
        key = str(value or "").strip().lower()
        if key in aliases:
            return aliases[key]
        if key.startswith("en-"):
            return "en"
    return "zh-CN"

def _text(value):
    return str(value if value is not None else "")

def _e(value):
    return html.escape(_text(value), quote=True)

def _md(value):
    return re.sub(r"([\\`*_{}\[\]()#!|])", r"\\\1", _e(value)).replace("\r", " ").replace("\n", " ")

def _svg(kind, fe, xiang, en):
    label = (lambda e: ELEMENTS_EN[e]) if en else (lambda e: e)
    status = (lambda s: STATUS_EN.get(s, "Unverified")) if en else (lambda s: s)
    title = ({"chain": "Five-element diagnostic chain", "xiang": "Four configurations", "radar": "Diagnostic status map"} if en else {"chain": "五行链条诊断图", "xiang": "四象定位图", "radar": "诊断状态示意图"})[kind]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 820 330" role="img" aria-label="{_e(title)}"><rect width="820" height="330" fill="#f6f2e9"/><text x="30" y="34" font-family="sans-serif" font-size="20" fill="#244e46">{_e(title)}</text>']
    if kind == "chain":
        for i,e in enumerate(ORDER):
            x=30+i*158
            out.append(f'<rect x="{x}" y="95" width="145" height="100" rx="6" fill="{COLORS[i]}"/><text x="{x+72}" y="130" text-anchor="middle" font-size="12" fill="white">{_e(label(e))}</text><text x="{x+72}" y="164" text-anchor="middle" font-size="14" fill="white">{_e(status(fe.get(e,{}).get("status","待验证")))}</text>')
        note = "Inspection follows this order. Repair priorities have no fixed sequence." if en else "检查有顺序；修复按损失、风险、证据、依赖、成本、可逆性排序。"
        out.append(f'<text x="30" y="245" font-size="14" fill="#37413d">{_e(note)}</text>')
    elif kind == "xiang":
        for i,k in enumerate(["少阳","老阳","少阴","老阴"]):
            x=30+(i%2)*390; y=65+(i//2)*95
            active = k==xiang
            short = XIANG_EN[k].split(" · ")[0] if en else k
            out.append(f'<rect x="{x}" y="{y}" width="370" height="80" rx="6" fill="{"#246b67" if active else "#e4dfd2"}"/><text x="{x+18}" y="{y+45}" font-size="18" fill="{"white" if active else "#37413d"}">{_e(short)}{" ✓" if active else ""}</text>')
        out.append(f'<text x="30" y="290" font-size="13" fill="#37413d">{_e(XIANG_EN.get(xiang, XIANG_EN["待判定"]) if en else xiang)}</text>')
    else:
        cx,cy,r=410,168,98
        points=[]
        values={"生":.85,"中":.55,"泄":.25,"待验证":0,"无":0}
        for i,e in enumerate(ORDER):
            angle=-math.pi/2+i*2*math.pi/5
            x,y=cx+r*math.cos(angle),cy+r*math.sin(angle)
            lx,ly=cx+(r+30)*math.cos(angle),cy+(r+23)*math.sin(angle)
            v=values.get(fe.get(e,{}).get("status"),0)
            points.append(f'{cx+r*v*math.cos(angle):.1f},{cy+r*v*math.sin(angle):.1f}')
            out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#bcb6a7"/><text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="11" fill="#37413d">{_e(label(e))}</text>')
        out.append(f'<polygon points="{" ".join(points)}" fill="#246b67" fill-opacity=".23" stroke="#246b67" stroke-width="2"/>')
        note="Ordinal illustration only; not measured scores. Missing evidence is not poor performance." if en else "仅示意规则状态，不是实测分数；待验证不等于经营表现差。"
        out.append(f'<text x="30" y="314" font-size="12" fill="#37413d">{_e(note)}</text>')
    out.append('</svg>')
    return "".join(out)

def generate_report(args, base_dir, interpretations, neutral, element_names):
    diagnosis=args.get("diagnosis") or {}
    if isinstance(diagnosis,str):
        try: diagnosis=json.loads(diagnosis)
        except (ValueError,TypeError): diagnosis={}
    if not isinstance(diagnosis,dict):
        return {"ok":False,"error":"diagnosis must be an object"}
    language=resolve_language(args,diagnosis); en=language=="en"
    brand=_text(args.get("brand_name") or diagnosis.get("brand_name") or ("Unnamed project" if en else "未命名项目"))
    industry=_text(diagnosis.get("industry") or args.get("industry") or "")
    fe=diagnosis.get("five_elements") or {}; xiang=(diagnosis.get("four_xiang") or {}).get("xiang","待判定")
    breaks=[e for e in diagnosis.get("break_chain",[]) if e in ORDER]
    repairs=[e for e in diagnosis.get("repair_order",[]) if e in ORDER]
    name=lambda e:ELEMENTS_EN[e] if en else element_names[e]
    state=lambda s:STATUS_EN.get(s,"Unverified") if en else s
    title="Business Diagnosis Report" if en else "品牌诊断报告"
    sections=[]
    def add(heading, paragraphs=(), bullets=()):
        sections.append((heading,list(paragraphs),list(bullets)))
    config=XIANG_EN.get(xiang,XIANG_EN["待判定"]) if en else xiang
    chain=" → ".join(f'{name(e)}: {state(fe.get(e,{}).get("status","待验证"))}' for e in ORDER)
    no_break="No clear break established" if en else "无明显断点"
    direction=EN_CONFIG.get(xiang,EN_CONFIG["待判定"]) if en else ZH_CONFIG.get(xiang,ZH_CONFIG["待判定"])
    add("0 · Diagnostic summary" if en else "〇 诊断摘要", [chain], [("Configuration: " if en else "入象：")+config,("Breaks requiring evidence review: " if en else "待核实断链环：")+("; ".join(name(e) for e in breaks) or no_break),("Suggested direction: " if en else "处方方向：")+direction])
    for i,e in enumerate(ORDER,1):
        st=fe.get(e,{}).get("status","待验证")
        interpretation=EN_INTERPRETATION[e].get(st,EN_INTERPRETATION[e]["待验证"]) if en else ZH_INTERPRETATION[e].get(st,ZH_INTERPRETATION[e]["待验证"])
        add(f'{i} · {name(e)}',[("Assessment: " if en else "判定：")+state(st),interpretation])
    configtext=EN_CONFIG.get(xiang,EN_CONFIG["待判定"]) if en else ZH_CONFIG.get(xiang,ZH_CONFIG["待判定"])
    add("6 · Four-configuration assessment" if en else "六 四象判定",[config,configtext])
    rule=("Inspect Metal → Water → Wood → Fire → Earth. Repair has no fixed sequence: prioritize loss, risk, evidence, dependencies, cost and reversibility. The list is a provisional assessment; choose only one or two actions after reviewing the current decision and loss limits." if en else "检查按金→水→木→火→土逐项查全；修复无固定顺序，按损失、风险、证据、依赖、成本、可逆性排序。以下为候选排序，结合当前决定、损失底线与经营记录确认后，一次只选一至两项。")
    add("7 · Repair priorities" if en else "七 修复优先级",[rule],[name(e)+": "+(EN_REPAIR[e] if en else interpretations["repair"][e]) for e in repairs])
    baseline=("Record repeat-purchase rate, organic acquisition share and returning-customer sales share, including numerator, denominator, period, definition and source. Review at 90 days or after an appropriate mature cohort window. Keep facts, estimates and model inferences separate." if en else "记录复购率、自然流占比和老客成交占比的值、分子、分母、周期、口径及来源；以本次为基线，90天或适合行业的成熟观察窗口复检。区分事实、估计与模型推断。")
    conclusion=("These are rule-based diagnostic signals, not verified causal findings. Preserve contrary evidence and alternative explanations. An uncontrolled before-and-after change alone does not establish that the diagnosis caused the result." if en else "以上是规则诊断信号，不是已经证实的因果结论。保留反证、替代解释与缺失项；没有对照的前后变化，不能自动归因于诊断。")
    add("8 · Verification and conclusion" if en else "八 验收标准与结论",[baseline,conclusion])
    case_id=_text(args.get("case_id") or "")
    follow=("Please report the action actually taken, dates, spending, completion, results under the same metric definition, sample size, mature observation window, concurrent changes, and any failure, no improvement or disagreement. Use the same case ID and the initial submission ID for a follow-up. Research records are for internal analysis and are not automatically published." if en else "请反馈实际做了什么、起止时间、投入与执行程度，以及同口径结果、样本量、成熟观察窗口、同期其他变化；无改善、负面结果和异议同样有价值。后续反馈沿用案例编号并关联初诊提交编号。研究案例仅供内部分析，不自动公开。")
    add("9 · Outcome feedback" if en else "九 效果反馈",[follow]+[("Case ID: " if en else "案例编号：")+case_id] if case_id else [follow])
    disclaimer=("Theory created by Chang Liang; operated by Beijing Changshi Songdao Business Consulting and Planning Co., Ltd. This AI-generated report supports business-chain analysis, not fortune telling, investment advice or guaranteed outcomes." if en else "理论创立：常亮；出品：北京常识宋道商业咨询策划有限公司。本报告由AI依择命行效理论生成，仅供经营判断参考，不构成唯一决策依据，不作命理、投资或结果保证。只修链，不修命。")
    license_text=LICENSE_EN if en else LICENSE_ZH
    charts={k:_svg(k,fe,xiang,en) for k in ("chain","xiang","radar")}
    chart_html="".join(f'<figure>{svg}</figure>' for svg in charts.values())
    section_html="".join('<section><h2>'+_e(h)+'</h2>'+''.join('<p>'+_e(p)+'</p>' for p in ps)+('<ul>'+''.join('<li>'+_e(b)+'</li>' for b in bs)+'</ul>' if bs else '')+'</section>' for h,ps,bs in sections)
    report=f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>{_e(brand)} · {title}</title><style>body{{margin:0;background:#eae6dc;color:#292d2b;font:16px/1.8 system-ui,sans-serif}}main{{max-width:960px;margin:32px auto;padding:48px;background:#faf7ef}}h1,h2{{color:#245a50}}h1{{font-size:32px}}h2{{font-size:22px;border-left:4px solid #a94f36;padding-left:14px}}section{{margin:34px 0}}figure{{margin:22px 0}}svg{{width:100%;height:auto}}footer{{border-top:1px solid #b7ac95;margin-top:36px;font-size:12px;color:#5e645e}}.kicker{{letter-spacing:2px;color:#8c713d}}@media print{{body{{background:white}}main{{margin:0;padding:15px;max-width:none}}section,figure{{break-inside:avoid}}}}</style></head><body><main><div class="kicker">ZEMINGXINGXIAO · {VERSION}</div><h1>{_e(brand)} · {title}</h1><p>{_e(industry)}</p>{chart_html}{section_html}<footer><p>{_e(disclaimer)}</p><p>{_e(license_text)}</p></footer></main></body></html>'''
    report_url=""; report_file=""; chart_refs=[]; artifact_error=""
    try:
        directory=Path(os.environ.get("ZMXX_REPORT_DIR") or Path(base_dir)/"static")
        directory.mkdir(parents=True,exist_ok=True)
        token=uuid.uuid4().hex
        dest=directory/f'{token}_report.html'; dest.write_text(report,encoding="utf-8"); report_file=str(dest.resolve())
        public=os.environ.get("ZMXX_PUBLIC_BASE_URL", "").rstrip("/")
        if public and re.fullmatch(r'https?://[^\s<>"\']+',public):
            report_url=public+"/static/"+dest.name
        for k,svg in charts.items():
            p=directory/f'{token}_{k}.svg'; p.write_text(svg,encoding="utf-8")
            if report_url:
                chart_refs.append(f'![{k}]({public}/static/{p.name})')
    except OSError:
        artifact_error="artifact_write_failed"
    md=f'# {_md(brand)} · {title}\n\n'+('\n\n'.join(chart_refs)+'\n\n' if chart_refs else '')
    for h,ps,bs in sections:
        md+='## '+h+'\n\n'+'\n\n'.join(_md(p) for p in ps)+'\n\n'
        if bs: md+='\n'.join('- '+_md(b) for b in bs)+'\n\n'
    md+='---\n\n'+_md(disclaimer)+'\n\n'+_md(license_text)
    instruction=("Deliver the report in English. Preserve computed assessments. Expand only evidence-supported interpretations; do not invent business facts. Include the available report link or local file and outcome-feedback invitation. Do not claim successful research submission without a receipt." if en else "用简体中文交付报告，保留规则判定；解读只能结合已有经营证据展开，不得编造事实。交付可用报告链接或本地文件并主动邀请效果反馈；无接收回执不得声称回传成功。")
    result={"brand_name":brand,"industry":industry,"report_language":language,"report_url":report_url,"report_file":report_file,"ai_instruction":instruction,"version":VERSION,"artifact_status":"saved" if report_file else "inline_only"}
    if artifact_error: result["artifact_error"]=artifact_error
    result["html" if str(args.get("format","markdown")).lower()=="html" else "markdown"]=report if str(args.get("format","markdown")).lower()=="html" else md
    return result
