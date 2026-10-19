#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
择命行效 · 五行商业诊断引擎  MCP Server (stdio)
理论创立：常亮 ｜ 出品：北京常识宋道商业咨询策划有限公司
理论：因果·五行·度 三原则 + 五行行动链（之金下刀→行水引水→有木植树→效火点火→归土归藏）
本引擎只修链，不修命。
"""
import json
import os
import re
import sys
from datetime import datetime

from interpretation_neutral import INTERPRETATION_NEUTRAL, INDUSTRY_LEXICON, AI_INSTRUCTION
from report_renderer import generate_report as render_report, resolve_language
from research_client import log_case, record_follow_up, retry_case_submissions
from case_store import CASE_SCHEMA, accept_case, accept_legacy_case, CaseValidationError
import copy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============ 加载案例索引 ============
def _load_case_index():
    p = os.path.join(BASE_DIR, "case_index.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)

CASE_INDEX = _load_case_index()

# 详细案例（40案，含象位/断链/启示，供 search_cases 返回详情）
def _load_case_detail():
    p = os.path.join(BASE_DIR, "case_detail.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}

CASE_DETAIL = _load_case_detail()

# ============ 五行框架 ============
FRAMEWORK = {
    "name": "择命行效-行之有效的五行商业诊断理论体系",
    "three_principles": ["因果", "五行", "度"],
    "three_iron_laws": ["行在知前", "循环不息", "效必归土"],
    "five_elements": [
        {"element": "金", "character": "之", "action": "定位下刀", "business": "定位取舍"},
        {"element": "水", "character": "行", "action": "流量引水", "business": "流量渠道"},
        {"element": "木", "character": "有", "action": "产品植树", "business": "产品内容"},
        {"element": "火", "character": "效", "action": "转化点火", "business": "转化爆发"},
        {"element": "土", "character": "归", "action": "资产归藏", "business": "复购沉淀"}
    ],
    "four_xiang": {
        "无象": {"净变化": "渠道未建", "特征": "水环未立，四象不成立，五行未转起", "地形": "—", "行动": "先建渠道再谈象"},
        "老阳": {"净变化": "猛增(≥15%)", "特征": "水猛灌，火未归土则虚火", "地形": "鞍点平台期", "行动": "效必归土，先验火是否沉淀"},
        "少阳": {"净变化": "温和增(0~15%)", "特征": "稳中有进", "地形": "陡坡下行期", "行动": "加大步长，引水放大"},
        "少阴": {"净变化": "持平(=0)", "特征": "死水不动，无新水", "地形": "震荡调整期", "行动": "加密观察，警惕转老阴"},
        "老阴": {"净变化": "净流失(<0)", "特征": "在漏水，往负走", "地形": "收敛蛰伏期", "行动": "归土重修，回老客找残金"}
    },
    "prescription_taboo": [
        "不给超出客户执行力的方",
        "不动客户的土去做火（烧用户资产换GMV是渎职）",
        "不承诺火的时辰（可承诺修复动作与排序依据，不承诺三个月必爆）"
    ],
    "five_precepts": [
        "未行不言知——没有实地取证，不出诊断",
        "断环不点火——链条未修，禁止建议大促/爆点",
        "动土不动本——可调资产，不动用户信任之本",
        "言效必言归——说效果必须说沉淀了什么",
        "循环方收费——报告交付是循环的归土，90天复检即续费"
    ],
    "red_lines": [
        "纯投资分析（只问'这只股票能不能买'，不涉及品牌运营）→ 拒绝",
        "预测股价/风口/爆发时点 → 拒绝",
        "分析平台规则/算法机制（如'抖音算法怎么运作'）→ 拒绝",
        "用五行分析个人命理/算命/风水 → 拒绝（本体系只修链、不修命）",
        "用户拒绝提供任何品牌信息 → 不诊断"
    ],
    "scope": "只诊断品牌/公司/项目的经营链条（定位·流量·产品·转化·复购），不分析平台规则、不做投资建议、不预测风口、不算命。",
    "three_talents": "天（趋势/周期）·地（行业/赛道）·人（团队/执行力）。三才定品牌所处地形，五行定输运。三才不对，五行再通也白搭——行业赛道在收缩，链修得再好也是在下沉的船上修甲板。",
    "saddle_point": "品牌困境的本质是鞍点问题：声量上去了但增长平躺，就像梯度下降卡在鞍点——不是到底了，是地形在这个方向上平了。出路不是加火（加大步长），是换方向（重新下刀）。",
    "over_under": {
        "金": {"过": "砍到筋骨（自伤）", "不及": "什么都舍不得砍（泄）"},
        "水": {"过": "自传播冲垮供应链（涝）", "不及": "投放一停滴水全无（涸）"},
        "木": {"过": "SKU疯长耗干根系", "不及": "从不种树，旺季一过就枯"},
        "火": {"过": "火大必耗金，出焦土", "不及": "从不点火，有木无光"},
        "土": {"过": "只囤不耕，资产变库存（板结）", "不及": "完全不沉淀，流量从指缝漏光（流沙）"}
    },
    "three_ceilings": [
        "定位理论是静态的：占住一个词之后呢？没告诉你怎么引水、种树、收火、归土、下一把刀从哪来",
        "增长黑客AARRR是无根的：从不追问流量是引来的还是抽来的、留存靠产品还是补贴",
        "品牌资产论没有循环：沉淀的资产如何反哺下一轮定位？西方理论的终点是财报，本体系的终点是下一轮起点（土再生金）"
    ],
    "disclaimer": "本体系不修命，只修链——不承诺改运、不预测风口、不担保爆发，只承诺依据证据定位断点并给出修复动作与排序依据；检查有顺序，修复无固定顺序。"
}

# ============ 解读文案库（报告的"血肉"：五诊/四象/断链/修复的确定性解读） ============
# 文案自 theory.md / diagnosis.md / api_reference.md 归纳，现代商业白话，报告直接引用，保证"有骨有肉"。
INTERPRETATION = {
    "five_elements": {
        "金": {
            "生": "刀已开刃，取舍清晰。团队能在 10 秒内说清“不做什么”，资源集中在一刀切口上，没有在摇摆的战线上空耗。",
            "泄": "定位在摇摆——典型的贪症或盲症：要么什么都想做、刀背朝外，要么得翻 PPT 才答得上“不做什么”。常见信号：战线越铺越多、新的增长没有带来对应的聚焦、一整年砍不下任何一块业务。",
            "中": "取舍尚可，但刀还不够快、不够狠，切口还差一刀定生死。",
            "待验证": "定位信息不足，待补取证——能否 10 秒说清“不做什么”、近一年砍掉了什么业务。",
        },
        "水": {
            "生": "水有落差。客户自己流来，自然流或口碑驱动，停掉投放生意仍有根基，不是一桶一桶挑来的。",
            "泄": "泵瘾——把挑水当成了拥有河流。流量靠买、靠抽，停投即断。常见信号：获客成本涨幅连续超过客单价涨幅、付费流量占比一年高过一年。",
            "中": "水流尚可，但势能差不足，还差一条能自流的渠。",
            "待验证": "流量结构数据缺失，待补——自然/付费/转介绍占比、停投后留存。",
            "无": "水环未立，渠道还没建起来。五行未转起，先建渠道再谈象。",
        },
        "木": {
            "生": "木有根。有可积累、可复用、三年不死的核心资产——攥在自己手里，不是租来的、不是借来的。",
            "泄": "核心可积累资产不在自己手里，壁垒在别人那里——产品或服务可被轻易替代，或频繁推新却留不下任何可复用的积累。常见信号：三年前的东西一个没活下来、上新等于换壳。",
            "中": "有资产，但根还不够深，还不足以撑起下一轮。",
            "待验证": "产品资产信息缺失，待补——供应链自有度、内容资产存量、研发归属。",
        },
        "火": {
            "生": "灶火。爆发之后有沉淀，爆后留存为正，火照亮了产品、烧出了资产，而不是烧掉资产。",
            "泄": "野火或纵火癖。爆发一地鸡毛，靠下一把火掩盖上一把的灰烬——火大必耗金、出焦土。常见信号：爆后 30 天留存为负、靠连续造势维持声量。",
            "中": "火候一般，爆发能带来量，但沉淀不明显。",
            "待验证": "爆后留存数据缺失，待补——历次大促前后对比、爆后 30 天留存。",
        },
        "土": {
            "生": "土厚。复购自然盘扎实，用户搜你的品牌名下单，而不是搜品类词后选你。",
            "泄": "佃农或假土。自然复购盘薄，客户留存握在别人手里，停掉投放即流失；或者把一次性成交、渠道压量、人情单误当成复购——假土比没土更危险，没土你知道慌，假土让你以为稳。",
            "中": "土尚可，但还不够厚，还扛不住停投。",
            "待验证": "复购/自然盘数据缺失，待补——复购率、老客成交占比、无投放自然销售。",
        },
    },
    "four_xiang": {
        "老阳": {
            "本质矛盾": "声量大、转化虚，烧钱换增长——增长曲线平躺而声量虚高，站在鞍点平台上：仪器报“到了”，地形没答应。",
            "典型画像": "投放 ROI 递减、自然流占比下滑、爆发不断但什么都没沉淀下来。",
            "行动方向": "严禁加火，先下刀减灶。你的问题不是不够响，是太响了——把火收到一口灶上，砍掉多余的产品线和渠道。",
        },
        "少阳": {
            "本质矛盾": "小而美、稳但慢——陡坡下行期：复购带动自然流持续上升，梯度大、方向稳，是健康的慢。",
            "典型画像": "产品扎实、有老客基本盘，但增长慢，怕扩品、怕乱动。",
            "行动方向": "加大步长，引水放大。别急着扩品，先找一条有势能差的渠道放大现有模型，水宽了再种新树。",
        },
        "少阴": {
            "本质矛盾": "货好没人知道——震荡调整期：数据方向频繁反转，波动不是死亡信号，是地形在重新定向。",
            "典型画像": "老实人生意，产品不弱，但无声量、从不点火，被埋没在货架里。",
            "行动方向": "减小步长、加密观察，同时造一个可验证的事件，烧一次密度给市场看，也给团队看。",
        },
        "老阴": {
            "本质矛盾": "靠惯性活着——收敛蛰伏期：各项读数双双趋稳，可榨取性耗尽。",
            "典型画像": "老客在流失、没有新水进来、生意整体往下走。",
            "行动方向": "归土重修，回老客数据里找残金，用老客人群包重新下刀。别点火，会烧死。",
        },
        "无象": {
            "本质矛盾": "水环未立，五行未转起。",
            "典型画像": "渠道还没建起来，或从未真正建立过引水能力。",
            "行动方向": "先建渠道再谈象。先引水，水立起来了，象才谈得上。",
        },
    },
    "repair": {
        "金": "重新切定位——做减法、定边界，说清“不做什么”，把资源从摇摆的战线收回到一刀切口上。",
        "水": "造自然落差——停止单纯买量，找一条有势能差的渠道，让客户自己流来。",
        "木": "种树不租树——建自有核心资产（供应链/内容/研发/数据/品牌心智），把资源集中给一棵能活三年的树，别同时种十棵速生杨。",
        "火": "灶火非野火——造一个可验证的事件，爆后盯留存，让火照亮产品而非烧掉资产。",
        "土": "归土重修——回老客数据找残金，把复购和口碑做厚，把结果沉淀成可复用的资产。",
    },
    "break_chain": {
        "金": "断在下刀——定位摇摆、什么都想做，刀没开刃。",
        "水": "断在引水——流量靠买不能自流，停投即断。",
        "木": "断在植树——核心资产无根、可被替代，树是租来的。",
        "火": "断在点火——爆发不沉淀、连续纵火，火是野的。",
        "土": "断在归土——无复购资产、停投即死，地是别人的。",
    },
}

# ============ 诊断引导手册（三刀定位法 + 五诊五问话术 + 取数引导） ============
# 宿主 AI 在诊断前先调 diagnosis_guide 拿到本手册，按话术分步引导用户收集证据。
DIAGNOSIS_GUIDE = {
    "交互铁律": "信息收集一律用【编号选项】让用户点选（①②③④），禁止开放式问答——开放问答浪费用户时间、损耗聊下去的兴趣。只有两个例外允许开放回答：品牌名、一句话痛点。每个选项已对应 diagnose_brand 的参数值，用户点选后按'映射'直接转成参数调用 diagnose_brand。",
    "第一轮_必问": [
        {"问": "品牌名 + 品类是什么？（开放回答）", "参数": "brand_name"},
        {"问": "品牌处于哪个生命周期？", "选项": ["① 出发期（还没开张/刚开张）", "② 搭建期（在搭团队和产品）", "③ 商业模式验证期（在验证赚不赚钱）", "④ 扩张期（已长大，毛病不致命）"], "参数": "lifecycle_stage"},
        {"问": "一句话说最大的痛点是什么？（开放回答）", "参数": "痛点"}
    ],
    "第二轮_五诊取证（全部选项式）": [
        {"问": "定位清晰吗——能不能10秒说清'你们不做什么'？", "选项": ["① 能，张口就来", "② 要翻PPT才说得清", "③ 说不清"], "参数": "jin_clarity", "映射": {"①": "clear", "②": "unclear", "③": "unknown"}},
        {"问": "客户主要怎么来的？", "选项": ["① 自然流/口碑/老客转介绍为主", "② 投流买量/补贴为主", "③ 两者混合", "④ 还没建渠道"], "参数": "shui_source", "映射": {"①": "natural", "②": "pump", "③": "mixed", "④": "none"}},
        {"问": "近期（观察周期内）增长趋势如何？", "选项": ["① 明显增长/爆发（20%以上）", "② 温和增长（5%-10%）", "③ 停滞（基本0）", "④ 流失（负增长）"], "参数": "water_growth", "映射": {"①": 25, "②": 8, "③": 0, "④": -10}},
        {"问": "有没有可积累、三年不死的资产（自有供应链/内容/研发）？", "选项": ["① 有，攥在自己手里", "② 没有，核心资产都不在自己手里", "③ 不确定"], "参数": "mu_asset", "映射": {"①": "yes", "②": "no", "③": "unknown"}},
        {"问": "做过营销点火（大促/事件/爆款）吗？爆后沉淀如何？", "选项": ["① 有爆发，且沉淀下来了（复购为正）", "② 有爆发，但一地鸡毛（没沉淀）", "③ 从没做过点火动作"], "参数": "fire_state+fire_returns", "映射": {"①": {"fire_state": "strong", "fire_returns": "positive"}, "②": {"fire_state": "strong", "fire_returns": "negative"}, "③": {"fire_state": "weak", "fire_returns": "unknown"}}},
        {"问": "不做任何投放，自然销售（老客复购）占比多少？", "选项": ["① 40%以上", "② 20%-40%", "③ 20%以下", "④ 不清楚"], "参数": "tu_natural", "映射": {"①": 45, "②": 30, "③": 10, "④": None}}
    ],
    "三刀定位法": {
        "第一刀_心智阶梯扫描": "确定品牌在消费者心智品类阶梯的位置。问法（选项式）：'买这东西的人，脑子里最先蹦出哪三个牌子？'先让用户说出前三，再判断品牌在哪一格。判定：说不出前三或把自己排过高→金泄；还没上梯子→金未定，转入问水/问火。",
        "第二刀_空位探测": "在阶梯上找未被占据的维度。七维度过筛：价格/人群/场景/渠道/地理/成分材料/时间。判定：3个以上没人占→有空位、刀口落最大空位；0-1个→空位极窄，考虑品类开创或对立面。",
        "第三刀_对立面校验": "确认差异化切口是老大的对立面（不是更好，而是不同）。问法：'品类里谁是老大？老大代表什么？'映射：正宗经典→新潮年轻；第一最大→努力贴心；全品类→单一极致；高端贵→平价；快即时→慢定制。判定：有真实支撑→刀成；无支撑→回空位换维度。"
    },
    "取数引导": {
        "复购率": "过去90天下单≥2次的用户数 ÷ 总下单用户数（电商后台/CRM/小程序）",
        "自然流占比": "非付费渠道（搜索/直接访问/转介绍）流量 ÷ 总流量（百度统计/生意参谋）",
        "获客成本": "过去30天总营销投放 ÷ 同期新增下单用户数（财务报表+广告后台）",
        "停投后留存": "停投7天日均销量 ÷ 停投前7天日均销量（实测）",
        "老客成交占比": "过去90天老客（购买≥2次）成交额 ÷ 总成交额（CRM/订单系统）",
        "爆后30天留存": "最近一次大促新客中，30天后仍活跃或复购的比例（广告后台+用户行为分析）"
    },
    "流程铁律": "收集用【2轮完成】，禁止一轮一个问题（多轮对话会丢状态、重复问）：第1轮问品牌名+行业+生命周期(选项)+问局四问（定局面：①当前要作的决定，最多三项 ②哪些损失正在扩大及速度 ③可承受损失底线 ④手头已有的经营记录——口述不算数；用户可简答，损失扩大最快的环映射成 situation_urgent_ring），务必把品牌名→brand_name、行业→industry、阶段→lifecycle_stage 记牢；第2轮一次性列出全部6个五诊选项题，让用户按顺序回复6个编号(如'1,3,3,3,2,3')，按编号映射成参数。收集完立即调 diagnose_brand(带齐 brand_name+industry+lifecycle_stage+6个五诊参数+问局参数)，再调 generate_report 出报告。五环检查按金→水→木→火→土逐项进行（检查有顺序）；修复动作按损失风险/证据/依赖排优先级，一次一至两项（施工无固定顺序）。铁律：禁止重复问已问过的问题、禁止问完又回头要品牌名/行业/阶段、禁止在用户已提供基础信息后再次索要。"
}

# ============ 诊断规则引擎（确定性计算，不调模型） ============
ELEMENT_ORDER = ["金", "水", "木", "火", "土"]
ELEMENT_NAME = {
    "金": "之金·下刀诊（定位取舍）",
    "水": "行水·引水诊（流量渠道）",
    "木": "有木·植树诊（产品内容）",
    "火": "效火·点火诊（转化爆发）",
    "土": "归土·归藏诊（复购沉淀）"
}

def _judge_level(value, threshold_high, threshold_low):
    """数值型判定：>=high 生；<low 泄；介于之间 中；None 待验证"""
    if value is None:
        return "待验证"
    if value >= threshold_high:
        return "生"
    if value < threshold_low:
        return "泄"
    return "中"

def _judge_bool(value, true_val="yes"):
    """yes/no 型判定"""
    if value is None or str(value).strip().lower() == "unknown":
        return "待验证"
    return "生" if str(value).strip().lower() == true_val else "泄"

# 行业观察周期默认表（月）——共识级默认，精确T留给付费一对一
INDUSTRY_PERIOD = {
    "快消": 3, "餐饮": 3, "日化": 3, "食品": 3, "饮料": 3, "零售": 3, "电商": 3,
    "汽车": 6, "消费电子": 6, "3c": 6, "房产单项目": 3, "房地产": 12, "地产": 12,
    "家居": 12, "家具": 12, "家装": 12, "建材": 12,
    "硬科技": 12, "b2b": 12, "医疗": 12, "教育": 12, "工业": 12, "制造": 12,
}
INDUSTRY_ALIASES_EN = {
    "fmcg": "快消", "fast-moving consumer goods": "快消",
    "restaurant": "餐饮", "restaurants": "餐饮", "food service": "餐饮", "foodservice": "餐饮",
    "daily chemicals": "日化", "food": "食品", "beverage": "饮料", "beverages": "饮料",
    "retail": "零售", "ecommerce": "电商", "e-commerce": "电商", "e commerce": "电商",
    "automotive": "汽车", "automobile": "汽车", "automobiles": "汽车", "cars": "汽车",
    "consumer electronics": "消费电子", "single property project": "房产单项目",
    "real estate": "房地产", "home furnishings": "家居", "furniture": "家具",
    "home improvement": "家装", "building materials": "建材", "deep tech": "硬科技",
    "healthcare": "医疗", "medical": "医疗", "education": "教育",
    "industrial": "工业", "manufacturing": "制造",
}

def infer_period(industry):
    """按行业推断观察周期（月）。表内直接匹配，表外给默认6月（AI可据节奏调整）。"""
    ind = (industry or "").strip().lower()
    # Exact documented synonyms only; unknown English industries keep the original default.
    ind = INDUSTRY_ALIASES_EN.get(ind, ind)
    if ind:
        for k, v in INDUSTRY_PERIOD.items():
            if k in ind or ind in k:
                return v
    return 6  # 默认：标注"按行业默认，可人工调整"

def diagnose(args):
    brand = args.get("brand_name", "").strip() or "未命名品牌"
    stage = args.get("lifecycle_stage", "")
    industry = args.get("industry", "")
    period = infer_period(industry)

    # 五环判定
    ele = {}
    ele["金"] = _judge_bool(args.get("jin_clarity"), "clear")
    # 水：看来路（投流/混合=滥泄，自然流=生，无渠道=无）
    shui_source = (args.get("shui_source") or "").strip().lower()
    if shui_source == "none":
        ele["水"] = "无"
    elif shui_source in ("pump", "mixed"):
        ele["水"] = "泄"
    elif shui_source == "natural":
        ele["水"] = "生"
    else:
        ele["水"] = "待验证"
    ele["木"] = _judge_bool(args.get("mu_asset"), "yes")
    fire_state = (args.get("fire_state") or "").strip().lower()      # strong=火旺, weak=火弱
    fire_returns = (args.get("fire_returns") or "").strip().lower()  # positive=归土, negative=未归土
    ele["火"] = {"positive": "生", "negative": "泄"}.get(fire_returns, "待验证")
    ele["土"] = _judge_level(args.get("tu_natural"), 40, 20)

    # 断链定位（泄优先，其次中；"主断点排序/因果定位"二级规则待细化）
    break_chain = []
    for e in ELEMENT_ORDER:
        if ele[e] == "泄":
            break_chain.append(e)
    if not break_chain:
        for e in ELEMENT_ORDER:
            if ele[e] == "中":
                break_chain.append(e)

    # 四象判定（v3·火为主轴、水为辅轴，沐哥拍板：火旺→少阳/老阳，火弱→少阴/老阴）
    has_channel = ele["水"] != "无"
    wg = args.get("water_growth")  # 净增长率%，可正可负

    if not has_channel:
        # 渠道无：区分"从没建渠道"(无象·五行未转) vs "渠道消失/地形消失"(老阴·水净流失)
        xiang = "老阴" if (wg is not None and wg < 0) else "无象"
    elif wg is None:
        xiang = "待判定"
    elif fire_state == "strong":  # 火旺：水增猛→老阳，水增温和→少阳
        xiang = "老阳" if wg >= 15 else "少阳"
    elif fire_state == "weak":    # 火弱（含加盟型"水直归土"的少阴正解）：水减→老阴，水不减→少阴
        xiang = "老阴" if wg < 0 else "少阴"
    else:
        xiang = "待判定"

    xiang_info = FRAMEWORK["four_xiang"].get(xiang, {})

    # 老阳的土校验（效必归土，不归土则象不准、根基不稳）
    virtual_fire_warning = None
    if xiang == "老阳" and fire_returns == "negative":
        virtual_fire_warning = "火未归土：猛增但爆发未沉淀，属虚火老阳，根基不稳"

    # 修复排序（口径统一版）：五环检查按金→水→木→火→土逐项进行（检查有顺序）；
    # 修复动作按「损失是否迅速扩大→是否改变决策→依赖、证据、成本、可逆性」排优先级，施工无固定顺序。
    # 引擎默认排序规则：① 定局面输入中损失扩大最快的环（situation_urgent_ring）优先；
    # ② 其余断链环（泄先于中）随后；③ 未断的环按五行依赖序兜底排在最后。
    # 本结果为默认排序，最终动作顺序须由宿主AI结合问局四问（决定/损失/底线/经营记录）确认，一次选一至两项。
    urgent_ring = (args.get("situation_urgent_ring") or "").strip()
    repair_order = []
    if urgent_ring in ELEMENT_ORDER:
        repair_order.append(urgent_ring)
    for e in break_chain:
        if e not in repair_order:
            repair_order.append(e)
    for e in ELEMENT_ORDER:
        if e not in repair_order:
            repair_order.append(e)

    # 处方方向
    prescription_direction = {
        "无象": "先建渠道：水环未立，五行未转，先引水再谈象",
        "老阳": "效必归土：先验火是否沉淀，未归土则下刀减灶",
        "少阳": "引水放大：找一条有势能差的渠道，水宽了再种新树",
        "少阴": "点火造势：造一个可验证的事件，烧一次密度给市场看",
        "老阴": "归土重修：回老客数据里找残金，用老客人群包重新下刀",
        "待判定": "补数据：需水的净增长率才能定象",
    }.get(xiang, "")

    return {
        "brand_name": brand,
        "report_language": resolve_language(args),
        "skill_version": "2.5.1",
        "lifecycle_stage": stage or "未填写",
        "industry": industry or "未填写",
        "observe_period_months": period,
        "five_elements": {
            e: {"status": ele[e], "name": ELEMENT_NAME[e]}
            for e in ELEMENT_ORDER
        },
        "four_xiang": {
            "xiang": xiang,
            "净变化": xiang_info.get("净变化", ""),
            "desc": xiang_info.get("特征", ""),
            "terrain": xiang_info.get("地形", ""),
            "action": xiang_info.get("行动", ""),
            "virtual_fire_warning": virtual_fire_warning
        },
        "break_chain": break_chain or ["无明显断点"],
        "repair_order": repair_order,
        "repair_order_note": "默认排序：定局面最急环优先→断链环→其余按依赖序兜底；施工无固定顺序，最终顺序须结合问局四问确认，一次选一至两项",
        "situation": {
            "decisions": args.get("situation_decisions") or "未提供",
            "losses": args.get("situation_losses") or "未提供",
            "loss_floor": args.get("situation_loss_floor") or "未提供",
            "urgent_ring": urgent_ring or "未提供"
        },
        "prescription": {
            "direction": prescription_direction,
            "taboos": FRAMEWORK["prescription_taboo"]
        },
        "verification_90d": {
            "复购率": "以本次为基线，90天复检对比",
            "自然流占比": "以本次为基线，90天复检对比",
            "老客成交占比": "以本次为基线，90天复检对比"
        },
        "disclaimer": FRAMEWORK["disclaimer"],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ============ 案例检索 ============
def search_cases(args):
    query = (args.get("query") or "").strip()
    dimension = (args.get("dimension") or "关键词").strip()
    limit = int(args.get("limit") or 20)

    def _with_detail(names):
        """案例名列表 → 带详情（40个详细案例附象位/断链/启示）；索引名与详情键做核心词模糊匹配"""
        def _core(s):
            return re.split(r'[（(]', s)[0].strip()
        out = []
        for n in names:
            nc = _core(n)
            matched = next((d for k, d in CASE_DETAIL.items() if nc in _core(k) or _core(k) in nc), None)
            if matched:
                out.append({"案例": n, "象位": matched.get("象位", ""), "断链": matched.get("断链", ""), "启示": matched.get("启示", "")})
            else:
                out.append({"案例": n})
        return out

    results = []
    if dimension in ("象位", "四象", "xiang"):
        for xiang, names in CASE_INDEX["by_xiang"].items():
            if query and query not in xiang:
                continue
            results.append({"维度": f"象位·{xiang}", "案例": _with_detail(names)})
    elif dimension in ("断链", "断链环", "break"):
        for ring, names in CASE_INDEX["by_break"].items():
            if query and query not in ring:
                continue
            results.append({"维度": f"断链·{ring}", "案例": _with_detail(names)})
    elif dimension in ("行业", "industry"):
        for ind, names in CASE_INDEX["by_industry"].items():
            if query and query not in ind:
                continue
            results.append({"维度": f"行业·{ind}", "案例": _with_detail(names)})
    else:  # 关键词：跨维度搜案例名
        hit = []
        for bucket in CASE_INDEX.values():
            for names in bucket.values():
                for n in names:
                    if query in n and n not in hit:
                        hit.append(n)
        if hit:
            results.append({"维度": f"关键词·{query}", "案例": _with_detail(hit[:limit])})
        else:
            results.append({"维度": f"关键词·{query}", "案例": [], "提示": "未匹配，建议改用象位/断链环/行业维度检索"})

    return {"query": query, "dimension": dimension, "results": results}

# ============ SVG 图表生成 ============
def _generate_chain_svg(fe, brand, color):
    """五行链条诊断图 SVG（五环环形布局 + 状态标注）"""
    status_cn = {"生": "生", "泄": "泄", "中": "中", "待验证": "待验证", "无": "无"}
    status_color = {"生": "#4CAF50", "泄": "#FF9800", "中": "#FF9800", "待验证": "#999999", "无": "#999999"}
    short = {"金": "下刀", "水": "引水", "木": "植树", "火": "点火", "土": "归土"}
    positions = {"金": (340, 130), "水": (500, 200), "木": (440, 330), "火": (240, 330), "土": (180, 200)}
    body = ""
    for e in ["金", "水", "木", "火", "土"]:
        x, y = positions[e]
        st = fe.get(e, {}).get("status", "待验证")
        sc = status_color.get(st, "#999999")
        body += (
            f'<circle cx="{x}" cy="{y}" r="55" fill="none" stroke="{sc}" stroke-width="3"/>'
            f'<text x="{x}" y="{y-10}" text-anchor="middle" font-size="14" font-weight="bold" fill="{color[e]}">{e}·{short[e]}</text>'
            f'<text x="{x}" y="{y+14}" text-anchor="middle" font-size="14" font-weight="bold" fill="{sc}">{status_cn.get(st, st)}</text>'
        )
    return f'''<svg viewBox="0 0 680 420" xmlns="http://www.w3.org/2000/svg">
<text x="340" y="30" text-anchor="middle" font-size="16" font-weight="bold" fill="#333">五行链条诊断图</text>
<text x="340" y="52" text-anchor="middle" font-size="12" fill="#666">{brand}</text>
{body}
<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#999"/></marker></defs>
<path d="M 380,150 Q 440,160 460,180" fill="none" stroke="#999" stroke-width="1.5" marker-end="url(#arrow)"/>
<path d="M 500,255 Q 500,290 470,305" fill="none" stroke="#999" stroke-width="1.5" marker-end="url(#arrow)"/>
<path d="M 385,330 Q 340,340 295,330" fill="none" stroke="#999" stroke-width="1.5" marker-end="url(#arrow)"/>
<path d="M 210,305 Q 190,280 190,255" fill="none" stroke="#999" stroke-width="1.5" marker-end="url(#arrow)"/>
<path d="M 220,170 Q 270,140 300,130" fill="none" stroke="#999" stroke-width="1.5" marker-end="url(#arrow)"/>
<text x="340" y="405" text-anchor="middle" font-size="11" fill="#999">行在知前 · 循环不息 · 效必归土</text>
</svg>'''

def _generate_xiang_svg(xiang_name, brand):
    """四象定位图 SVG（X=引水能力水，Y=点火能力火，标注品牌象位）"""
    quad = {
        "老阳": (470, 140, "#F44336"),
        "少阳": (470, 300, "#4CAF50"),
        "少阴": (210, 140, "#2196F3"),
        "老阴": (210, 300, "#9E9E9E"),
    }
    bx, by, bc = quad.get(xiang_name, (340, 220, "#999999"))
    return f'''<svg viewBox="0 0 680 420" xmlns="http://www.w3.org/2000/svg">
<text x="340" y="30" text-anchor="middle" font-size="16" font-weight="bold" fill="#333">四象定位图</text>
<text x="340" y="52" text-anchor="middle" font-size="12" fill="#666">{brand}</text>
<line x1="340" y1="70" x2="340" y2="380" stroke="#ccc" stroke-width="1"/>
<line x1="90" y1="225" x2="590" y2="225" stroke="#ccc" stroke-width="1"/>
<text x="600" y="230" font-size="12" fill="#666">引水能力(水)→</text>
<text x="345" y="65" font-size="12" fill="#666">↑点火能力(火)</text>
<rect x="340" y="70" width="250" height="155" fill="#F44336" fill-opacity="0.08"/>
<text x="465" y="100" text-anchor="middle" font-size="14" font-weight="bold" fill="#F44336">老阳·火旺水滥</text>
<rect x="340" y="225" width="250" height="155" fill="#4CAF50" fill-opacity="0.08"/>
<text x="465" y="255" text-anchor="middle" font-size="14" font-weight="bold" fill="#4CAF50">少阳·火生水蓄</text>
<rect x="90" y="70" width="250" height="155" fill="#2196F3" fill-opacity="0.08"/>
<text x="215" y="100" text-anchor="middle" font-size="14" font-weight="bold" fill="#2196F3">少阴·火弱水滞</text>
<rect x="90" y="225" width="250" height="155" fill="#9E9E9E" fill-opacity="0.08"/>
<text x="215" y="255" text-anchor="middle" font-size="14" font-weight="bold" fill="#9E9E9E">老阴·火水俱衰</text>
<circle cx="{bx}" cy="{by}" r="11" fill="{bc}" stroke="#333" stroke-width="2"/>
<text x="{bx}" y="{by-18}" text-anchor="middle" font-size="13" font-weight="bold" fill="#333">{xiang_name}</text>
<text x="340" y="405" text-anchor="middle" font-size="11" fill="#999">定位依据：水=停投后自然流占比，火=爆发后留存沉淀率</text>
</svg>'''

def _generate_radar_svg(fe, brand):
    """治未病预警雷达图 SVG（五维：金水木火土，读数映射 + 预警线）"""
    import math
    score = {"生": 85, "中": 55, "泄": 25, "待验证": 0, "无": 0}
    cx, cy, R = 340, 235, 150
    angles = {"金": 90, "水": 18, "木": -54, "火": -126, "土": 162}
    color = {"金": "#D4A017", "水": "#2196F3", "木": "#4CAF50", "火": "#F44336", "土": "#795548"}
    short = {"金": "下刀", "水": "引水", "木": "植树", "火": "点火", "土": "归土"}
    axes, labels, pts = "", "", []
    for e in ["金", "水", "木", "火", "土"]:
        a = math.radians(angles[e])
        ex, ey = cx + R * math.cos(a), cy - R * math.sin(a)
        axes += f'<line x1="{cx}" y1="{cy}" x2="{ex:.0f}" y2="{ey:.0f}" stroke="#ccc" stroke-width="1"/>'
        lx, ly = cx + (R + 22) * math.cos(a), cy - (R + 22) * math.sin(a)
        labels += f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" font-size="13" font-weight="bold" fill="{color[e]}">{e}·{short[e]}</text>'
        s = score.get(fe.get(e, {}).get("status", "待验证"), 0)
        r = R * s / 100
        pts.append(f"{cx + r*math.cos(a):.0f},{cy - r*math.sin(a):.0f}")
    polygon = " ".join(pts)
    wr = R * 0.6
    return f'''<svg viewBox="0 0 680 450" xmlns="http://www.w3.org/2000/svg">
<text x="340" y="25" text-anchor="middle" font-size="16" font-weight="bold" fill="#333">治未病预警雷达图</text>
<text x="340" y="47" text-anchor="middle" font-size="12" fill="#666">{brand}</text>
<circle cx="{cx}" cy="{cy}" r="{R*0.25:.0f}" fill="none" stroke="#eee"/>
<circle cx="{cx}" cy="{cy}" r="{R*0.5:.0f}" fill="none" stroke="#eee"/>
<circle cx="{cx}" cy="{cy}" r="{R*0.75:.0f}" fill="none" stroke="#eee"/>
<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="#ddd" stroke-width="1.5"/>
<circle cx="{cx}" cy="{cy}" r="{wr:.0f}" fill="none" stroke="#FF9800" stroke-width="1.5" stroke-dasharray="4,3"/>
<text x="{cx}" y="{cy-wr-5:.0f}" text-anchor="middle" font-size="9" fill="#FF9800">预警线(60%)</text>
{axes}
<polygon points="{polygon}" fill="#795548" fill-opacity="0.25" stroke="#795548" stroke-width="2"/>
{labels}
<text x="340" y="438" text-anchor="middle" font-size="10" fill="#999">读数：生=85 中=55 泄=25 待验证=0 | 低于预警线触发预警</text>
</svg>'''

# ============ 报告生成 ============
def _html_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def generate_report(args):
    return render_report(args, BASE_DIR, INTERPRETATION, INTERPRETATION_NEUTRAL, ELEMENT_NAME)

# ============ 工具清单 ============
TOOLS = [
    {
        "name": "get_framework",
        "description": "返回择命行效五行商业诊断理论体系的框架定义（三原则、五行行动链、四象、铁律、五戒、红线、处方禁忌、免责声明）。宿主AI在诊断前应先调用本工具理解理论。",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "diagnosis_guide",
        "description": "返回诊断引导手册：三刀定位法（心智阶梯→空位→对立面）+ 五诊五问话术 + 数据取数引导 + 信息收集流程。诊断前先调用本工具，按手册分步引导用户收集品牌证据，收集完再调 diagnose_brand 计算、generate_report 出报告。",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "search_cases",
        "description": "在二百四十案行业案例库中检索对照案例。支持按象位（老阳/少阳/少阴/老阴）、断链环（金/水/木/火/土）、行业、关键词四个维度检索。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索词，如象位名/断链环名/行业名/案例名关键词"},
                "dimension": {"type": "string", "enum": ["象位", "断链", "行业", "关键词"], "description": "检索维度，默认关键词"},
                "limit": {"type": "integer", "description": "返回案例数量上限，默认20"}
            }
        }
    },
    {
        "name": "diagnose_brand",
        "description": "五行诊断引擎：输入品牌五环证据，确定性计算五环判定（生/泄/中/待验证）、四象、断链环、修复顺序、处方方向。纯规则计算，不调模型。五环检查按金→水→木→火→土逐项进行（检查有顺序）；修复动作按损失风险/证据/依赖排优先级，一次一至两项（施工无固定顺序）——可传入问局「定局面」参数（situation_*）让最急环优先。注意：本工具只返回结构化判定数据，不是给用户看的最终交付；诊断完成后必须再调用 generate_report 生成正式报告交给用户。红线场景（投资分析/算命/预测股价/分析平台规则）请直接拒绝，不调用本工具。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brand_name": {"type": "string", "description": "品牌/项目名（必填）"},
                "industry": {"type": "string", "description": "所属行业（用于推断观察周期T：快消3月/汽车6月/家居12月等，表外AI按节奏推断）"},
                "lifecycle_stage": {"type": "string", "description": "生命周期：出发期/搭建期/商业模式验证期/扩张期"},
                "jin_clarity": {"type": "string", "enum": ["clear", "unclear", "unknown"], "description": "问金·定位清晰度（问用户用选项点选）：'定位清晰吗？①能10秒说清不做什么 ②要翻PPT才说得清 ③说不清'。①→clear ②→unclear ③→unknown"},
                "shui_source": {"type": "string", "enum": ["natural", "pump", "mixed", "none"], "description": "问水·流量来路（问用户用选项点选）：'客户主要怎么来？①自然流/口碑/老客转介绍为主 ②投流买量/补贴为主 ③两者混合 ④还没建渠道'。①→natural ②→pump ③→mixed ④→none。注意'地形未就'（行业基础设施不存在，如早期电商网民基数不足）不是无渠道，应填pump"},
                "water_growth": {"type": "number", "description": "水的净增长率%（观察周期T内）。问用户用选项点选：'近期增长趋势？①明显增长/爆发(20%+) ②温和增长(5-10%) ③停滞(0) ④流失(负增长)'。①→25 ②→8 ③→0 ④→-10"},
                "mu_asset": {"type": "string", "enum": ["yes", "no", "unknown"], "description": "问木·产品资产（问用户用选项点选）：'有没有可积累、三年不死的资产(自有供应链/内容/研发)？①有，攥在自己手里 ②没有，核心资产都不在自己手里 ③不确定'。①→yes ②→no ③→unknown"},
                "fire_state": {"type": "string", "enum": ["strong", "weak"], "description": "火旺/火弱：strong=有爆发/点火/声量动作，weak=无声量/从不点火。看'点火动作'而非'品牌知名度'——老字号(同仁堂/片仔癀)知名度高但从不点火，填weak"},
                "fire_returns": {"type": "string", "enum": ["positive", "negative", "unknown"], "description": "火是否归土（爆后沉淀）：positive=归土灶火，negative=未归土野火。问用户用选项点选：'做过营销点火吗？爆后沉淀如何？①有爆发且沉淀了(复购为正) ②有爆发但一地鸡毛(没沉淀) ③从没做过点火'。①→fire_state=strong+fire_returns=positive ②→strong+negative ③→weak+unknown"},
                "tu_natural": {"type": "number", "description": "问土·自然盘占比%（0-100）。问用户用选项点选：'不做投放，自然销售(老客复购)占多少？①40%以上 ②20-40% ③20%以下 ④不清楚'。①→45 ②→30 ③→10 ④→不填(待验证)"},
                "situation_decisions": {"type": "string", "description": "问局·定局面①（选填）：当前要作的决定（加不加预算/先改什么/扩不扩，最多三项）"},
                "situation_losses": {"type": "string", "description": "问局·定局面②（选填）：正在扩大的损失及速度（现金流/客户/团队）"},
                "situation_loss_floor": {"type": "string", "description": "问局·定局面③（选填）：可承受损失底线"},
                "situation_urgent_ring": {"type": "string", "enum": ["金", "水", "木", "火", "土"], "description": "问局·定局面（选填）：损失扩大最快、必须最先处置的环。提供后该环排修复顺序首位；不提供则按默认排序（断链环优先，其余按依赖序兜底）"}
            },
            "required": ["brand_name"]
        }
    },
    {
        "name": "generate_report",
        "description": "品牌诊断的唯一交付出口。根据 diagnose_brand 的结构化结果生成诊断报告（含五诊逐环判定与解读要点、四象判定、修复顺序、验收标准、免责落款）。返回 report_url：完整排版版 HTML 报告（含水印与图表）的在线链接，必须在回复开头原样交付用户。默认输出 markdown；format=html 输出带水印 HTML 源码（保存/打印）。返回里带 ai_instruction：判定（生/泄/中、四象、断链、修复顺序、处方）为规则结果须原文保留；解读要点为行业中性骨架，须结合品牌名+行业展开成针对性解读（禁照抄、禁套消费品/制造业模板）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brand_name": {"type": "string", "description": "品牌/项目名"},
                "diagnosis": {"type": "object", "description": "diagnose_brand 返回的结构化诊断结果（JSON对象）"},
                "format": {"type": "string", "enum": ["markdown", "html"], "description": "报告格式：markdown（默认，聊天场景直接展示）或 html（带水印，保存/打印用）"}
            },
            "required": ["brand_name"]
        }
    },
    {
        "name": "log_case",
        "description": "将一次诊断结果脱敏落库（不含品牌名与财务数据），用于积累案例蓄水池。落库到 cases.log.jsonl。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "industry": {"type": "string"},
                "lifecycle_stage": {"type": "string"},
                "five_elements": {"type": "object"},
                "four_xiang": {"type": "string"},
                "break_chain": {"type": "array"},
                "prescription_direction": {"type": "string"}
            }
        }
    }
]

# Runtime schemas keep legacy tool names and fields while adding the evidence-rich contract.
_LANGUAGE_PROPERTIES = {
    "report_language": {"type": "string", "enum": ["zh-CN", "en"], "description": "Explicit user-requested report language; has highest priority."},
    "conversation_language": {"type": "string", "description": "Current conversation language; used only when the user has not specified report language. Defaults to zh-CN."}
}
_RESEARCH_SCHEMA = copy.deepcopy(CASE_SCHEMA)
_RESEARCH_SCHEMA.pop("$schema", None)
if os.environ.get("ZMXX_SERVER_MODE") != "remote":
    _RESEARCH_SCHEMA["required"] = [x for x in _RESEARCH_SCHEMA["required"] if x not in ("case_token", "case_id", "submission_id", "version", "skill_version", "source_platform", "report_language")]
_RESEARCH_SCHEMA["properties"]["case_token"]["description"] = "Optional on the same local client: a private case token is generated and stored locally. Cross-client follow-up needs the existing token; never put it in public reports."
for _tool in TOOLS:
    if _tool["name"] in ("generate_report", "diagnose_brand"):
        _tool["inputSchema"]["properties"].update(_LANGUAGE_PROPERTIES)
    if _tool["name"] == "generate_report":
        _tool["description"] = "Generate a complete Chinese or English diagnosis report with three charts, conclusions, outcome-feedback invitation and free commercial use notice. Explicit report_language takes precedence over conversation_language; default zh-CN. Retains markdown/html formats. report_url exists only when a public report origin is configured; otherwise deliver report_file or inline output."
        _tool["inputSchema"]["properties"]["case_id"] = {"type": "string", "description": "Non-identifying research case ID for linking outcome feedback (never a case token)."}
    if _tool["name"] == "diagnose_brand":
        _tool["inputSchema"]["properties"]["water_growth"]["description"] = "Actual net acquisition growth percentage in the stated observation window. Never convert a qualitative option into an invented number. Omit when unknown."
        _tool["inputSchema"]["properties"]["tu_natural"]["description"] = "Actual organic sales share, 0–100, with definition and observation window. Do not substitute a made-up number for an answer range; omit if unavailable."
    if _tool["name"] == "log_case":
        _legacy = copy.deepcopy(_tool["inputSchema"])
        _tool["description"] = "Submit an internally authorized, deidentified research case with substantive observations, definitions, evidence, reasoning, predictions and actions. Preserve aggregate financial metrics. Remote delivery requires ZMXX_RESEARCH_ENDPOINT; queued/local is not remote success. Schema v3 is preferred. Legacy summary calls remain compatible but are quarantined and not accepted as research evidence."
        _tool["inputSchema"] = {"type": "object", "properties": {**_RESEARCH_SCHEMA["properties"], **_legacy["properties"]}}
_follow_schema = copy.deepcopy(_RESEARCH_SCHEMA)
_follow_schema["required"] = list(dict.fromkeys(_follow_schema["required"] + ["case_id", "parent_submission_id", "version"]))
TOOLS.extend([
    {"name": "record_follow_up", "description": "Link actual actions, same-definition outcomes, mature cohort windows, concurrent changes, failure, no improvement and objections to the initial case. Reuse case_id and provide parent_submission_id; increments must follow the existing case version. No uncontrolled change is automatically attributed to the diagnosis.", "inputSchema": _follow_schema},
    {"name": "retry_case_submissions", "description": "Retry up to 20 deidentified local pending submissions with their original stable IDs. Reports remain usable when networking fails; only a validated accepted/duplicate receipt confirms remote delivery.", "inputSchema": {"type": "object", "properties": {}}}
])
DIAGNOSIS_GUIDE["流程铁律"] = "优先复用用户已给信息。可两轮低负担收集，但不把选项值编造成实测数值。允许品牌使用化名。收集行业、阶段、商业模式、目标与约束，并记录经营指标的值/单位/分子分母/周期/口径/来源与缺失项；保留证据、反证和替代解释。诊断规则计算后生成报告。已有合法且覆盖内部研究用途的授权不逐次弹确认；未经授权资料不上传。研究回传前在本地去身份并复核组合识别风险，保留必要经营精度，使用log_case v3；主动邀请实际行动与效果反馈，反馈用record_follow_up关联初诊。"
DIAGNOSIS_GUIDE["报告语言"] = "用户明确指定优先，其次当前对话，无法判断则zh-CN；支持en。向diagnose_brand和generate_report传report_language或conversation_language。"
DIAGNOSIS_GUIDE["报告与回执"] = "回传失败不阻断报告；queued/local不表示远端接收成功，pending可调用retry_case_submissions。私有研究库不并入search_cases公开案例库。"

# ============ 工具分发 ============
def call_tool(name, args, remote=False):
    if remote and name in ("log_case", "record_follow_up"):
        payload=dict(args.get("case") if isinstance(args.get("case"),dict) else args)
        if name == "record_follow_up":
            payload["record_type"]="follow_up"
        try:
            if not any(k in payload for k in ("schema_version", "record_type", "observations", "context", "authorization")):
                return accept_legacy_case(payload)
            return accept_case(payload)
        except CaseValidationError as exc:
            return {"ok":False,"status":"rejected","code":exc.code,"message":exc.message}
    if remote and name == "retry_case_submissions":
        return {"ok":False,"status":"not_configured","code":"retry_on_originating_client","message":"Retry is available only on the local client that owns the pending queue."}
    if name == "get_framework":
        return FRAMEWORK
    if name == "diagnosis_guide":
        return DIAGNOSIS_GUIDE
    if name == "search_cases":
        return search_cases(args)
    if name == "diagnose_brand":
        return diagnose(args)
    if name == "generate_report":
        return generate_report(args)
    if name == "log_case":
        return log_case(args)
    if name == "record_follow_up":
        return record_follow_up(args)
    if name == "retry_case_submissions":
        return retry_case_submissions(args)
    return {"error": f"未知工具: {name}"}

# ============ MCP stdio 主循环 ============
def _respond(request_id, result):
    sys.stdout.write(json.dumps({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    }, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method")
        rid = msg.get("id")

        if method == "initialize":
            _respond(rid, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "zemingxingxiao-engine", "version": "2.5.1"}
            })
        elif method == "tools/list":
            _respond(rid, {"tools": TOOLS})
        elif method == "tools/call":
            name = msg["params"]["name"]
            args = msg["params"].get("arguments", {}) or {}
            try:
                result = call_tool(name, args)
                content_text = json.dumps(result, ensure_ascii=False)
            except CaseValidationError as e:
                content_text = json.dumps({"ok": False, "code": e.code, "message": e.message}, ensure_ascii=False)
            except Exception:
                content_text = json.dumps({"ok": False, "code": "tool_failed", "message": "Tool execution failed; report generation and pending submissions can be retried."}, ensure_ascii=False)
            _respond(rid, {"content": [{"type": "text", "text": content_text}]})
        # 其他（notifications/initialized 等）静默忽略

if __name__ == "__main__":
    main()
