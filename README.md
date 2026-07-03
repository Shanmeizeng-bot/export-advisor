# 出口目的国智能推荐系统

基于 **RPA + MCP + AI** 三层自动化的企业出口决策助手，帮助中小外贸企业科学选择目标市场。

## 功能

输入产品描述和企业信息，系统自动完成：
- AI 语义理解 → 匹配 HS 编码
- RPA 从 UN Comtrade 实时抓取 55 国贸易数据
- 7 维度算法评分（市场规模/增长/质量/关税/竞争/合规/便利）
- AI 大模型生成个性化出口策略报告

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key
# 注册地址: https://platform.deepseek.com/api_keys

# 3. 启动
streamlit run app.py
```

## 项目结构

```
├── app.py                      # Streamlit 主应用
├── mcp_server.py               # MCP Server (AI Agent 集成)
├── rpa/
│   └── comtrade_fetcher.py     # RPA 数据采集层 (UN Comtrade API)
├── tools/
│   ├── country_recommend.py    # 7维度评分引擎
│   ├── llm_analyst.py          # LLM 分析引擎 (DeepSeek)
│   └── ai_analyst.py           # 规则引擎 (LLM 回退)
└── data/                       # JSON 知识库
    ├── hs_products.json        # HS 编码库
    ├── tariff_schedules.json   # FTA 关税减让表
    ├── origin_rules.json       # 原产地规则
    ├── trade_shows.json        # 国际展会库
    ├── b2b_platforms.json      # B2B/电商平台库
    └── references.json         # 参考链接
```

## 技术架构

```
用户输入 → AI语义理解(HS匹配) → RPA数据采集(55国) → 7维度算法评分 → AI策略生成 → 结果展示
```

- **RPA 层**: Python 自动抓取 UN Comtrade 实时贸易数据
- **MCP 层**: 将关税查询/原产地规则/多维度评分封装为标准 Tool
- **AI 层**: DeepSeek 大模型基于结构化数据生成个性化出口策略

## 数据来源

- 贸易数据: [UN Comtrade Public Preview API](https://comtradeplus.un.org/)
- FTA 关税: 中国自由贸易区服务网 (fta.mofcom.gov.cn)
- 国家画像: 世界银行、IMF、WTO 等公开数据

## 作者

邓丽洒 · 曾善美
