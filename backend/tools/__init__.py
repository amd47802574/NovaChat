"""LangChain Agent 可调用的工具（@tool 装饰的函数）。"""

from backend.env import load_env

# MCP Server 可独立启动，导入工具前必须主动加载项目环境变量。
load_env()

from backend.tools.knowledge import make_search_knowledge_base
from backend.tools.weather import get_current_weather_tool as get_current_weather
from backend.tools.documents import list_documents
from backend.tools.datetime_tool import get_current_time
from backend.tools.calculator import calculate
from backend.tools.session_analyzer import make_analyze_conversation_history
from backend.tools.web_search import web_search
from backend.tools.text_analyzer import analyze_text

# MCP 子包公共 API(懒加载,避免在没有安装 mcp SDK 的环境下整体导入失败)
from backend.tools.mcp import (
    load_external_mcp_tools,
    load_external_mcp_tools_sync,
    load_mcp_config,
)

__all__ = [
    "get_current_weather",
    "make_search_knowledge_base",
    "list_documents",
    "get_current_time",
    "calculate",
    "make_analyze_conversation_history",
    "web_search",
    "analyze_text",
    # MCP 相关
    "load_external_mcp_tools",
    "load_external_mcp_tools_sync",
    "load_mcp_config",
]

