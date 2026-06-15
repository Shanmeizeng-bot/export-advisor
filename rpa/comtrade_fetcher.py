"""RPA Layer: 从 UN Comtrade API 自动抓取国际贸易数据

数据来源: UN Comtrade (https://comtradeplus.un.org/)
接口: Public Preview API, 免费, 无需注册, 每次返回500条记录
更新频率: 月度, 数据覆盖200+国家/地区

这是整个系统的自动化基础 —— 不是静态JSON, 而是每次分析时实时抓取最新贸易数据.
"""

import requests
import time
from datetime import datetime

BASE_URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"

# 支持的目的国候选列表 (55国/地区, 覆盖全球主要经济体)
TARGET_COUNTRIES = {
    # 北美 (3)
    "USA": {"name": "美国", "code": 842, "region": "北美"},
    "CAN": {"name": "加拿大", "code": 124, "region": "北美"},
    "MEX": {"name": "墨西哥", "code": 484, "region": "北美"},
    # 东亚 (4)
    "JPN": {"name": "日本", "code": 392, "region": "东亚"},
    "KOR": {"name": "韩国", "code": 410, "region": "东亚"},
    "TWN": {"name": "中国台湾", "code": 158, "region": "东亚"},
    "HKG": {"name": "中国香港", "code": 344, "region": "东亚"},
    # 欧盟核心 (12)
    "DEU": {"name": "德国", "code": 276, "region": "欧盟"},
    "FRA": {"name": "法国", "code": 251, "region": "欧盟"},
    "NLD": {"name": "荷兰", "code": 528, "region": "欧盟"},
    "ITA": {"name": "意大利", "code": 380, "region": "欧盟"},
    "ESP": {"name": "西班牙", "code": 724, "region": "欧盟"},
    "BEL": {"name": "比利时", "code": 56, "region": "欧盟"},
    "POL": {"name": "波兰", "code": 616, "region": "欧盟"},
    "SWE": {"name": "瑞典", "code": 752, "region": "欧盟"},
    "AUT": {"name": "奥地利", "code": 40, "region": "欧盟"},
    "CZE": {"name": "捷克", "code": 203, "region": "欧盟"},
    "PRT": {"name": "葡萄牙", "code": 620, "region": "欧盟"},
    "IRL": {"name": "爱尔兰", "code": 372, "region": "欧盟"},
    # 欧洲其他 (5)
    "GBR": {"name": "英国", "code": 826, "region": "欧洲"},
    "CHE": {"name": "瑞士", "code": 756, "region": "欧洲"},
    "NOR": {"name": "挪威", "code": 579, "region": "欧洲"},
    "DNK": {"name": "丹麦", "code": 208, "region": "欧洲"},
    "HUN": {"name": "匈牙利", "code": 348, "region": "欧洲"},
    # 东盟 (8)
    "VNM": {"name": "越南", "code": 704, "region": "东盟"},
    "THA": {"name": "泰国", "code": 764, "region": "东盟"},
    "MYS": {"name": "马来西亚", "code": 458, "region": "东盟"},
    "IDN": {"name": "印度尼西亚", "code": 360, "region": "东盟"},
    "SGP": {"name": "新加坡", "code": 702, "region": "东盟"},
    "PHL": {"name": "菲律宾", "code": 608, "region": "东盟"},
    "KHM": {"name": "柬埔寨", "code": 116, "region": "东盟"},
    "MMR": {"name": "缅甸", "code": 104, "region": "东盟"},
    # 南亚 (4)
    "IND": {"name": "印度", "code": 356, "region": "南亚"},
    "BGD": {"name": "孟加拉国", "code": 50, "region": "南亚"},
    "PAK": {"name": "巴基斯坦", "code": 586, "region": "南亚"},
    "LKA": {"name": "斯里兰卡", "code": 144, "region": "南亚"},
    # 中东 (7)
    "ARE": {"name": "阿联酋", "code": 784, "region": "中东"},
    "SAU": {"name": "沙特阿拉伯", "code": 682, "region": "中东"},
    "TUR": {"name": "土耳其", "code": 792, "region": "中东"},
    "ISR": {"name": "以色列", "code": 376, "region": "中东"},
    "QAT": {"name": "卡塔尔", "code": 634, "region": "中东"},
    "KWT": {"name": "科威特", "code": 414, "region": "中东"},
    "IRQ": {"name": "伊拉克", "code": 368, "region": "中东"},
    # 拉美 (6)
    "BRA": {"name": "巴西", "code": 76, "region": "拉美"},
    "CHL": {"name": "智利", "code": 152, "region": "拉美"},
    "ARG": {"name": "阿根廷", "code": 32, "region": "拉美"},
    "COL": {"name": "哥伦比亚", "code": 170, "region": "拉美"},
    "PER": {"name": "秘鲁", "code": 604, "region": "拉美"},
    "PAN": {"name": "巴拿马", "code": 591, "region": "拉美"},
    # 非洲 (6)
    "ZAF": {"name": "南非", "code": 710, "region": "非洲"},
    "NGA": {"name": "尼日利亚", "code": 566, "region": "非洲"},
    "KEN": {"name": "肯尼亚", "code": 404, "region": "非洲"},
    "EGY": {"name": "埃及", "code": 818, "region": "非洲"},
    "MAR": {"name": "摩洛哥", "code": 504, "region": "非洲"},
    "GHA": {"name": "加纳", "code": 288, "region": "非洲"},
    # 大洋洲 (2)
    "AUS": {"name": "澳大利亚", "code": 36, "region": "大洋洲"},
    "NZL": {"name": "新西兰", "code": 554, "region": "大洋洲"},
    # 欧亚 (2)
    "RUS": {"name": "俄罗斯", "code": 643, "region": "欧亚"},
    "KAZ": {"name": "哈萨克斯坦", "code": 398, "region": "欧亚"},
}


def _fetch_comtrade(params: dict, max_retries: int = 3) -> list[dict]:
    """通用请求方法, 带重试、限流处理和SSL兼容"""
    for attempt in range(max_retries):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
            if resp.status_code == 200:
                result = resp.json()
                return result.get("data", [])
            elif resp.status_code == 429:
                # 限流, 等待后重试
                wait = (attempt + 1) * 2
                time.sleep(wait)
                continue
            else:
                return []
        except requests.exceptions.SSLError:
            try:
                resp = requests.get(BASE_URL, params=params, timeout=30, verify=False)
                if resp.status_code == 200:
                    return resp.json().get("data", [])
            except Exception:
                pass
            return []
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return []
    return []


def fetch_import_by_country(hs_code: str, year: int = 2023, target_list: dict = None) -> dict:
    """查询目标国家列表中各国从全球进口某产品的总额和增速"""
    if target_list is None:
        target_list = TARGET_COUNTRIES
    results = {}
    countries = list(target_list.items())

    print(f"  🌐 正在查询 {len(countries)} 个目标国的进口数据...")

    for iso, info in countries:
        code = info["code"]
        # 查当年数据
        current_data = _fetch_comtrade({
            "reporterCode": code,
            "flowCode": "M",
            "period": str(year),
            "cmdCode": hs_code,
            "partnerCode": 0,      # 从全球进口
            "partner2Code": 0,
            "motCode": 0,
            "customsCode": "C00",
        })
        current_value = _extract_total_value(current_data)

        # 查前一年数据 (计算增速)
        prev_data = _fetch_comtrade({
            "reporterCode": code,
            "flowCode": "M",
            "period": str(year - 1),
            "cmdCode": hs_code,
            "partnerCode": 0,
            "partner2Code": 0,
            "motCode": 0,
            "customsCode": "C00",
        })
        prev_value = _extract_total_value(prev_data)

        growth = None
        if current_value is not None and prev_value is not None and prev_value > 0:
            growth = round((current_value - prev_value) / prev_value * 100, 1)

        results[iso] = {
            "name": info["name"],
            "region": info["region"],
            "code": code,
            "import_value_usd": current_value,
            "import_growth_pct": growth,
            "year": year,
        }

        # 避免触发限流
        time.sleep(0.5)

    return results


def fetch_china_exports(hs_code: str, year: int = 2023) -> dict:
    """查询中国对该产品向各国的出口情况

    返回: { partner_iso: {value, share_of_china_exports} }
    """
    params = {
        "reporterCode": 156,  # 中国
        "flowCode": "X",       # 出口
        "period": str(year),
        "cmdCode": hs_code,
        "partnerCode": "all",  # 所有伙伴国
        "partner2Code": 0,
        "motCode": 0,
        "customsCode": "C00",
    }
    data = _fetch_comtrade(params)

    if not data:
        return {}

    total_exports = sum(row.get("primaryValue", 0) or 0 for row in data)
    results = {}
    for row in data:
        partner_code = row.get("partnerCode")
        value = row.get("primaryValue", 0) or 0
        # 将partner code映射到ISO
        for iso, info in TARGET_COUNTRIES.items():
            if info["code"] == partner_code:
                results[iso] = {
                    "name": info["name"],
                    "export_value_usd": value,
                    "share_of_china_exports": round(value / total_exports * 100, 1) if total_exports > 0 else 0,
                }
    return results


def fetch_country_imports_from_china(hs_code: str, year: int = 2023, target_list: dict = None) -> dict:
    """查询各国从中国进口该产品的数据"""
    if target_list is None:
        target_list = TARGET_COUNTRIES
    results = {}
    for iso, info in target_list.items():
        data = _fetch_comtrade({
            "reporterCode": info["code"],
            "flowCode": "M",
            "period": str(year),
            "cmdCode": hs_code,
            "partnerCode": 156,    # 从中国进口
            "partner2Code": 0,
            "motCode": 0,
            "customsCode": "C00",
        })
        from_china = _extract_total_value(data)

        # 同时也查该国的总进口, 计算中国份额
        total_data = _fetch_comtrade({
            "reporterCode": info["code"],
            "flowCode": "M",
            "period": str(year),
            "cmdCode": hs_code,
            "partnerCode": 0,      # 全球
            "partner2Code": 0,
            "motCode": 0,
            "customsCode": "C00",
        })
        total_value = _extract_total_value(total_data)

        china_share = None
        if total_value and total_value > 0 and from_china:
            china_share = round(from_china / total_value * 100, 1)

        results[iso] = {
            "name": info["name"],
            "from_china_usd": from_china,
            "total_import_usd": total_value,
            "china_market_share_pct": china_share,
        }
        time.sleep(0.5)

    return results


def _extract_total_value(data: list[dict]) -> int | None:
    """从API返回数据中提取总额 (partnerCode=0时通常只有一条汇总记录)"""
    if not data:
        return None
    total = sum(row.get("primaryValue", 0) or 0 for row in data)
    return int(total) if total > 0 else None


# Quick demo: only query these 8 key countries (faster for classroom)
DEMO_COUNTRIES = [
    "USA", "DEU", "GBR", "FRA", "JPN", "KOR", "AUS",
    "VNM", "THA", "IDN", "IND", "BRA", "ARE", "ZAF", "MEX",
]


def fetch_all(hs_code: str, year: int = 2023, quick_mode: bool = False,
             target_list: dict = None) -> dict:
    """一键拉取所有数据: 各国进口 + 中国出口 + 各国从中国进口

    Args:
        target_list: 自定义目标国家dict, 为None时根据quick_mode自动选择
    """
    # Choose countries to query
    if target_list is not None:
        pass  # 使用传入的自定义列表
    elif quick_mode:
        target_list = {iso: TARGET_COUNTRIES[iso] for iso in DEMO_COUNTRIES if iso in TARGET_COUNTRIES}
    else:
        target_list = TARGET_COUNTRIES

    print(f"\n🤖 RPA 自动数据采集启动")
    print(f"   产品: HS {hs_code}")
    print(f"   年份: {year}")
    print(f"   模式: {'快速演示(' + str(len(target_list)) + '国)' if quick_mode else '完整分析(' + str(len(target_list)) + '国)'}")
    print(f"   数据源: UN Comtrade Public Preview API")
    print(f"   抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    t0 = time.time()

    # 1. 各国从全球进口 (市场规模)
    imports = fetch_import_by_country(hs_code, year, target_list)

    # 2. 中国向各国出口 (中国已有市场)
    exports = fetch_china_exports(hs_code, year)

    # 3. 各国从中国进口的份额 (竞争力)
    china_share = fetch_country_imports_from_china(hs_code, year, target_list)

    elapsed = time.time() - t0
    print(f"  ✅ 数据采集完成, 耗时 {elapsed:.1f}秒")

    return {
        "hs_code": hs_code,
        "year": year,
        "fetch_timestamp": datetime.now().isoformat(),
        "data_source": "UN Comtrade Public Preview API",
        "countries": {
            iso: {
                **imports.get(iso, {}),
                "china_exports_to": exports.get(iso, {}).get("export_value_usd"),
                "china_share_of_exports": exports.get(iso, {}).get("share_of_china_exports"),
                "china_market_share": china_share.get(iso, {}).get("china_market_share_pct"),
            }
            for iso in target_list
        },
    }


if __name__ == "__main__":
    # 独立测试
    result = fetch_all("851830", 2023)
    print(f"\n 拉取完成, 覆盖 {len(result['countries'])} 个国家")
