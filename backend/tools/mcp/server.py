"""NovaChat 本地工具的 MCP Server 入口。

通过 FastMCP / MCPServer 将 backend/tools/ 下的现有工具暴露为符合 MCP 协议的标准工具,
可被任意 MCP 客户端(Claude Desktop、其他 Agent、外部进程)通过 stdio 调用。

启动方式:
    # 作为子进程被 MCP 客户端拉起(推荐)
    python -m backend.tools.mcp.server

    # 或直接运行
    python backend/tools/mcp/server.py

设计说明:
- `make_search_knowledge_base` 等依赖 ChatRequestContext 的工厂类工具不在此处暴露,
  因为 MCP Server 作为独立子进程运行,无法访问主进程的请求级上下文。
- 其余 7 个纯函数工具(get_current_weather / list_documents / get_current_time /
  calculate / analyze_conversation_history / web_search / analyze_text)均会注册到 MCP Server。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Tuple

# 兼容新旧版本 mcp SDK:
# - 新版(>=1.6): `from mcp.server import MCPServer`
# - 旧版(<1.6): `from mcp.server.fastmcp import FastMCP`
try:
    from mcp.server import MCPServer as _McpServer  # type: ignore
except ImportError:  # pragma: no cover - 老版本回退
    try:
        from mcp.server.fastmcp import FastMCP as _McpServer  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "需要 mcp SDK,请先执行 `uv sync` 或 `pip install mcp` 安装依赖"
        ) from exc

from backend.tools import (
    analyze_conversation_history,
    analyze_text,
    calculate,
    get_current_time,
    get_current_weather,
    list_documents,
    web_search,
)
from backend.tools.mcp.adapters import build_mcp_tools_from_langchain

logger = logging.getLogger(__name__)

# 服务端暴露的工具名,与 make_search_knowledge_base 区分开
SERVER_NAME = "NovaChat-Tools"

# 依赖请求上下文的工具,不在 MCP Server 模式下暴露
EXCLUDED_TOOL_NAMES: List[str] = [
    "search_knowledge_base",
]


def _create_mcp_server() -> _McpServer:
    """创建并配置 MCPServer / FastMCP 实例,把本地工具注册进去。"""
    mcp = _McpServer(SERVER_NAME)

    # 收集要暴露的本地 LangChain 工具
    local_tools = [
        get_current_weather,
        list_documents,
        get_current_time,
        calculate,
        analyze_conversation_history,
        web_search,
        analyze_text,
    ]

    adapted: List[Tuple[str, Callable, Dict[str, Any]]] = build_mcp_tools_from_langchain(
        local_tools, exclude_names=EXCLUDED_TOOL_NAMES
    )

    registered_names: List[str] = []
    for name, callable_fn, _schema in adapted:
        # MCPServer.add_tool 与 FastMCP.add_tool 签名兼容:
        #   add_tool(fn, name=None, description=None, ...)
        mcp.add_tool(
            fn=callable_fn,
            name=name,
            description=callable_fn.__doc__ or f"MCP tool: {name}",
        )
        registered_names.append(name)
        logger.debug("已注册 MCP 工具: %s", name)

    logger.info("MCP Server 已注册工具: %s", registered_names)
    return mcp


def main() -> None:
    """MCP Server 启动入口,使用 stdio 传输协议。"""
    logging.basicConfig(level=logging.INFO)
    mcp = _create_mcp_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
