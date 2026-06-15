"""AI Analyst: 基于企业画像+贸易数据+品类知识库, 生成具体可执行的出口策略

核心改进:
- 认证按产品品类匹配 (不再把FCC推到塑料制品)
- 展会只推品类相关的 (不再对塑料制品推CES)
- B2B平台按品类+国家匹配
- 输出简洁, 直接可执行
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# ── 产品品类 → 关键认证映射 ──
# 按国家组织, 每个认证标注适用品类
CATEGORY_CERTIFICATIONS = {
    "消费电子": {
        "USA": [
            {"name": "FCC", "desc": "电磁兼容强制认证", "time": "2-4周", "cost": "$2,000-5,000"},
            {"name": "UL/ETL", "desc": "产品安全认证(零售商要求)", "time": "4-8周", "cost": "$5,000-20,000"},
        ],
        "DEU": [
            {"name": "CE", "desc": "欧盟强制安全认证", "time": "2-8周", "cost": "$1,000-10,000"},
            {"name": "WEEE", "desc": "电子垃圾回收注册", "time": "2-4周", "cost": "€200-500/年"},
            {"name": "RoHS", "desc": "有害物质限制", "time": "2-4周", "cost": "$1,000-3,000"},
        ],
        "JPN": [{"name": "PSE", "desc": "电器产品安全认证", "time": "4-8周", "cost": "$3,000-8,000"}],
        "KOR": [{"name": "KC", "desc": "韩国安全认证", "time": "4-8周", "cost": "$2,000-6,000"}],
        "ARE": [{"name": "ESMA", "desc": "阿联酋标准化认证", "time": "2-6周", "cost": "$1,000-4,000"}],
    },
    "LED照明": {
        "USA": [{"name": "FCC", "desc": "电磁兼容认证", "time": "2-4周", "cost": "$2,000-5,000"},
                 {"name": "UL", "desc": "安全认证", "time": "4-8周", "cost": "$5,000-15,000"},
                 {"name": "Energy Star", "desc": "能源之星能效认证(加分项)", "time": "4-8周", "cost": "$3,000-8,000"}],
        "DEU": [{"name": "CE", "desc": "欧盟强制安全认证", "time": "2-8周", "cost": "$1,000-10,000"},
                 {"name": "WEEE+RoHS", "desc": "电子垃圾+有害物质", "time": "2-4周", "cost": "$1,000-3,000"}],
        "ARE": [{"name": "ESMA", "desc": "标准化认证", "time": "2-6周", "cost": "$1,000-4,000"}],
    },
    "纺织服装": {
        "USA": [{"name": "CPSC", "desc": "消费品安全(阻燃/铅含量)", "time": "2-4周", "cost": "$1,000-5,000"},
                 {"name": "CPSIA", "desc": "儿童产品安全(如涉及童装)", "time": "2-4周", "cost": "$500-2,000"}],
        "DEU": [{"name": "OEKO-TEX 100", "desc": "纺织品有害物质检测(德国买家强烈要求)", "time": "2-4周", "cost": "$1,000-3,000"},
                 {"name": "REACH", "desc": "化学品合规(含染料/助剂)", "time": "4-8周", "cost": "视产品"}],
        "JPN": [{"name": "JIS", "desc": "日本工业标准(品质要求)", "time": "视产品", "cost": "视产品"}],
    },
    "鞋类": {
        "USA": [{"name": "CPSIA", "desc": "消费品安全(如涉及童鞋)", "time": "2-4周", "cost": "$500-2,000"}],
        "DEU": [{"name": "REACH", "desc": "化学品合规(鞋材)", "time": "4-8周", "cost": "视产品"},
                 {"name": "CE", "desc": "如涉及安全鞋(PPE)", "time": "4-8周", "cost": "$2,000-8,000"}],
    },
    "塑料制品": {
        "USA": [
            {"name": "FDA 21 CFR", "desc": "食品接触材料强制认证(核心门槛)", "time": "4-8周", "cost": "$2,000-8,000", "critical": True},
            {"name": "California Prop 65", "desc": "加州65号提案(有害物质警告)", "time": "2-4周", "cost": "$1,000-3,000"},
        ],
        "DEU": [
            {"name": "EU 10/2011", "desc": "食品接触塑料材料强制法规(核心门槛)", "time": "4-8周", "cost": "$2,000-6,000", "critical": True},
            {"name": "LFGB", "desc": "德国食品接触材料法(高于EU标准的德国要求)", "time": "4-8周", "cost": "$2,000-5,000"},
            {"name": "REACH", "desc": "化学品合规", "time": "4-8周", "cost": "视产品"},
        ],
        "FRA": [
            {"name": "EU 10/2011", "desc": "食品接触塑料材料强制法规", "time": "4-8周", "cost": "$2,000-6,000", "critical": True},
        ],
        "GBR": [
            {"name": "UK Plastic Food Contact Regs", "desc": "英国脱欧后独立食品接触法规", "time": "4-8周", "cost": "$1,500-5,000"},
        ],
        "NLD": [
            {"name": "EU 10/2011", "desc": "食品接触塑料材料强制法规", "time": "4-8周", "cost": "$2,000-6,000", "critical": True},
        ],
        "JPN": [
            {"name": "Japan Food Sanitation Law", "desc": "食品接触材料强制认证(厚生劳动省)", "time": "6-12周", "cost": "$3,000-10,000"},
            {"name": "JIS", "desc": "日本工业标准(如涉及)", "time": "视产品", "cost": "视产品"},
        ],
        "KOR": [
            {"name": "MFDS", "desc": "韩国食品医药品安全厅食品接触认证", "time": "4-12周", "cost": "$2,000-8,000"},
            {"name": "KC", "desc": "如涉及电器部件(如智能杯盖)", "time": "4-8周", "cost": "$2,000-6,000"},
        ],
        "AUS": [
            {"name": "AS 2070", "desc": "澳大利亚食品接触塑料标准", "time": "4-8周", "cost": "$1,500-4,000"},
        ],
        "ARE": [
            {"name": "ESMA", "desc": "阿联酋标准化认证(食品接触)", "time": "2-6周", "cost": "$1,000-4,000"},
        ],
        "SAU": [
            {"name": "SABER", "desc": "沙特产品安全强制认证平台", "time": "4-12周", "cost": "$1,000-5,000", "critical": True},
        ],
        "VNM": [
            {"name": "QCVN", "desc": "越南技术标准(食品接触)", "time": "2-6周", "cost": "$500-2,000"},
        ],
        "THA": [
            {"name": "TISI", "desc": "泰国工业标准(食品接触)", "time": "4-8周", "cost": "$1,000-3,000"},
        ],
        "MYS": [
            {"name": "SIRIM", "desc": "马来西亚标准认证", "time": "4-8周", "cost": "$1,000-3,000"},
        ],
        "IDN": [
            {"name": "SNI", "desc": "印尼国家标准(食品接触强制)", "time": "6-12周", "cost": "$1,500-5,000"},
        ],
        "IND": [
            {"name": "BIS", "desc": "印度标准局强制认证(核心门槛)", "time": "8-16周", "cost": "$3,000-10,000+", "critical": True},
            {"name": "FSSAI", "desc": "印度食品安全局食品接触认证", "time": "4-12周", "cost": "$1,000-4,000"},
        ],
        "BRA": [
            {"name": "ANVISA", "desc": "巴西卫生监督局食品接触认证", "time": "8-20周", "cost": "$2,000-8,000"},
            {"name": "INMETRO", "desc": "巴西计量质量认证", "time": "8-16周", "cost": "$2,000-8,000"},
        ],
    },
    "家具": {
        "USA": [{"name": "CPSC", "desc": "消费品安全(甲醛/稳定性)", "time": "2-4周", "cost": "$1,000-5,000"},
                 {"name": "CARB", "desc": "加州甲醛释放标准(板材家具)", "time": "4-8周", "cost": "$2,000-6,000"}],
        "DEU": [{"name": "CE", "desc": "欧盟安全认证", "time": "2-8周", "cost": "$1,000-10,000"},
                 {"name": "E1", "desc": "欧盟甲醛释放标准", "time": "2-4周", "cost": "$1,000-3,000"}],
    },
    "玩具": {
        "USA": [{"name": "ASTM F963", "desc": "玩具安全强制标准", "time": "4-8周", "cost": "$2,000-8,000"},
                 {"name": "CPSIA", "desc": "儿童产品安全(铅/邻苯)", "time": "2-6周", "cost": "$1,000-5,000"}],
        "DEU": [{"name": "CE+EN71", "desc": "欧盟玩具安全指令", "time": "4-8周", "cost": "$2,000-6,000"},
                 {"name": "REACH", "desc": "化学品合规", "time": "4-8周", "cost": "视产品"}],
    },
}

# ── 通用回落认证 (当品类不匹配时) ──
GENERIC_CERTIFICATIONS = {
    "USA": [{"name": "FDA(如食品接触)/CPSC(消费品安全)", "desc": "根据具体产品类型确定, 建议咨询认证机构", "time": "待确认", "cost": "视产品"}],
    "DEU": [{"name": "CE(如适用)/LFGB(食品接触)/REACH(化学品)", "desc": "根据具体产品类型确定", "time": "待确认", "cost": "视产品"}],
}


def generate_recommendations(
    rankings: list[dict],
    product_category: str,
    company_profile: dict,
    top_n: int = 3,
) -> dict:
    """生成行业分析师级别的深度建议"""
    trade_shows = _load_json("trade_shows.json")
    b2b_platforms = _load_json("b2b_platforms.json")
    market_strategies = _load_json("market_strategies.json")

    scale = company_profile.get("scale", "中小企业")
    export_exp = company_profile.get("export_experience", "无经验")
    has_ecommerce = company_profile.get("has_ecommerce_team", False)

    top_countries = rankings[:top_n]

    # ── 总览摘要 ──
    executive_summary = _gen_executive_summary(top_countries, product_category, scale, export_exp)

    # ── 逐国深度分析 ──
    market_analyses = []
    for i, r in enumerate(top_countries):
        iso = r["iso"]
        strategy = market_strategies.get(iso, {})
        shows = _find_trade_shows(trade_shows, product_category, iso)
        certs = _get_certifications(product_category, iso)
        platforms = _find_b2b_platforms(b2b_platforms, iso, product_category, has_ecommerce)

        analysis = {
            "rank": i + 1,
            "country": r["name"],
            "iso": iso,
            "region": r["region"],
            "total_score": r["total_score"],
            "market_quality_score": r["scores"].get("market_quality", 0),
            "why_this_market": _gen_market_rationale(r),
            "certifications": certs,
            "recommended_shows": shows[:3],
            "recommended_platforms": platforms[:2],
            "channel_strategy": strategy.get("channel_strategy", "阿里巴巴国际站B2B + 当地进口商/代理商"),
            "payment_terms": strategy.get("payment_terms", "T/T"),
            "tariff_note": strategy.get("tariff_note", ""),
            "cultural_note": strategy.get("cultural_note", ""),
            "risk_warning": _gen_risk_warning(r, certs),
        }
        market_analyses.append(analysis)

    # ── 展会计划 ──
    trade_show_plan = _gen_trade_show_plan(trade_shows, product_category, top_countries)

    # ── B2B平台 ──
    b2b_strategy = _gen_b2b_strategy(b2b_platforms, top_countries, product_category, scale, has_ecommerce)

    # ── 行动路线图 ──
    action_roadmap = _gen_action_roadmap(market_analyses, product_category, scale, export_exp, has_ecommerce)

    return {
        "executive_summary": executive_summary,
        "top_markets": market_analyses,
        "trade_show_plan": trade_show_plan,
        "b2b_strategy": b2b_strategy,
        "action_roadmap": action_roadmap,
    }


def _get_certifications(category: str, iso: str) -> list[dict]:
    """获取该品类在该国的关键认证, 确保不跨品类推荐"""
    cat_certs = CATEGORY_CERTIFICATIONS.get(category, {})
    country_certs = cat_certs.get(iso, [])
    if country_certs:
        return country_certs
    # 仅当品类完全不匹配时用通用回落
    generic = GENERIC_CERTIFICATIONS.get(iso, [])
    if generic:
        return generic
    return [{"name": "建议根据产品类型咨询当地认证机构", "desc": "暂无该品类自动匹配数据", "time": "待确认", "cost": "视产品"}]


def _gen_executive_summary(top_countries, category, scale, export_exp):
    country_names = "、".join([c["name"] for c in top_countries[:3]])
    exp_advice = {
        "无经验": "建议'先易后难'——先从关税低、合规门槛低的市场切入, 建立出口能力后再拓展高价值市场",
        "有经验(已有出口)": "建议优化市场组合——将高关税订单转至FTA优惠路径, 同时开拓高利润新市场",
        "成熟出口商": "应关注利润最大化——优先高市场质量(强货币+高消费力)目的国, 品牌化提升溢价",
    }.get(export_exp, "建议'先易后难'")

    return (
        f"**{country_names}** 是{category}产品的最优出口组合。"
        f"{exp_advice}。作为{scale}, 建议集中深耕1-2个核心市场。"
    )


def _gen_market_rationale(r):
    s = r["scores"]
    d = r["details"]
    reasons = []
    currency = d.get("currency", "")

    if s.get("market_quality", 0) >= 15:
        reasons.append(f"{currency}结算的高价值市场, 人均GDP ${d.get('gdp_per_capita', 0):,}, 消费者价格容忍度{d.get('consumer_sensitivity', '中')}, 利润空间远高于新兴市场")
    elif s.get("market_quality", 0) >= 10:
        reasons.append(f"中等消费力市场, 以性价比产品切入")

    if s.get("tariff_advantage", 0) >= 12:
        reasons.append("FTA关税优惠显著, 可大幅节省关税成本")
    elif s.get("tariff_advantage", 0) <= 5:
        reasons.append("关税较高但高市场质量可弥补——税后利润仍可能优于低关税低价市场")

    if s.get("market_growth", 0) >= 10:
        reasons.append(f"市场增速强劲(同比增长{r['details'].get('import_growth_pct', 0)}%), 处于需求扩张期")

    if s.get("business_convenience", 0) >= 6:
        reasons.append("物流和电商基础设施完善, 适合快速启动")

    return "。".join(reasons) + "。"


def _gen_risk_warning(r, certs):
    d = r["details"]
    warnings = []
    if d.get("policy_risk", "中") in ("高", "极高"):
        warnings.append(f"政策风险{d['policy_risk']}: 关注双边关系变化")
    if d.get("trade_barriers", "中") in ("高", "极高"):
        warnings.append(f"贸易壁垒{d['trade_barriers']}")
    critical_certs = [c for c in certs if c.get("critical")]
    if critical_certs:
        warnings.append(f"{critical_certs[0]['name']}认证是核心门槛, 耗时{critical_certs[0].get('time','?')}, 需提前准备")
    return " | ".join(warnings) if warnings else "当前风险较低"


def _find_trade_shows(trade_shows, category, iso):
    """匹配品类+国家的展会, 不跨品类推荐"""
    cat_shows = trade_shows.get(category, {})
    if not cat_shows:
        return []  # 品类不匹配, 不推荐展会 (防止FCC/CES问题)
    return cat_shows.get(iso, [])


def _find_b2b_platforms(b2b_data, iso, category, has_ecommerce):
    """匹配品类+国家的B2B平台"""
    results = []
    for key, p in b2b_data.get("platforms", {}).items():
        countries = p.get("best_for_countries", [])
        cats = p.get("best_for_categories", [])
        if (iso in countries or "全球" in countries) and (category in cats or "全品类" in cats):
            results.append({**p, "platform_key": key})
    results.sort(key=lambda x: 0 if category in x.get("best_for_categories", []) else 1)
    return results


def _gen_trade_show_plan(trade_shows, category, top_countries):
    months_order = {"1月": 1, "2月": 2, "3月": 3, "4月": 4, "5月": 5, "6月": 6,
                    "7月": 7, "8月": 8, "9月": 9, "10月": 10, "11月": 11, "12月": 12}
    all_shows = []
    seen = set()
    for country in top_countries[:5]:
        for show in _find_trade_shows(trade_shows, category, country["iso"]):
            if show["name"] not in seen:
                seen.add(show["name"])
                month_str = show["month"].split("/")[0].split("(")[0].strip()
                m = months_order.get(month_str[:2], 12) if month_str[0].isdigit() else 12
                all_shows.append({**show, "target_country": country["name"], "sort_month": m})
    all_shows.sort(key=lambda x: x["sort_month"])
    return all_shows[:8]


def _gen_b2b_strategy(b2b_data, top_countries, category, scale, has_ecommerce):
    platform_scores = {}
    for country in top_countries[:3]:
        for p in _find_b2b_platforms(b2b_data, country["iso"], category, has_ecommerce):
            key = p["platform_key"]
            if key not in platform_scores:
                platform_scores[key] = {"platform": p, "countries": [], "score": 0}
            platform_scores[key]["countries"].append(country["name"])
            platform_scores[key]["score"] += 3 if category in p.get("best_for_categories", []) else 1

    sorted_p = sorted(platform_scores.values(), key=lambda x: x["score"], reverse=True)
    primary, secondary = [], []
    for item in sorted_p:
        entry = {"name": item["platform"]["name"], "type": item["platform"]["type"],
                 "url": item["platform"]["url"], "target_countries": item["countries"],
                 "entry_cost": item["platform"]["entry_cost"],
                 "pros": item["platform"]["pros"], "cons": item["platform"].get("cons", ""),
                 "suitable_for": item["platform"]["suitable_for"]}
        (primary if item["score"] >= 4 else secondary).append(entry)

    is_small = scale == "中小企业"
    return {
        "primary_platforms": primary[:3],
        "secondary_platforms": secondary[:3],
        "strategy_note": (
            f"作为{scale}, 建议{'以阿里巴巴国际站(B2B)为核心, 不超2个平台同时运营' if is_small else '以阿里巴巴国际站+独立站(Shopify)为核心组合'}。"
            f"{'暂无电商团队, 从B2B平台起步最稳妥。' if not has_ecommerce else ''}"
        ),
    }


def _gen_action_roadmap(market_analyses, category, scale, export_exp, has_ecommerce):
    roadmap = []

    # Phase 1
    p1 = []
    if market_analyses:
        top = market_analyses[0]
        certs = top.get("certifications", [])
        if certs and certs[0].get("name") and "建议" not in certs[0]["name"]:
            cert_names = "、".join(c["name"] for c in certs[:3])
            p1.append(f"启动{top['country']}市场认证: {cert_names}")
        else:
            p1.append(f"确认{top['country']}市场对{category}产品的具体准入要求, 联系第三方检测机构(SGS/TÜV/Intertek)")
    p1.append("完善中英文产品资料: 产品目录/规格书/FOB报价单/验厂报告")
    p1.append(f"注册阿里巴巴国际站/中国制造网等B2B平台账号, 建立公司主页")
    if not has_ecommerce:
        p1.append("组建或外包外贸团队(至少1名业务+1名跟单)")
    p1.append("确认HS编码准确归类, 办理原产地证书资质(FORM E/FORM RCEP等)")

    roadmap.append({"phase": "第一阶段: 基础准备 (1-3个月)", "goal": "完成认证+搭建平台+组建团队", "steps": p1})

    # Phase 2
    p2 = []
    if market_analyses:
        for m in market_analyses[:3]:
            shows = m.get("recommended_shows", [])
            if shows:
                p2.append(f"参加**{shows[0]['name']}**({shows[0].get('city','')}, {shows[0].get('month','')})——{shows[0].get('notes','')}")
        if not any(m.get("recommended_shows") for m in market_analyses[:3]):
            p2.append(f"参加广交会(Canton Fair, 广州, 4月/10月)——全球最大综合展, 面向全品类采购商")
        p2.append(f"向{market_analyses[0]['country']}发出首批样品/试单, 验证产品适销性和物流链路")
        if len(market_analyses) > 1:
            p2.append(f"同步调研{market_analyses[1]['country']}市场渠道")
    p2.append("建立客户跟进系统(CRM), 管理询盘和样品")

    roadmap.append({"phase": "第二阶段: 市场切入 (3-6个月)", "goal": "完成试单+参加展会+获取种子客户", "steps": p2})

    # Phase 3
    p3 = []
    if market_analyses:
        p3.append(f"{market_analyses[0]['country']}市场: 从试单转为稳定返单, 考虑本地仓储/代理")
        if len(market_analyses) > 2:
            p3.append(f"拓展{market_analyses[2]['country']}市场")
    p3.append("根据市场反馈优化产品(包装/认证/规格)")
    p3.append("评估品牌化: 注册商标, 建立独立站")
    p3.append("建立汇率风险管理(远期结汇/多币种账户)")

    roadmap.append({"phase": "第三阶段: 规模扩张 (6-12个月)", "goal": "稳定出货+新市场拓展+品牌化", "steps": p3})

    return roadmap


def _load_json(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)
