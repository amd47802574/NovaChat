"""MCP 客户端:连接外部 MCP Server 并把其工具转为 LangChain 工具。

设计要点:
1. 读取项目根目录下的 `mcp_config.json`(格式兼容 Claude Desktop 配置):
   ```json
   {
     "mcpServers": {
       "filesystem": {
         "command": "npx",
         "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
         "env": {}
       }
     }
   }
   ```
2. 通过 `langchain-mcp-adapters` 的 `MultiServerMCPClient` 管理 stdio 连接。
3. 提供同步入口 `load_external_mcp_tools_sync()` 给 `runtime.py` 使用
   (LangChain 的 `create_agent` 是同步 API,需要把异步加载桥接到同步)。
4. 启动失败的外部 Server 会被跳过并记录警告,不影响主流程。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 默认配置文件位置:项目根目录下的 mcp_config.json
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "mcp_config.json"

# 是否启用 MCP 客户端(可通过环境变量 NOVACHAT_MCP_ENABLED=0 关闭)
ENV_ENABLED_FLAG = "NOVACHAT_MCP_ENABLED"


def _is_enabled() -> bool:
    """是否启用 MCP 客户端加载。"""
    return os.getenv(ENV_ENABLED_FLAG, "1").lower() not in ("0", "false", "no", "off")


def load_mcp_config(config_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """读取并校验 mcp_config.json。

    Args:
        config_path: 自定义配置路径,默认为项目根目录下的 `mcp_config.json`。

    Returns:
        `{server_name: server_config, ...}` 字典;无配置时返回空字典。
    """
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        logger.debug("MCP 配置文件不存在: %s", path)
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("解析 MCP 配置失败 (%s): %s", path, exc)
        return {}

    servers = raw.get("mcpServers") if isinstance(raw, dict) else None
    if not isinstance(servers, dict):
        logger.warning("MCP 配置缺少 `mcpServers` 字段: %s", path)
        return {}

    # 校验每个 server 必须包含 command (stdio 模式)
    cleaned: Dict[str, Dict[str, Any]] = {}
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        command = cfg.get("command")
        if not command:
            logger.warning("MCP server `%s` 缺少 command 字段,已跳过", name)
            continue
        cleaned[name] = {
            "transport": cfg.get("transport", "stdio"),
            "command": command,
            "args": cfg.get("args", []),
            "env": cfg.get("env"),
        }
    return cleaned


async def load_external_mcp_tools(
    config_path: Optional[Path] = None,
) -> List[Any]:
    """异步加载所有外部 MCP Server 的工具。

    Args:
        config_path: 自定义配置路径。

    Returns:
        LangChain BaseTool 列表(可能是空列表)。失败的 Server 会被跳过。
    """
    if not _is_enabled():
        logger.info("MCP 客户端已被 %s 关闭", ENV_ENABLED_FLAG)
        return []

    servers = load_mcp_config(config_path)
    if not servers:
        return []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as exc:  # pragma: no cover
        logger.warning("未安装 langchain-mcp-adapters,跳过 MCP 工具加载: %s", exc)
        return []

    # MultiServerMCPClient 期望的字典结构与我们 cleaned 的一致
    try:
        client = MultiServerMCPClient(servers)
        tools = await client.get_tools()
    except Exception as exc:
        logger.warning("加载 MCP 工具失败(将跳过外部工具): %s", exc)
        return []

    logger.info("从 %d 个 MCP server 加载到 %d 个工具",
                len(servers), len(tools))
    return list(tools)


def load_external_mcp_tools_sync(
    config_path: Optional[Path] = None,
) -> List[Any]:
    """同步包装:在当前事件循环中加载外部 MCP 工具。

    给 `create_agent_for_request` 等同步上下文使用。如果当前已有运行中的事件循环
    (例如在 async handler 内调用),会新建一个独立线程的事件循环执行,
    避免阻塞主循环。

    Args:
        config_path: 自定义配置路径。

    Returns:
        LangChain BaseTool 列表(失败返回空列表,不抛异常)。
    """
    if not _is_enabled():
        return []

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 没有运行中的事件循环,直接 asyncio.run
        try:
            return asyncio.run(load_external_mcp_tools(config_path))
        except Exception as exc:
            logger.warning("同步加载 MCP 工具失败: %s", exc)
            return []

    # 已在事件循环内:在新线程中跑一个独立循环,避免嵌套
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, load_external_mcp_tools(config_path))
        try:
            return future.result(timeout=30)
        except Exception as exc:
            logger.warning("线程中加载 MCP 工具超时或失败: %s", exc)
            return []
