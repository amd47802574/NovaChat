"""NovaChat MCP 子包:客户端 + 服务端双向支持。

公开 API:
- `load_external_mcp_tools_sync`:同步加载外部 MCP Server 的工具(供 runtime.py 调用)
- `load_external_mcp_tools`:异步加载版本
- `load_mcp_config`:读取 mcp_config.json
- `create_mcp_server`:构造本地 FastMCP 实例(用于测试或自定义启动)
- `run_mcp_server`:启动本地 MCP Server (stdio)
"""
from backend.tools.mcp.client import (
    load_external_mcp_tools,
    load_external_mcp_tools_sync,
    load_mcp_config,
)
from backend.tools.mcp.server import SERVER_NAME, _create_mcp_server

__all__ = [
    "SERVER_NAME",
    "load_external_mcp_tools",
    "load_external_mcp_tools_sync",
    "load_mcp_config",
    "create_mcp_server",
    "run_mcp_server",
]


def create_mcp_server():
    """创建并返回配置好的 FastMCP 实例。"""
    return _create_mcp_server()


def run_mcp_server() -> None:
    """启动本地 MCP Server (stdio 传输)。"""
    from backend.tools.mcp.server import main

    main()
