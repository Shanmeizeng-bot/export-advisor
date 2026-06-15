"""Core Recommendation Engine: 综合多维度数据推荐最优出口目的国

评分维度 (7个, 总分100):
  1. 市场规模 (0-20): 目标国该产品的进口总额
  2. 市场增长 (0-15): 进口增速 (同比增长)
  3. 市场质量 (0-20): GDP per capita + 货币强度 + 消费者价格容忍度
  4. 关税优势 (0-15): FTA优惠税率 vs MFN税率
  5. 竞争格局 (0-12): 中国已占该市场的份额 (区分成熟市场vs新兴市场)
  6. 合规与准入 (0-10): 原产地规则 + 政策风险 + 贸易壁垒
  7. 商业便利 (0-8): 物流绩效 + 电商渗透率 + 营商环境
"""

import json
import math
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# ── 国家基础画像 (含商业质量维度) ──
COUNTRY_PROFILES = {
    "USA": {
        "gdp_per_capita": 85000, "currency": "USD",
        "currency_premium": 6,  # 全球储备货币, 结汇便利, 汇率稳定
        "consumer_price_sensitivity": "极低",
        "lpi": 4.0, "e_commerce_penetration": 0.87,
        "ease_of_business": "高",
        "policy_risk": "极高", "trade_barriers": "高",
        "notes": "全球最大消费市场, 赚美元利润空间大, 消费者价格敏感度极低, 品牌溢价能力强; 但2025年后对华关税叠加严重, 需关注原产地审查",
    },
    "JPN": {
        "gdp_per_capita": 34000, "currency": "JPY",
        "currency_premium": 4,
        "consumer_price_sensitivity": "低",
        "lpi": 4.0, "e_commerce_penetration": 0.76,
        "ease_of_business": "高",
        "policy_risk": "低", "trade_barriers": "中",
        "notes": "成熟高消费市场, RCEP零关税逐步到位, 品质要求极高但利润可观",
    },
    "KOR": {
        "gdp_per_capita": 35000, "currency": "KRW",
        "currency_premium": 4,
        "consumer_price_sensitivity": "低",
        "lpi": 3.8, "e_commerce_penetration": 0.92,
        "ease_of_business": "高",
        "policy_risk": "低", "trade_barriers": "低",
        "notes": "中韩FTA覆盖广, 电商渗透率全球最高, 文化相近适合中小企业起步",
    },
    "DEU": {
        "gdp_per_capita": 54000, "currency": "EUR",
        "currency_premium": 6,  # 欧元全球第二储备货币
        "consumer_price_sensitivity": "低",
        "lpi": 4.1, "e_commerce_penetration": 0.81,
        "ease_of_business": "高",
        "policy_risk": "中", "trade_barriers": "中",
        "notes": "欧盟最大经济体, 欧元结算汇率稳定, CE认证是门槛但市场利润高, 消费者愿为品质付溢价",
    },
    "GBR": {
        "gdp_per_capita": 51000, "currency": "GBP",
        "currency_premium": 5,
        "consumer_price_sensitivity": "低",
        "lpi": 3.9, "e_commerce_penetration": 0.89,
        "ease_of_business": "高",
        "policy_risk": "中", "trade_barriers": "中",
        "notes": "脱欧后独立贸易政策, 英镑结算有溢价, UKCA认证要求, 电商发达",
    },
    "FRA": {
        "gdp_per_capita": 47000, "currency": "EUR",
        "currency_premium": 6,
        "consumer_price_sensitivity": "低",
        "lpi": 3.8, "e_commerce_penetration": 0.80,
        "ease_of_business": "中",
        "policy_risk": "中", "trade_barriers": "中",
        "notes": "欧盟核心市场, 欧元结算, 消费品需求稳定, 品牌意识强",
    },
    "NLD": {
        "gdp_per_capita": 63000, "currency": "EUR",
        "currency_premium": 6,
        "consumer_price_sensitivity": "低",
        "lpi": 4.2, "e_commerce_penetration": 0.85,
        "ease_of_business": "高",
        "policy_risk": "低", "trade_barriers": "低",
        "notes": "欧洲物流门户, 鹿特丹港辐射全欧, 转口贸易重镇, LPI全球第一梯队",
    },
    "AUS": {
        "gdp_per_capita": 65000, "currency": "AUD",
        "currency_premium": 4,
        "consumer_price_sensitivity": "低",
        "lpi": 3.8, "e_commerce_penetration": 0.79,
        "ease_of_business": "高",
        "policy_risk": "低", "trade_barriers": "低",
        "notes": "RCEP框架下贸易顺畅, 高人均消费能力强, 对中国产品接受度高",
    },
    "VNM": {
        "gdp_per_capita": 4800, "currency": "VND",
        "currency_premium": 1,
        "consumer_price_sensitivity": "高",
        "lpi": 3.3, "e_commerce_penetration": 0.45,
        "ease_of_business": "中",
        "policy_risk": "低", "trade_barriers": "低",
        "notes": "东盟新兴制造+消费市场, 价格敏感型消费者, 中国-东盟FTA零关税, 但利润空间有限",
    },
    "THA": {
        "gdp_per_capita": 7800, "currency": "THB",
        "currency_premium": 1,
        "consumer_price_sensitivity": "高",
        "lpi": 3.5, "e_commerce_penetration": 0.62,
        "ease_of_business": "中",
        "policy_risk": "低", "trade_barriers": "低",
        "notes": "中国-东盟FTA深度整合, 电商快速增长, 但消费者对价格敏感",
    },
    "MYS": {
        "gdp_per_capita": 13000, "currency": "MYR",
        "currency_premium": 2,
        "consumer_price_sensitivity": "中",
        "lpi": 3.6, "e_commerce_penetration": 0.66,
        "ease_of_business": "中",
        "policy_risk": "低", "trade_barriers": "低",
        "notes": "英文普及率高, 清真认证是加分项, 东南亚中转枢纽, 中等消费力",
    },
    "IDN": {
        "gdp_per_capita": 5200, "currency": "IDR",
        "currency_premium": 1,
        "consumer_price_sensitivity": "高",
        "lpi": 3.1, "e_commerce_penetration": 0.48,
        "ease_of_business": "中低",
        "policy_risk": "中", "trade_barriers": "中",
        "notes": "东南亚最大人口国, 消费升级中但人均仍低, 进口许可较复杂",
    },
    "SGP": {
        "gdp_per_capita": 88000, "currency": "SGD",
        "currency_premium": 5,  # 新加坡元是亚洲最稳定货币之一
        "consumer_price_sensitivity": "低",
        "lpi": 4.3, "e_commerce_penetration": 0.84,
        "ease_of_business": "极高",
        "policy_risk": "极低", "trade_barriers": "极低",
        "notes": "零关税贸易自由港, 全球LPI第一, 但本地市场规模有限, 适合做区域总部和转口",
    },
    "IND": {
        "gdp_per_capita": 2900, "currency": "INR",
        "currency_premium": 1,
        "consumer_price_sensitivity": "极高",
        "lpi": 3.2, "e_commerce_penetration": 0.35,
        "ease_of_business": "低",
        "policy_risk": "高", "trade_barriers": "高",
        "notes": "人口红利巨大但人均消费力弱, 价格极度敏感市场, 关税高+BIS认证门槛高",
    },
    "BRA": {
        "gdp_per_capita": 10500, "currency": "BRL",
        "currency_premium": 1,
        "consumer_price_sensitivity": "中",
        "lpi": 3.0, "e_commerce_penetration": 0.52,
        "ease_of_business": "低",
        "policy_risk": "高", "trade_barriers": "高",
        "notes": "拉美最大市场, 汇率波动大, 关税高清关慢, 需葡萄牙语能力",
    },
    "MEX": {
        "gdp_per_capita": 14000, "currency": "MXN",
        "currency_premium": 2,
        "consumer_price_sensitivity": "中",
        "lpi": 3.2, "e_commerce_penetration": 0.55,
        "ease_of_business": "中",
        "policy_risk": "中", "trade_barriers": "中",
        "notes": "USMCA成员国可作为北美跳板, 但需关注原产地规则, 中等消费力",
    },
    "ARE": {
        "gdp_per_capita": 54000, "currency": "AED",
        "currency_premium": 4,  # 阿联酋迪拉姆与美元挂钩
        "consumer_price_sensitivity": "低",
        "lpi": 3.7, "e_commerce_penetration": 0.71,
        "ease_of_business": "高",
        "policy_risk": "低", "trade_barriers": "低",
        "notes": "中东转口贸易中心, 迪拉姆挂钩美元汇率稳定, 高消费力海湾市场, 辐射非洲",
    },
    "SAU": {
        "gdp_per_capita": 33000, "currency": "SAR",
        "currency_premium": 4,  # 沙特里亚尔与美元挂钩
        "consumer_price_sensitivity": "低",
        "lpi": 3.1, "e_commerce_penetration": 0.58,
        "ease_of_business": "中",
        "policy_risk": "低", "trade_barriers": "中",
        "notes": "沙特愿景2030驱动消费升级, 里亚尔挂钩美元收入稳定, 但SABER认证要求",
    },
    "RUS": {
        "gdp_per_capita": 15000, "currency": "RUB",
        "currency_premium": 0,  # 卢布受制裁, 结汇困难
        "consumer_price_sensitivity": "中",
        "lpi": 2.8, "e_commerce_penetration": 0.42,
        "ease_of_business": "低",
        "policy_risk": "极高", "trade_barriers": "高",
        "notes": "受制裁影响卢布结算风险大, 支付和物流渠道受限, 需谨慎评估",
    },
    "ZAF": {
        "gdp_per_capita": 6500, "currency": "ZAR",
        "currency_premium": 1,
        "consumer_price_sensitivity": "中",
        "lpi": 3.3, "e_commerce_penetration": 0.40,
        "ease_of_business": "中低",
        "policy_risk": "中", "trade_barriers": "中",
        "notes": "非洲最发达市场辐射南部非洲, 兰特汇率波动大, 电力供应不稳定影响物流",
    },
}


def recommend_countries(
    trade_data: dict,
    hs_code: str,
    product_category: str = "",
    company_scale: str = "中小企业",
) -> dict:
    """核心推荐算法: 7维度评分 —— 市场规模 + 增长 + 市场质量 + 关税 + 竞争 + 合规准入 + 商业便利

    Args:
        trade_data: RPA层从UN Comtrade抓取的结构化贸易数据
        hs_code: 产品HS编码
        product_category: 产品类别
        company_scale: 企业规模 (影响推荐偏好)
    """
    rankings = []
    country_data = trade_data.get("countries", {})

    products = _load_json("hs_products.json")
    tariff_data = _load_json("tariff_schedules.json")
    origin_rules = _load_json("origin_rules.json")

    product_info = products.get(hs_code, {})
    wto_mfn = tariff_data.get("wto_mfn", {})

    # 找出该产品在所有目标国的最大进口额 (用于归一化)
    max_import = max(
        (c.get("import_value_usd") or 0 for c in country_data.values()),
        default=1
    )
    # 找出最大GDP per capita (用于归一化)
    max_gdp_pc = max(
        (COUNTRY_PROFILES.get(iso, {}).get("gdp_per_capita", 10000)
         for iso in country_data),
        default=100000
    )

    for iso, c in country_data.items():
        if not c.get("import_value_usd"):
            continue

        profile = COUNTRY_PROFILES.get(iso, {})
        import_val = c.get("import_value_usd", 0) or 0
        gdp_pc = profile.get("gdp_per_capita", 10000)
        growth = c.get("import_growth_pct")
        china_share = c.get("china_market_share")

        # ── 1. 市场规模 (0-20) ──
        # 对数归一化 + GDP规模加权 (同样进口额, 高GDP市场意味着更高单价)
        if import_val > 0:
            log_score = math.log(import_val + 1) / math.log(max_import + 1)
            gdp_multiplier = 0.8 + 0.2 * (math.log(gdp_pc) / math.log(max_gdp_pc))
            market_score = round(log_score * 18 * gdp_multiplier + min(2, gdp_pc / 40000))
            market_score = min(20, max(1, market_score))
        else:
            market_score = 0

        # ── 2. 市场增长 (0-15) ──
        if growth is not None:
            if growth > 20:
                growth_score = 15
            elif growth > 10:
                growth_score = 12
            elif growth > 5:
                growth_score = 9
            elif growth > 0:
                growth_score = 6
            elif growth > -5:
                growth_score = 3
            else:
                growth_score = 0
        else:
            growth_score = 5

        # ── 3. 市场质量 (0-20): GDP per capita + 货币强度 + 消费者价格容忍度 ──
        quality_score = _calc_market_quality(profile, gdp_pc, max_gdp_pc)

        # ── 4. 关税优势 (0-15) ──
        raw_tariff = _estimate_tariff_score(iso, hs_code, wto_mfn, tariff_data)
        tariff_score = round(raw_tariff * 15 / 20)  # 从原0-20缩放到0-15

        # ── 5. 竞争格局 (0-12) ──
        # 关键改进: 区分市场类型
        is_premium = gdp_pc >= 30000  # 高消费力市场
        if china_share is not None:
            if is_premium:
                # 成熟市场: 中国份额高说明产品有竞争力, 不完全是坏事
                if china_share < 5:
                    competition_score = 6   # 还没进去, 门槛可能高
                elif china_share < 15:
                    competition_score = 10  # 有增长空间+已证明可行
                elif china_share < 35:
                    competition_score = 12  # 中国产品有竞争力, 最优区间
                elif china_share < 55:
                    competition_score = 9   # 已较成熟但仍有空间
                elif china_share < 75:
                    competition_score = 5   # 趋于饱和
                else:
                    competition_score = 2   # 红海
            else:
                # 新兴市场: 传统逻辑 —— 份额低=蓝海
                if china_share < 15:
                    competition_score = 12
                elif china_share < 30:
                    competition_score = 9
                elif china_share < 50:
                    competition_score = 6
                elif china_share < 70:
                    competition_score = 3
                else:
                    competition_score = 1
        else:
            competition_score = 7

        # ── 6. 合规与准入 (0-10): 合规容易度 + 市场准入合并 ──
        compliance_raw = _estimate_compliance(iso, hs_code, origin_rules)  # 1-10
        access_raw = _estimate_market_access(profile)  # 0-10
        compliance_score = round((compliance_raw + access_raw) / 2)

        # ── 7. 商业便利 (0-8): 物流 + 电商 + 营商环境 ──
        business_score = _calc_business_convenience(profile)

        total = (
            market_score + growth_score + quality_score
            + tariff_score + competition_score + compliance_score + business_score
        )

        rankings.append({
            "iso": iso,
            "name": c.get("name", iso),
            "region": c.get("region", ""),
            "total_score": total,
            "scores": {
                "market_size": market_score,
                "market_growth": growth_score,
                "market_quality": quality_score,
                "tariff_advantage": tariff_score,
                "competition_landscape": competition_score,
                "compliance_access": compliance_score,
                "business_convenience": business_score,
            },
            "details": {
                "import_value_usd": import_val,
                "import_growth_pct": growth,
                "china_market_share_pct": china_share,
                "china_exports_to_usd": c.get("china_exports_to"),
                "gdp_per_capita": gdp_pc,
                "currency": profile.get("currency", ""),
                "currency_premium": profile.get("currency_premium", 0),
                "consumer_sensitivity": profile.get("consumer_price_sensitivity", "未知"),
                "logistics_lpi": profile.get("lpi", 0),
                "policy_risk": profile.get("policy_risk", "未知"),
                "trade_barriers": profile.get("trade_barriers", "未知"),
                "notes": profile.get("notes", ""),
            },
        })

    rankings.sort(key=lambda x: x["total_score"], reverse=True)

    return {
        "hs_code": hs_code,
        "product_name": product_info.get("name_zh", hs_code),
        "product_category": product_category or product_info.get("category", ""),
        "company_scale": company_scale,
        "total_countries_analyzed": len(rankings),
        "rankings": rankings,
        "data_source": trade_data.get("data_source", "UN Comtrade"),
        "fetch_timestamp": trade_data.get("fetch_timestamp", ""),
    }


def _calc_market_quality(profile: dict, gdp_pc: float, max_gdp_pc: float) -> int:
    """计算市场质量得分 (0-20)

    子维度:
    - GDP per capita (0-8): 消费能力基础
    - 货币强度 (0-7): 结汇便利 + 汇率稳定 → 实际到手利润
    - 消费者价格容忍度 (0-5): 能否卖出高单价/高毛利
    """
    # GDP per capita (0-8): 对数归一
    if gdp_pc > 0:
        gdp_score = round(math.log(gdp_pc) / math.log(max_gdp_pc) * 8)
    else:
        gdp_score = 1

    # 货币强度 (0-7): currency_premium 映射
    currency_premium = profile.get("currency_premium", 1)
    currency_score = round(currency_premium / 6 * 7)

    # 消费者价格容忍度 (0-5)
    sensitivity = profile.get("consumer_price_sensitivity", "中")
    sensitivity_map = {"极低": 5, "低": 4, "中": 2, "高": 1, "极高": 0}
    price_score = sensitivity_map.get(sensitivity, 2)

    return gdp_score + currency_score + price_score


def _calc_business_convenience(profile: dict) -> int:
    """计算商业便利得分 (0-8)

    子维度:
    - 物流绩效 LPI (0-4): World Bank Logistics Performance Index
    - 电商+营商环境 (0-4): e-commerce penetration + ease of doing business
    """
    lpi = profile.get("lpi", 3.0)
    # LPI 范围 2.5-4.5, 映射到 0-4
    lpi_score = round(max(0, min(4, (lpi - 2.0) / 2.5 * 4)))

    # 电商+营商环境
    ecommerce = profile.get("e_commerce_penetration", 0.5)
    biz_ease = profile.get("ease_of_business", "中")
    ease_map = {"极高": 5, "高": 4, "中": 3, "中低": 2, "低": 1}

    # ecommerce (0-2) + ease (0-2)
    ecom_score = round(ecommerce * 2)
    ease_score = round(ease_map.get(biz_ease, 3) / 5 * 2)

    return lpi_score + ecom_score + ease_score


def _estimate_tariff_score(iso: str, hs_code: str, wto_mfn: dict, tariff_data: dict) -> int:
    """估算关税优势得分 (0-20原始分, 调用方会缩放到0-15)"""
    country_map = {
        "USA": "usa", "JPN": "japan", "KOR": "korea", "AUS": "australia",
        "VNM": "vietnam", "THA": "thailand", "MYS": "malaysia",
    }
    country_key = country_map.get(iso, iso.lower())
    mfn_entry = wto_mfn.get(country_key, {})
    mfn_rate = (mfn_entry.get(hs_code, {}) or {}).get("rate", None) if isinstance(mfn_entry, dict) else None

    asean = {"VNM", "THA", "MYS", "IDN", "SGP"}
    rcep = asean | {"JPN", "KOR", "AUS"}
    bilateral_fta = {"KOR"}

    has_rcep = iso in rcep
    has_asfta = iso in asean
    has_bilateral = iso in bilateral_fta

    if mfn_rate is None:
        if iso in {"USA", "JPN", "AUS", "SGP"}:
            mfn_rate = 5
        elif iso in {"KOR", "DEU", "GBR", "FRA", "NLD"}:
            mfn_rate = 8
        elif iso in asean:
            mfn_rate = 15
        elif iso in {"IND", "BRA"}:
            mfn_rate = 20
        else:
            mfn_rate = 12

    if has_bilateral and has_rcep:
        tariff_score = 20
    elif has_asfta:
        tariff_score = 18
    elif has_rcep:
        tariff_score = 14
    elif mfn_rate <= 3:
        tariff_score = 12
    elif mfn_rate <= 8:
        tariff_score = 8
    elif mfn_rate <= 15:
        tariff_score = 4
    else:
        tariff_score = 1

    return tariff_score


def _estimate_compliance(iso: str, hs_code: str, origin_rules: dict) -> int:
    """估算合规容易度 (0-10)"""
    asean = {"VNM", "THA", "MYS", "IDN", "SGP"}

    if iso == "KOR":
        rcep_rules = origin_rules.get("rcep", {})
        rule = rcep_rules.get(hs_code) or rcep_rules.get("_default", {})
        diff = rule.get("difficulty", "中")
    elif iso in asean:
        acfta_rules = origin_rules.get("china_asean_fta", {})
        rule = acfta_rules.get(hs_code) or acfta_rules.get("_default", {})
        diff = rule.get("difficulty", "低")
    elif iso in {"JPN", "AUS"}:
        rcep_rules = origin_rules.get("rcep", {})
        rule = rcep_rules.get(hs_code) or rcep_rules.get("_default", {})
        diff = rule.get("difficulty", "中")
    else:
        diff = "中"

    diff_map = {"低": 10, "中": 6, "高": 3, "极高": 1}
    return diff_map.get(diff, 5)


def _estimate_market_access(profile: dict) -> int:
    """估算市场准入难度 (0-10)"""
    risk = profile.get("policy_risk", "中")
    barriers = profile.get("trade_barriers", "中")

    risk_map = {"极低": 5, "低": 4, "中": 3, "高": 1, "极高": 0}
    barrier_map = {"极低": 5, "低": 4, "中": 3, "高": 1, "极高": 0}

    return risk_map.get(risk, 3) + barrier_map.get(barriers, 3)


def _load_json(filename: str) -> dict:
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)
