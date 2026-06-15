"""出口目的国智能推荐系统 — 企业出口决策AI助手"""
import streamlit as st
import plotly.graph_objects as go
import json, os, re
from pathlib import Path

from rpa.comtrade_fetcher import fetch_all, TARGET_COUNTRIES
from tools.country_recommend import recommend_countries

# ── 加载 .env ──
def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k not in os.environ:
                    os.environ[k] = v
_load_env()

st.set_page_config(page_title="出口目的国智能推荐", page_icon="", layout="wide")

DATA_DIR = Path(__file__).parent / "data"

# ═══════════════════════════════════════════════════════
# CSS 主题
# ═══════════════════════════════════════════════════════
st.markdown("""
<style>
    /* ── 全局变量 ── */
    :root {
        --primary: #1B3A5C;
        --secondary: #3A7BD5;
        --accent-bg: #E8F0FE;
        --text: #1a1a1a;
        --gray: #555555;
        --bg: #EEF3FB;
        --border: #CCD8F0;
        --white: #FFFFFF;
    }

    /* ── 基础字体 ── */
    .stApp { background: var(--bg); }
    h1 { font-size: 36px !important; font-weight: 700 !important; color: #1B3A5C !important; }
    h2 { font-size: 28px !important; font-weight: 600 !important; color: #1B3A5C !important; }
    h3 { font-size: 22px !important; font-weight: 600 !important; color: #1a1a1a !important; }
    p, li, label, .stMarkdown { font-size: 18px !important; color: #1a1a1a !important; line-height: 1.6 !important; }
    .stCaption { color: #444444 !important; font-size: 14px !important; font-weight: 500 !important; }
    small, .small-text { color: #444444 !important; font-weight: 500 !important; }
    div[data-testid="stMarkdownContainer"] p { color: #1a1a1a !important; }

    /* ── 侧边栏 ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #F8FAFE 0%, #EEF3FB 100%) !important;
        border-right: 1px solid #CCD8F0 !important;
        padding-top: 32px !important;
        min-width: 380px !important;
    }
    [data-testid="stSidebar"] .stMarkdown h2 { font-size: 22px !important; color: #1B3A5C !important; }
    [data-testid="stSidebar"] .stMarkdown h3 { font-size: 18px !important; color: #1B3A5C !important; }
    [data-testid="stSidebar"] label { font-size: 15px !important; color: #1a1a1a !important; }
    [data-testid="stSidebar"] .stCaption { color: #555555 !important; }
    [data-testid="stSidebar"] .stButton > button {
        width: 100% !important; background: #1B3A5C !important; color: #8AB8E8 !important;
        border: none !important; border-radius: 8px !important; padding: 12px !important;
        font-size: 16px !important; font-weight: 600 !important;
    }

    /* ── Bento卡片 ── */
    .bento-card {
        background: #FFFFFF; border: 1px solid #CCD8F0;
        border-radius: 16px; padding: 24px; margin-bottom: 24px;
        box-shadow: 0 1px 3px rgba(27,58,92,0.04);
    }
    .bento-card h3 { margin-top: 0 !important; color: #1B3A5C !important; }

    /* ── 首页背景装饰(让玻璃拟态有内容可模糊) ── */
    .glass-wrapper {
        position: relative;
        max-width: 820px; min-height: 340px;
        margin: 80px auto 32px auto;
        overflow: visible;
    }
    .glass-bg-blob {
        position: absolute;
        border-radius: 50%;
        z-index: 0;
        opacity: 0.7;
    }
    .glass-bg-blob.blob1 {
        width: 260px; height: 260px;
        background: radial-gradient(circle at 30% 30%, #3A7BD5 0%, rgba(58,123,213,0) 70%);
        top: -80px; left: -50px;
    }
    .glass-bg-blob.blob2 {
        width: 300px; height: 300px;
        background: radial-gradient(circle at 60% 40%, #5A9BE0 0%, rgba(90,155,224,0) 70%);
        bottom: -100px; right: -60px;
    }
    .glass-bg-blob.blob3 {
        width: 180px; height: 180px;
        background: radial-gradient(circle at 50% 50%, #1B3A5C 0%, rgba(27,58,92,0) 70%);
        top: 30%; left: 55%;
    }

    /* ── 玻璃拟态卡片(首页) ── */
    .glass-card {
        position: relative; z-index: 1;
        background: rgba(255,255,255,0.25);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255,255,255,0.4);
        border-radius: 24px;
        padding: 64px 56px; text-align: center;
        box-shadow:
            0 8px 40px rgba(27,58,92,0.08),
            0 2px 8px rgba(27,58,92,0.04),
            inset 0 1px 0 rgba(255,255,255,0.5);
        overflow: hidden;
    }
    .glass-card::before {
        content: "";
        position: absolute;
        top: 0; left: 20px; right: 20px;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.7), transparent);
    }
    .glass-card h1 {
        margin-bottom: 24px !important;
        color: #1B3A5C !important;
        font-size: 36px !important; font-weight: 700 !important;
        -webkit-text-fill-color: #1B3A5C !important;
    }
    .glass-card .subtitle {
        color: #3A7BD5 !important; font-size: 21px !important;
        font-weight: 500 !important; line-height: 1.5 !important;
        text-shadow: 0 1px 2px rgba(255,255,255,0.5);
    }

    /* ── 首页Tab按钮 ── */
    .info-tab-row {
        max-width: 780px; margin: 0 auto 0 auto;
        display: flex; gap: 12px;
    }
    .info-tab-content {
        max-width: 780px; margin: 16px auto 0 auto;
        background: rgba(255,255,255,0.35);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border: 1px solid rgba(255,255,255,0.4);
        border-radius: 16px;
        padding: 32px;
    }
    .info-tab-content * { color: #3A7BD5 !important; }
    .info-tab-content h3 { color: #1B3A5C !important; }
    .info-tab-content a { color: #2D5A8A !important; }
    .info-tab-content strong { color: #1B3A5C !important; }

    /* ── 信息按钮 ── */
    .info-btn-row { display: flex; gap: 12px; justify-content: center; margin-top: 32px; flex-wrap: wrap; }

    /* ── Metric 卡片 ── */
    [data-testid="stMetric"] {
        background: var(--accent-bg) !important; border-radius: 12px !important;
        padding: 16px !important; border: 1px solid var(--border) !important;
    }
    [data-testid="stMetric"] label { font-size: 14px !important; color: #555555 !important; font-weight: 500 !important; }
    [data-testid="stMetric"] div[data-testid="stMetricValue"] { font-size: 28px !important; color: var(--primary) !important; }
    [data-testid="stMetric"] label[data-testid="stMetricLabel"] { color: #1a1a1a !important; font-weight: 500 !important; }
    [data-testid="stMetric"] div[data-testid="stMetricDelta"] { color: #555555 !important; }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] { border-radius: 12px !important; overflow: hidden !important; }

    /* ── Expander ── */
    [data-testid="stExpander"] {
        background: var(--white) !important; border: 1px solid var(--border) !important;
        border-radius: 12px !important;
    }
    [data-testid="stExpander"] details summary p {
        font-size: 17px !important; font-weight: 600 !important; color: #1a1a1a !important;
    }
    [data-testid="stExpander"] details summary:hover p { color: var(--secondary) !important; }
    /* 展开后内容文字必须清晰可见 */
    [data-testid="stExpander"] .stMarkdown,
    [data-testid="stExpander"] div[data-testid="stMarkdownContainer"] { color: #1a1a1a !important; }
    [data-testid="stExpander"] .stMarkdown p,
    [data-testid="stExpander"] .stMarkdown li,
    [data-testid="stExpander"] div[data-testid="stMarkdownContainer"] p,
    [data-testid="stExpander"] div[data-testid="stMarkdownContainer"] li { color: #1a1a1a !important; }
    /* 展开后内容区背景与文字对比 */
    [data-testid="stExpander"] > div:last-child { background: var(--white) !important; }

    /* ── 按钮 ── */
    .stButton > button {
        border-radius: 8px !important; font-weight: 600 !important;
        padding: 8px 20px !important; font-size: 16px !important;
    }

    /* ── Primary按钮(激活/强调) ── */
    button[kind="primary"] {
        background: #1B3A5C !important; color: #8AB8E8 !important;
        border: 2px solid #1B3A5C !important;
    }
    button[kind="primary"]:hover {
        background: #2a5a8c !important; border-color: #2a5a8c !important; color: #B0D0F0 !important;
    }

    /* ── Secondary按钮(非激活/普通) ── */
    button[kind="secondary"] {
        background: #FFFFFF !important; color: #3A7BD5 !important;
        border: 2px solid #CCD8F0 !important;
    }
    button[kind="secondary"]:hover {
        background: #E8F0FE !important; border-color: #3A7BD5 !important; color: #1B3A5C !important;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab"] { font-size: 16px !important; }

    /* ── 国家芯片按钮 ── */
    .country-chip-row { display: flex; flex-wrap: wrap; gap: 10px; margin: 16px 0; }
    .country-chip-btn button {
        border-radius: 24px !important; padding: 8px 18px !important; font-size: 14px !important;
        font-weight: 600 !important; border: 2px solid var(--border) !important;
        background: var(--white) !important; color: #1B3A5C !important;
        cursor: pointer !important; transition: all 0.2s !important;
        white-space: nowrap !important;
    }
    .country-chip-btn button:hover {
        border-color: var(--secondary) !important; background: var(--accent-bg) !important;
        color: #1B3A5C !important;
        transform: translateY(-2px) !important; box-shadow: 0 4px 12px rgba(58,123,213,0.2) !important;
    }
    .country-chip-active button {
        background: var(--primary) !important; color: #FFFFFF !important;
        border-color: var(--primary) !important;
    }

    /* ── 时间线 ── */
    .timeline-phase {
        background: var(--white); border-left: 4px solid var(--secondary);
        border-radius: 8px; padding: 16px 20px; margin: 12px 0;
    }
    .timeline-phase h4 { margin: 0 0 8px 0; color: var(--primary); font-size: 17px; }

    /* ── 展会表格 ── */
    .exhibition-table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 15px; }
    .exhibition-table th { background: var(--primary); color: white; padding: 10px 14px; text-align: left; font-size: 14px; }
    .exhibition-table td { padding: 10px 14px; border-bottom: 1px solid var(--border); }
    .exhibition-table tr:hover td { background: var(--accent-bg); }

    /* ── 市场分析卡片 ── */
    .market-card {
        background: var(--white); border: 1px solid var(--border);
        border-radius: 12px; padding: 20px; margin: 12px 0;
    }
    .market-card h4 { color: var(--primary); margin-top: 0; font-size: 19px; }
    .market-card .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .market-card .detail-item { font-size: 15px; color: #1a1a1a !important; }
    .market-card p, .market-card li, .market-card span, .market-card div { color: #1a1a1a !important; }
    .market-card strong, .market-card b { color: #1B3A5C !important; }

    /* ── 参考数据紧凑布局 ── */
    .ref-compact { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
    .ref-compact .ref-cat { background: var(--white); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }
    .ref-compact .ref-cat h4 { font-size: 16px; color: var(--primary); margin: 0 0 10px 0; }
    .ref-compact .ref-cat a { font-size: 14px; display: block; margin: 4px 0; }
    .ref-compact .ref-cat span { font-size: 13px; color: var(--gray); }

""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════
@st.cache_data(ttl=3600)
def cached_fetch(hs_code, year=2023, quick=True):
    return fetch_all(hs_code, year, quick_mode=quick)

@st.cache_data(ttl=3600)
def cached_fetch_filtered(hs_code, year, country_isos):
    isos = country_isos.split(",")
    target = {iso: TARGET_COUNTRIES[iso] for iso in isos if iso in TARGET_COUNTRIES}
    return fetch_all(hs_code, year, target_list=target)

def _read_uploaded_files(files):
    content = ""
    if not files: return content
    for uf in files:
        if uf.type == "application/pdf":
            try:
                import io; from PyPDF2 import PdfReader
                reader = PdfReader(io.BytesIO(uf.read()))
                text = " ".join(p.extract_text() or "" for p in reader.pages[:5])[:2000]
                if text: content += f"\n[{uf.name}]: {text}"
            except Exception:
                content += f"\n[PDF: {uf.name}]"
        else:
            content += f"\n[图片: {uf.name}]"
    return content.strip()

def _load_references():
    p = DATA_DIR / "references.json"
    return json.load(open(p, encoding="utf-8")) if p.exists() else {"categories": {}}

@st.cache_data(ttl=3600)
def _verify_reference_urls(refs):
    import urllib.request, ssl
    verified = {}
    ctx = ssl.create_default_context()
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    for items in refs.get("categories", {}).values():
        for item in items:
            url = item.get("url", "")
            if not url: verified[url] = False; continue
            try:
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("User-Agent", "Mozilla/5.0")
                with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                    verified[url] = resp.status in (200, 301, 302, 307, 308)
            except Exception:
                verified[url] = False
    return verified

def _render_references(refs, verified_urls):
    cats = refs.get("categories", {})
    if not cats: return
    # 紧凑网格布局
    html_parts = ['<div class="ref-compact">']
    for cat_name, items in cats.items():
        html_parts.append(f'<div class="ref-cat"><h4>{cat_name}</h4>')
        for item in items:
            url = item.get("url", "")
            name = item.get("name", "")
            desc = item.get("description", "")
            ok = verified_urls.get(url, item.get("verified", False))
            if ok and url:
                html_parts.append(f'<a href="{url}" target="_blank">{name}</a><span>{desc}</span>')
            else:
                html_parts.append(f'<div style="font-size:14px;margin:6px 0"><strong>{name}</strong></div><span>{desc}</span>')
        html_parts.append('</div>')
    html_parts.append('</div>')
    st.markdown("".join(html_parts), unsafe_allow_html=True)
    st.caption(f"验证时间: {refs.get('_last_verified', 'N/A')}")


def _render_exhibition_section(title, body):
    """将展会章节渲染为可读表格"""
    with st.expander(f"■ {title}", expanded=True):
        # 尝试从body中提取表格行
        table_rows = re.findall(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", body)
        if len(table_rows) >= 2:
            # 跳过表头分隔行
            data_rows = [r for r in table_rows if not re.match(r"^[-:]+$", r[0].strip())]
            if data_rows:
                st.markdown(f"""
                <table class="exhibition-table">
                    <thead><tr><th>{data_rows[0][0].strip()}</th><th>{data_rows[0][1].strip()}</th>
                    <th>{data_rows[0][2].strip()}</th><th>{data_rows[0][3].strip()}</th></tr></thead>
                    <tbody>{"".join(f'<tr><td>{r[0].strip()}</td><td>{r[1].strip()}</td><td>{r[2].strip()}</td><td>{r[3].strip()}</td></tr>' for r in data_rows[1:])}</tbody>
                </table>
                """, unsafe_allow_html=True)
                return
        st.markdown(body)

def _render_timeline_section(title, body):
    """将行动时间线渲染为三列阶段卡片"""
    with st.expander(f"■ {title}", expanded=True):
        phases = re.findall(r"\*\*(.+?)\*\*[：:]\s*(.+)", body)
        if len(phases) >= 2:
            cols = st.columns(len(phases))
            for i, (col, (phase_name, phase_content)) in enumerate(zip(cols, phases)):
                # 清理阶段名称
                name = re.sub(r'[^\w\s一-鿿\-（）()]', '', phase_name).strip()
                # 去除内容中的markdown链接和列表符号
                content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', phase_content)
                # 按分号或句号拆分为列表项
                items = re.split(r'[；;。.](?:\s*)', content)
                items = [it.strip() for it in items if it.strip()]
                with col:
                    st.markdown(f"""
                    <div class="timeline-phase">
                        <h4>{name}</h4>
                        <ul style="margin:8px 0 0 0;padding-left:18px;font-size:15px;">
                            {"".join(f'<li style="margin:4px 0">{it}</li>' for it in items[:5])}
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown(body)

def _render_market_section(title, body):
    """将目标市场分析渲染为独立卡片"""
    with st.expander(f"■ {title}", expanded=True):
        # 按 **#数字 国家名 拆分每个市场
        markets = re.split(r"\n(?=\*\*#\d+)", body)
        if len(markets) > 1:
            for mkt in markets:
                mkt = mkt.strip()
                if not mkt:
                    continue
                # 提取市场标题行
                head_match = re.match(r"\*\*(.+?)\*\*(.*)", mkt)
                if head_match:
                    mkt_title = head_match.group(1).strip()
                    mkt_body = mkt[head_match.end():].strip()
                    # 清理掉markdown **
                    mkt_title_clean = mkt_title.replace("**", "").strip()
                    # 将列表项提取为键值对
                    items = re.findall(r"-\s*\*\*(.+?)\*\*[：:]?\s*(.+)", mkt_body)
                    if items:
                        st.markdown(f'<div class="market-card"><h4>{mkt_title_clean}</h4>', unsafe_allow_html=True)
                        for key, val in items:
                            st.markdown(f'<div style="margin:4px 0"><strong>{key}</strong>：{val}</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="market-card"><h4>{mkt_title_clean}</h4><div style="font-size:15px">{mkt_body}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown(body)

# ── Session State ──
for k, v in {
    "step": "input", "product_desc": "", "hs_candidates": [],
    "selected_hs": "", "selected_product_name": "", "selected_category": "",
    "uploaded_content": "", "extracted": None, "raw_input": "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════════════
# 侧边栏 (Sticky + Bento Grid)
# ═══════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 企业信息")

    raw_input = st.text_area(
        "粘贴企业/产品信息，AI自动提取",
        value=st.session_state.get("raw_input", ""),
        placeholder="粘贴任意文本：企业名称、产品描述、材质、产能、认证、出口经验等...\n\n示例：\n东莞市卡珀包装科技有限公司，官网kapocup.com，专注一次性塑料杯和餐盒，PP材质，年产2000万只，ISO9001认证，已有出口东南亚经验，有电商团队做阿里巴巴国际站...",
        height=130,
        label_visibility="collapsed",
    )

    st.markdown("### 上传资料")
    uploaded_files = st.file_uploader(
        "上传产品图册/企业介绍(PDF/图片)",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    manual_hs = st.text_input("或直接输入HS编码", placeholder="如 392410")

    quick_mode = st.checkbox("智能筛选模式", value=True, help="AI筛选15-25个最相关国家")

    st.divider()

    if st.button("开始智能分析", type="primary", use_container_width=True):
        if manual_hs.strip():
            st.session_state.selected_hs = manual_hs.strip()
            st.session_state.selected_product_name = f"HS {manual_hs.strip()}"
            st.session_state.selected_category = ""
            st.session_state.product_desc = raw_input.strip() or f"HS {manual_hs.strip()}"
            st.session_state.raw_input = raw_input
            st.session_state.step = "analyze"
            st.rerun()
        elif raw_input.strip():
            st.session_state.raw_input = raw_input
            st.session_state.step = "extract"
            st.rerun()
        else:
            st.error("请粘贴企业/产品信息")

    st.divider()
    st.caption(f"覆盖 {len(TARGET_COUNTRIES)} 个国家 | UN Comtrade实时数据")
    st.caption("DeepSeek AI | MCP Server架构")

# ── 企业画像 ──
company_profile = {
    "name": "未填写", "scale": "中小企业", "website": "",
    "description": "", "export_experience": "无经验", "has_ecommerce_team": False,
}

# ═══════════════════════════════════════════════════════
# 首页：玻璃拟态卡片
# ═══════════════════════════════════════════════════════
if st.session_state.step == "input":
    # 玻璃拟态主卡片(带背景装饰让blur可见)
    st.markdown("""
    <div class="glass-wrapper">
        <div class="glass-bg-blob blob1"></div>
        <div class="glass-bg-blob blob2"></div>
        <div class="glass-bg-blob blob3"></div>
        <div class="glass-card">
            <h1>出口目的国智能推荐系统</h1>
            <p class="subtitle">全球化时代，你的产品应该走到世界的哪个角落？</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 三选一Tab切换 — 占满宽度，相互覆盖
    tab_names = ["系统运行流程", "7维度评分体系", "55个目标市场"]
    if "home_tab" not in st.session_state:
        st.session_state.home_tab = 0

    # Tab按钮栏
    cols = st.columns(3)
    for i, (col, name) in enumerate(zip(cols, tab_names)):
        with col:
            active = st.session_state.home_tab == i
            if st.button(name, key=f"home_tab_btn_{i}",
                        type="primary" if active else "secondary",
                        use_container_width=True):
                st.session_state.home_tab = i
                st.rerun()

    # 对应内容 — 全宽展开
    st.markdown('<div class="info-tab-content">', unsafe_allow_html=True)
    if st.session_state.home_tab == 0:
        st.markdown("""
        ### 系统运行流程

        1. **信息输入** — 用户粘贴企业/产品文本，AI自动提取关键信息
        2. **HS编码匹配** — DeepSeek大模型根据产品描述匹配HS 6位编码
        3. **RPA数据采集** — 从UN Comtrade实时抓取55国进口贸易数据
        4. **7维评分** — 市场规模/增长/质量/关税/竞争/合规/便利综合评估
        5. **AI策略生成** — 基于企业画像生成个性化出口方案

        **参考贸易政策文件：**
        - [RCEP协定文本](http://fta.mofcom.gov.cn/rcep/)
        - [中国-东盟FTA](http://fta.mofcom.gov.cn/dongmeng/)
        - [中韩FTA](http://fta.mofcom.gov.cn/korea/)
        - [WTO贸易便利化协定](https://www.wto.org/english/tratop_e/tradfa_e/tradfa_e.htm)
        - [UN Comtrade Methodology](https://unstats.un.org/unsd/tradekb/Knowledgebase/50075/Comtrade-Methodology)
        """)
    elif st.session_state.home_tab == 1:
        st.markdown("""
        ### 7维度评分体系

        | 维度 | 权重 | 数据来源 |
        |------|------|---------|
        | 市场规模 | 20% | UN Comtrade进口额 + GDP |
        | 市场增长 | 15% | UN Comtrade同比增长率 |
        | 市场质量 | 20% | 人均GDP + 货币稳定性 + 消费敏感度 |
        | 关税优势 | 15% | WTO/FTA关税减让表 |
        | 竞争格局 | 12% | 中国市场份额分析 |
        | 合规准入 | 10% | 政策风险 + 贸易壁垒评估 |
        | 商业便利 | 8% | 世界银行LPI + 营商环境 |

        **参考文献：**
        - WTO Trade Performance Index
        - World Bank Ease of Doing Business Index
        - World Bank Logistics Performance Index (LPI)
        - UNCTAD Trade and Development Report
        - 中国海关总署《进出口税则》
        """)
    else:
        st.markdown("### 55个国家/地区")
        regions = {}
        for iso, info in TARGET_COUNTRIES.items():
            r = info["region"]
            regions.setdefault(r, []).append(info["name"])
        for region, countries in regions.items():
            st.markdown(f"**{region}**：{'、'.join(countries)}")
    st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════
# 提取步骤
# ═══════════════════════════════════════════════════════
elif st.session_state.step == "extract":
    st.markdown("## AI智能提取")

    if uploaded_files and not st.session_state.uploaded_content:
        st.session_state.uploaded_content = _read_uploaded_files(uploaded_files)

    combined = st.session_state.get("raw_input", "")
    if st.session_state.uploaded_content:
        combined += "\n" + st.session_state.uploaded_content

    if not st.session_state.extracted:
        with st.spinner("AI正在从文本中提取企业/产品信息..."):
            from tools.llm_analyst import extract_company_info
            st.session_state.extracted = extract_company_info(combined)

    extracted = st.session_state.extracted
    if extracted and extracted.get("product_desc"):
        st.success("提取完成，请核对以下信息")

        col1, col2 = st.columns(2)
        with col1:
            _cn = st.text_input("企业名称", value=extracted.get("company_name", ""), key="e_cn")
            _cs = st.radio("企业规模", ["中小企业", "大型企业"],
                           index=0 if extracted.get("company_scale") != "大型企业" else 1,
                           horizontal=True, key="e_cs")
            _ee = st.selectbox("出口经验", ["无经验", "有经验(已有出口)", "成熟出口商"],
                               index={"无经验":0,"有经验":1,"成熟":2}.get(extracted.get("export_experience",""),0), key="e_ee")
        with col2:
            _pd = st.text_area("产品描述", value=extracted.get("product_desc", ""), height=100, key="e_pd")
            _hec = st.checkbox("已有电商运营团队", value=extracted.get("has_ecommerce", False), key="e_hec")
            _cd = st.text_area("企业简介", value=extracted.get("company_description", ""), height=80, key="e_cd")

        hsc = extracted.get("hs_candidates", [])
        if hsc:
            st.markdown("**匹配的HS编码候选**")
            cols = st.columns(min(len(hsc), 4))
            for i, c in enumerate(hsc):
                with cols[i]:
                    st.metric(c["hs_code"], c.get("name", ""), f"匹配度 {c.get('confidence',0):.0%}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("确认并继续", type="primary", use_container_width=True):
                st.session_state.product_desc = _pd
                st.session_state.extracted = {
                    "company_name": _cn, "company_scale": _cs, "product_desc": _pd,
                    "company_description": _cd, "export_experience": _ee,
                    "has_ecommerce": _hec, "hs_candidates": hsc,
                }
                st.session_state.hs_candidates = hsc or []
                st.session_state.step = "confirm_hs" if hsc else "analyze"
                st.rerun()
        with c2:
            if st.button("重新提取"):
                st.session_state.extracted = None
                st.session_state.uploaded_content = ""
                st.rerun()
    else:
        st.warning("AI未能提取到足够信息")
        if st.button("返回修改"):
            st.session_state.step = "input"; st.rerun()

# ═══════════════════════════════════════════════════════
# HS确认
# ═══════════════════════════════════════════════════════
elif st.session_state.step == "confirm_hs":
    st.markdown("## 确认HS编码")

    extracted = st.session_state.extracted or {}
    pd_text = st.session_state.product_desc or st.session_state.get("raw_input", "")
    cd_text = extracted.get("company_description", "")

    if extracted:
        company_profile.update({
            "name": extracted.get("company_name", "") or "未填写",
            "scale": extracted.get("company_scale", "中小企业"),
            "description": cd_text or "",
            "export_experience": extracted.get("export_experience", "无经验"),
            "has_ecommerce_team": extracted.get("has_ecommerce", False),
        })

    if not st.session_state.hs_candidates:
        with st.spinner("AI正在匹配HS编码..."):
            from tools.llm_analyst import suggest_hs_codes
            st.session_state.hs_candidates = suggest_hs_codes(pd_text, cd_text)

    candidates = st.session_state.hs_candidates
    if not candidates or candidates[0]["hs_code"] == "N/A":
        st.warning("未匹配到，请手动输入")
        m = st.text_input("HS编码（6位）", placeholder="如 392410")
        if st.button("使用此编码") and m.strip():
            st.session_state.selected_hs = m.strip()
            st.session_state.selected_product_name = f"HS {m.strip()}"
            st.session_state.selected_category = ""
            st.session_state.step = "analyze"
            st.rerun()
    else:
        st.success(f"匹配到 {len(candidates)} 个候选HS编码")
        cols = st.columns(min(len(candidates), 4))
        chosen = None
        for i, c in enumerate(candidates):
            with cols[i]:
                st.metric(c["hs_code"], c.get("name",""), f"匹配度 {c.get('confidence',0):.0%} | {c.get('category','')}")
                if st.button(f"选择 {c['hs_code']}", key=f"hs_{i}", use_container_width=True):
                    chosen = i
        if chosen is not None:
            c = candidates[chosen]
            st.session_state.selected_hs = c["hs_code"]
            st.session_state.selected_product_name = c.get("name", "")
            st.session_state.selected_category = c.get("category", "")
            st.session_state.step = "analyze"
            st.rerun()

        mo = st.text_input("或手动输入HS编码覆盖", placeholder="如以上都不匹配")
        if mo.strip() and st.button("使用手动编码"):
            st.session_state.selected_hs = mo.strip()
            st.session_state.selected_product_name = f"HS {mo.strip()}"
            st.session_state.selected_category = ""
            st.session_state.step = "analyze"
            st.rerun()

    if st.button("返回修改"):
        st.session_state.step = "input"
        st.session_state.hs_candidates = []
        st.session_state.extracted = None
        st.rerun()

# ═══════════════════════════════════════════════════════
# 分析结果页 (Bento Grid)
# ═══════════════════════════════════════════════════════
elif st.session_state.step == "analyze":
    hs_code = st.session_state.selected_hs
    product_name = st.session_state.selected_product_name
    product_category = st.session_state.selected_category

    # 更新企业画像
    extracted = st.session_state.extracted or {}
    if extracted:
        company_profile.update({
            "name": extracted.get("company_name", "") or "未填写",
            "scale": extracted.get("company_scale", "中小企业"),
            "description": extracted.get("company_description", "") or "",
            "export_experience": extracted.get("export_experience", "无经验"),
            "has_ecommerce_team": extracted.get("has_ecommerce", False),
        })
    if st.session_state.uploaded_content:
        company_profile["description"] = (company_profile.get("description","") or "") + "\n[资料]: " + st.session_state.uploaded_content[:4000]

    # 检查缓存：HS编码没变则跳过重计算
    cache_key = f"{hs_code}_{company_profile.get('scale','')}"
    if st.session_state.get("_cache_key") != cache_key:
        # 智能国家筛选
        target_override = None
        if quick_mode and st.session_state.product_desc:
            from tools.llm_analyst import suggest_target_countries
            suggested = suggest_target_countries(
                st.session_state.product_desc, hs_code,
                company_profile.get("description", ""),
            )
            if suggested and len(suggested) >= 5:
                target_override = suggested

        # 抓取数据
        with st.spinner("RPA正在从UN Comtrade实时抓取贸易数据..."):
            if target_override:
                trade_data = cached_fetch_filtered(hs_code, 2023, ",".join(target_override))
            else:
                trade_data = cached_fetch(hs_code, 2023, quick=quick_mode)

        # 处理上传文件
        if uploaded_files and not st.session_state.uploaded_content:
            st.session_state.uploaded_content = _read_uploaded_files(uploaded_files)
        if st.session_state.uploaded_content:
            existing = company_profile.get("description", "") or ""
            if st.session_state.uploaded_content not in existing:
                company_profile["description"] = existing + "\n[资料]: " + st.session_state.uploaded_content[:4000]

        # 加载产品信息
        products = json.load(open(DATA_DIR / "hs_products.json", encoding="utf-8"))
        product_info = products.get(hs_code, {"name_zh": product_name, "category": product_category or "待分类"})

        # 评分
        with st.spinner("7维度评分中..."):
            result = recommend_countries(
                trade_data, hs_code,
                product_category or product_info.get("category", ""),
                company_profile.get("scale", "中小企业"),
            )

        # 缓存结果
        st.session_state._cache_key = cache_key
        st.session_state._cached_result = result
        st.session_state._cached_trade_data = trade_data
        st.session_state._cached_product_info = product_info
    else:
        result = st.session_state._cached_result
        trade_data = st.session_state._cached_trade_data
        product_info = st.session_state._cached_product_info

    rankings = result["rankings"]
    if not rankings:
        st.error("未获取到贸易数据，请检查HS编码或网络连接")
        st.stop()

    # ═══════════════════════════════════════════
    # A. 结果头部：HS编码 + Top3
    # ═══════════════════════════════════════════
    st.markdown(f"## {product_info.get('name_zh', product_name)} — 出口目的国推荐")

    top3 = rankings[:3]
    c1, c2, c3 = st.columns(3)
    medals = ["", "", ""]
    for col, country, medal in zip([c1, c2, c3], top3, medals):
        with col:
            d = country["details"]
            st.metric(
                f"{medal}#{rankings.index(country)+1} {country['name']}",
                f"{country['total_score']}/100分",
                f"{country['region']} | {d.get('currency','')} | GDP per capita ${d.get('gdp_per_capita',0):,}",
            )

    # ═══════════════════════════════════════════
    # B. Top10 排名表 + 国家按钮
    # ═══════════════════════════════════════════
    st.markdown("### Top 10 推荐国家排名")

    table_data = []
    for r in rankings[:10]:
        s = r["scores"]
        table_data.append({
            "排名": rankings.index(r) + 1, "国家": r["name"], "区域": r["region"],
            "综合评分": r["total_score"],
            "市场规模": f"{s['market_size']}/20", "市场增长": f"{s['market_growth']}/15",
            "市场质量": f"{s['market_quality']}/20", "关税优势": f"{s['tariff_advantage']}/15",
            "竞争格局": f"{s['competition_landscape']}/12", "合规准入": f"{s['compliance_access']}/10",
            "商业便利": f"{s['business_convenience']}/8",
        })
    st.dataframe(table_data, column_config={
        "综合评分": st.column_config.ProgressColumn("综合评分", format="%d", min_value=0, max_value=100),
    }, use_container_width=True, hide_index=True)

    # 国家芯片按钮 — 看得见、点得到
    st.markdown("#### 各国数据明细")
    if "selected_country_idx" not in st.session_state:
        st.session_state.selected_country_idx = None

    chip_cols = st.columns(10)
    for i, (col, r) in enumerate(zip(chip_cols, rankings[:10])):
        with col:
            cls = "country-chip-active" if st.session_state.selected_country_idx == i else "country-chip-btn"
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            if st.button(r['name'], key=f"chip_{i}", use_container_width=True):
                st.session_state.selected_country_idx = i
            st.markdown('</div>', unsafe_allow_html=True)

    # 只在用户点击后显示详情
    if st.session_state.selected_country_idx is not None:
        sel_r = rankings[st.session_state.selected_country_idx]
        s = sel_r["scores"]; d = sel_r["details"]
        st.markdown(f"#### {sel_r['name']} — {sel_r['total_score']}分")

        c1, c2, c3 = st.columns([2, 2, 3])
        with c1:
            st.markdown('<div class="market-card">', unsafe_allow_html=True)
            st.markdown("**贸易数据**")
            st.metric("进口总额", f"${d['import_value_usd']:,.0f}" if d.get('import_value_usd') else "暂无")
            delta = f"{d['import_growth_pct']}%" if d.get('import_growth_pct') else "暂无"
            st.metric("进口增速", delta)
            china_share = f"{d.get('china_market_share_pct','暂无')}%"
            st.metric("中国市场份额", china_share if d.get('china_market_share_pct') is not None else "暂无")
            st.markdown('</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="market-card">', unsafe_allow_html=True)
            st.markdown("**市场质量**")
            st.metric("人均GDP", f"${d.get('gdp_per_capita',0):,}")
            st.metric("结算货币", str(d.get('currency','暂无')))
            st.metric("物流LPI", str(d.get('logistics_lpi','暂无')))
            st.metric("政策风险", str(d.get('policy_risk','暂无')))
            st.markdown('</div>', unsafe_allow_html=True)
        with c3:
            st.markdown('<div class="market-card">', unsafe_allow_html=True)
            st.markdown("**七维得分**")
            score_items = [
                ("市场规模", s['market_size'], 20), ("市场增长", s['market_growth'], 15),
                ("市场质量", s['market_quality'], 20), ("关税优势", s['tariff_advantage'], 15),
                ("竞争格局", s['competition_landscape'], 12), ("合规准入", s['compliance_access'], 10),
                ("商业便利", s['business_convenience'], 8),
            ]
            for name, val, mx in score_items:
                pct = val / mx
                color = "#1B3A5C" if pct >= 0.7 else ("#3A7BD5" if pct >= 0.5 else "#D93025")
                st.markdown(f'<div style="margin:6px 0"><span style="font-size:14px">{name}</span> '
                            f'<span style="float:right;font-weight:600;color:{color}">{val}/{mx}</span>'
                            f'<div style="background:#E8F0FE;border-radius:4px;height:6px;margin-top:2px">'
                            f'<div style="background:{color};border-radius:4px;height:6px;width:{pct*100}%"></div></div></div>',
                            unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            if d.get('notes'):
                st.caption(d['notes'])

    # ═══════════════════════════════════════════
    # C. 雷达图 + 维度按钮
    # ═══════════════════════════════════════════
    st.markdown("### Top 5 七维度雷达图对比")

    radar_cats = ["市场规模", "市场增长", "市场质量", "关税优势", "竞争格局", "合规准入", "商业便利"]
    dim_keys = ["market_size", "market_growth", "market_quality", "tariff_advantage",
                "competition_landscape", "compliance_access", "business_convenience"]

    fig = go.Figure()
    colors = ["#1B3A5C", "#3A7BD5", "#5A9BE0", "#8AB8E8", "#B0D0F0"]
    for i, r in enumerate(rankings[:5]):
        s = r["scores"]
        fig.add_trace(go.Scatterpolar(
            r=[s[k] for k in dim_keys], theta=radar_cats, fill="toself",
            name=f"#{i+1} {r['name']} ({r['total_score']}分)", line_color=colors[i],
        ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 20])),
        showlegend=True, legend=dict(orientation="h", y=-0.2),
        height=480, margin=dict(l=40, r=40, t=20, b=80),
    )
    st.plotly_chart(fig, use_container_width=True)

    # 维度对比图表
    st.markdown("#### 各维度Top10对比")
    dim_tabs = st.tabs(radar_cats)
    for i, (tab, dim_name, dim_key) in enumerate(zip(dim_tabs, radar_cats, dim_keys)):
        with tab:
            sorted_data = sorted(
                [(r["name"], r["scores"][dim_key]) for r in rankings[:10]],
                key=lambda x: x[1], reverse=True
            )
            dim_fig = go.Figure()
            dim_fig.add_trace(go.Bar(
                x=[x[1] for x in sorted_data], y=[x[0] for x in sorted_data],
                orientation="h", marker_color=colors[i % 5],
                text=[str(x[1]) for x in sorted_data], textposition="outside",
            ))
            dim_fig.update_layout(height=350, margin=dict(l=10, r=30, t=10, b=10),
                                  xaxis_title=dim_name)
            st.plotly_chart(dim_fig, use_container_width=True)


    # ═══════════════════════════════════════════
    # D. AI深度分析 (结构化渲染)
    # ═══════════════════════════════════════════
    st.divider()

    import importlib
    import tools.llm_analyst as _llm_mod
    importlib.reload(_llm_mod)
    generate_instant_analysis = _llm_mod.generate_instant_analysis
    build_context = _llm_mod.build_context
    call_llm = _llm_mod.call_llm
    generate_country_analysis = _llm_mod.generate_country_analysis

    # 判断是否选中了具体国家
    selected_country = None
    if st.session_state.get("selected_country_idx") is not None:
        sel_idx = st.session_state.selected_country_idx
        if sel_idx < len(rankings):
            selected_country = rankings[sel_idx]

    # ── 按选中/未选中分别处理 ──
    if selected_country is not None:
        # 选中了具体国家 → 生成该国个性化分析
        country_iso = selected_country["iso"]
        st.markdown(f"## {selected_country['name']}市场 · 深度分析")

        # 每国独立缓存
        if "_cached_country_analyses" not in st.session_state:
            st.session_state._cached_country_analyses = {}

        if country_iso in st.session_state._cached_country_analyses:
            analysis_md = st.session_state._cached_country_analyses[country_iso]
        else:
            # 构建context_data (需要rankings信息)
            context_data = {
                "company_profile": company_profile, "hs_code": hs_code,
                "product_name": result["product_name"],
                "product_category": product_info.get("category", ""),
                "rankings": [{"rank": i+1, "name": r["name"], "iso": r["iso"],
                               "region": r["region"], "total_score": r["total_score"],
                               "scores": r["scores"], "details": r["details"]}
                              for i, r in enumerate(rankings)],
            }

            api_key = os.environ.get("LLM_API_KEY", "").strip()
            api_provider = os.environ.get("LLM_PROVIDER", "openai")

            if api_key:
                with st.spinner(f"AI正在为{selected_country['name']}市场生成个性化分析..."):
                    try:
                        analysis_md = generate_country_analysis(
                            selected_country, context_data, api_key, api_provider
                        )
                        st.caption(f"{selected_country['name']} · {api_provider} 大模型深度分析")
                    except Exception as e:
                        st.warning(f"LLM调用失败: {str(e)[:200]}，使用规则引擎")
                        analysis_md = generate_country_analysis(selected_country, context_data)
            else:
                with st.spinner(f"AI正在分析{selected_country['name']}市场..."):
                    analysis_md = generate_country_analysis(selected_country, context_data)

            st.session_state._cached_country_analyses[country_iso] = analysis_md

    else:
        # 未选中具体国家 → 整体多国分析 (原逻辑)
        st.markdown("## AI行业分析师 · 深度建议")

        if st.session_state.get("_cached_analysis") and st.session_state.get("_analysis_cache_key") == cache_key:
            analysis_md = st.session_state._cached_analysis
        else:
            context_data = {
                "company_profile": company_profile, "hs_code": hs_code,
                "product_name": result["product_name"], "product_category": product_info.get("category", ""),
                "rankings": [{"rank": i+1, "name": r["name"], "iso": r["iso"], "region": r["region"],
                               "total_score": r["total_score"], "scores": r["scores"], "details": r["details"]}
                              for i, r in enumerate(rankings)],
                "data_source": result["data_source"], "fetch_timestamp": result["fetch_timestamp"],
                "total_countries_analyzed": result["total_countries_analyzed"],
            }
            json.dump(context_data, open(DATA_DIR / "analysis_context.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)

            api_key = os.environ.get("LLM_API_KEY", "").strip()
            api_provider = os.environ.get("LLM_PROVIDER", "openai")

            if api_key:
                with st.spinner("AI大模型正在深度分析..."):
                    try:
                        ctx = build_context(
                            context_data["rankings"], context_data["product_category"],
                            context_data["product_name"], context_data["hs_code"], company_profile,
                        )
                        analysis_md = call_llm(ctx, api_key, api_provider)
                        st.caption(f"分析模式: {api_provider} 大模型深度分析")
                    except Exception as e:
                        st.warning(f"LLM调用失败: {str(e)[:200]}，已切换为智能规则引擎")
                        analysis_md = generate_instant_analysis(context_data)
            else:
                with st.spinner("AI正在深度分析..."):
                    analysis_md = generate_instant_analysis(context_data)

            st.session_state._cached_analysis = analysis_md
            st.session_state._analysis_cache_key = cache_key

    # 缓存AI分析渲染结果：只有analysis_md变化时才重新解析
    if (st.session_state.get("_cached_parsed_sections") is None
            or st.session_state.get("_parsed_md_hash") != hash(analysis_md)):
        sections = re.split(r"\n(?=###\s+)", analysis_md)
        st.session_state._cached_parsed_sections = sections
        st.session_state._parsed_md_hash = hash(analysis_md)
    else:
        sections = st.session_state._cached_parsed_sections
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        # 提取标题和正文
        header_match = re.match(r"###\s+(.+)", sec)
        if not header_match:
            continue
        title = header_match.group(1)
        # 移除标题中的所有emoji
        clean_title = re.sub(r'[^\w\s一-鿿\-]', '', title).strip()
        body = sec[header_match.end():].strip()

        if not clean_title:
            continue

        # 根据章节类型选择渲染方式
        if "参展计划" in title or "展会" in title:
            _render_exhibition_section(clean_title, body)
        elif "行动时间线" in title or "时间线" in title:
            _render_timeline_section(clean_title, body)
        elif "目标市场" in title or "市场分析" in title:
            _render_market_section(clean_title, body)
        elif "策略总览" in title or "总览" in title:
            with st.expander(f"■ {clean_title}", expanded=True):
                st.markdown(body)
        elif "提醒" in title or "风险" in title:
            with st.expander(f"■ {clean_title}", expanded=True):
                st.markdown(body)
        else:
            with st.expander(f"■ {clean_title}", expanded=False):
                st.markdown(body)

    # ═══════════════════════════════════════════
    # E. 数据来源 (折叠)
    # ═══════════════════════════════════════════
    st.divider()
    with st.expander("数据来源与参考资料"):
        refs = _load_references()
        verified = _verify_reference_urls(refs)
        _render_references(refs, verified)

    # 重新分析
    st.divider()
    if st.button("重新分析（修改信息）"):
        for k in ["step", "hs_candidates", "extracted", "uploaded_content", "selected_hs",
                   "_cache_key", "_cached_result", "_cached_trade_data",
                   "_cached_product_info", "_cached_analysis", "_analysis_cache_key",
                   "_cached_country_analyses", "_cached_parsed_sections", "_parsed_md_hash",
                   "selected_country_idx"]:
            if k in st.session_state:
                del st.session_state[k]
        st.session_state.step = "input"
        st.rerun()
