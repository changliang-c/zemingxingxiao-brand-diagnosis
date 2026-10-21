# Zemingxingxiao — evidence-based brand diagnosis

English · [简体中文](README.zh-CN.md)

Zemingxingxiao (择命行效) diagnoses business and brand problems across positioning, acquisition, product, conversion and retention. It combines cause and effect, five interconnected elements, and calibrated balance to locate breaks in a business chain and produce actionable HTML reports. Theory created by **Chang Liang (常亮)**; operated by **北京常识宋道商业咨询策划有限公司**.

**Skill release: 2.6.0 · 2026-10-21** · [Website](https://www.zmxx.work/) · [Public teaching cases](https://www.zmxx.work/cases) · [Downloads](https://www.zmxx.work/#download)

Inspect Metal → Water → Wood → Fire → Earth in order to avoid omissions. Repairs have **no fixed element order**: choose one or two initial actions based on losses, risk, evidence, dependencies, cost and reversibility. This is a business framework, not fortune-telling, stock prediction or a guarantee of growth.

## Start a diagnosis

Install `zemingxingxiao-brand-diagnosis/` in your host's supported skills location, or import the versioned ZIP if the platform accepts Agent Skills packages. The ZIP's internal folder remains stable across releases. `SKILL.md` uses standard frontmatter and string-valued metadata; file-based and DSH adapters remain available.

Ask “Diagnose my brand's retention problem” or “择命行效，帮我做品牌体检”. The assistant offers Chat and Full Report modes, collects business facts in short rounds, and produces evidence, uncertainties, repair priorities and measurable follow-up criteria. A project alias is sufficient; a real brand name is not required.

**Report language:** your explicit choice wins; otherwise the current conversation language applies; if unclear, the default is Simplified Chinese. An English discovery description does not force Chinese conversations into English. Both templates share the same theory and diagnosis rules. See [language and terminology](references/language.md).

## Business research and follow-up

Retain substantive evidence: context, metric values and units, numerators and denominators, observation windows, sources, reasoning and counterevidence, proposed and actual actions, results, failures and disagreement. Aggregate revenue, costs, margin, orders and retention figures are not categorically excluded. Direct identifiers and identifying combinations are removed **before transmission**.

Submissions are for internal research. They are not automatically published, added to the public teaching library or exposed to other users. Existing valid authorization is reused without repeated prompts. When its scope is unclear, explain the recipient, deidentified records and internal research purpose once and obtain authorization; installation or a software license does not supply it. Installation and ordinary questions do not upload conversations, create research records or track installer identities.

When a formal diagnosis is complete, a host with Python and network capability must actually submit the authorized, deidentification-reviewed initial diagnosis using:

```text
python scripts/submit_case.py --input /private/path/case.json
```

The client prepares a deidentified local copy, sends it and records a real receipt. Report delivery must clearly state **received** with a real receipt ID, **pending** with a saved private outbox record and reason, or **not sent** with the reason. If a request was rejected, state that it was attempted but not accepted. A feedback invitation or disclaimer cannot replace submission. Network failures do not prevent report delivery. Per-case follow-up credentials stay in the private outbox, never in reports or public packages.

At skill start, `python scripts/submit_case.py --status` checks local state without networking. If networking is available, the assistant may retry at most one previously authorized and reviewed pending record using `--retry-pending --submission-id ID --retries 2 --timeout 15`; blocked or unauthorized drafts are excluded. This is a bounded recovery step, not a background service.

After delivery, the assistant actively invites an outcome update: action and date; cost and execution level; comparable before/after metrics and mature windows; concurrent changes; failure, harm or disagreement. Initial diagnosis records contain evidence, judgments and proposed actions; later `follow_up` records link actual actions and observed results to that diagnosis. Predictions are not actual outcomes. See the [complete workflow](references/research-feedback.md) and [schema](references/case-schema-v3.json). Synthetic examples demonstrate the structure; they are not customer success evidence.

## MIT License

Code, skill text, prompts, documentation and templates are released under the standard [MIT License](LICENSE). You may use, copy, modify, merge, publish, distribute, sublicense and sell the Software, including commercially, provided the copyright and permission notices are retained in copies or substantial portions. Names, marks, third-party materials and non-public research data are outside the software license; see [RIGHTS.md](RIGHTS.md).

## DeepSeek Harness

The repository remains a DSH bundle with no runtime package dependencies:

```text
dsh plugin --profile web add github:changliang-c/zemingxingxiao-brand-diagnosis
```

Restart the host after installation. The adapter registers the main skill, five companion references and a routing prompt, with local paths to templates and assets. English and Chinese diagnosis requests are supported. Registration itself does not provide network access or prove successful transmission.

## Contents and verification

- `SKILL.md`: common rules and diagnostic workflow.
- `references/`: original theory, procedures, terminology, bilingual templates, research schema and workflow.
- `scripts/submit_case.py`: deidentification, private outbox, bounded retries and real receipts.
- `examples/*.synthetic.json`: fictional diagnosis and linked follow-up.
- `assets/`: framework illustrations.
- `dsh/` and `cordis.patch.yml`: existing DSH integration.

Run `npm test` for DSH registration and cleanup; `python -m unittest discover -s test -p "test_*.py"` for transport and recovery; `python skill_test_suite.py` for existing static checks. Standard Agent Skills validation runs on the stable-name folder during release. Online store installation and network access depend on platform permissions and configuration.
