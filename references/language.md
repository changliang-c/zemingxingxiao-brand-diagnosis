# 语言与术语 / Language and terminology

优先级：用户明确指定的报告语言 > 当前对话主要语言 > 简体中文（zh-CN）。README、宿主界面、模型默认语言和 discovery description 不覆盖这一顺序。中英混合且未指定时跟随用户最近的实质性请求；无法判断则中文。研究记录 `report_language` 为 `zh-CN` 或 `en`。

中文报告使用 `report_template.html`；英文报告使用 `report_template.en.html`。两者使用同一理论语义来源 `theory.md` 与同一诊断流程 `diagnosis.md`。翻译只改变呈现语言，不另立阈值、五行映射、四象含义或处方顺序。保留品牌名及专名“择命行效”，首次出现附英文解释。正文、标题、章节、图表标题、坐标轴、图例、表头、结论、反馈邀请与页脚全部随报告语言；不能只改 HTML lang。

| 原词 | English rendering | 固定经营含义 |
|---|---|---|
| 择命行效 | Zemingxingxiao | 专有理论名称，保留中文品牌标识 |
| 因果·五行·度 | Cause and effect; five elements; calibrated balance | 因果、链路输运与分寸，不是占卜 |
| 之金·下刀 | Metal — positioning and choices | 定位取舍 |
| 行水·引水 | Water — acquisition and channels | 流量与渠道 |
| 有木·植树 | Wood — product and delivery | 产品、内容和持续交付 |
| 效火·点火 | Fire — conversion and activation | 转化与增长爆发 |
| 归土·归藏 | Earth — retention and accumulated assets | 复购、信用和品牌资产 |
| 生 / 泄 / 耗 | Generating / leaking / consuming | 需附具体事实解释，避免只发标签 |
| 老阳 | Old Yang — high visibility, weak durable conversion | 火旺水滥 |
| 少阳 | Young Yang — retained demand supports organic inflow | 火生水蓄 |
| 少阴 | Young Yin — valuable product with weak reach | 火弱水滞 |
| 老阴 | Old Yin — weak inflow and activation | 火水俱衰 |

Invariant: inspect Metal → Water → Wood → Fire → Earth to avoid omissions. Choose only one or two initial repair actions based on loss, risk, evidence, dependencies, cost and reversibility; repairs have no fixed element order. Observations, estimates and model inferences remain distinguishable. A change without a comparison group must not be presented as proof of causality.

英文入口示例：
“Choose a service mode: 1) Chat — discuss a brand or positioning problem, estimated 3,000–15,000 tokens; 2) Full report — a few focused information rounds followed by an HTML diagnosis, estimated 20,000–50,000 tokens. Estimates are indicative, not a price or usage guarantee.”

英文反馈邀请示例：
“For case {case_id}, please update: what you actually did and when; time and money spent; the same metric and denominator before and after a mature observation window; concurrent price, menu or holiday changes; and any failures, harms or disagreement. Missing or unchanged results are useful too. Receipt status: {actual_status}.”
