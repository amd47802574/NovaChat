"""网络搜索工具

支持三种搜索后端（通过环境变量 WEB_SEARCH_API 切换）：
- firecrawl（默认，推荐）：使用 Firecrawl v2 搜索接口，需要 FIRECRAWL_API_KEY
- serper：使用 Serper API，需要 SERPER_API_KEY
- duckduckgo：使用 DuckDuckGo Instant Answer API，免费但结果有限
"""
import os
from typing import List

import requests

try:
    from langchain_core.tools import tool
except ImportError:
    from langchain_core.tools import tool

# ===== 搜索后端配置 =====
# 搜索引擎选择：firecrawl（默认）/ serper / duckduckgo
WEB_SEARCH_API = os.getenv("WEB_SEARCH_API", "firecrawl").lower()

# Firecrawl v2 配置
FIRECRAWL_API_URL = "https://api.firecrawl.dev/v2/search"
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")

# Serper 配置
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_API_URL = "https://google.serper.dev/search"

# 单次返回结果数上限，避免请求过大
MAX_RESULTS_LIMIT = 10
DEFAULT_RESULTS = 5


def search_firecrawl(query: str, num_results: int = DEFAULT_RESULTS) -> List[dict]:
    """使用 Firecrawl v2 搜索接口返回结果。

    响应结构形如：
        {"success": True, "data": {"web": [{"title", "url", "description"}, ...]}}
    """
    if not FIRECRAWL_API_KEY:
        raise Exception(
            "Firecrawl API 密钥未配置，请设置 FIRECRAWL_API_KEY 环境变量，"
            "或将 WEB_SEARCH_API 切换为 duckduckgo"
        )

    payload = {
        "query": query,
        "sources": ["web"],
        "categories": [],
        "limit": num_results,
        "scrapeOptions": {
            "onlyMainContent": True,
            "maxAge": 172800000,
            "parsers": ["pdf"],
            "formats": [],
        },
    }
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            FIRECRAWL_API_URL, json=payload, headers=headers, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        raise Exception("Firecrawl 搜索请求超时")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Firecrawl 搜索请求失败：{e}")
    except Exception as e:
        raise Exception(f"Firecrawl 搜索失败：{e}")

    if not data.get("success", False):
        raise Exception(f"Firecrawl 搜索失败：{data}")

    # data.data 形如 {"web": [{...}, ...]}，也可能直接是列表，做兼容处理
    raw = data.get("data", {})
    items: List[dict] = []
    if isinstance(raw, dict):
        for group_items in raw.values():
            if isinstance(group_items, list):
                items.extend(group_items)
    elif isinstance(raw, list):
        items = raw

    results: List[dict] = []
    for item in items[:num_results]:
        results.append(
            {
                "title": item.get("title", "") or "无标题",
                "link": item.get("url", "") or "",
                "snippet": item.get("description", "") or "",
            }
        )
    return results


def search_serper(query: str, num_results: int = DEFAULT_RESULTS) -> List[dict]:
    """使用 Serper API 返回结果（需要 API key）。"""
    if not SERPER_API_KEY:
        raise Exception("Serper API 密钥未配置，请设置 SERPER_API_KEY 环境变量")

    try:
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {"q": query, "num": num_results}
        response = requests.post(
            SERPER_API_URL, headers=headers, json=payload, timeout=10
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        raise Exception("Serper 搜索请求超时")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Serper 搜索请求失败：{e}")
    except Exception as e:
        raise Exception(f"Serper 搜索失败：{e}")

    results: List[dict] = []
    for item in data.get("organic", [])[:num_results]:
        results.append(
            {
                "title": item.get("title", "") or "无标题",
                "link": item.get("link", "") or "",
                "snippet": item.get("snippet", "") or "",
            }
        )
    return results


def search_duckduckgo(query: str, num_results: int = DEFAULT_RESULTS) -> List[dict]:
    """使用 DuckDuckGo Instant Answer API 返回结果（免费，但结果有限）。"""
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        raise Exception("DuckDuckGo 搜索请求超时")
    except requests.exceptions.RequestException as e:
        raise Exception(f"DuckDuckGo 搜索请求失败：{e}")
    except Exception as e:
        raise Exception(f"DuckDuckGo 搜索失败：{e}")

    results: List[dict] = []

    # 摘要结果
    if data.get("AbstractText"):
        results.append(
            {
                "title": data.get("Heading", "摘要"),
                "link": data.get("AbstractURL", ""),
                "snippet": data.get("AbstractText", ""),
            }
        )

    # 相关主题
    for topic in data.get("RelatedTopics", [])[: max(num_results - 1, 0)]:
        if isinstance(topic, dict) and "Text" in topic:
            text = topic.get("Text", "")
            results.append(
                {
                    "title": text.split(" - ")[0] if " - " in text else text,
                    "link": topic.get("FirstURL", ""),
                    "snippet": text,
                }
            )

    return results[:num_results]


@tool("web_search")
def web_search(query: str, num_results: int = DEFAULT_RESULTS) -> str:
    """搜索网络以获取关于任何主题的实时信息。

    当用户询问时事、实时信息或知识库中没有的主题时，使用此工具。

    关于 num_results 的重要说明：
    - 你必须从用户的提示中解析出用户想要的结果数量。
      例如，如果用户说"搜索 3 条关于 AI 的信息"或"给我前 8 条结果"，
      就将 num_results 相应地设置为 3 或 8。
    - 如果用户未指定数字，则将 num_results 保留为默认值 5。
    - num_results 必须在 1 到 10 之间。

    Args:
        query: 搜索查询字符串。不能为空。
        num_results: 返回的结果数量。默认值为 5，最大为 10。
            当用户在请求中指定数量时（例如"搜索3条"、"返回8条"、"top 3"），
            请据此解析；否则使用默认值 5。

    Returns:
        格式化的搜索结果，包含标题、摘要和链接。
    """
    try:
        # 参数校验
        if not query or not query.strip():
            return "错误：搜索关键词不能为空"

        num_results = min(max(1, int(num_results)), MAX_RESULTS_LIMIT)

        # 按配置选择搜索后端
        provider = WEB_SEARCH_API.lower()
        if provider == "serper":
            results = search_serper(query, num_results)
        elif provider == "duckduckgo":
            results = search_duckduckgo(query, num_results)
        else:
            results = search_firecrawl(query, num_results)

        if not results:
            return f"未找到与 '{query}' 相关的结果"

        # 格式化输出
        output_lines = [f"搜索结果：'{query}'（共 {len(results)} 条）\n"]
        output_lines.append("━━━━━━━━━━━━━━━━━━\n")

        for i, result in enumerate(results, 1):
            title = result.get("title", "无标题")
            snippet = result.get("snippet", "无摘要")
            link = result.get("link", "")

            if link:
                output_lines.append(f"{i}. [{title}]({link})")
            else:
                output_lines.append(f"{i}. {title}")
            output_lines.append(f"   {snippet}")
            output_lines.append("")

        output_lines.append(f"注：搜索来源：{WEB_SEARCH_API.upper()}")
        output_lines.append("搜索结果仅供参考，请验证信息准确性。")

        return "\n".join(output_lines)

    except Exception as e:
        return f"搜索失败：{str(e)}"
