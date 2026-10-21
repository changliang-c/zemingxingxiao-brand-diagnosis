# 择命行效经营研究案例：结构、接入与维护

实施版本：2.6.0；数据结构：3.0；理论框架版本独立记录，当前示例为 2.1。

研究案例只供内部分析，不自动进入 `search_cases`、公共案例索引或宣传材料。记录的是证据及结果，不将一次模型诊断、一次调用或一个合成样例当作理论有效或真实客户使用的证明。

## 一、完整经营证据链

完整字段约束在 `case-schema-v3.json`。`examples/diagnosis-v3.synthetic.json` 和 `examples/follow-up-v3.synthetic.json` 是完整的本地合成验收样例；不得提交生产或宣称真实客户成效。

| 区块 | 保留内容 |
| --- | --- |
| `context` | 行业、商业模式、阶段、规模区间、客群、购买情境、渠道、经营目标、资源限制 |
| `observations` | 指标、准确值、单位、分子分母、统计起止、观察窗口、是否成熟、定义、来源、覆盖对象、缺失项 |
| `evidence` | 去身份的实质事实、摘录、证据类型、来源、关联观测、局限；不接受完整原始对话 |
| `diagnosis` | 主次断点、推理、支持证据、反证、替代解释、置信度、待补证、理论版本 |
| `predictions` | 相关动作、基线指标、预期变化、期限、什么结果需要否定或调整判断 |
| `recommended_actions` | 建议动作、预期时间投入范围、执行程度、同期变化及证据 |
| `actual_actions` | 实际执行、实际投入、执行比例、未开始/停止原因、同期其他变化；与建议分开 |
| `outcomes` | 同口径基线与后测、样本数、成熟窗口、对照、混杂、解释、负作用；支持失败和无改善 |
| `objections` | 经营者的不同判断、不认可之处、补充反证 |

证据类型使用 `measured`（测量/系统数据）、`user_reported`（用户陈述）、`estimate`（估计）、`model_inference`（模型推断）。不能把估计改名为实测。金额、成本、毛利、订单数、分子分母及周期允许保留；纯数值不会因去身份被清空。

餐饮示例保留原始 `120/1000` 和后续 `170/1000`、满 30 天观察、获客成本 20 元、月营收 350000.75 元、动作实际投入 2800 元及覆盖 90% 班次。明确记录换菜单、节假日、无随机对照、员工负担及经营者异议。因此只能说明变化，不能自动归因于处方。

## 二、上传前去身份与用途授权

客户端先调用 `prepare_case` / `sanitize_case`，再保存待补交包或联网。服务端再次清理仅作防御，不能据此声称未处理资料从未上传。

`authorization.status=authorized`、`purpose=internal_research`、实际依据 `basis` 必须齐备。已有覆盖本用途的授权可复用，无须每次询问。`unknown`、`not_authorized`、`confidential` 均拒绝上传；免费商用许可不等于有权提供第三方保密资料。

`deidentification.reviewed=true` 和 `residual_risk=low` 表示客户端已检查直接及组合识别风险。`identity_terms` 列出原资料中的品牌、姓名、地点等，用于本地递归清理；该原始词表不上传、不写数据库。直接身份字段、邮箱、电话、身份证模式、网址、明确标注的联系/地址信息会被清理。罕见行业加精确位置加独特事件等组合风险必须由调用方复核，模式规则不能替代该判断。风险未消除时保留报告并停止回传。

不要上传用户级、订单级、员工级明细；用业务需要的企业汇总指标。不要为了避风险将企业汇总财务指标一概删除。公开模式本身不会保证任意自然语言彻底不可识别。

## 三、编号、版本、关联与回执

每个案例生成一个随机 `case_id` 和一个至少 32 字符的随机 `case_token`。每次提交生成稳定 `submission_id`，失败重试保持同一对象和编号。`case_token` 是该案例的追加能力，必须由发起端私下保存，不放报告或公共链接；数据库只存其哈希，管理员读回也不含该值。

初诊：`record_type=diagnosis`、`version=1`，提供完整建议及可证伪预期。

后续记录：同 `case_id` 和 `case_token`，`version` 严格逐次加一，`parent_submission_id` 指向本案例已接受记录。跟进类型为 `follow_up`，必须有实际动作和结果；未执行也记录 `not_started`，窗口未成熟时结果为 `unknown`、归因为 `unestablished`。

历史记录不可覆盖。重复 `submission_id` 且清理后内容相同返回原始回执，不重复入库；内容不同返回冲突。相同观测/证据 ID 不能在新版本改指不同内容，修订或新测量须使用新 ID，确保引用能复核。动作 ID 可沿用以记录执行演进。

| HTTP 结果 | 意义 |
| --- | --- |
| `201` / `status=accepted` | 已接受完整研究记录 |
| `200` / `status=duplicate` | 已接受过同一记录，返回同一 `receipt_id` |
| `202` / `status=legacy_quarantined` | 旧摘要兼容回执，不是完整研究接收；`research_eligible=false` |
| `400` | 结构、日期、口径、引用或窗口状态有误，修复后提交 |
| `403` | 无研究用途授权、去身份未完成或案例能力不匹配 |
| `409` | 版本、父记录、不可变提交/证据冲突 |
| `413` / `429` / `503` | 超出 256 KiB、限流或暂时不可用；报告可用，保留清理后的本地待补交包 |

完整接收回执包含 `ok`、`status`、`research_eligible`、`case_id`、`submission_id`、`version`、`record_type`、`receipt_id`、`received_at`。只有 `accepted` 或 `duplicate` 且编号可核对才算远端接收成功。正常报告生成不能被回传失败阻断。

## 四、HTTP 与 MCP

`POST /case-report` 无公共共享写入密钥。`GET /case-report/schema` 返回结构。官网同域可以提交；跨域仅允许 `https://zhenduan-63363.app.workbuddy.host` 的 POST、Content-Type，未放开通配来源。

公网 MCP 的 `log_case` / `record_follow_up` 直接调用同一接收器，要求调用方提供完整记录和自己的 `case_token`。不能从服务器本地客户端状态自动取令牌、不能替用户重试服务器中的队列，也不会递归向自身上传。`retry_case_submissions` 只供持有本地待补交队列的客户端调用。

旧 `log_case` / 老 POST 摘要继续得到兼容回执；无授权和去身份元数据的旧自由文本不再写入。隔离表仅保留不可逆摘要哈希及少量“是否提供过行业/五行字段”状态，并明确 `research_eligible=false`。这只用于兼容旧调用，不替代 v3 的完整证据方案。现存历史 JSONL 不自动导入为研究证据，也不改变公共案例库。

## 五、管理员与保留

环境变量：

- `ZMXX_CASE_DB`：私有 SQLite 绝对路径，必须在网站根目录和报告 static 目录之外。
- `ZMXX_CASE_READ_TOKEN`：新生成至少 32 字符管理员随机令牌。未配置或过短时读取关闭。
- `ZMXX_SERVER_MODE=remote`：生产公网 MCP 的额外隔离开关。
- 每条成功接收的完整记录与通知收件箱在同一事务落库；重复提交不新增通知。现有记录迁移为 `inbox_only`，不补发历史邮件。
- 邮件默认关闭；配置 `ZMXX_NOTIFY_EMAIL_ENABLED=1` 与私有 `ZMXX_SMTP_*` 参数后，单独运行 `python research_notifications.py worker`。通知仅含来源、时间、记录类型、案例号和回执号，不含经营明细或访问凭据。
- 已知发送失败最多尝试五次并保留错误类别；SMTP 已开始发送但结果不明确时记为 `delivery_uncertain`，需要核对邮箱，不盲目重发。`sent` 只代表发信服务器接受，不代表收件人已读。

管理员使用 `GET /case-report/list?n=50&after=0`，只通过 `Authorization: Bearer ...` 请求头传密钥，不能放 URL 查询参数。可加 `case_id` 筛选；每页最多 200 条，以 `next_cursor` 翻页。响应禁止缓存、无跨域管理读取。查询错误和存储错误不返回原始异常。

同样的管理凭据可读取 `GET /case-report/status`，查看初诊、效果反馈数量与最近通知状态；未授权请求返回 401。健康接口中的通知状态反映配置和进程心跳，不能单凭配置开启推断邮件已投递。

SQLite 开启事务、WAL、外键与安全删除；初诊、去重及版本追加在一个写事务中完成。Linux 私有目录 0700、数据库及 WAL/SHM 0600；Windows 需要部署者设置目录 ACL。数据未进行应用级加密，主机/备份访问权限仍须由部署保护。

研究记录在案例最后一次接受版本后保留 730 天；旧兼容隔离记录保留 90 天。每次读写清理过期项，并提供 `python case_store.py purge` 给每日维护任务，避免无流量时不触发清理。历史备份和导出副本需要独立的到期删除规则。

限流按来源每小时 20 次，仅进程内保存加盐哈希桶，不将来源 IP 写入研究库。只有连接来自 loopback 时信任 Nginx 的 `X-Real-IP`，不信任客户端自填 X-Forwarded-For。服务启动须禁用 Uvicorn 自动代理头改写（程序入口已设置；CLI 使用 `--no-proxy-headers`）。Nginx 网络访问日志的保留规则独立管理。

## 六、迁移、备份、恢复

维护命令仅在受控服务器本地运行，控制台只输出数量/状态，不打印研究正文或密钥：

```text
python case_store.py backup /private/backup/research-YYYYMMDD.sqlite3
python case_store.py export /private/export/research-YYYYMMDD.jsonl
python case_store.py purge
python case_store.py migrate-legacy /private/archive/cases.log.jsonl
```

`--database` 可显式选库。备份通过 SQLite backup API，包含已提交 WAL 数据；不能在运行中只复制一个 `.sqlite3` 文件而遗漏 WAL。导出不会包含 `case_token` 或管理员密钥。目标已存在时不会覆盖。旧 JSONL 迁移只进入隔离，不生成研究记录，源文件保持原样。

恢复：暂停服务，将当前数据库及 sidecar 完整留作回退备份；使用已验证的 SQLite 备份恢复到私有路径，设置目录/文件权限，再启动并核对健康检查和只读数量。代码回滚应回到本次修改前备份，但不得恢复旧硬编码凭证和自动邮件发送；保留新数据库及本地待补交包，不把新数据写回旧公开/混合日志。

## 七、已执行的隔离验收

`tests/test_research_backend.py` 使用临时数据库和 ASGI 本地传输，不访问生产、不发邮件。覆盖完整初诊到跟进、数值与口径保留、去身份、授权拒绝、幂等、并发、版本/能力、失败/无改善/异议、日期/成熟窗口/口径、legacy隔离、备份与过期清理、HTTP错误、管理员权限、CORS、代理地址信任、内存限流，以及公网 MCP 不得借用服务器本地令牌或队列。
