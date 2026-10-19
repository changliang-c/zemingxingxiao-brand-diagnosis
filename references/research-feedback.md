# 经营案例回传与效果反馈（schema 3.0）

目的：保留能复核诊断的经营证据、推理、行动和结果，内部研究默认不公开、不跨用户检索、不写入 `cases.md`。不是只收使用次数、行业和五行标签。使用免费许可本身不构成资料授权。

## 授权与去身份

先确认当前上下文已有覆盖内部研究用途的有效授权及资料提供权；已有授权无需每次反复询问。首次缺少依据时，简明说明仅回传去身份经营记录、内部研究用途，并请求一次授权。对保密资料或第三方信息存在具体权利缺口时，只处理缺口字段，不抹空整个案例。用户拒绝或无法确认则正常完成报告，研究回传留在本地待处理，不发送。

在发送前删除品牌、门店地址、负责人/客户身份、电话、邮箱、账号、链接及可定位的独特事件；审查罕见行业、精确地点与事件的组合风险。随机案例编号本身不等于匿名化。`identity_terms` 仅用于本地清理，发送时必须是空列表。脚本的模式匹配是辅助，不能代替上下文审查。

保留企业聚合经营数据，包括必要的准确营收、毛利、成本、订单量、客单价、获客成本、转化与复购值；保留单位、分子分母、统计周期、口径、来源、覆盖群体、缺失项。不得将财务数据一概禁止或随意降精度。完整对话、客户明细表和原始保密资料不直接上传。

## 数据结构

完整机器约束见 `case-schema-v3.json`，合成初诊及跟进样例见 `../examples/research-diagnosis.synthetic.json`、`../examples/research-follow-up.synthetic.json`。它们只证明流程，不是真实客户效果验证。

- `schema_version: "3.0"`；`record_type: diagnosis | follow_up`；稳定随机 `case_id`、每份记录唯一 `submission_id`；`version` 从 1 递增。跟进以 `parent_submission_id` 指向初诊或前次记录，使用相同 `case_id`。
- `authorization`: `status=authorized`、`purpose=internal_research` 和真实 `basis`。不得编造“已授权”。
- `deidentification`: `reviewed=true`、`identity_terms=[]`、`residual_risk=low`，仅在实际完成审查后填写。
- `context`：行业/品类、商业模式、阶段、规模、客群、场景、渠道、目标、资源限制。
- `observations` / `evidence`：事实与指标；区分实测、用户陈述、估计、模型推断，保留来源与反证。
- `diagnosis`：主次断点、证据引用、替代解释、置信度、待补证项及理论/技能版本。
- `predictions`：动作、指标、期限、预期变化、证伪条件。
- `recommended_actions` 与 `actual_actions` 分开；后者记时间、投入、范围、执行程度与同期变化。
- `outcomes`：同口径前后值、成熟窗口、样本量、对照条件；无对照则不自动归因。
- `objections`：异议、无改善、失败和负面效果同样保留。
- `source_platform`、`skill_version=2.5.0`、`report_language=zh-CN|en`。

`case_token` 是用于同一案例后续写入的随机凭据，客户端首次生成、后续复用，保存在用户私有目录；不要显示在报告、贴到聊天、提交到仓库或公开分发。服务端只存哈希，研究正文不保留它。无需在公开技能里放服务器写入密钥。

新版本复用旧 observation_id / evidence_id 时内容必须相同；修订和后测使用新 ID，保留历史证据。跟进版本至少为 2，并逐次递增。

## 实际发送与失败恢复

具备 Python 与网络的宿主可执行（路径相对技能目录）：

```text
python scripts/submit_case.py --input /private/path/case.json
```

脚本先做本地去身份，保存待补交包，再 POST `https://www.zmxx.work/case-report`。回执保存到同一私有目录（默认用户目录 `.zemingxingxiao/outbox`，可用 `--outbox` 修改）。只对网络故障、429 和服务器暂时失败有限重试，保留相同 `submission_id`；收到 `accepted` 或 `duplicate` 以及 `receipt_id` 才能说“服务端已接收”。409/校验错误要修正原因，不盲目换编号重复上报。网络失败不影响诊断报告完成。

仅准备本地补交包：

```text
python scripts/submit_case.py --input /private/path/case.json --prepare-only
```

补交时以输出的 `.pending.json` 重新作为 `--input`，保持编号、版本和 `case_token` 不变。成功后脚本保存 `.receipt.json`（不含令牌的去身份档案）、`.private-receipt.json`（可导入官网反馈页，含私有跟进令牌），并移除对应待补交文件。仅在自己设备间私下转移 `.private-receipt.json`；不要公开。私有目录应使用当前用户可访问的本机位置，勿选公共分享盘。

纯提示词、没有脚本/HTTP权限的宿主只生成去身份 JSON，并明确“待提交，尚未收到服务端回执”；提供此脚本或已配置的 `log_case` 工具为补交途径。不得因提示词写了联网要求就声称已经联网、提交成功或安排了后台提醒。

## 主动跟进

报告交付时主动给出案例号、当前真实接收状态和一次明确的反馈卡：①实际做了什么与何时；②投入和执行程度；③同口径前后指标、分母及成熟窗口；④同期变化；⑤失败、负面影响和异议。默认按报告验收期限给反馈日期，餐饮 30 天复购必须等待该新客群每人观察满 30 天；同时保留原报告 90 天复检安排。

用户回到同一案例时优先询问实际行动和结果，生成 `follow_up` 并关联初诊。宿主具备且用户已授权日程/提醒能力时可安排；否则给可复制的日期与反馈卡，不声称已设自动提醒，不给第三方发邮件。不要用作者预期代替用户结果，不因效果差而拒收案例。
