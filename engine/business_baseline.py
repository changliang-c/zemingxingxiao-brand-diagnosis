"""Pure financial-intake and contextual checks; never a sales rejection gate."""
import math
import re
from datetime import date

DIAGNOSTIC_REVISION = "2.6.0-profit-baseline-20261021"
FIRST_QUESTION = "你企业年毛利润多少？净利润多少？"
RATE_TOLERANCE_PP = 0.1  # Supplied rounded percentages, not a policy tolerance.
META_FIELDS = ("entity", "period", "currency", "unit", "basis")

_METRIC_SCHEMA = {
    "oneOf": [
        {"type": "number"}, {"type": "null"},
        {"type": "object", "properties": {
            "value": {"type": ["number", "null"]},
            **{k: {"type": "string"} for k in META_FIELDS},
            "data_status": {"type": "string", "enum": ["actual", "estimate", "unknown"]},
            "source_type": {"type": "string", "description": "Enterprise records/user report; never an industry average."},
        }, "required": ["value"]},
    ]
}
FINANCIAL_INTAKE_SCHEMA = {
    "type": "object",
    "description": "Start with annual gross and net profit, then the same entity/year revenue, currency, unit and accounting basis. Missing data stays unverified; do not fill with industry averages.",
    "properties": {
        **{k: {"type": "string"} for k in META_FIELDS},
        "income": _METRIC_SCHEMA, "gross": _METRIC_SCHEMA, "net": _METRIC_SCHEMA,
        "data_status": {"type": "string", "enum": ["actual", "estimate", "unknown"]},
        "net_definition": {"type": "string", "enum": ["after_tax_consolidated", "attributable", "adjusted", "pre_tax", "segment", "unknown"], "description": "Net means consolidated after-tax profit. Other profit measures remain separately identified and unverified for this policy."},
        "source_type": {"type": "string"},
        "industry": {"type": "string"},
        "gross_applicable": {"type": "boolean", "description": "False for banks or other models without merchandise gross profit; do not fabricate it."},
        "provided_rates": {"type": "object", "description": "Percentage points, e.g. 40 means 40%; checked against amounts within 0.1 pp rounding tolerance.", "properties": {"gross_margin": {"type": "number"}, "net_margin": {"type": "number"}}},
        "informed_continuation": {"type": "boolean", "description": "True only after the user understands the fit/effectiveness boundary and still wishes to continue."},
    },
}
CONTEXT_FIELDS = (
    ("causal_loop", "因果循环", "Causal loop"),
    ("three_powers", "三才条件", "Three powers: conditions"),
    ("critical_thresholds", "关键门槛", "Critical thresholds"),
    ("four_xiang_stage", "四象阶段", "Four-configuration stage"),
    ("four_xiang_transition", "阶段转换条件", "Stage transition conditions"),
    ("isomorphic_comparison", "同构对照", "Structural comparison"),
    ("saddle_point", "鞍点与行动时机", "Saddle point and action timing"),
)
OPERATIONAL_CONTEXT_SCHEMA = {
    "type": "object", "description": "Evidence-supported context supplied by the practitioner. No fixed universal threshold and no causal certainty from a water/fire screen alone.",
    "properties": {key: {"type": ["string", "object", "array", "null"], "description": en + "; include observations, contrary evidence, window and testable conditions where available."} for key, _, en in CONTEXT_FIELDS},
}


def json_safe(value):
    """Preserve provided evidence while excluding non-finite JSON numbers."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return str(value)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except (OverflowError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _annual(period):
    text = str(period or "").strip()
    if re.fullmatch(r"(?:FY\s*)?\d{4}(?:年(?:全年)?|全年)?", text, re.I):
        return True
    matches = re.findall(r"\d{4}-\d{2}-\d{2}", text)
    if len(matches) == 2:
        try:
            return 360 <= (date.fromisoformat(matches[1]) - date.fromisoformat(matches[0])).days <= 370
        except ValueError:
            pass
    return False


def assess_service_fit(financial_intake=None):
    """Return a reversible service-fit reminder, never an automatic refusal.

    Flat amounts inherit metadata; metric objects may supply it explicitly. All
    compared amounts must share entity, annual period, currency, unit and basis.
    A net profit above gross profit is possible and is not rejected by this check.
    """
    data = financial_intake if isinstance(financial_intake, dict) else {}
    issues = []
    if not isinstance(financial_intake, (dict, type(None))):
        issues.append("invalid_intake")
    industry = str(data.get("industry") or "").strip().lower()
    bank = "银行" in industry or bool(re.search(r"\bbank(?:ing|s)?\b", industry))
    applicable = data.get("gross_applicable") is not False and not bank
    required = ("income", "gross", "net") if applicable else ("income", "net")
    values, metadata, qualities = {}, {}, {}
    for key in required:
        raw = data.get(key)
        item = raw if isinstance(raw, dict) else {"value": raw}
        value = _number(item.get("value"))
        values[key] = value
        if value is None:
            issues.append("missing_or_nonfinite_" + key)
        metadata[key] = {m: str(item.get(m, data.get(m)) or "").strip() for m in META_FIELDS}
        qualities[key] = item.get("data_status", data.get("data_status"))
        if qualities[key] != "actual":
            issues.append("estimate_" + key if qualities[key] == "estimate" else "unknown_quality_" + key)
        source = str(item.get("source_type", data.get("source_type", ""))).lower()
        if any(t in source for t in ("industry_average", "industry_mean", "benchmark", "行业均值", "行业平均")):
            issues.append("industry_average_not_enterprise_" + key)
        for m in META_FIELDS:
            if not metadata[key][m]:
                issues.append("missing_" + m)
            elif data.get(m) is not None and str(data[m]).strip() != metadata[key][m]:
                issues.append("inconsistent_" + m)
    for m in META_FIELDS:
        if len({metadata[k][m] for k in required}) > 1:
            issues.append("inconsistent_" + m)
    period = metadata.get("income", {}).get("period", "")
    if period and not _annual(period):
        issues.append("annual_period_unverified")
    income = values.get("income")
    if income is not None and income <= 0:
        issues.append("nonpositive_income")
    if applicable and income is not None and values.get("gross") is not None and values["gross"] > income:
        issues.append("gross_exceeds_income")
    net_basis = metadata.get("net", {}).get("basis", "").lower()
    net_definition = data.get("net_definition", "after_tax_consolidated")
    if net_definition != "after_tax_consolidated" or any(t in net_basis for t in ("pretax", "pre-tax", "利润总额", "税前", "归母", "attributable", "adjusted", "调整后", "segment", "分部")):
        issues.append("net_definition_unverified")
    # Estimate/unknown-quality amounts remain visibly provisional; missing or
    # incompatible metadata never gets silently combined into a ratio.
    blockers = [i for i in issues if not i.startswith(("estimate_", "unknown_quality_"))]
    rates = {"gross_margin": None, "net_margin": None}
    if not blockers and income is not None and income > 0:
        for name, key in (("gross_margin", "gross"), ("net_margin", "net")):
            if key in required and values.get(key) is not None:
                rate = values[key] / income * 100
                if math.isfinite(rate):
                    rates[name] = rate
                else:
                    issues.append("nonfinite_computed_" + name)
    supplied = data.get("provided_rates", {})
    if not isinstance(supplied, dict):
        issues.append("invalid_provided_rates")
    else:
        for name in rates:
            if name == "gross_margin" and not applicable:
                continue
            if name in supplied:
                supplied_value = _number(supplied[name])
                if supplied_value is None:
                    issues.append("nonfinite_provided_" + name)
                elif rates[name] is not None and abs(supplied_value - rates[name]) > RATE_TOLERANCE_PP + 1e-9:
                    issues.append("inconsistent_" + name)
    inconsistent = any(i.startswith(("inconsistent_", "nonfinite_provided_")) or i == "invalid_provided_rates" for i in issues)
    if inconsistent:
        rates = {"gross_margin": None, "net_margin": None}
    reasons = []
    if rates["gross_margin"] is not None and rates["gross_margin"] > 40:
        reasons.append("gross_above_40")
    if rates["net_margin"] is not None and rates["net_margin"] < 5:
        reasons.append("net_below_5")
    informed = data.get("informed_continuation") is True
    if not applicable:
        issues.append("gross_not_applicable_product_fit_required")
    issues = list(dict.fromkeys(issues))
    status = "pending_verification" if issues else ("proceed_informed" if reasons and informed else "fit_reminder" if reasons else "within_policy_reference")
    return {
        "diagnostic_revision": DIAGNOSTIC_REVISION,
        "status": status, "can_continue": True, "automatic_rejection": False,
        "reminder_required": bool(reasons), "reminder_reasons": reasons,
        "informed_continuation": informed, "gross_applicable": applicable,
        "rates": rates, "issues": issues, "period": period,
        "internal_category": "contribution" if not issues and len(reasons) == 2 else None,
        "policy": {"gross_reminder_above": 40, "net_reminder_below": 5, "net_upper_limit": None,
                   "meaning": "Service-fit policy, not industry health, enterprise value or cause."},
    }


def fit_summary(assessment, en=False):
    rates = assessment["rates"]
    missing = "unverified" if en else "待核实"
    gross = ("not applicable" if en else "不适用") if not assessment["gross_applicable"] else (f'{rates["gross_margin"]:.2f}%' if rates["gross_margin"] is not None else missing)
    net = f'{rates["net_margin"]:.2f}%' if rates["net_margin"] is not None else missing
    lines = [(f"Gross margin: {gross}; net margin: {net}." if en else f"毛利率：{gross}；净利率：{net}。")]
    if assessment["issues"]:
        lines.append("Profit-based service fit is pending verification: confirm actual amounts, one entity, annual period, currency, unit, accounting basis and any supplied rates. No industry average is substituted." if en else "利润适配待核实：请核对实际金额、同一主体、年度、币种、单位、会计口径与已报比率；不以行业均值代填。")
        if any(i.startswith(("estimate_", "unknown_quality_")) for i in assessment["issues"]):
            lines.append("Some amounts are estimates or their evidence quality is unknown; any displayed ratios are provisional calculations." if en else "金额含估算或数据性质尚不明确；如显示比例，仅是临时核算，仍待核实。")
        if any(i.startswith("inconsistent_") for i in assessment["issues"]):
            lines.append("The amounts, metadata or supplied ratios disagree; conflicting ratios are withheld until reconciled." if en else "金额、元数据或已报比例存在不一致，核对前不显示冲突比例。")
        if "nonpositive_income" in assessment["issues"]:
            lines.append("Revenue is zero or negative, so profit ratios are not calculated." if en else "营收为零或负值，不计算利润比例。")
    if assessment["reminder_required"]:
        if "gross_above_40" in assessment["reminder_reasons"]:
            lines.append("Your reported gross margin is above this product's main service range of 40%; the incremental help may be limited, so we should match the scope to your specific problem." if en else "目前所报毛利率高于40%，超出本产品主要服务区间；能提供的增量帮助可能有限，需要结合您的具体问题确定范围。")
        if "net_below_5" in assessment["reminder_reasons"]:
            lines.append("Your reported net margin is below 5%, leaving a thin profit buffer. We can help clarify problems and priorities, but this diagnosis may not improve profit immediately." if en else "目前所报净利率低于5%，利润缓冲较薄。我们可以协助梳理问题和先后顺序，但这套诊断未必能立竿见影地改善利润。")
        lines.append("These are service-fit reminders, not a judgment of business health, value or cause; they never automatically refuse service." if en else "以上仅为服务适配提醒，不代表行业健康、企业价值或原因判断，也不会自动拒单。")
    elif not assessment["issues"]:
        lines.append("No service-fit reminder is triggered by these profit ratios; this is not a finding of business health. There is no upper net-margin limit." if en else "当前利润比例未触发服务适配提醒；这不等于经营健康结论，净利率不设上限。")
    if assessment["informed_continuation"]:
        lines.append("The user understands the boundary and wishes to continue; proceed, keeping any verification gaps visible." if en else "用户已知情并坚持继续：继续诊断，同时保留待核实项。")
    elif assessment["reminder_required"]:
        lines.append("Explain the boundary and record the user's choice; continue if they still wish to proceed." if en else "说明边界后记录用户选择；用户仍希望继续时照常进行。")
    if not assessment["gross_applicable"]:
        lines.append("Merchandise gross margin is not applicable; confirm product fit separately instead of treating it as zero or as a pass." if en else "商品毛利率不适用，需另行确认产品适配，不能按零值或默认通过处理。")
    return lines


def normalize_context(value):
    source = value if isinstance(value, dict) else {}
    return {key: json_safe(source.get(key)) for key, _, _ in CONTEXT_FIELDS}


_LABELS = {
    "evidence": ("证据", "Evidence"), "counterevidence": ("反证", "Contrary evidence"),
    "stage": ("阶段", "Stage"), "transition": ("转换", "Transition"),
    "trigger": ("触发条件", "Trigger"), "metric": ("指标", "Metric"),
    "value": ("值", "Value"), "unit": ("单位", "Unit"), "window": ("观察窗口", "Observation window"),
    "天": ("天", "Heaven"), "地": ("地", "Earth"), "人": ("人", "People"),
    "heaven": ("天", "Heaven"), "earth": ("地", "Earth"), "people": ("人", "People"),
    "similarity": ("同构关系", "Structural similarity"), "difference": ("差异", "Difference"),
    "action": ("行动", "Action"), "timing": ("行动时机", "Timing"),
    "stop_condition": ("停止条件", "Stop condition"), "links": ("关系", "Links"),
}


def _context_text(value, en, depth=0):
    if value is None or value == "" or value == [] or value == {}:
        return "Not provided" if en else "未提供"
    if depth > 8:
        return "Nested evidence requires review" if en else "多层证据需人工核验"
    if isinstance(value, dict):
        return "; ".join(f'{_LABELS.get(k, (k, k))[int(en)]}: {_context_text(v, en, depth+1)}' for k, v in value.items())
    if isinstance(value, list):
        return "; ".join(_context_text(v, en, depth+1) for v in value)
    return str(value)


def context_lines(context, en=False):
    normalized = normalize_context(context)
    return [(english if en else chinese) + ": " + _context_text(normalized[key], en) for key, chinese, english in CONTEXT_FIELDS]
