# 择命行效-行之有效的五行商业诊断理论体系

## 简介

品牌营销诊断与咨询报告生成器。基于**北京常识宋道商业咨询策划有限公司**出品的「**择命行效-行之有效的五行商业诊断理论体系**」（理论创立：常亮），用三大核心原则（因果·五行·度）和五行行动链（之金→行水→有木→效火→归土→循环）对品牌做全链条体检，定位断链环，输出含可视化图表的HTML诊断报告。

问金环节含三刀定位法（心智阶梯扫描→空位探测→对立面校验）。提供三档入口：快速入象、完整五诊、案例对照。内置二百四十案行业案例库。

## 版权与授权

**行之有效理论体系由常亮创立，体系文字内容著作权归常亮所有，授权北京常识宋道商业咨询策划有限公司运营。** 本仓库为开源协作版：**个人学习免费；商业使用（含企业内训、咨询交付、付费课程引用等）请联系北京常识宋道商业咨询策划有限公司申请授权**。

- 电话：13120164730
- 邮箱：13120164730@163.com

## 适用场景

- 品牌诊断 / 品牌体检
- 断链分析
- 增长停滞诊断
- 竞品对标诊断
- 定位诊断 / 心智定位

## 不适用场景

- 写 slogan 或广告文案
- 纯数据分析
- 代码编写
- 中医 / 算命的五行
- 与品牌经营无关的话题

## 快速上手

1. 在 WorkBuddy 对话中输入触发词（如"择命行效"或"品牌诊断"）
2. AI 先报 token 消耗区间，确认后进入信息收集
3. 第一轮只问必填 3 项（品牌名+品类/生命周期/痛点）
4. 必填答完后补充选填 5 项（营收/渠道/复购/营销/竞品）
5. 信息充足后 AI 输出 HTML 诊断报告（含水印+SVG 可视化+落款）

## 目录结构

```
zemingxingxiao-brand-diagnosis/
├── SKILL.md                # 核心 skill 文件（frontmatter + 指令）
├── README.md               # 本文件
├── LICENSE                 # 版权声明
├── .gitignore              # Git 忽略规则
├── skill_test_suite.py     # 77 项静态自动化测试
├── test_framework.md       # 5 层测试体系深度参考文档
├── evals/                  # 测试用例目录
│   ├── trigger-tests.md        # 25 个触发测试（10 显式+10 隐式+5 负面）
│   ├── rubric.md               # 10 项质量评分表（5 个 ★ 一票否决）
│   └── case-zhongxuegao.md     # 钟薛高回归基准案例
├── references/             # 参考文档目录
│   ├── theory.md               # 理论原文
│   ├── diagnosis.md            # 诊断流程（含问金三刀）
│   ├── cases.md                # 行业案例库（二百四十案）
│   ├── api_reference.md        # 术语速查
│   ├── visual_templates.md    # 可视化模板
│   └── report_template.html    # HTML 报告模板
├── assets/                 # 配图资源（13 张）
└── examples/               # 示例输出
    └── 钟薛高品牌诊断报告.html  # 完整示例报告
```

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| v2.3.7 | 2026-08-15 | P1+P2 修复：description 收紧、断链表格式统一 HTML、钟薛高顺行修复、present_files 条件化、GBK 编码修复、.gitignore、agent_created |
| v2.3.6 | 2026-08-15 | 收紧 description、自检闸门升级、新建 evals/ 目录 |
| v2.3.5 | 2026-08-15 | 分步硬约束+交互格式+token 区间 |
| v2.3.4 | 2026-08-15 | HTML 化+回传极简+信息分层 |
| v2.3.3 | 2026-08-15 | 报告格式标准化 |
| v2.3.2 | 2026-08-15 | 内化原则 |
| v2.3.1 | 2026-08-15 | 逐刀推进硬约束 |
| v2.3 | 2026-08-15 | 框架字段+触发词置顶 |
| v2.2 | 2026-08-13 | 问金三刀升级+全量统一命名 |

## 测试

### 静态测试（L1）

```bash
python skill_test_suite.py
```

77 项自动化测试，覆盖：结构完整性、理论框架一致性、触发规则与边界、诊断流程完整性、输出规范、引用文件质量、文档合规。

### 行为测试（L2-L5）

详见 `test_framework.md` 和 `evals/` 目录。核心流程：

1. 按 `evals/trigger-tests.md` 的 25 个输入在 WorkBuddy 里切模型跑
2. 按 `evals/rubric.md` 的 10 项标准打分
3. 用 `evals/case-zhongxuegao.md` 做回归基准
4. 改版后重跑，分数不降即为通过

## 版权

详见 [LICENSE](LICENSE)

## 联系方式

- 理论创立：常亮
- 出品方：北京常识宋道商业咨询策划有限公司


---

## DeepSeek Harness 插件（dsh plugin）

本仓库同时是一个可安装的 DeepSeek Harness bundle 插件：`package.json` 声明了 `dsh.bundle`（patch 指向根目录 `cordis.patch.yml`），可被 `dsh plugin add` 直接安装。

安装：

```bash
dsh plugin --profile web add github:changliang-c/zemingxingxiao-brand-diagnosis
```

重启 `dsh web` 后生效。验证挂载：

```bash
dsh --profile web --dump-config | grep zemingxingxiao
```

装上后插件做三件事：

1. 注册主技能 `zemingxingxiao-brand-diagnosis`（本文件 = 完整诊断方法论）；
2. 注册 5 个伴随参考技能，模型用 `skill` 工具按需加载：`zemingxingxiao-theory`（理论）、`zemingxingxiao-diagnosis`（诊断手册）、`zemingxingxiao-cases`（二百四十案案例库）、`zemingxingxiao-visual-templates`（可视化模板）、`zemingxingxiao-glossary`（术语表）；
3. 注入 systemPrompt 路由提示：用户提到品牌诊断/体检/断链分析/定位诊断等意图时主动加载主技能。

报告模板（`references/report_template.html`）与 13 张配图（`assets/`）路径在技能加载时注入为本机绝对路径。插件零运行时依赖（不 import 任何 `@deepseek-ai/*`），卸载自动撤销全部注册。

冒烟测试（无需安装 dsh，mock ctx 直接验证注册行为）：

```bash
npm test
```
