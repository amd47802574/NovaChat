"""将现有 LangChain @tool 函数适配为符合 MCP 协议的标准工具。

本模块提供两类适配:
1. `langchain_tool_to_mcp_callable` —— 把 LangChain `@tool` 函数转换为可注册到 FastMCP 的纯函数,
   并根据 LangChain 工具的 `args_schema` (pydantic) 自动生成 MCP 工具的输入 JSON Schema。
2. `build_mcp_tools_from_langchain` —— 批量适配一组 LangChain 工具,返回 [(name, callable, schema)] 列表,
   供 `server.py` 注册到 FastMCP 实例。

注意:
- 需要请求上下文 (ChatRequestContext) 的工厂类工具 (如 `make_search_knowledge_base`)
  不应在 MCP Server 模式下暴露,因为 MCP Server 通常作为独立子进程运行,
  无法访问主进程的请求上下文。此类工具请通过 `exclude_names` 排除。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from langchain_core.tools import BaseTool
except ImportError as exc:  # pragma: no cover - 环境缺失保护
    raise ImportError(
        "需要 langchain-core 才能适配工具,请先执行 `uv sync` 安装依赖"
    ) from exc


def _pydantic_schema_to_json(schema_model: Any) -> Dict[str, Any]:
    """把 LangChain 工具的 args_schema (pydantic v2) 转为 JSON Schema 字典。

    LangChain 的 `@tool` 装饰器会根据函数签名自动生成一个 pydantic 模型,
    我们借助它的 `model_json_schema()` 方法得到标准 JSON Schema,
    再精简掉 pydantic 内部字段以符合 MCP 协议的工具输入 schema 规范。
    """
    if schema_model is None:
        return {"type": "object", "properties": {}}

    # pydantic v2
    if hasattr(schema_model, "model_json_schema"):
        raw = schema_model.model_json_schema()
    # pydantic v1 兼容
    elif hasattr(schema_model, "schema"):
        raw = schema_model.schema()
    else:
        return {"type": "object", "properties": {}}

    # 移除 pydantic 内部扩展字段,MCP 协议只关心标准 JSON Schema
    cleaned: Dict[str, Any] = {}
    for key, value in raw.items():
        if key in ("title", "definitions", "$defs"):
            continue
        cleaned[key] = value

    # 处理 $defs 引用(把 definitions 内联展开过于复杂,这里保留 $defs 兼容大多数客户端)
    if "$defs" in raw and "$defs" not in cleaned:
        cleaned["$defs"] = raw["$defs"]

    return cleaned or {"type": "object", "properties": {}}


def langchain_tool_to_mcp_callable(tool: BaseTool) -> Tuple[str, Callable, Dict[str, Any]]:
    """把单个 LangChain 工具转换为 (name, callable, input_schema) 三元组。

    返回的 callable 保持同步签名(FastMCP 同时支持同步与异步工具)。
    StructuredTool 会直接暴露原始 func/coroutine，避免在 MCP 执行器中嵌套 LangChain 运行时。

    Args:
        tool: 已实例化的 LangChain BaseTool 对象。

    Returns:
        (工具名, 可调用包装函数, 输入 JSON Schema)
    """
    if not isinstance(tool, BaseTool):
        raise TypeError(f"期望 LangChain BaseTool,收到 {type(tool).__name__}")

    name = tool.name
    description = tool.description or f"MCP-exposed tool: {name}"
    input_schema = _pydantic_schema_to_json(getattr(tool, "args_schema", None))

    source_callable = getattr(tool, "coroutine", None) or getattr(tool, "func", None)
    if source_callable is not None:
        return name, source_callable, input_schema

    def _mcp_callable(**kwargs: Any) -> Any:
        return tool.invoke(kwargs)

    _mcp_callable.__name__ = name
    _mcp_callable.__doc__ = description
    return name, _mcp_callable, input_schema


def build_mcp_tools_from_langchain(
    tools: List[BaseTool],
    *,
    exclude_names: Optional[List[str]] = None,
) -> List[Tuple[str, Callable, Dict[str, Any]]]:
    """批量把 LangChain 工具适配为 MCP 工具描述。

    Args:
        tools: LangChain 工具列表。
        exclude_names: 需要排除的工具名列表(例如依赖请求上下文的工具)。

    Returns:
        [(name, callable, input_schema), ...] 列表,可直接用于注册到 FastMCP。
    """
    exclude_set = set(exclude_names or [])
    adapted: List[Tuple[str, Callable, Dict[str, Any]]] = []

    for tool in tools:
        if not isinstance(tool, BaseTool):
            continue
        if tool.name in exclude_set:
            continue
        adapted.append(langchain_tool_to_mcp_callable(tool))

    return adapted
