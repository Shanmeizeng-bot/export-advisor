"""LLM-Powered Analyst: 真正读取企业信息, 生成个性化出口策略

与 ai_analyst.py 的区别:
- ai_analyst: 规则匹配知识库, 同类产品输出一样
- llm_analyst: 读取企业画像+产品图册+网站+贸易数据, 真正个性化生成

核心函数: generate_instant_analysis() — 无需外部API, 直接基于企业数据生成分析

支持:
- OpenAI API (也兼容国内代理如 DeepSeek, Qwen 等)
- Anthropic API
- 无 API key 时使用增强版规则匹配(但会提示)
"""

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def build_context(
    rankings: list[dict],
    product_category: str,
    product_name: str,
    hs_code: str,
    company_profile: dict,
    top_n: int = 3,
) -> str:
    """构建发送给LLM的完整上下文"""
    ctx_parts = []

    # ── 企业画像 ──
    ctx_parts.append("## 企业画像")
    ctx_parts.append(f"- 企业名称: {company_profile.get('name', '未提供')}")
    ctx_parts.append(f"- 企业规模: {company_profile.get('scale', '未提供')}")
    ctx_parts.append(f"- 企业官网: {company_profile.get('website', '未提供')}")
    ctx_parts.append(f"- 出口经验: {company_profile.get('export_experience', '未提供')}")
    ctx_parts.append(f"- 是否有电商团队: {'是' if company_profile.get('has_ecommerce_team') else '否'}")
    desc = company_profile.get('description', '').strip()
    if desc and desc != '未填写' and len(desc) > 2:
        ctx_parts.append(f"- 企业简介(含上传资料): {desc[:2000]}")
    else:
        ctx_parts.append("- 企业简介: 未提供(建议填写以获取更精准的建议)")

    # ── 产品信息 ──
    ctx_parts.append("\n## 产品信息")
    ctx_parts.append(f"- HS编码: {hs_code}")
    ctx_parts.append(f"- 产品名称: {product_name}")
    ctx_parts.append(f"- 产品类别: {product_category}")

    # ── 评分结果 ──
    ctx_parts.append("\n## 7维度综合评分结果 (Top 5)")
    ctx_parts.append("| 排名 | 国家 | 区域 | 总分 | 市场规模 | 市场增长 | 市场质量 | 关税优势 | 竞争格局 | 合规准入 | 商业便利 |")
    ctx_parts.append("|------|------|------|------|----------|----------|----------|----------|----------|----------|----------|")
    for r in rankings[:5]:
        s = r["scores"]
        ctx_parts.append(
            f"| {rankings.index(r)+1} | {r['name']} | {r['region']} | {r['total_score']} | "
            f"{s['market_size']}/20 | {s['market_growth']}/15 | {s['market_quality']}/20 | "
            f"{s['tariff_advantage']}/15 | {s['competition_landscape']}/12 | "
            f"{s['compliance_access']}/10 | {s['business_convenience']}/8 |"
        )

    # ── Top 3 详细数据 ──
    ctx_parts.append("\n## Top 3 市场详细数据")
    for r in rankings[:top_n]:
        d = r["details"]
        ctx_parts.append(f"\n### {r['name']} ({r['region']})")
        ctx_parts.append(f"- 进口总额: ${d.get('import_value_usd', 0):,}")
        ctx_parts.append(f"- 进口增速: {d.get('import_growth_pct', 'N/A')}%")
        ctx_parts.append(f"- 中国市场份额: {d.get('china_market_share_pct', 'N/A')}%")
        ctx_parts.append(f"- 人均GDP: ${d.get('gdp_per_capita', 0):,}")
        ctx_parts.append(f"- 结算货币: {d.get('currency', 'N/A')}")
        ctx_parts.append(f"- 消费者价格敏感度: {d.get('consumer_sensitivity', 'N/A')}")
        ctx_parts.append(f"- 物流绩效LPI: {d.get('logistics_lpi', 'N/A')}")
        ctx_parts.append(f"- 政策风险: {d.get('policy_risk', 'N/A')}")
        ctx_parts.append(f"- 贸易壁垒: {d.get('trade_barriers', 'N/A')}")

    # ── 知识库参考 ──
    ctx_parts.append("\n## 行业知识库参考(可作为建议依据)")
    try:
        trade_shows = json.load(open(DATA_DIR / "trade_shows.json", encoding="utf-8"))
        cat_shows = trade_shows.get(product_category, {})
        if cat_shows:
            ctx_parts.append("\n### 相关国际展会")
            for country_iso, shows in cat_shows.items():
                for s in shows[:2]:
                    ctx_parts.append(f"- {s['name']} ({s.get('city','')}, {s.get('month','')}): {s.get('notes','')}")
    except Exception:
        pass

    try:
        from tools.ai_analyst import CATEGORY_CERTIFICATIONS
        certs_data = CATEGORY_CERTIFICATIONS.get(product_category, {})
        if certs_data:
            ctx_parts.append("\n### 各国关键认证要求")
            for country_iso in rankings[:top_n]:
                iso = country_iso["iso"]
                certs = certs_data.get(iso, [])
                if certs:
                    cert_str = ", ".join(f"{c['name']}({c.get('time','?')})" for c in certs[:3])
                    ctx_parts.append(f"- {country_iso}: {cert_str}")
    except Exception:
        pass

    return "\n".join(ctx_parts)


def call_llm(context: str, api_key: str, provider: str = "openai",
             system_prompt: str = None) -> str:
    """调用LLM — 可用于分析或HS匹配等任务

    Args:
        context: 用户提示/内容
        system_prompt: 自定义系统提示，为None时使用默认分析提示
    """
    if system_prompt is None:
        system_prompt = """你是一个出口策略分析引擎。基于企业数据+贸易数据直接输出分析，严格遵循以下规则：

## 铁律
- **禁止任何开场白/问候语/自我介绍**。第一行直接输出"### 📋 策略总览"
- **每句话必须有信息量**。不说"建议参加展会"，要说具体展会名称+时间+地点+理由
- **引用数据**。提到企业名称、HS编码、具体数字
- **根据企业阶段调整**：无出口→从东盟/中东切入；有出口→优化组合拓高利润市场；成熟→品牌化+海外仓
- **根据企业能力调整**：无电商→不推荐Amazon B2C；中小企业→聚焦1-2个市场
- **每个市场不超过5行**

## 输出格式 (严格按此结构，用Markdown):

### 📋 策略总览
[2-3句，必须含企业名称+首选市场+核心理由]

### 🌍 目标市场分析
**#1 [国家名] — [评分]/100分**
- 机会: [1句话，结合企业情况]
- 认证: [具体名称/周期/费用]
- 渠道: [具体平台/展会名称+时间地点]
- 风险: [1句话]

(每个市场重复以上格式，最多5个)

### 🎪 参展计划
| 时间 | 展会 | 地点 | 理由 |
|------|------|------|------|
(列出最相关的3-5个展会)

### 🗺️ 行动时间线
- **准备期(1-3月)**: [3-4项具体行动]
- **切入期(3-6月)**: [3-4项具体行动]
- **扩张期(6-12月)**: [3-4项具体行动]

### ⚠️ 关键提醒
[根据企业画像，1-2条可能被忽略的关键建议]
"""

    user_prompt = f"请基于以下企业信息, 给出个性化出口策略建议:\n\n{context}"

    if provider == "openai":
        return _call_openai(api_key, system_prompt, user_prompt)
    elif provider == "anthropic":
        return _call_anthropic(api_key, system_prompt, user_prompt)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _call_openai(api_key: str, system_prompt: str, user_prompt: str) -> str:
    """调用 OpenAI API (兼容 DeepSeek, Qwen, 等)"""
    import urllib.request
    import urllib.error
    import ssl

    # 支持自定义 base_url (如 DeepSeek: https://api.deepseek.com)
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    body = json.dumps({
        "model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 3000,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    # 尝试标准SSL; 失败则降级为兼容模式
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except (ssl.SSLError, OSError) as ssl_err:
        # SSL证书问题, 降级重试
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                result = json.loads(resp.read())
                return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"API调用失败 (HTTP {e.code}): {error_body[:300]}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"API调用失败 (HTTP {e.code}): {error_body[:300]}")
    except Exception as e:
        raise RuntimeError(f"API调用失败: {str(e)[:300]}")


def _call_anthropic(api_key: str, system_prompt: str, user_prompt: str) -> str:
    """调用 Anthropic API"""
    import urllib.request
    import urllib.error

    body = json.dumps({
        "model": os.environ.get("LLM_MODEL", "claude-sonnet-4-6"),
        "max_tokens": 3000,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_prompt},
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result["content"][0]["text"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"API调用失败 (HTTP {e.code}): {error_body[:300]}")
    except Exception as e:
        raise RuntimeError(f"API调用失败: {str(e)[:300]}")


def generate_llm_recommendations(
    rankings: list[dict],
    product_category: str,
    product_name: str,
    hs_code: str,
    company_profile: dict,
    api_key: str = "",
    provider: str = "openai",
) -> dict:
    """生成LLM个性化建议 (有API key用LLM, 没key用增强规则匹配)"""
    context = build_context(rankings, product_category, product_name, hs_code, company_profile)

    has_real_key = bool(api_key and len(api_key) > 10)

    if has_real_key:
        try:
            llm_response = call_llm(context, api_key, provider)
            return {
                "mode": "llm",
                "content": llm_response,
                "context": context,
            }
        except Exception as e:
            # LLM调用失败, 回退到规则匹配
            return {
                "mode": "fallback",
                "content": f"⚠️ LLM调用失败: {str(e)[:200]}\n\n以下为知识库匹配结果:\n\n",
                "context": context,
            }
    else:
        # 无API key: 使用增强版上下文生成, 但告知用户
        from tools.ai_analyst import generate_recommendations as rule_based

        rule_result = rule_based(rankings, product_category, company_profile)
        content = _format_enhanced_rule_based(rule_result, company_profile, product_name)

        return {
            "mode": "rule",
            "content": content,
            "context": context,
            "rule_result": rule_result,
        }


def suggest_hs_codes(product_description: str, company_description: str = "") -> list[dict]:
    """根据产品描述智能匹配HS编码 (调用DeepSeek)

    返回: [{"hs_code": "392410", "name": "塑料餐具", "confidence": 0.95, "category": "塑料制品"}, ...]
    """
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        return _fallback_hs_match(product_description)

    provider = os.environ.get("LLM_PROVIDER", "openai")

    prompt = f"""你是一个HS编码匹配专家。根据产品描述，返回最匹配的3-5个HS 6位编码。
只返回JSON数组，不要任何其他文字。格式：
[{{"hs_code":"392410","name":"塑料餐具/厨房用具","confidence":0.95,"category":"塑料制品"}}]

产品描述: {product_description}
企业信息: {company_description or "无"}"""

    hs_system = "你是HS编码匹配专家。只返回JSON数组，不要任何其他内容。"
    try:
        result = call_llm(prompt, api_key, provider, system_prompt=hs_system)
        import re
        json_match = re.search(r"\[.*\]", result, re.DOTALL)
        if json_match:
            candidates = json.loads(json_match.group())
            for c in candidates:
                if len(c.get("hs_code", "")) > 6:
                    c["hs_code"] = c["hs_code"][:6]
            return candidates[:5]
    except Exception:
        pass
    return _fallback_hs_match(product_description)


def _fallback_hs_match(desc: str) -> list[dict]:
    """无API时的后备HS匹配 (基于关键词)"""
    import json as _json
    hs_data = _json.load(open(DATA_DIR / "hs_products.json", encoding="utf-8"))
    desc_lower = desc.lower()
    matches = []
    for code, info in hs_data.items():
        score = 0
        name = info.get("name_zh", "") + " " + info.get("name_en", "")
        # 名称分词匹配
        for char in name:
            if char in desc_lower:
                score += 0.01
        # 品类匹配
        cat = info.get("category", "")
        if cat and any(c in desc_lower for c in cat.split()):
            score += 0.5
        # 关键组件匹配
        components = info.get("key_components", [])
        for comp in components:
            if comp.lower() in desc_lower:
                score += 0.3
        if score > 0.1:
            matches.append({
                "hs_code": code,
                "name": info.get("name_zh", ""),
                "confidence": min(0.85, 0.3 + score * 0.3),
                "category": cat,
            })
    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return matches[:5] if matches else [
        {"hs_code": "N/A", "name": "未找到匹配，请手动输入HS编码", "confidence": 0, "category": ""}
    ]


def suggest_target_countries(product_desc: str, hs_code: str, company_desc: str = "") -> list[str]:
    """根据产品特征智能推荐目标市场 (调用DeepSeek)

    返回: ["USA", "DEU", "VNM", ...] ISO代码列表
    """
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        return []

    provider = os.environ.get("LLM_PROVIDER", "openai")

    # 加载可用国家列表
    from rpa.comtrade_fetcher import TARGET_COUNTRIES
    country_list = "\n".join(f"{iso}: {v['name']}({v['region']})" for iso, v in TARGET_COUNTRIES.items())

    prompt = f"""根据产品信息，从以下国家列表中选出最值得出口的10-15个目标市场。
只返回ISO代码的JSON数组，不要任何其他文字。
格式: ["USA","DEU","VNM","THA"]

产品: {product_desc}
HS编码: {hs_code}
企业: {company_desc or "中小企业"}

可选国家:
{country_list}"""

    country_system = "你是国际贸易市场分析专家。只返回ISO代码的JSON数组，不要任何其他内容。"
    try:
        result = call_llm(prompt, api_key, provider, system_prompt=country_system)
        import re
        json_match = re.search(r"\[.*\]", result, re.DOTALL)
        if json_match:
            countries = json.loads(json_match.group())
            valid = set(TARGET_COUNTRIES.keys())
            return [c for c in countries if c in valid][:15]
    except Exception:
        pass
    return []


def extract_company_info(raw_text: str) -> dict:
    """从非结构化文本中智能提取企业和产品信息

    输入: 用户粘贴的任意文本 (企业介绍/产品描述/网站内容等)
    输出: {"company_name": "", "product_desc": "", "company_description": "",
            "export_experience": "", "has_ecommerce": false, "company_scale": "",
            "hs_candidates": [{"hs_code":"","name":"","confidence":0.0,"category":""}]}
    """
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        return {"company_name": "", "product_desc": raw_text[:500], "hs_candidates": []}

    provider = os.environ.get("LLM_PROVIDER", "openai")

    prompt = f"""从以下文本中提取企业和产品信息，返回JSON。文本可能来自企业网站、产品目录、公司介绍等。

提取规则:
- company_name: 企业全称
- product_desc: 产品详细描述(50-200字，包含材质/用途/规格/目标市场等)
- hs_candidates: 最匹配的2-4个HS 6位编码 [{{"hs_code":"392410","name":"","confidence":0.0,"category":""}}]
- company_description: 企业能力简介(30-100字)
- export_experience: 出口经验，只能是 "无经验"/"有经验"/"成熟" 之一
- has_ecommerce: 是否有电商团队 true/false
- company_scale: 只能是 "中小企业"/"大型企业" 之一

只返回JSON，不要其他文字:
{{"company_name":"","product_desc":"","hs_candidates":[],"company_description":"","export_experience":"无经验","has_ecommerce":false,"company_scale":"中小企业"}}

文本内容:
{raw_text[:3000]}"""

    system = "你是企业信息提取专家。只返回JSON，不要任何其他内容。"
    try:
        result = call_llm(prompt, api_key, provider, system_prompt=system)
        import re
        json_match = re.search(r"\{.*\}", result, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            # 修剪HS编码到6位
            for c in data.get("hs_candidates", []):
                if len(c.get("hs_code", "")) > 6:
                    c["hs_code"] = c["hs_code"][:6]
            return data
    except Exception:
        pass

    return {"company_name": "", "product_desc": raw_text[:500], "hs_candidates": []}


def _load_json(filename: str) -> dict:
    """加载data目录下的JSON文件"""
    p = DATA_DIR / filename
    if p.exists():
        return json.load(open(p, encoding="utf-8"))
    return {}


def generate_instant_analysis(context: dict) -> str:
    """即时生成个性化分析报告 — 无需外部API, 直接在企业数据基础上推理

    这是核心函数: 读取企业画像+产品+排名+知识库, 输出结构化markdown分析报告
    """
    cp = context.get("company_profile", {})
    rankings = context.get("rankings", [])
    category = context.get("product_category", "")
    product_name = context.get("product_name", "")
    hs_code = context.get("hs_code", "")

    company_name = cp.get("name", "贵公司") if cp.get("name") and cp.get("name") != "未填写" else "贵公司"
    scale = cp.get("scale", "中小企业")
    exp = cp.get("export_experience", "无经验")
    has_ecom = cp.get("has_ecommerce_team", False)
    description = cp.get("description", "").strip()
    website = cp.get("website", "").strip()

    # ── 企业能力分析 ──
    capabilities = _analyze_company_capabilities(cp)

    # ── 加载知识库 ──
    trade_shows = _load_json("trade_shows.json")
    b2b_data = _load_json("b2b_platforms.json")

    lines = []

    # ═══ 策略总览 ═══
    lines.append("### 📋 策略总览\n")

    top3 = rankings[:3]

    if company_name != "贵公司":
        lines.append(f"**{company_name}** 是一家{scale}")
        if capabilities:
            lines.append(f"，已识别能力: {', '.join(capabilities)}")
        lines.append("。\n")

    if exp == "无经验":
        lines.append(
            f"作为首次出海企业, 建议从**{top3[0]['name']}**切入——"
            f"关税低、合规门槛可控、文化距离近, 是{category}产品最稳妥的首次出海目的地。\n"
        )
    elif "成熟" in exp:
        lines.append(
            f"作为成熟出口商, 当前重点不是'去哪里'而是'去哪里利润最高'。"
            f"建议优先布局**{top3[0]['name']}**——高市场质量+强货币结算, 利润空间远超新兴市场。\n"
        )
    else:
        lines.append(
            f"已有出口经验, 建议优化市场布局。当前最优选择是**{top3[0]['name']}**"
            f"({'增速强劲' if top3[0]['details'].get('import_growth_pct', 0) > 10 else '市场规模大'}), "
            f"可作为下一阶段核心增长市场。\n"
        )

    # 关键数据洞察
    if top3[0]["details"].get("import_growth_pct", 0) > 50:
        lines.append(f"> 🚀 **数据洞察**: {top3[0]['name']}市场进口增速{top3[0]['details']['import_growth_pct']}%——属于爆炸性增长, 新进入者的黄金窗口期。\n")

    # 找蓝海市场 (中国份额<20%的高分市场)
    blue_oceans = [r for r in rankings[:8] if r["details"].get("china_market_share_pct", 100) < 20 and r["total_score"] > 50]
    if blue_oceans:
        bo = blue_oceans[0]
        lines.append(f"> 💎 **蓝海发现**: {bo['name']}市场中国份额仅**{bo['details']['china_market_share_pct']}%**, 说明中国同行尚未大规模进入——先发优势窗口仍在。\n")

    # ═══ 逐国分析 ═══
    lines.append("### 🌍 目标市场逐个分析\n")

    for i, r in enumerate(rankings[:5]):
        iso = r["iso"]
        name = r["name"]
        score = r["total_score"]
        s = r["scores"]
        d = r["details"]
        medal = ["🥇", "🥈", "🥉", "  ", "  "][i]

        # 中国市场特征
        china_share = d.get("china_market_share_pct", 0)
        if china_share and china_share < 15:
            competition_desc = "蓝海——中国产品渗透率极低"
        elif china_share and china_share < 35:
            competition_desc = "成长型——中国产品正在进入, 仍有较大空间"
        elif china_share and china_share < 55:
            competition_desc = "竞争型——中国产品已占一定份额, 需差异化"
        else:
            competition_desc = "红海——中国产品主导, 利润空间可能有限"

        growth = d.get("import_growth_pct", 0) or 0
        if growth > 20:
            growth_desc = f"🔥 爆炸增长 {growth}%"
        elif growth > 5:
            growth_desc = f"📈 稳健增长 {growth}%"
        elif growth > -5:
            growth_desc = f"➡️ 基本持平 {growth}%"
        else:
            growth_desc = f"📉 下滑 {growth}%"

        currency = d.get("currency", "")
        gdp = d.get("gdp_per_capita", 0)
        quality_label = "超高消费力" if gdp >= 50000 else "高消费力" if gdp >= 25000 else "中等消费力" if gdp >= 10000 else "价格敏感"

        lines.append(f"#### {medal} #{i+1} {name} — {score}分 | {quality_label} | {growth_desc}\n")

        # 为什么选
        reasons = []
        if s.get("market_quality", 0) >= 15:
            reasons.append(f"{currency}结算的高价值市场, 人均GDP ${gdp:,}, 产品可定较高单价")
        if s.get("tariff_advantage", 0) >= 12:
            reasons.append("FTA关税优惠显著, 关税成本大幅节约")
        if growth > 10:
            reasons.append(f"增速{'+' if growth > 0 else ''}{growth}%, 市场仍在快速扩张")
        if s.get("business_convenience", 0) >= 6:
            reasons.append("物流/电商基础设施完善, 适合快速启动")
        if china_share and china_share < 20:
            reasons.append(f"中国产品仅占{china_share}%——先发优势明显")

        lines.append(f"**为什么选它**: {'; '.join(reasons)}。\n")

        # 认证
        certs = _get_certs_for_country(category, iso)
        if certs:
            lines.append(f"**认证要求**:")
            for c in certs[:3]:
                critical = " 🔴核心门槛" if c.get("critical") else ""
                lines.append(f"- {c['name']}{critical}: {c['desc']} ({c.get('time','')}, {c.get('cost','')})")
            lines.append("")

        # 展会
        cat_shows = trade_shows.get(category, {})
        country_shows = cat_shows.get(iso, [])
        if country_shows:
            lines.append(f"**推荐展会**:")
            for s_show in country_shows[:2]:
                lines.append(f"- {s_show['name']} ({s_show.get('city','')}, {s_show.get('month','')}): {s_show.get('notes','')}")
            lines.append("")
        else:
            lines.append(f"**推荐展会**: 广交会(Canton Fair, 广州, 4月/10月)——全球最大综合展, 覆盖全品类\n")

        # 平台
        platforms = []
        for key, p in b2b_data.get("platforms", {}).items():
            countries = p.get("best_for_countries", [])
            cats = p.get("best_for_categories", [])
            if (iso in countries or "全球" in countries) and (category in cats or "全品类" in cats):
                platforms.append(p)
        if platforms:
            plat_names = [f"{p['name']}({p.get('entry_cost','')})" for p in platforms[:2]]
            lines.append(f"**B2B平台**: {' | '.join(plat_names)}\n")

        # 竞争评估
        lines.append(f"**竞争格局**: {competition_desc}\n")

    # ═══ 展会计划 ═══
    lines.append("### 🎪 推荐参展计划\n")
    all_shows = []
    seen = set()
    for r in rankings[:5]:
        cat_shows = trade_shows.get(category, {})
        for show in cat_shows.get(r["iso"], []):
            if show["name"] not in seen:
                seen.add(show["name"])
                all_shows.append({**show, "target": r["name"]})

    if all_shows:
        lines.append("| 时间 | 展会 | 地点 | 目标市场 |")
        lines.append("|------|------|------|----------|")
        for s_show in all_shows[:8]:
            lines.append(f"| {s_show.get('month','')} | {s_show['name']} | {s_show.get('city','')} | {s_show.get('target','')} |")
    else:
        lines.append("- 广交会(Canton Fair, 广州, 每年4月/10月)——全球最大综合展, 外贸获客核心渠道")
    lines.append("")

    # ═══ 行动路线图 ═══
    lines.append("### 🗺️ 分阶段行动计划\n")

    # Phase 1
    lines.append("#### 🔧 第一阶段: 基础准备 (1-3个月)\n")

    # 根据Top1国家推荐认证
    top_iso = rankings[0]["iso"]
    top_name = rankings[0]["name"]
    top_certs = _get_certs_for_country(category, top_iso)
    if top_certs:
        cert_names = "、".join(c["name"] for c in top_certs[:2])
        lines.append(f"1. 启动{top_name}市场认证: **{cert_names}**——这是进入该市场的硬门槛, 必须第一步完成")

    if not has_ecom:
        lines.append(f"2. 组建或外包外贸团队(至少1名业务+1名跟单)——暂无电商团队, 建议先从B2B起步")
        lines.append(f"3. 注册**阿里巴巴国际站**(B2B, 约¥3-4万/年)并建立公司主页")
    else:
        lines.append(f"2. 在**阿里巴巴国际站**优化店铺, 增加{category}相关关键词")
    lines.append(f"4. 确认HS {hs_code}的准确归类, 办理相关原产地证书\n")

    # Phase 2
    lines.append("#### 🚀 第二阶段: 市场切入 (3-6个月)\n")
    if all_shows:
        first_show = all_shows[0]
        lines.append(f"1. 参加**{first_show['name']}**({first_show.get('city','')}, {first_show.get('month','')})——{first_show.get('notes','')}")
    lines.append(f"2. 向{top_name}发出首批样品/试单, 验证产品适销性和物流")
    if len(rankings) > 1:
        lines.append(f"3. 同步调研{rankings[1]['name']}市场, 准备第二阶段扩展")
    lines.append("")

    # Phase 3
    lines.append("#### 📈 第三阶段: 规模扩张 (6-12个月)\n")
    lines.append(f"1. {top_name}市场: 从试单转为稳定返单, 考虑本地代理或仓储")
    if len(rankings) > 2:
        lines.append(f"2. 拓展{rankings[2]['name']}市场, 复制成功模式")
    lines.append("3. 根据市场反馈优化产品, 评估品牌化路径(注册商标/独立站)")
    lines.append("4. 建立多币种结算和汇率风险管理\n")

    # ═══ 个性化建议 ═══
    lines.append("### 💡 针对您企业的特别建议\n")

    if company_name != "贵公司":
        lines.append(f"**关于{company_name}**:\n")

    if exp == "无经验" and scale == "中小企业":
        lines.append("- **先B2B后B2C**: 无出口经验时, B2B(阿里巴巴国际站接OEM订单)比B2C(直接做Amazon)风险低得多。先接几个稳定OEM客户, 建立出口流程能力")
    elif "成熟" in exp and has_ecom:
        lines.append("- **品牌化是下一阶段核心**: 您已有出口经验和电商能力, 建议在核心市场注册商标, 从OEM向自有品牌转型")
    elif has_ecom:
        lines.append("- **电商能力是您的差异化优势**: 多数工厂只能做B2B, 您有电商团队——可以在目标市场本土电商平台(Coupang/Noon/Amazon)直接零售, 利润空间是B2B的3-5倍")

    if not has_ecom and exp == "无经验":
        lines.append("- **广交会是最高效的获客方式**: 4月和10月两届, 一个展位约3-8万, 5天能接触到的有效客户远超线上平台半年")
        lines.append("- **聚焦1个市场**: 中小企业资源有限, 先在一个市场做出深度(稳定月出货>1柜), 再考虑扩展第二个市场")

    if capabilities:
        lines.append(f"- **发挥已有优势**: 您的{', '.join(capabilities[:3])}是竞争对手不具备的, 在出口策略中应重点突出")

    lines.append("")
    lines.append("---")
    lines.append(f"*分析基于: UN Comtrade实时贸易数据 | {context.get('total_countries_analyzed', 0)}国数据 | {category}行业知识库*")

    return "\n".join(lines)


def _analyze_company_capabilities(cp: dict) -> list[str]:
    """分析企业能力, 提取关键优势"""
    caps = []
    desc = cp.get("description", "").strip()
    if not desc or desc == "未填写":
        return caps

    if any(w in desc.lower() for w in ["oem", "odm", "代工", "贴牌", "定制"]):
        caps.append("OEM/ODM定制能力")
    if any(w in desc.lower() for w in ["iso", "9001", "14001", "认证"]):
        caps.append("体系认证(ISO等)")
    if any(w in desc.lower() for w in ["fda", "lfgb", "eu", "ce", "fcc", "kc", "rohs"]):
        caps.append("产品认证")
    if any(w in desc for w in ["电商", "亚马逊", "amazon", "淘宝", "天猫", "京东"]):
        caps.append("电商运营经验")
    if any(w in desc for w in ["出口", "外贸", "海外", "国际", "export"]):
        caps.append("出口经验")
    if any(w in desc for w in ["研发", "设计", "开发", "专利", "r&d"]):
        caps.append("研发设计能力")
    if any(w in desc for w in ["环保", "可降解", "pla", "生物基", "再生", "recycl"]):
        caps.append("环保/可持续材料")
    if any(w in desc for w in ["年产", "产能", "万只", "万件", "万套", "吨"]):
        caps.append("规模化产能")
    if any(w in desc for w in ["德国", "日本", "美国", "欧洲", "韩国"]):
        caps.append("高端市场经验")

    return caps


def _get_certs_for_country(category: str, iso: str) -> list[dict]:
    """获取该品类在该国的认证要求"""
    from tools.ai_analyst import CATEGORY_CERTIFICATIONS
    cat_certs = CATEGORY_CERTIFICATIONS.get(category, {})
    return cat_certs.get(iso, [])


def _format_enhanced_rule_based(rule_result: dict, company_profile: dict, product_name: str) -> str:
    """将规则匹配结果格式化为个性化文本 (比原版更个性化, 但仍不如LLM)"""
    lines = []
    company_name = company_profile.get("name", "贵公司")
    if company_name == "未填写":
        company_name = "贵公司"
    scale = company_profile.get("scale", "中小企业")
    exp = company_profile.get("export_experience", "无经验")
    has_ecom = company_profile.get("has_ecommerce_team", False)

    desc = company_profile.get("description", "")

    lines.append(f"### 📋 {company_name} · {product_name} 出口策略\n")
    lines.append(f"> ⚠️ **当前为知识库匹配模式** (未配置LLM API key)。建议配置API key获取真正个性化的AI分析。\n")

    # 根据企业信息调整策略
    if exp == "无经验":
        lines.append(f"**{company_name}** 作为首次出海企业, 建议采用保守策略——先从1-2个低风险市场切入。\n")
    elif "成熟" in exp:
        lines.append(f"**{company_name}** 作为成熟出口商, 当前阶段应关注利润最大化——优先高市场质量市场, 品牌化运作。\n")
    else:
        lines.append(f"**{company_name}** 已有出口经验, 建议优化现有市场组合, 开拓高利润新市场。\n")

    # 企业描述中的关键词
    if desc and desc != "未填写":
        keywords = []
        if any(w in desc for w in ["OEM", "ODM", "代工", "贴牌"]):
            keywords.append("OEM/ODM能力")
        if any(w in desc for w in ["ISO", "认证", "BSCI", "FDA"]):
            keywords.append("已有认证基础")
        if any(w in desc for w in ["东南亚", "欧美", "中东"]):
            keywords.append("已有区域市场经验")
        if any(w in desc for w in ["电商", "亚马逊", "Amazon", "阿里"]):
            keywords.append("电商经验")
        if keywords:
            lines.append(f"**企业优势识别**: {', '.join(keywords)}。建议在出口策略中充分利用这些优势。\n")

    lines.append("**基于您的企业画像, 以下为个性化调整后的建议:**\n")

    for m in rule_result.get("top_markets", []):
        lines.append(f"#### #{m['rank']} {m['country']} ({m['region']})")
        lines.append(f"- **市场机会**: {m['why_this_market'][:200]}")
        lines.append(f"- **渠道**: {m['channel_strategy']}")

        certs = m.get("certifications", [])
        if certs:
            cert_list = ", ".join(f"{c['name']}({c.get('time','?')})" for c in certs[:3])
            lines.append(f"- **认证**: {cert_list}")

        shows = m.get("recommended_shows", [])
        if shows:
            show_list = ", ".join(f"{s['name']}({s.get('city','')}, {s.get('month','')})" for s in shows[:2])
            lines.append(f"- **展会**: {show_list}")
        else:
            lines.append(f"- **展会**: 广交会(Canton Fair, 广州, 4月/10月)——全球最大综合展")

        lines.append("")

    # 基于企业能力的个性化建议
    lines.append("### 💡 基于您企业现状的建议\n")
    if not has_ecom and scale == "中小企业":
        lines.append("- **优先B2B**: 暂无电商团队, 不建议直接做B2C。先从阿里巴巴国际站(B2B)接OEM/ODM订单起步")
        lines.append("- **轻资产运营**: 不设海外仓, 通过FOB/CIF方式由客户承担海运")
    elif has_ecom:
        lines.append("- **B2B+B2C并行**: 有电商团队, 可阿里巴巴国际站(B2B)+Amazon(B2C)双渠道")

    if exp == "无经验":
        lines.append("- **首选关税低+合规易的市场**: 如东盟(ACFTA零关税)、韩国(中韩FTA)、中东")
        lines.append("- **参加广交会**: 最直接接触全球买家的方式, 4月和10月两届")
    elif "成熟" in exp:
        lines.append("- **品牌化**: 注册商标, 建独立站Shopify, 参加国际评奖提升品牌溢价")
        lines.append("- **设海外仓**: 在核心市场设立仓储, 提升本地配送竞争力")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# 单国家个性化分析 (点击国家时触发)
# ═══════════════════════════════════════════════════════════

def build_single_country_context(
    country_data: dict,
    product_category: str,
    product_name: str,
    hs_code: str,
    company_profile: dict,
    all_rankings: list[dict],
) -> str:
    """构建聚焦单个国家的LLM上下文"""
    ctx_parts = []

    ctx_parts.append("## 企业画像")
    ctx_parts.append(f"- 企业名称: {company_profile.get('name', '未提供')}")
    ctx_parts.append(f"- 企业规模: {company_profile.get('scale', '未提供')}")
    ctx_parts.append(f"- 出口经验: {company_profile.get('export_experience', '未提供')}")
    ctx_parts.append(f"- 是否有电商团队: {'是' if company_profile.get('has_ecommerce_team') else '否'}")
    desc = company_profile.get('description', '').strip()
    if desc and desc != '未填写' and len(desc) > 2:
        ctx_parts.append(f"- 企业简介: {desc[:2000]}")

    ctx_parts.append(f"\n## 产品信息")
    ctx_parts.append(f"- HS编码: {hs_code}")
    ctx_parts.append(f"- 产品名称: {product_name}")
    ctx_parts.append(f"- 产品类别: {product_category}")

    iso = country_data["iso"]
    name = country_data["name"]
    s = country_data["scores"]
    d = country_data["details"]

    ctx_parts.append(f"\n## 目标市场: {name} (总分 {country_data['total_score']}/100)")
    ctx_parts.append(f"\n### 7维度得分明细")
    ctx_parts.append(f"- 市场规模: {s['market_size']}/20")
    ctx_parts.append(f"- 市场增长: {s['market_growth']}/15")
    ctx_parts.append(f"- 市场质量: {s['market_quality']}/20")
    ctx_parts.append(f"- 关税优势: {s['tariff_advantage']}/15")
    ctx_parts.append(f"- 竞争格局: {s['competition_landscape']}/12")
    ctx_parts.append(f"- 合规准入: {s['compliance_access']}/10")
    ctx_parts.append(f"- 商业便利: {s['business_convenience']}/8")

    ctx_parts.append(f"\n### 贸易数据")
    ctx_parts.append(f"- 进口总额: ${d.get('import_value_usd', 0):,}")
    ctx_parts.append(f"- 进口增速: {d.get('import_growth_pct', 'N/A')}%")
    ctx_parts.append(f"- 中国市场份额: {d.get('china_market_share_pct', 'N/A')}%")
    ctx_parts.append(f"- 人均GDP: ${d.get('gdp_per_capita', 0):,}")
    ctx_parts.append(f"- 结算货币: {d.get('currency', 'N/A')}")
    ctx_parts.append(f"- 消费者价格敏感度: {d.get('consumer_sensitivity', 'N/A')}")
    ctx_parts.append(f"- 物流绩效LPI: {d.get('logistics_lpi', 'N/A')}")
    ctx_parts.append(f"- 政策风险: {d.get('policy_risk', 'N/A')}")
    ctx_parts.append(f"- 贸易壁垒: {d.get('trade_barriers', 'N/A')}")
    if d.get('notes'):
        ctx_parts.append(f"- 市场备注: {d['notes']}")

    ctx_parts.append("\n## 行业知识库参考")
    try:
        trade_shows = json.load(open(DATA_DIR / "trade_shows.json", encoding="utf-8"))
        cat_shows = trade_shows.get(product_category, {})
        country_shows = cat_shows.get(iso, [])
        if country_shows:
            ctx_parts.append(f"\n### {name}相关展会")
            for s_show in country_shows[:3]:
                ctx_parts.append(f"- {s_show['name']} ({s_show.get('city','')}, {s_show.get('month','')}): {s_show.get('notes','')}")
    except Exception:
        pass

    try:
        from tools.ai_analyst import CATEGORY_CERTIFICATIONS
        certs_data = CATEGORY_CERTIFICATIONS.get(product_category, {})
        certs = certs_data.get(iso, [])
        if certs:
            ctx_parts.append(f"\n### {name}关键认证要求")
            for c in certs[:3]:
                ctx_parts.append(f"- {c['name']}: {c.get('desc','')} ({c.get('time','')}, {c.get('cost','')})")
    except Exception:
        pass

    return "\n".join(ctx_parts)


def generate_country_analysis(country_data: dict, context: dict,
                               api_key: str = "", provider: str = "openai") -> str:
    """为单个国家生成个性化深度分析 (LLM模式或规则模式)"""
    cp = context.get("company_profile", {})
    rankings = context.get("rankings", [])
    category = context.get("product_category", "")
    product_name = context.get("product_name", "")
    hs_code = context.get("hs_code", "")

    if api_key and len(api_key) > 10:
        ctx = build_single_country_context(
            country_data, category, product_name, hs_code, cp, rankings
        )
        system_prompt = f"""你是一个资深外贸出口顾问，现在要为一个特定目标市场做深度分析。

## 铁律
- **禁止任何开场白/问候语**。第一行直接输出"### {country_data['name']}市场深度分析"
- **所有建议必须结合企业画像**。如果企业有电商团队，推荐线上渠道；如果没有，推荐B2B和展会
- **每个建议都要具体**。不说"建议做认证"，要说"需要办理KFDC食品接触材料认证，约1-2个月，费用约￥5000-15000"
- **引用实际数据**。提到具体的进口额、增速、中国份额
- **中小企业视角**：建议聚焦单一市场，不要多线作战

## 输出格式 (严格按此结构):

### {country_data['name']}市场深度分析
[2-3句话，必须含企业名称+该市场的核心机会+为什么这个分数]

### 数据解读
- 市场规模意味着什么
- 增速说明了什么趋势
- 中国份额的竞争含义

### 准入门槛与应对
[列出该市场的具体认证要求、办理周期、费用估算、注意事项]

### 获客渠道
[具体的B2B平台、电商平台、展会名称+时间+地点，必须结合企业是否有电商团队]

### 行动路线图
- **准备期(1-3月)**: [3-4项针对该市场的具体行动]
- **切入期(3-6月)**: [3-4项针对该市场的具体行动]
- **扩张期(6-12月)**: [2-3项针对该市场的具体行动]

### 风险与提醒
[该市场特有的风险、容易踩的坑、与中国市场的差异]
"""
        try:
            return call_llm(ctx, api_key, provider, system_prompt=system_prompt)
        except Exception:
            return _generate_country_analysis_rule(country_data, context)

    return _generate_country_analysis_rule(country_data, context)


def _generate_country_analysis_rule(country_data: dict, context: dict) -> str:
    """规则引擎生成单国家分析 (无需API)"""
    cp = context.get("company_profile", {})
    category = context.get("product_category", "")

    company_name = cp.get("name", "贵公司") if cp.get("name") and cp.get("name") != "未填写" else "贵公司"
    has_ecom = cp.get("has_ecommerce_team", False)

    iso = country_data["iso"]
    name = country_data["name"]
    score = country_data["total_score"]
    s = country_data["scores"]
    d = country_data["details"]

    trade_shows = _load_json("trade_shows.json")
    b2b_data = _load_json("b2b_platforms.json")

    lines = []

    lines.append(f"### {name}市场深度分析\n")
    lines.append(f"**{company_name}** 聚焦 **{name}** 市场——7维度综合评分 **{score}/100分**。")

    growth = d.get("import_growth_pct", 0) or 0
    china_share = d.get("china_market_share_pct", 0) or 0
    gdp = d.get("gdp_per_capita", 0)

    if s.get("tariff_advantage", 0) >= 12:
        lines.append(f"FTA关税优势显著，关税成本远低于非FTA国家。")
    if growth > 10:
        lines.append(f"市场增速{'+' if growth > 0 else ''}{growth}%，仍在快速扩张期。")
    if china_share < 20:
        lines.append(f"中国产品仅占{china_share}%，蓝海机会明确。\n")
    else:
        lines.append(f"中国产品已占{china_share}%，需差异化竞争。\n")

    lines.append(f"### 数据解读\n")
    import_value = d.get('import_value_usd', 0) or 0
    lines.append(f"- **市场规模**: 进口总额 ${import_value:,}，{'规模较大，值得投入' if import_value > 10000000 else '小而美市场，适合中小企业试水'}")
    if growth > 20:
        lines.append(f"- **增长趋势**: {growth}% 爆炸式增长——新进入者的黄金窗口期")
    elif growth > 5:
        lines.append(f"- **增长趋势**: {growth}% 稳健增长——市场成熟但仍有增量空间")
    else:
        lines.append(f"- **增长趋势**: {growth}%——需关注是否已进入饱和期")
    lines.append(f"- **竞争格局**: 中国产品占{china_share}%——{'先发优势明显' if china_share < 15 else '已被验证可行' if china_share < 35 else '竞争较激烈'}")
    lines.append(f"- **消费能力**: 人均GDP ${gdp:,}，{d.get('currency','')}结算——{'高单价高利润' if gdp >= 25000 else '走量为主'}\n")

    lines.append(f"### 准入门槛与应对\n")
    certs = _get_certs_for_country(category, iso)
    if certs:
        for c in certs[:3]:
            critical = " (核心门槛)" if c.get("critical") else ""
            lines.append(f"- **{c['name']}**{critical}: {c.get('desc','')} (办理周期: {c.get('time','')}, 费用: {c.get('cost','')})")
    else:
        lines.append(f"- 该品类暂无特殊强制认证要求，但仍需符合{name}的通用产品安全标准")
    lines.append("")

    lines.append(f"### 获客渠道\n")
    if has_ecom:
        platforms = []
        for key, p in b2b_data.get("platforms", {}).items():
            countries = p.get("best_for_countries", [])
            cats = p.get("best_for_categories", [])
            if (iso in countries or "全球" in countries) and (category in cats or "全品类" in cats):
                platforms.append(p)
        if platforms:
            for p in platforms[:2]:
                lines.append(f"- **{p['name']}**({p.get('type','')}): {p.get('entry_cost','')}——{'适合直接零售' if p.get('type') == 'B2C' else '适合接OEM/ODM订单'}")
    else:
        lines.append(f"- **阿里巴巴国际站**(B2B, 约￥3-4万/年)——外贸获客核心渠道")

    cat_shows = trade_shows.get(category, {})
    country_shows = cat_shows.get(iso, [])
    if country_shows:
        lines.append(f"- **{name}本地展会**:")
        for s_show in country_shows[:2]:
            lines.append(f"  - {s_show['name']} ({s_show.get('city','')}, {s_show.get('month','')}): {s_show.get('notes','')}")
    lines.append(f"- **广交会**(Canton Fair, 广州, 4月/10月)——覆盖全球买家\n")

    lines.append(f"### 行动路线图\n")
    lines.append(f"**准备期(1-3月)**:")
    if certs:
        cert_names = "、".join(c["name"] for c in certs[:2])
        lines.append(f"  1. 启动{cert_names}认证——这是进入{name}市场的硬门槛")
    lines.append(f"  2. 准备{name}市场专用产品资料(报价单/规格书/包装设计)")
    lines.append(f"  3. 确认物流方案和首批样品安排")
    lines.append(f"  4. 注册相关B2B平台账号并建立公司主页\n")

    lines.append(f"**切入期(3-6月)**:")
    if country_shows:
        lines.append(f"  1. 参加{country_shows[0]['name']}({country_shows[0].get('city','')})——面对面接触{name}买家")
    lines.append(f"  2. 向{name}发出首批样品/试单, 验证产品适销性")
    if has_ecom:
        lines.append(f"  3. 上线{name}本土电商平台, 启动线上销售")
    lines.append(f"  4. 收集{name}客户反馈, 针对性优化产品\n")

    lines.append(f"**扩张期(6-12月)**:")
    lines.append(f"  1. 从试单转为稳定返单, 月出货稳定在1柜以上")
    lines.append(f"  2. 考虑{name}本地代理或合作伙伴, 降低获客成本")
    lines.append(f"  3. 根据市场反馈评估是否需要本地仓储\n")

    lines.append(f"### 风险与提醒\n")
    policy_risk = d.get("policy_risk", "中")
    trade_barriers = d.get("trade_barriers", "中")
    if policy_risk in ("高", "极高"):
        lines.append(f"- {name}政策风险为 **{policy_risk}**——需密切关注贸易政策变化，做好预案")
    if trade_barriers in ("高", "极高"):
        lines.append(f"- {name}贸易壁垒为 **{trade_barriers}**——认证和合规成本可能高于预期")
    if china_share > 50:
        lines.append(f"- 中国产品已占{china_share}%，价格竞争激烈——建议走差异化路线而非低价竞争")
    if gdp < 10000:
        lines.append(f"- {name}为人均GDP ${gdp:,}的价格敏感市场——定价策略需调整")

    lines.append(f"- 建议先小批量试单验证市场反应，不要一次性投入过大")
    lines.append("")

    return "\n".join(lines)
