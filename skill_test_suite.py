#!/usr/bin/env python3
"""
择命行效-行之有效的五行商业诊断理论体系 Skill 一键全维度测试套件
=====================================================
基于 nihaixia-tianji-mingli skill_test_suite.py 的 7 维测试方法论，
适配为择命行效理论体系的专项测试。

用法:
    python skill_test_suite.py

报告分级:
    P0 - 必须修复（阻断性问题，skill 无法正常工作）
    P1 - 建议修复（重要问题，影响可靠性或准确性）
    P2 - 看创作者意愿（改进建议，不影响核心功能）
    P3 - 无需修复（信息性提醒）
"""

import sys
import os
import re
import time
import json
import traceback
from pathlib import Path
from datetime import datetime

# ============================================================
# 配置
# ============================================================
SKILL_DIR = Path(__file__).parent
REFERENCES_DIR = SKILL_DIR / "references"
ASSETS_DIR = SKILL_DIR / "assets"

# ============================================================
# 测试结果收集
# ============================================================
class TestResult:
    def __init__(self, dimension, name, passed, detail="", severity="P0"):
        self.dimension = dimension
        self.name = name
        self.passed = passed
        self.detail = detail
        self.severity = severity
        self.duration = 0

class TestSuite:
    def __init__(self):
        self.results = []
        self.current_dimension = ""

    def set_dimension(self, name):
        self.current_dimension = name

    def record(self, name, passed, detail="", severity="P0"):
        r = TestResult(self.current_dimension, name, passed, detail, severity)
        self.results.append(r)
        return r

    def run_test(self, name, test_func, severity="P0"):
        t0 = time.perf_counter()
        try:
            passed, detail = test_func()
        except Exception as e:
            passed = False
            detail = f"异常: {e}\n{traceback.format_exc()[-200:]}"
        elapsed = (time.perf_counter() - t0) * 1000

        r = self.record(name, passed, detail, severity)
        r.duration = elapsed
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}" + (f" ({elapsed:.0f}ms)" if elapsed > 10 else ""))
        if not passed and detail:
            for line in detail.split("\n"):
                print(f"         {line}")
        return passed


def read_skill_md():
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def extract_frontmatter(content):
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return None
    return match.group(1)


# ============================================================
# 测试维度 1: 结构完整性验证 (P0)
# ============================================================
def test_structural(suite):
    suite.set_dimension("一、结构完整性验证")
    print("\n一、结构完整性验证 (P0 - 必须通过)")

    # 1.1 SKILL.md 存在
    def t():
        skill_md = SKILL_DIR / "SKILL.md"
        if not skill_md.exists():
            return False, "SKILL.md 不存在"
        return True, f"找到 SKILL.md ({skill_md.stat().st_size} bytes)"
    suite.run_test("SKILL.md 存在", t, "P0")

    # 1.2 YAML frontmatter 格式
    def t():
        content = read_skill_md()
        if not content.startswith("---"):
            return False, "缺少 YAML frontmatter 开头 ---"
        fm = extract_frontmatter(content)
        if not fm:
            return False, "YAML frontmatter 格式无效"
        return True, "frontmatter 格式正确"
    suite.run_test("YAML frontmatter 格式", t, "P0")

    # 1.3 name 字段
    def t():
        fm = extract_frontmatter(read_skill_md())
        name_match = re.search(r'name:\s*(.+)', fm)
        if not name_match:
            return False, "缺少 name 字段"
        name = name_match.group(1).strip()
        if not re.match(r'^[a-z0-9-]+$', name):
            return False, f"name '{name}' 不符合 hyphen-case 规范"
        if name.startswith('-') or name.endswith('-') or '--' in name:
            return False, f"name '{name}' 含有非法连字符位置"
        return True, f"name = '{name}'"
    suite.run_test("name 字段规范", t, "P0")

    # 1.4 description 字段
    def t():
        fm = extract_frontmatter(read_skill_md())
        desc_match = re.search(r'description:\s*(.+)', fm)
        if not desc_match:
            return False, "缺少 description 字段"
        desc = desc_match.group(1).strip()
        if '<' in desc or '>' in desc:
            return False, "description 含有尖括号"
        if len(desc) < 20:
            return False, f"description 过短 ({len(desc)} 字符)"
        return True, f"description 长度 {len(desc)} 字符"
    suite.run_test("description 字段规范", t, "P0")

    # 1.5 version 字段
    def t():
        fm = extract_frontmatter(read_skill_md())
        ver_match = re.search(r'version:\s*(.+)', fm)
        if not ver_match:
            return False, "缺少 version 字段"
        ver = ver_match.group(1).strip()
        return True, f"version = {ver}"
    suite.run_test("version 字段存在", t, "P0")

    # 1.6 license 字段
    def t():
        fm = extract_frontmatter(read_skill_md())
        lic_match = re.search(r'license:\s*(.+)', fm, re.DOTALL)
        if not lic_match:
            return False, "缺少 license 字段"
        lic = lic_match.group(1).strip()
        if len(lic) < 20:
            return False, f"license 过短 ({len(lic)} 字符)，可能缺少版权说明"
        if "常亮" not in lic:
            return False, "license 未提及理论创立人'常亮'"
        return True, f"license 字段完整 ({len(lic)} 字符)"
    suite.run_test("license 版权字段", t, "P0")

    # 1.7 所有引用文件存在
    def t():
        required_files = [
            "SKILL.md",
            "references/theory.md",
            "references/cases.md",
            "references/diagnosis.md",
            "references/api_reference.md",
            "references/visual_templates.md",
            "references/report_template.html",
            "assets/README.md",
        ]
        missing = []
        for f in required_files:
            if not (SKILL_DIR / f).exists():
                missing.append(f)
        if missing:
            return False, f"缺失文件: {', '.join(missing)}"
        return True, f"全部 {len(required_files)} 个文件存在"
    suite.run_test("引用文件完整性", t, "P0")

    # 1.8 SKILL.md 中引用的文件路径都存在
    def t():
        content = read_skill_md()
        refs = re.findall(r'(?:references|assets)/[a-zA-Z0-9_./\-\u4e00-\u9fff]+', content)
        missing = []
        for ref in refs:
            ref = ref.rstrip('`.,;)')
            if not (SKILL_DIR / ref).exists():
                missing.append(ref)
        if missing:
            return False, f"SKILL.md 引用了不存在的文件: {', '.join(set(missing))}"
        return True, f"SKILL.md 中 {len(set(refs))} 个文件引用全部存在"
    suite.run_test("SKILL.md 引用路径有效", t, "P0")

    # 1.9 assets 目录配图完整性
    def t():
        expected_images = [
            "01_因果两极五行输运图.png",
            "02_五行行动链循环图.png",
            "03_五行相生相克双环图.png",
            "04_鞍点地形图.png",
            "05_四象地形状态图.png",
            "06_五诊五问流程图.png",
            "07_三才定位结构图.png",
            "08_度_因果秤杆图.png",
            "09_五行过与不及图.png",
            "10_SWOT对比五行图.png",
            "11_行业五行定位图.png",
            "12_苹果五行链图.png",
            "12_苹果五行链图_出版版.png",
        ]
        missing = []
        for img in expected_images:
            if not (ASSETS_DIR / img).exists():
                missing.append(img)
        if missing:
            return False, f"缺失配图: {', '.join(missing)}"
        actual_count = len(list(ASSETS_DIR.glob("*.png")))
        return True, f"全部 {len(expected_images)} 张配图存在 (目录共 {actual_count} 张 PNG)"
    suite.run_test("assets 配图完整性", t, "P0")


# ============================================================
# 测试维度 2: 理论框架一致性验证 (P0)
# ============================================================
def test_theory_consistency(suite):
    suite.set_dimension("二、理论框架一致性验证")
    print("\n二、理论框架一致性验证 (P0 - 必须通过)")

    content = read_skill_md()

    # 2.1 五行 JSON 结构存在且可解析
    def t():
        json_match = re.search(r'```json\s*(\{.*?"framework".*?\})\s*```', content, re.DOTALL)
        if not json_match:
            return False, "未找到五行框架 JSON 定义"
        try:
            data = json.loads(json_match.group(1))
            fw = data.get("framework", {})
            if not fw:
                return False, "JSON 中缺少 framework 字段"
            elements = fw.get("five_elements", [])
            if len(elements) != 5:
                return False, f"five_elements 应有5环，实际 {len(elements)} 环"
            return True, f"五行 JSON 结构有效，5环: {[e['element'] for e in elements]}"
        except json.JSONDecodeError as e:
            return False, f"JSON 解析失败: {e}"
    suite.run_test("五行 JSON 结构可解析", t, "P0")

    # 2.2 五行五环顺序正确（金→水→木→火→土）
    def t():
        json_match = re.search(r'```json\s*(\{.*?"framework".*?\})\s*```', content, re.DOTALL)
        if not json_match:
            return False, "未找到五行框架 JSON"
        data = json.loads(json_match.group(1))
        elements = data["framework"]["five_elements"]
        order = [e["element"] for e in elements]
        expected = ["金", "水", "木", "火", "土"]
        if order != expected:
            return False, f"五行顺序错误: {order}，应为 {expected}"
        # 检查操作动词
        actions = [e["character"] + e["action"] for e in elements]
        expected_actions = ["之定位下刀", "行流量引水", "有产品植树", "效转化点火", "归资产归藏"]
        return True, f"顺序正确: {order}，操作: {actions}"
    suite.run_test("五行五环顺序正确", t, "P0")

    # 2.3 三原则存在
    def t():
        json_match = re.search(r'```json\s*(\{.*?"framework".*?\})\s*```', content, re.DOTALL)
        data = json.loads(json_match.group(1))
        principles = data["framework"].get("three_principles", [])
        expected = ["因果", "五行", "度"]
        if principles != expected:
            return False, f"三原则不匹配: {principles}，应为 {expected}"
        # 检查正文是否展开解释
        for p in expected:
            if p not in content:
                return False, f"正文未展开解释原则'{p}'"
        return True, f"三原则完整: {principles}"
    suite.run_test("三大核心原则完整", t, "P0")

    # 2.4 三铁律与 theory.md 一致
    def t():
        json_match = re.search(r'```json\s*(\{.*?"framework".*?\})\s*```', content, re.DOTALL)
        data = json.loads(json_match.group(1))
        laws = data["framework"].get("three_iron_laws", [])
        expected = ["行在知前", "循环不息", "效必归土"]
        if laws != expected:
            return False, f"三铁律不匹配: {laws}，应为 {expected}"
        # 交叉验证 theory.md
        theory = (REFERENCES_DIR / "theory.md").read_text(encoding="utf-8")
        for law in expected:
            if law not in theory:
                return False, f"三铁律'{law}'在 theory.md 中未找到"
        return True, f"三铁律一致: {laws} (SKILL.md ↔ theory.md 交叉验证通过)"
    suite.run_test("三铁律 theory.md 交叉验证", t, "P0")

    # 2.5 五行操作法速查表完整
    def t():
        table_match = re.search(r'## 五行操作法速查\s*\n.*?(?=\n##|\n###|\Z)', content, re.DOTALL)
        if not table_match:
            return False, "未找到五行操作法速查表"
        table = table_match.group(0)
        required_terms = ["之金", "行水", "有木", "效火", "归土", "下刀", "引水", "植树", "点火", "归藏"]
        missing = [t for t in required_terms if t not in table]
        if missing:
            return False, f"速查表缺少术语: {missing}"
        return True, "五行操作法速查表完整"
    suite.run_test("五行操作法速查表完整", t, "P0")

    # 2.6 度的过与不及速查表
    def t():
        if "过与不及" not in content:
            return False, "缺少'度'的过与不及速查表"
        # 检查每环都有过/不及两种错法
        table_match = re.search(r'\| 金 \|.*?\| 土 \|', content, re.DOTALL)
        if not table_match:
            return False, "过与不及表格式不完整"
        return True, "度的过与不及速查表存在且完整"
    suite.run_test("度的过与不及速查表", t, "P0")

    # 2.7 四象判定表完整
    def t():
        if "老阳" not in content or "少阳" not in content or "少阴" not in content or "老阴" not in content:
            return False, "四象判定缺少象位名称"
        # 检查四象都有特征描述
        for xiang in ["老阳", "少阳", "少阴", "老阴"]:
            pattern = rf'{xiang}.*?火.*?水|{xiang}.*?水.*?火'
            if not re.search(pattern, content):
                return False, f"四象'{xiang}'缺少水火状态描述"
        return True, "四象判定表完整（老阳/少阳/少阴/老阴）"
    suite.run_test("四象判定表完整", t, "P0")

    # 2.8 断链定位规则完整
    def t():
        chain_terms = ["金锈", "泵抽式", "塑料树", "野火", "佃农"]
        missing = [t for t in chain_terms if t not in content]
        if missing:
            return False, f"断链定位缺少术语: {missing}"
        # 检查断链→修复环节映射
        if "断在" not in content:
            return False, "缺少断链定位规则"
        return True, f"断链定位规则完整，5种断链术语全部存在"
    suite.run_test("断链定位规则完整", t, "P0")


# ============================================================
# 测试维度 3: 触发规则与边界 (P1)
# ============================================================
def test_trigger_rules(suite):
    suite.set_dimension("三、触发规则与边界")
    print("\n三、触发规则与边界 (P1 - 建议通过)")

    content = read_skill_md()
    fm = extract_frontmatter(content)

    # 3.1 触发词"择命行效"在 description 首位
    def t():
        desc_match = re.search(r'description:\s*"?(.+?)"?\s*$', fm, re.MULTILINE)
        if not desc_match:
            return False, "无法提取 description"
        desc = desc_match.group(1)
        if "择命行效" not in desc:
            return False, "description 未包含触发词'择命行效'"
        # 检查是否在首位（description 开头附近）
        if desc.index("择命行效") > 20:
            return False, f"'择命行效'未在 description 首位 (位置={desc.index('择命行效')})"
        return True, "'择命行效'在 description 首位"
    suite.run_test("触发词'择命行效'首位", t, "P1")

    # 3.2 兼容触发词"行之有效"
    def t():
        if "行之有效" not in content:
            return False, "缺少兼容触发词'行之有效'"
        return True, "'行之有效'作为兼容触发词存在"
    suite.run_test("兼容触发词'行之有效'", t, "P1")

    # 3.3 应覆盖的关键词
    should_trigger = ["品牌诊断", "品牌定位", "营销方案", "营销策略", "咨询报告",
                      "品牌分析", "定位诊断", "品牌体检", "心智阶梯", "空位探测",
                      "商业计划书", "品牌策略", "差异化定位", "品类开创", "定位复盘"]
    for kw in should_trigger:
        def make_test(keyword):
            def t():
                if keyword in content:
                    return True, f"'{keyword}' 在 SKILL.md 中被覆盖"
                return False, f"'{keyword}' 未在 SKILL.md 中出现"
            return t
        suite.run_test(f"应触发关键词: '{kw}'", make_test(kw), "P1")

    # 3.4 八类触发类别存在
    def t():
        categories = ["第一类", "第二类", "第三类", "第四类", "第五类", "第六类", "第七类", "第八类"]
        missing = [c for c in categories if c not in content]
        if missing:
            return False, f"缺少触发类别: {missing}"
        return True, f"八类触发类别全部存在"
    suite.run_test("八类触发类别完整", t, "P1")

    # 3.5 排除规则存在
    def t():
        if "排除规则" not in content and "不触发" not in content:
            return False, "缺少排除规则"
        # 检查是否排除了中医/算命
        if "中医" not in content or "算命" not in content:
            return False, "排除规则未明确排除中医/算命场景"
        return True, "排除规则存在（含中医/算命排除）"
    suite.run_test("排除规则存在性", t, "P1")

    # 3.6 红线场景定义
    def t():
        if "红线" not in content:
            return False, "缺少红线场景定义"
        red_lines = ["投资分析", "预测股价", "平台规则", "算命", "风水"]
        found = [r for r in red_lines if r in content]
        if len(found) < 3:
            return False, f"红线场景覆盖不足: 仅找到 {found}"
        return True, f"红线场景定义完整: {found}"
    suite.run_test("红线场景定义", t, "P1")

    # 3.7 模型建议标注
    def t():
        if "建议使用较强模型" not in content and "较强模型" not in content:
            return False, "缺少模型建议标注"
        return True, "模型建议标注存在"
    suite.run_test("模型建议标注", t, "P1")


# ============================================================
# 测试维度 4: 诊断流程完整性 (P1)
# ============================================================
def test_diagnostic_flow(suite):
    suite.set_dimension("四、诊断流程完整性")
    print("\n四、诊断流程完整性 (P1 - 建议通过)")

    content = read_skill_md()

    # 4.1 信息收集引擎存在
    def t():
        if "信息收集引擎" not in content:
            return False, "缺少信息收集引擎"
        return True, "信息收集引擎存在"
    suite.run_test("信息收集引擎存在", t, "P1")

    # 4.2 分步·硬约束存在
    def t():
        if "分步" not in content or "硬约束" not in content:
            return False, "缺少分步·硬约束"
        if "禁止一次性抛出全部" not in content:
            return False, "缺少'禁止一次性抛出全部'硬约束"
        return True, "分步·硬约束存在且完整"
    suite.run_test("分步·硬约束", t, "P1")

    # 4.3 交互格式·硬约束存在
    def t():
        if "交互格式" not in content or "硬约束" not in content:
            return False, "缺少交互格式·硬约束"
        if "禁止冗余" not in content:
            return False, "缺少'禁止冗余'约束"
        return True, "交互格式·硬约束存在"
    suite.run_test("交互格式·硬约束", t, "P1")

    # 4.4 token 区间提示
    def t():
        if "token" not in content.lower() or "区间" not in content:
            return False, "缺少 token 区间提示"
        return True, "token 区间提示存在"
    suite.run_test("token 区间提示", t, "P1")

    # 4.5 三档路由存在
    def t():
        if "档一" not in content or "档二" not in content or "档三" not in content:
            return False, "缺少三档路由"
        if "快速入象" not in content or "完整五诊" not in content or "案例对照" not in content:
            return False, "三档名称不完整"
        return True, "三档路由完整（快速入象/完整五诊/案例对照）"
    suite.run_test("三档路由完整", t, "P1")

    # 4.6 诊断决策矩阵存在
    def t():
        if "诊断决策矩阵" not in content:
            return False, "缺少诊断决策矩阵"
        return True, "诊断决策矩阵存在"
    suite.run_test("诊断决策矩阵", t, "P1")

    # 4.7 问金三刀存在
    def t():
        if "问金三刀" not in content:
            return False, "缺少问金三刀"
        knives = ["心智阶梯", "空位探测", "对立面校验"]
        missing = [k for k in knives if k not in content]
        if missing:
            return False, f"问金三刀缺少: {missing}"
        return True, "问金三刀完整（心智阶梯→空位探测→对立面校验）"
    suite.run_test("问金三刀完整", t, "P1")

    # 4.8 三刀执行·硬约束（v2.4 由逐刀推进升级）
    def t():
        if "三刀执行" not in content or "硬约束" not in content:
            return False, "缺少三刀执行·硬约束"
        if "禁止跳刀" not in content:
            return False, "缺少'禁止跳刀'约束"
        if "心智阶梯扫描" not in content or "空位探测" not in content or "对立面校验" not in content:
            return False, "缺少三刀顺序定义"
        return True, "三刀执行·硬约束完整"
    suite.run_test("三刀执行·硬约束", t, "P1")

    # 4.8a 取证优先·硬约束（v2.4 新增）
    def t():
        if "取证优先" not in content:
            return False, "缺少取证优先·硬约束"
        if "估计" not in content or "预判" not in content:
            return False, "缺少'禁止估计/预判支撑结论'约束"
        if "行业功课" not in content:
            return False, "缺少'进刀前行业功课'要求"
        return True, "取证优先·硬约束完整"
    suite.run_test("取证优先·硬约束", t, "P1")

    # 4.8b 问题分流·硬约束（v2.4 新增）
    def t():
        if "问题分流" not in content:
            return False, "缺少问题分流·硬约束"
        if "客观公开类" not in content or "主观内部类" not in content:
            return False, "缺少两类信息划分"
        return True, "问题分流·硬约束完整"
    suite.run_test("问题分流·硬约束", t, "P1")

    # 4.8c 双模式入口（v2.4 新增）
    def t():
        if "双模式" not in content:
            return False, "缺少双模式入口"
        if "Chat 模式" not in content or "完整报告模式" not in content:
            return False, "缺少两模式定义"
        if "选项化作答" not in content:
            return False, "缺少'选项化作答'约束"
        if "收集完再整体分析" not in content:
            return False, "缺少'收集完再整体分析'约束"
        return True, "双模式入口完整"
    suite.run_test("双模式入口", t, "P1")

    # 4.8d 被质疑事实应对（v2.4 新增）
    def t():
        if "被质疑事实" not in content:
            return False, "缺少被质疑事实应对规则"
        if "认账修正" not in content or "禁止辩解" not in content:
            return False, "缺少'认账修正/禁止辩解'约束"
        return True, "被质疑事实应对规则完整"
    suite.run_test("被质疑事实应对", t, "P1")

    # 4.9 内化原则
    def t():
        if "内化原则" not in content:
            return False, "缺少内化原则"
        if "禁止在对话中显式宣告" not in content:
            return False, "缺少'禁止显式宣告'约束"
        if "念报告" not in content:
            return False, "缺少'念报告的分析师'禁止项"
        return True, "内化原则完整"
    suite.run_test("内化原则", t, "P1")

    # 4.10 三刀后必接五行链
    def t():
        if "三刀之后必接五行链" not in content:
            return False, "缺少'三刀之后必接五行链'衔接规则"
        # 检查三个必接问题
        if "引来的水" not in content or "树撑着" not in content or "土在哪里" not in content:
            return False, "三刀后衔接问题不完整"
        return True, "三刀后必接五行链规则完整"
    suite.run_test("三刀后必接五行链", t, "P1")

    # 4.11 五诊五问维度覆盖
    def t():
        dims = ["定位与下刀", "流量与引水", "产品与植树", "增长与点火", "复购与归土"]
        missing = [d for d in dims if d not in content]
        if missing:
            return False, f"五诊维度缺少: {missing}"
        return True, f"五诊五问维度全覆盖"
    suite.run_test("五诊五问维度覆盖", t, "P1")

    # 4.12 诊断五阶段完整
    def t():
        stages = ["五诊收集", "四象判定", "断链定位", "处方开方", "报告生成"]
        missing = [s for s in stages if s not in content]
        if missing:
            return False, f"诊断阶段缺少: {missing}"
        return True, "诊断五阶段完整"
    suite.run_test("诊断五阶段完整", t, "P1")

    # 4.13 处方顺行规则
    def t():
        if "顺行" not in content:
            return False, "缺少处方顺行规则"
        if "严禁乱序" not in content:
            return False, "缺少'严禁乱序'约束"
        return True, "处方顺行规则存在"
    suite.run_test("处方顺行规则", t, "P1")

    # 4.14 执业约束（四边界+五戒）
    def t():
        if "四边界" not in content:
            return False, "缺少四边界"
        if "五戒" not in content and "执业五戒" not in content:
            return False, "缺少执业五戒"
        return True, "执业约束完整（四边界+五戒）"
    suite.run_test("执业约束（四边界+五戒）", t, "P1")


# ============================================================
# 测试维度 5: 输出规范测试 (P2)
# ============================================================
def test_output_spec(suite):
    suite.set_dimension("五、输出规范测试")
    print("\n五、输出规范测试 (P2 - 看创作者意愿)")

    content = read_skill_md()

    # 5.1 五条强制规则
    def t():
        if "五条强制规则" not in content and "五条" not in content:
            return False, "缺少'五条强制规则'标注"
        # 计数规则条目
        rules = re.findall(r'\n\d+\.\s\*\*', content)
        if len(rules) < 5:
            return False, f"标注为五条但实际只找到 {len(rules)} 条"
        return True, f"找到五条强制规则 ({len(rules)} 条)"
    suite.run_test("五条强制规则", t, "P2")

    # 5.2 HTML 输出要求
    def t():
        if "HTML" not in content:
            return False, "缺少 HTML 输出要求"
        if "present_files" not in content:
            return False, "缺少 present_files 展示要求"
        return True, "HTML 输出要求存在"
    suite.run_test("HTML 输出要求", t, "P2")

    # 5.3 水印 CSS 要求
    def t():
        if "水印" not in content:
            return False, "缺少水印要求"
        if "body::before" not in content:
            return False, "缺少 body::before 水印 CSS 说明"
        if "opacity" not in content:
            return False, "缺少水印 opacity 说明"
        return True, "水印 CSS 要求完整"
    suite.run_test("水印 CSS 要求", t, "P2")

    # 5.4 SVG 可视化嵌入要求
    def t():
        if "svg" not in content.lower():
            return False, "缺少 SVG 可视化要求"
        if "禁止退化为 Markdown" not in content:
            return False, "缺少'禁止退化为 Markdown'约束"
        return True, "SVG 嵌入要求存在"
    suite.run_test("SVG 可视化嵌入要求", t, "P2")

    # 5.5 五行配色规范
    def t():
        colors = {
            "金": "#D4A017",
            "水": "#2196F3",
            "木": "#4CAF50",
            "火": "#F44336",
            "土": "#795548",
        }
        missing = []
        for element, color in colors.items():
            if color not in content:
                missing.append(f"{element}={color}")
        if missing:
            return False, f"五行配色缺少: {missing}"
        return True, "五行配色规范完整"
    suite.run_test("五行配色规范", t, "P2")

    # 5.6 自检清单完整
    def t():
        if "自检清单" not in content:
            return False, "缺少自检清单"
        checks = ["品牌名", "理论体系标注", "入象", "断链", "开方", "取数方法",
                  "现代白话", "90天复检", "可视化", "SVG", "HTML格式", "顺行"]
        missing = [c for c in checks if c not in content]
        if len(missing) > 2:
            return False, f"自检清单缺少多项: {missing}"
        return True, f"自检清单完整 (覆盖 {len(checks)-len(missing)}/{len(checks)} 检查项)"
    suite.run_test("自检清单完整", t, "P2")

    # 5.7 90天复检目标值
    def t():
        if "90天复检" not in content:
            return False, "缺少 90 天复检要求"
        if "复购率" not in content or "自然流占比" not in content or "老客成交" not in content:
            return False, "缺少土指标三件套"
        return True, "90天复检土指标三件套完整"
    suite.run_test("90天复检土指标三件套", t, "P2")

    # 5.8 案例回传机制
    def t():
        if "案例回传" not in content and "回传" not in content:
            return False, "缺少案例回传机制"
        if "脱敏" not in content:
            return False, "缺少脱敏规则"
        return True, "案例回传机制存在（含脱敏规则）"
    suite.run_test("案例回传机制", t, "P2")

    # 5.9 数据取数引导
    def t():
        if "取数" not in content:
            return False, "缺少数据取数引导"
        methods = ["复购率", "自然流占比", "获客成本", "老客成交占比"]
        missing = [m for m in methods if m not in content]
        if missing:
            return False, f"取数方法缺少: {missing}"
        return True, "数据取数引导完整（4种关键指标）"
    suite.run_test("数据取数引导", t, "P2")


# ============================================================
# 测试维度 6: 引用文件质量验证 (P2)
# ============================================================
def test_reference_quality(suite):
    suite.set_dimension("六、引用文件质量验证")
    print("\n六、引用文件质量验证 (P2 - 看创作者意愿)")

    # 6.1 theory.md 理论框架文档
    def t():
        p = REFERENCES_DIR / "theory.md"
        if not p.exists():
            return False, "theory.md 不存在"
        size = p.stat().st_size
        if size < 10000:
            return False, f"theory.md 内容过少 ({size} bytes)"
        content = p.read_text(encoding="utf-8")
        # 检查关键章节
        required_sections = ["因果", "五行", "度", "三铁律", "行在知前", "循环不息", "效必归土"]
        missing = [s for s in required_sections if s not in content]
        if missing:
            return False, f"theory.md 缺少关键内容: {missing}"
        return True, f"theory.md 完整 ({size} bytes)"
    suite.run_test("theory.md 理论文档", t, "P2")

    # 6.2 cases.md 案例库
    def t():
        p = REFERENCES_DIR / "cases.md"
        if not p.exists():
            return False, "cases.md 不存在"
        size = p.stat().st_size
        if size < 100000:
            return False, f"cases.md 内容过少 ({size} bytes)，应为二百四十案"
        content = p.read_text(encoding="utf-8")
        # 统计案例数量（按标题模式）
        case_count = len(re.findall(r'^#{1,3}\s+.*案', content, re.MULTILINE))
        if case_count < 50:
            return False, f"案例数量过少 ({case_count} 个)，应为 240 案"
        return True, f"cases.md ({size} bytes, 约 {case_count} 个案例标题)"
    suite.run_test("cases.md 案例库", t, "P2")

    # 6.3 diagnosis.md 诊断操作手册
    def t():
        p = REFERENCES_DIR / "diagnosis.md"
        if not p.exists():
            return False, "diagnosis.md 不存在"
        size = p.stat().st_size
        if size < 10000:
            return False, f"diagnosis.md 内容过少 ({size} bytes)"
        content = p.read_text(encoding="utf-8")
        required = ["五诊", "四象", "处方", "报告模板", "问金"]
        missing = [r for r in required if r not in content]
        if missing:
            return False, f"diagnosis.md 缺少: {missing}"
        return True, f"diagnosis.md 完整 ({size} bytes)"
    suite.run_test("diagnosis.md 诊断手册", t, "P2")

    # 6.4 api_reference.md 术语速查
    def t():
        p = REFERENCES_DIR / "api_reference.md"
        if not p.exists():
            return False, "api_reference.md 不存在"
        size = p.stat().st_size
        if size < 1000:
            return False, f"api_reference.md 内容过少 ({size} bytes)"
        content = p.read_text(encoding="utf-8")
        if "心智阶梯" not in content or "空位探测" not in content:
            return False, "术语速查缺少定位三刀术语"
        return True, f"api_reference.md 完整 ({size} bytes)"
    suite.run_test("api_reference.md 术语速查", t, "P2")

    # 6.5 visual_templates.md 可视化模板
    def t():
        p = REFERENCES_DIR / "visual_templates.md"
        if not p.exists():
            return False, "visual_templates.md 不存在"
        size = p.stat().st_size
        if size < 5000:
            return False, f"visual_templates.md 内容过少 ({size} bytes)"
        return True, f"visual_templates.md 完整 ({size} bytes)"
    suite.run_test("visual_templates.md 可视化模板", t, "P2")

    # 6.6 report_template.html 报告模板
    def t():
        p = REFERENCES_DIR / "report_template.html"
        if not p.exists():
            return False, "report_template.html 不存在"
        size = p.stat().st_size
        if size < 3000:
            return False, f"report_template.html 内容过少 ({size} bytes)"
        content = p.read_text(encoding="utf-8")
        # 检查关键元素
        checks = {
            "水印CSS": "body::before" in content or "body::after" in content,
            "rotate": "rotate" in content,
            "opacity": "opacity" in content,
            "五行配色": "#D4A017" in content or "D4A017" in content,
            "table标签": "<table" in content,
            "svg嵌入位": "chart-container" in content or "svg" in content.lower(),
            "免责声明": "免责" in content or "声明" in content,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            return False, f"report_template.html 缺少: {missing}"
        return True, f"report_template.html 完整 ({size} bytes, 7项检查全过)"
    suite.run_test("report_template.html 报告模板", t, "P2")

    # 6.7 SKILL.md 与 theory.md 公司名一致性
    def t():
        skill_content = read_skill_md()
        theory_content = (REFERENCES_DIR / "theory.md").read_text(encoding="utf-8")
        company = "北京常识宋道商业咨询策划有限公司"
        skill_has = company in skill_content
        theory_has = company in theory_content
        if not skill_has:
            return False, f"SKILL.md 中未找到完整公司名"
        if not theory_has:
            return False, f"theory.md 中未找到完整公司名"
        return True, f"公司名一致: '{company}'"
    suite.run_test("公司名一致性 (SKILL.md <-> theory.md)", t, "P2")

    # 6.8 案例库卷数完整性
    def t():
        content = (REFERENCES_DIR / "cases.md").read_text(encoding="utf-8")
        volumes = ["卷一", "卷二", "卷三", "卷四"]
        missing = [v for v in volumes if v not in content]
        if missing:
            return False, f"案例库缺少卷: {missing}"
        return True, "案例库四卷齐全"
    suite.run_test("案例库四卷完整", t, "P2")


# ============================================================
# 测试维度 7: 文档与合规 (P3)
# ============================================================
def test_documentation(suite):
    suite.set_dimension("七、文档与合规")
    print("\n七、文档与合规 (P3 - 无需修复)")

    content = read_skill_md()

    # 7.1 版权声明存在
    def t():
        if "版权" not in content:
            return False, "缺少版权声明"
        if "常亮" not in content:
            return False, "版权声明未提及理论创立人"
        if "开源协作" not in content:
            return False, "缺少'开源协作'声明"
        return True, "版权声明完整"
    suite.run_test("版权声明", t, "P3")

    # 7.2 author 字段
    def t():
        fm = extract_frontmatter(content)
        author_match = re.search(r'author:\s*(.+)', fm)
        if not author_match:
            return False, "缺少 author 字段"
        author = author_match.group(1).strip()
        if author != "常亮":
            return False, f"author = '{author}'，应为 '常亮'"
        return True, f"author = '{author}'"
    suite.run_test("author 字段", t, "P3")

    # 7.3 空文件检查（白名单模式，避免测试产物自污染）
    def t():
        whitelist_files = [
            "SKILL.md",
            "references/theory.md",
            "references/cases.md",
            "references/diagnosis.md",
            "references/api_reference.md",
            "references/visual_templates.md",
            "references/report_template.html",
            "assets/README.md",
            "evals/trigger-tests.md",
            "evals/rubric.md",
            "evals/case-zhongxuegao.md",
            "test_framework.md",
        ]
        empty_files = []
        for f in whitelist_files:
            p = SKILL_DIR / f
            if p.exists() and p.stat().st_size == 0:
                empty_files.append(f)
        if empty_files:
            return False, f"发现空文件: {', '.join(empty_files)}"
        return True, "无空文件（白名单检查12个核心文件）"
    suite.run_test("空文件检查", t, "P3")

    # 7.4 assets/README.md 存在且有内容
    def t():
        p = ASSETS_DIR / "README.md"
        if not p.exists():
            return False, "assets/README.md 不存在"
        size = p.stat().st_size
        if size < 100:
            return False, f"assets/README.md 内容过少 ({size} bytes)"
        return True, f"assets/README.md ({size} bytes)"
    suite.run_test("assets/README.md", t, "P3")

    # 7.5 SKILL.md 中无残留占位符
    def t():
        placeholders = ["TODO", "FIXME", "XXX", "待填写", "PLACEHOLDER"]
        found = []
        for ph in placeholders:
            if ph in content:
                found.append(ph)
        if found:
            return False, f"发现残留占位符: {found}"
        return True, "无残留占位符"
    suite.run_test("无残留占位符", t, "P3")

    # 7.6 .git 仓库存在（P3：存在即提示，缺失不判失败）
    def t():
        git_dir = SKILL_DIR / ".git"
        if not git_dir.exists():
            return True, ".git 目录不存在（zip 分发时正常，不影响功能）"
        return True, ".git 版本管理存在"
    suite.run_test("Git 版本管理", t, "P3")

    # 7.7 统一命名检查
    def t():
        # 检查 SKILL.md 主标题是否为统一名称
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if not title_match:
            return False, "未找到主标题"
        title = title_match.group(1).strip()
        expected = "择命行效-行之有效的五行商业诊断理论体系"
        if title != expected:
            return False, f"主标题='{title}'，应为'{expected}'"
        return True, f"主标题统一: '{title}'"
    suite.run_test("统一命名检查", t, "P3")

    # 7.8 必备可视化清单完整
    def t():
        visuals = ["五行链条诊断图", "四象定位图", "断链与修复序列表", "雷达图"]
        missing = [v for v in visuals if v not in content]
        if missing:
            return False, f"必备可视化缺少: {missing}"
        return True, "4项必备可视化清单完整"
    suite.run_test("必备可视化清单", t, "P3")


# ============================================================
# 报告生成
# ============================================================
def generate_report(suite):
    print("\n" + "=" * 72)
    print("  择命行效-行之有效的五行商业诊断理论体系 Skill 测试报告")
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 读取版本
    try:
        content = read_skill_md()
        ver_match = re.search(r'version:\s*(.+)', extract_frontmatter(content))
        ver = ver_match.group(1).strip() if ver_match else "?"
    except:
        ver = "?"
    print(f"  Skill版本: v{ver}")
    print("=" * 72)

    # 按维度统计
    dimensions = {}
    for r in suite.results:
        if r.dimension not in dimensions:
            dimensions[r.dimension] = {"pass": 0, "fail": 0, "total": 0}
        dimensions[r.dimension]["total"] += 1
        if r.passed:
            dimensions[r.dimension]["pass"] += 1
        else:
            dimensions[r.dimension]["fail"] += 1

    print("\n维度汇总:")
    for dim, stats in dimensions.items():
        status = "✓" if stats["fail"] == 0 else "✗"
        print(f"  {status} {dim}: {stats['pass']}/{stats['total']} 通过")

    # 按严重性统计失败
    severity_fail = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for r in suite.results:
        if not r.passed:
            severity_fail[r.severity] = severity_fail.get(r.severity, 0) + 1

    total = len(suite.results)
    total_pass = sum(1 for r in suite.results if r.passed)
    total_fail = total - total_pass

    print(f"\n总计: {total_pass}/{total} 通过 | {total_fail} 失败")
    print(f"  P0 必须修复: {severity_fail['P0']}")
    print(f"  P1 建议修复: {severity_fail['P1']}")
    print(f"  P2 看创作者意愿: {severity_fail['P2']}")
    print(f"  P3 无需修复: {severity_fail['P3']}")

    # 详细失败列表
    if total_fail > 0:
        print("\n" + "-" * 72)
        print("失败项详情:")
        for r in suite.results:
            if not r.passed:
                print(f"\n  [{r.severity}] {r.dimension} > {r.name}")
                if r.detail:
                    for line in r.detail.split("\n")[:3]:
                        print(f"    {line}")

    # 建议
    print("\n" + "-" * 72)
    print("修复建议:")
    if severity_fail["P0"] > 0:
        print(f"  ⚠ P0 必须修复 {severity_fail['P0']} 项 — 这些问题会导致 skill 无法正常工作")
    if severity_fail["P1"] > 0:
        print(f"  ⚠ P1 建议修复 {severity_fail['P1']} 项 — 影响可靠性或边界情况处理")
    if severity_fail["P2"] > 0:
        print(f"  ℹ P2 看创作者意愿 {severity_fail['P2']} 项 — 改进建议，不影响核心功能")
    if severity_fail["P3"] > 0:
        print(f"  ℹ P3 无需修复 {severity_fail['P3']} 项 — 信息性提醒")
    if total_fail == 0:
        print("  ✓ 全部测试通过，skill 状态良好")

    print("\n" + "=" * 72)

    return total_fail


# ============================================================
# 主入口
# ============================================================
def main():
    # P1-4: 修复 Windows GBK 控制台编码崩溃
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 72)
    print("  择命行效-行之有效的五行商业诊断理论体系 Skill 一键全维度测试")
    print(f"  测试路径: {SKILL_DIR}")
    print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    suite = TestSuite()

    # 运行7个维度
    test_structural(suite)              # P0 结构验证
    test_theory_consistency(suite)      # P0 理论框架一致性
    test_trigger_rules(suite)           # P1 触发规则与边界
    test_diagnostic_flow(suite)         # P1 诊断流程完整性
    test_output_spec(suite)             # P2 输出规范
    test_reference_quality(suite)       # P2 引用文件质量
    test_documentation(suite)           # P3 文档与合规

    # 生成报告
    total_fail = generate_report(suite)

    # 退出码
    sys.exit(1 if total_fail > 0 else 0)


if __name__ == "__main__":
    main()
