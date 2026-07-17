"""网络搜索工具"""
import os
import json
from typing import Optional
import requests

try:
    from langchain_core.tools import tool
except ImportError:
    from langchain_core.tools import tool

# Search API configuration
WEB_SEARCH_API = os.getenv("WEB_SEARCH_API", "duckduckgo")  # duckduckgo or serper
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_API_URL = "https://google.serper.dev/search"


def search_duckduckgo(query: str, num_results: int = 5) -> list:
    """
    Search using DuckDuckGo Instant Answer API (no API key required).
    Note: This provides limited results compared to paid services.
    """
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        
        # Get abstract
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", "摘要"),
                "link": data.get("AbstractURL", ""),
                "snippet": data.get("AbstractText", "")
            })
        
        # Get related topics
        for topic in data.get("RelatedTopics", [])[:num_results-1]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append({
                    "title": topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else topic.get("Text", ""),
                    "link": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", "")
                })
        
        return results[:num_results]
        
    except Exception as e:
        raise Exception(f"DuckDuckGo 搜索失败：{str(e)}")


def search_serper(query: str, num_results: int = 5) -> list:
    """Search using Serper API (requires API key)."""
    if not SERPER_API_KEY:
        raise Exception("Serper API 密钥未配置，请设置 SERPER_API_KEY 环境变量")
    
    try:
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "q": query,
            "num": num_results
        }
        
        response = requests.post(
            SERPER_API_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        results = []
        
        # Extract organic results
        for item in data.get("organic", [])[:num_results]:
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", "")
            })
        
        return results
        
    except Exception as e:
        raise Exception(f"Serper 搜索失败：{str(e)}")


@tool("web_search")
def web_search(query: str, num_results: int = 5) -> str:
    """
    Search the web for real-time information.
    Supports DuckDuckGo (free, no API key) or Serper (requires API key).
    Use this tool when users ask about current events, real-time information, or topics not in the knowledge base.
    
    Args:
        query: Search query string.
        num_results: Number of results to return (default: 5, max: 10).
    
    Returns:
        Formatted search results with titles, snippets, and links.
    """
    try:
        # Validate inputs
        if not query or not query.strip():
            return "错误：搜索关键词不能为空"
        
        num_results = min(max(1, num_results), 10)  # Clamp between 1 and 10
        
        # Perform search based on configured API
        if WEB_SEARCH_API.lower() == "serper":
            results = search_serper(query, num_results)
        else:
            results = search_duckduckgo(query, num_results)
        
        if not results:
            return f"未找到与 '{query}' 相关的结果"
        
        # Format output
        output_lines = [f"搜索结果：'{query}'（共 {len(results)} 条）\n"]
        output_lines.append("━━━━━━━━━━━━━━━━━━\n")
        
        for i, result in enumerate(results, 1):
            title = result.get("title", "无标题")
            snippet = result.get("snippet", "无摘要")
            link = result.get("link", "")
            
            output_lines.append(f"{i}. {title}")
            output_lines.append(f"   {snippet}")
            if link:
                output_lines.append(f"   链接：{link}")
            output_lines.append("")
        
        output_lines.append(f"注：搜索来源：{WEB_SEARCH_API.upper()}")
        output_lines.append("搜索结果仅供参考，请验证信息准确性。")
        
        return "\n".join(output_lines)
        
    except Exception as e:
        return f"搜索失败：{str(e)}"