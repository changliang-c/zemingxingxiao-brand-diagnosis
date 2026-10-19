"""Synthetic fixtures only. Never submit these to production."""
import copy


def initial_case():
    period = {"start": "2026-06-01", "end": "2026-06-30", "window_days": 30, "matured": True}
    def metric(identifier, name, value, unit, numerator=None, denominator=None):
        return {"observation_id": identifier, "metric": name, "value": value, "unit": unit,
                "numerator": numerator, "denominator": denominator, "period": copy.deepcopy(period),
                "definition": "复购人数/首次消费后满30天的新客人数；每人最多计一次，不含未成熟窗口。",
                "source": "合成验收数据，不是真实客户", "evidence_type": "measured",
                "population": "完成30天观察的新客1000人；不上传客户明细", "missing": []}
    action = {"action_id": "return-visit", "description": "首次用餐离店时提供下次到店承接，并在有授权的自有渠道提醒。",
              "status": "planned", "start_date": "2026-07-01", "end_date": "2026-08-31",
              "investment": 3000, "investment_unit": "CNY", "scope": "同一门店的1000名新客聚合群体",
              "execution_extent": "计划覆盖100%收银班次", "concurrent_changes": [], "evidence_refs": ["ev-retention"]}
    result = {
        "schema_version": "3.0", "record_type": "diagnosis", "case_id": "synthetic_case_20261019_0001",
        "submission_id": "synthetic_initial_20261019_0001", "case_token": "SYNTHETIC_ONLY_never_production_0123456789012345",
        "version": 1, "source_platform": "local-isolated-test", "skill_version": "2.5.0", "report_language": "zh-CN",
        "authorization": {"status": "authorized", "purpose": "internal_research", "basis": "全量虚构数据，专用于本地验收。"},
        "deidentification": {"reviewed": True, "identity_terms": ["虚构示例餐厅", "示例负责人"], "residual_risk": "low"},
        "context": {"industry": "餐饮", "business_model": "门店即时消费", "stage": "稳定经营",
                    "scale_band": "单店、月订单约10000", "customer_segment": "附近工作与生活客群",
                    "purchase_scenario": "工作日午餐", "channels": ["门店自然客流", "付费本地推广"],
                    "goal": "在不降低毛利率的情况下改善成熟新客群复购", "constraints": ["预算3000元", "不扩大人员编制"]},
        "observations": [metric("repeat-baseline", "30天新客复购率", .12, "ratio", 120, 1000),
                         metric("ticket-baseline", "客单价", 35.000075, "CNY/order", 350000.75, 10000),
                         metric("cac-baseline", "付费获客成本", 20, "CNY/customer", 20000, 1000),
                         metric("revenue-baseline", "月营收", 350000.75, "CNY")],
        "evidence": [{"evidence_id": "ev-retention", "statement": "首次消费后缺少再次到店承接；虚构示例餐厅由示例负责人提供汇总说明。",
                      "evidence_type": "user_reported", "source": "合成访谈摘录", "observation_refs": ["repeat-baseline"],
                      "limitations": ["无顾客级数据，暂不能分离餐品偏好与回访机制影响"]}],
        "diagnosis": {"primary_break": "土：留存承接不足", "secondary_breaks": ["水：付费获客成本需追踪"],
                      "reasoning": "复购120/1000且离店后缺少再次到店机制，优先试验低成本承接动作。检查有顺序，修复无固定顺序。",
                      "supporting_evidence": ["ev-retention"], "counter_evidence": ["已有自然回头客，不能推断完全没有留存"],
                      "alternative_explanations": ["菜品匹配", "服务体验", "季节与节假日"], "confidence": .65,
                      "missing_evidence": ["同口径未接受动作的对照群体"], "theory_version": "2.1"},
        "predictions": [{"prediction_id": "pred-repeat", "action_ids": ["return-visit"], "metric": "30天新客复购率",
                         "baseline_observation_id": "repeat-baseline", "expected_change": "成熟新客群复购率从12%向17%改善；属于可检验预期而非保证。",
                         "deadline": "2026-08-31", "falsification": "执行充分且观察窗口成熟后仍≤12%，应否定或调整留存承接是主断点的判断。"}],
        "recommended_actions": [action], "actual_actions": [], "outcomes": [], "objections": [],
    }
    result["observations"][1].update({"definition": "6月已完成且扣除退款的订单收入350000.75元 / 10000笔订单；精确比值35.000075，面向展示可约为35元。", "population": "6月全部10000笔已完成订单"})
    result["observations"][2].update({"definition": "6月付费渠道费用20000元 / 该渠道首次完成消费的新客1000人；不含自然到店新客。", "population": "6月付费渠道获客1000人；与复购成熟队列不默认同一人群"})
    result["observations"][3].update({"definition": "6月已完成订单的实收收入，扣除退款；金额350000.75元，未扣成本和获客费用。", "population": "6月全部已完成订单的企业聚合收入"})
    return result


def follow_up_case():
    initial = initial_case()
    record = copy.deepcopy(initial)
    record.update({"record_type": "follow_up", "submission_id": "synthetic_followup_20261019_0001", "version": 2,
                   "parent_submission_id": initial["submission_id"]})
    observation = copy.deepcopy(initial["observations"][0])
    observation.update({"observation_id": "repeat-followup", "value": .17, "numerator": 170,
                        "period": {"start": "2026-07-01", "end": "2026-08-31", "window_days": 30, "matured": True}})
    record["observations"] = [observation]
    record["evidence"] = [{"evidence_id": "ev-followup", "statement": "合成记录：1000名已满30天观察的新客中170人复购。",
                           "evidence_type": "measured", "source": "合成聚合订单核对", "observation_refs": ["repeat-followup"], "limitations": ["没有随机对照"]}]
    action = copy.deepcopy(initial["recommended_actions"][0])
    action.update({"status": "completed", "execution_extent": "实际覆盖90%收银班次", "investment": 2800,
                   "concurrent_changes": ["同期换了两款午餐菜单", "没有降价", "含一个节假日"], "evidence_refs": ["ev-followup"]})
    record["actual_actions"] = [action]
    record["outcomes"] = [{"observation_id": "repeat-followup", "baseline_observation_id": "repeat-baseline", "result": "improved",
                           "sample_size": 1000, "observation_window": "新客首次消费后完整30天，成熟队列", "control": "无随机或同期未干预对照",
                           "confounders": ["菜单更新", "节假日"], "attribution": "unestablished", "interpretation": "复购从120/1000到170/1000，增加5个百分点；不能单凭前后变化归因于处方。",
                           "adverse_effects": ["部分员工反馈离店提示增加工作量"]}]
    record["objections"] = ["经营者认为菜品更新可能是主要原因，要求保留异议。"]
    return record


if __name__ == "__main__":
    import json
    from pathlib import Path
    from case_store import CASE_SCHEMA
    base = Path(__file__).resolve().parent.parent
    (base / "examples").mkdir(exist_ok=True)
    for name, value in (("diagnosis-v3.synthetic.json", initial_case()), ("follow-up-v3.synthetic.json", follow_up_case())):
        (base / "examples" / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (base / "case-schema-v3.json").write_text(json.dumps(CASE_SCHEMA, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
