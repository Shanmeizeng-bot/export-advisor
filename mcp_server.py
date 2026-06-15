"""MCP Server: 出口目的国智能推荐 Agent

Tools:
  - fetch_trade_data: 从UN Comtrade实时抓取贸易数据 (RPA)
  - analyze_market: 分析单个市场的规模/增长/竞争
  - recommend_countries: 综合推荐Top-N出口目的国 (核心)
"""

import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from rpa.comtrade_fetcher import fetch_all, TARGET_COUNTRIES
from tools.country_recommend import recommend_countries

server = Server("export-advisor")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="fetch_trade_data",
            description="RPA自动化: 从UN Comtrade实时抓取产品在全球各国的进口/出口数据, 包括进口额、增速、中国市场份额",
            inputSchema={
                "type": "object",
                "properties": {
                    "hs_code": {
                        "type": "string",
                        "description": "HS编码前6位, 如 '851830' (耳机)",
                    },
                    "year": {
                        "type": "integer",
                        "description": "数据年份, 默认2023",
                        "default": 2023,
                    },
                },
                "required": ["hs_code"],
            },
        ),
        Tool(
            name="analyze_market",
            description="深入分析单个目标市场: 市场规模、增长趋势、中国产品竞争力、关税分析",
            inputSchema={
                "type": "object",
                "properties": {
                    "country_iso": {
                        "type": "string",
                        "description": "国家ISO代码, 如 'USA', 'JPN', 'VNM'",
                    },
                    "hs_code": {
                        "type": "string",
                        "description": "HS编码",
                    },
                },
                "required": ["country_iso", "hs_code"],
            },
        ),
        Tool(
            name="recommend_countries",
            description="核心工具: 综合6个维度(市场规模/增长/关税/竞争/合规/准入)推荐最优出口目的国Top-N",
            inputSchema={
                "type": "object",
                "properties": {
                    "hs_code": {
                        "type": "string",
                        "description": "产品HS编码前6位",
                    },
                    "product_category": {
                        "type": "string",
                        "description": "产品类别, 如 '消费电子', '纺织服装'",
                    },
                    "company_scale": {
                        "type": "string",
                        "description": "企业规模: '中小企业' / '大型企业'",
                        "default": "中小企业",
                    },
                    "year": {
                        "type": "integer",
                        "description": "贸易数据年份",
                        "default": 2023,
                    },
                },
                "required": ["hs_code"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "fetch_trade_data":
        hs = arguments["hs_code"]
        year = arguments.get("year", 2023)
        data = fetch_all(hs, year)
        # 精简输出, 只返回摘要
        summary = {
            "hs_code": hs,
            "year": year,
            "countries_with_data": sum(
                1 for c in data["countries"].values() if c.get("import_value_usd")
            ),
            "top_importers": sorted(
                [
                    {"country": iso, "name": c["name"], "import_usd": c["import_value_usd"]}
                    for iso, c in data["countries"].items()
                    if c.get("import_value_usd")
                ],
                key=lambda x: x["import_usd"] or 0,
                reverse=True,
            )[:5],
            "data_source": data["data_source"],
        }
        return [TextContent(type="text", text=json.dumps(summary, ensure_ascii=False, indent=2))]

    elif name == "analyze_market":
        hs = arguments["hs_code"]
        iso = arguments["country_iso"].upper()
        data = fetch_all(hs)
        country = data["countries"].get(iso, {})
        result = {
            "country": iso,
            "name": country.get("name", ""),
            "import_value_usd": country.get("import_value_usd"),
            "import_growth_pct": country.get("import_growth_pct"),
            "china_market_share_pct": country.get("china_market_share"),
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "recommend_countries":
        hs = arguments["hs_code"]
        category = arguments.get("product_category", "")
        scale = arguments.get("company_scale", "中小企业")
        year = arguments.get("year", 2023)

        trade_data = fetch_all(hs, year)
        result = recommend_countries(trade_data, hs, category, scale)

        # 精简输出 Top 5
        top5 = []
        for r in result["rankings"][:5]:
            top5.append({
                "rank": result["rankings"].index(r) + 1,
                "country": r["name"],
                "region": r["region"],
                "total_score": r["total_score"],
                "scores": r["scores"],
                "key_reason": r["details"]["notes"][:60],
            })

        output = {
            "product": result["product_name"],
            "hs_code": result["hs_code"],
            "analyzed_countries": result["total_countries_analyzed"],
            "data_source": result["data_source"],
            "fetch_time": result["fetch_timestamp"],
            "top_recommendations": top5,
        }
        return [TextContent(type="text", text=json.dumps(output, ensure_ascii=False, indent=2))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
