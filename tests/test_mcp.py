"""
NovaChat MCP 集成验证测试

验证内容:
1. `adapters.py` 能正确把 LangChain @tool 函数转换为 (name, callable, schema) 三元组
2. `client.py` 能正确解析 mcp_config.json 并处理空/缺失/非法配置
3. `server.py` 能正确创建 FastMCP 实例并注册本地工具
4. NOVACHAT_MCP_ENABLED 环境变量能正确开关 MCP 客户端

运行方式:
    python tests/test_mcp.py
    # 或
    pytest tests/test_mcp.py -v
"""
from __future__ import annotations

import inspect
import json
import os
import sys
from pathlib import Path

# 把项目根目录加入 sys.path,便于直接运行
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


# ------------------------------------------------------------------
# 测试 1: adapters.py - LangChain 工具转 MCP 工具描述
# ------------------------------------------------------------------
def test_adapters_basic():
    """验证 adapters 能把 calculate 工具正确转换为 MCP 三元组。"""
    from backend.tools.calculator import calculate
    from backend.tools.mcp.adapters import (
        build_mcp_tools_from_langchain,
        langchain_tool_to_mcp_callable,
    )

    console.print("\n[yellow]测试 1a: 单个工具转换[/yellow]")
    name, fn, schema = langchain_tool_to_mcp_callable(calculate)
    assert name == "calculate", f"工具名应为 calculate,实际为 {name}"
    assert callable(fn), "返回的应是可调用对象"
    assert isinstance(schema, dict), "schema 应为字典"
    assert schema.get("type") == "object" or "properties" in schema, \
        f"schema 应为对象类型,实际: {schema}"
    assert str(inspect.signature(fn)) == "(expression: str) -> str"
    assert fn is calculate.func, "StructuredTool 应直接暴露原始函数，避免嵌套 invoke"
    assert fn(expression="1 + 2").endswith("= 3")
    console.print(f"  ✓ 工具名: {name}")
    console.print(f"  ✓ 输入 schema 键: {list(schema.keys())}")

    console.print("\n[yellow]测试 1b: 批量转换 + exclude_names[/yellow]")
    from backend.tools import (
        calculate, get_current_time, web_search,
    )
    adapted = build_mcp_tools_from_langchain(
        [calculate, get_current_time, web_search],
        exclude_names=["web_search"],
    )
    names = [n for n, _, _ in adapted]
    assert "calculate" in names
    assert "get_current_time" in names
    assert "web_search" not in names, "web_search 应被排除"
    console.print(f"  ✓ 已适配工具: {names}")
    console.print(f"  ✓ web_search 已正确排除")


# ------------------------------------------------------------------
# 测试 2: client.py - 配置文件解析
# ------------------------------------------------------------------
def test_client_config_parsing(tmp_path: Path):
    """验证 mcp_config.json 的解析逻辑(包括缺字段、空文件、非法 JSON)。"""
    from backend.tools.mcp.client import load_mcp_config

    # 2a: 正常配置
    console.print("\n[yellow]测试 2a: 正常配置解析[/yellow]")
    cfg = tmp_path / "good.json"
    cfg.write_text(json.dumps({
        "mcpServers": {
            "fs": {"command": "npx", "args": ["-y", "fs-server"]},
            "calc": {"command": "python", "args": ["-m", "backend.tools.mcp.server"]},
        }
    }), encoding="utf-8")
    servers = load_mcp_config(cfg)
    assert set(servers.keys()) == {"fs", "calc"}, f"解析结果错误: {servers}"
    assert servers["fs"]["command"] == "npx"
    assert servers["calc"]["command"] == sys.executable
    assert servers["calc"]["cwd"] == str(PROJECT_ROOT)
    assert servers["calc"]["encoding"] == "utf-8"
    assert servers["calc"]["env"]["PYTHONUTF8"] == "1"
    assert servers["calc"]["env"]["PYTHONIOENCODING"] == "utf-8"
    console.print(f"  ✓ 解析到 {len(servers)} 个 server: {list(servers.keys())}")

    # 2b: 缺少 command 字段的条目应被跳过
    console.print("\n[yellow]测试 2b: 缺 command 字段的条目跳过[/yellow]")
    cfg = tmp_path / "bad.json"
    cfg.write_text(json.dumps({
        "mcpServers": {
            "good": {"command": "npx"},
            "bad": {"args": ["only-args"]},
            "_comment": "this is a string, should be skipped",
        }
    }), encoding="utf-8")
    servers = load_mcp_config(cfg)
    assert "good" in servers
    assert "bad" not in servers, "缺 command 的条目应被跳过"
    assert "_comment" not in servers, "非 dict 条目应被跳过"
    console.print(f"  ✓ 解析结果: {list(servers.keys())}")

    # 2c: 文件不存在 / 空配置
    console.print("\n[yellow]测试 2c: 文件不存在时返回空字典[/yellow]")
    servers = load_mcp_config(tmp_path / "not-exist.json")
    assert servers == {}
    console.print("  ✓ 文件不存在时返回空字典")

    # 2d: 非法 JSON
    console.print("\n[yellow]测试 2d: 非法 JSON 返回空字典[/yellow]")
    cfg = tmp_path / "invalid.json"
    cfg.write_text("{not valid json", encoding="utf-8")
    servers = load_mcp_config(cfg)
    assert servers == {}
    console.print("  ✓ 非法 JSON 返回空字典")


# ------------------------------------------------------------------
# 测试 3: server.py - 创建 FastMCP 实例
# ------------------------------------------------------------------
def test_server_creation():
    """验证能创建 FastMCP 实例并注册本地工具。"""
    console.print("\n[yellow]测试 3: 创建 MCP Server 并注册工具[/yellow]")
    try:
        from backend.tools.mcp.server import _create_mcp_server
    except ImportError as exc:
        console.print(f"  [red]✗ 跳过:未安装 mcp SDK ({exc})[/red]")
        return False

    mcp = _create_mcp_server()
    # 兼容新旧版 mcp SDK:
    # - 新版 MCPServer 提供 list_tools() (异步)
    # - 旧版 FastMCP 通过 _tool_manager._tools 暴露
    import asyncio

    async def _get_tool_names() -> list:
        # 新版 MCPServer.list_tools() 返回 Tool 对象列表
        if hasattr(mcp, "list_tools"):
            try:
                tools = await mcp.list_tools()
                return [t.name for t in tools]
            except Exception:
                pass
        # 旧版回退
        tm = getattr(mcp, "_tool_manager", None)
        if tm is not None and hasattr(tm, "_tools"):
            return list(tm._tools.keys())
        return []

    try:
        registered = asyncio.run(_get_tool_names())
    except Exception as exc:
        console.print(f"  [red]✗ 无法获取已注册工具列表: {exc}[/red]")
        return False

    expected = [
        "get_current_weather", "list_documents", "get_current_time",
        "calculate", "web_search", "analyze_text",
    ]
    missing = [t for t in expected if t not in registered]
    if missing:
        console.print(f"  [red]✗ 缺少工具: {missing}[/red]")
        console.print(f"  实际注册: {registered}")
        return False

    # 依赖请求上下文(当前会话作用域)的工具应被排除
    assert "search_knowledge_base" not in registered, "search_knowledge_base 不应在 MCP Server 中暴露"
    assert "analyze_conversation_history" not in registered, "analyze_conversation_history 依赖当前会话上下文,不应在 MCP Server 中暴露"
    console.print(f"  ✓ 已注册 {len(registered)} 个工具: {registered}")
    console.print("  ✓ search_knowledge_base 已正确排除")
    return True


# ------------------------------------------------------------------
# 测试 4: NOVACHAT_MCP_ENABLED 开关
# ------------------------------------------------------------------
def test_env_flag(monkeypatch_os_environ):
    """验证 NOVACHAT_MCP_ENABLED=0 时,同步加载返回空列表。"""
    console.print("\n[yellow]测试 4: 环境变量开关[/yellow]")
    from backend.tools.mcp.client import load_external_mcp_tools_sync

    # 保存原值
    original = os.environ.get("NOVACHAT_MCP_ENABLED")
    try:
        os.environ["NOVACHAT_MCP_ENABLED"] = "0"
        tools = load_external_mcp_tools_sync()
        assert tools == [], f"关闭后应返回空列表,实际: {tools}"
        console.print("  ✓ NOVACHAT_MCP_ENABLED=0 时返回空列表")

        os.environ["NOVACHAT_MCP_ENABLED"] = "1"
        # 即使开启,没有 mcp_config.json 也应返回空
        # (项目根目录可能没有 mcp_config.json,这种情况下也返回空)
        tools = load_external_mcp_tools_sync()
        assert isinstance(tools, list), "返回值应为列表"
        console.print(f"  ✓ NOVACHAT_MCP_ENABLED=1 时正常执行(返回 {len(tools)} 个工具)")
    finally:
        if original is None:
            os.environ.pop("NOVACHAT_MCP_ENABLED", None)
        else:
            os.environ["NOVACHAT_MCP_ENABLED"] = original


# ------------------------------------------------------------------
# pytest fixture 兼容(允许不装 pytest 也能跑)
# ------------------------------------------------------------------
def monkeypatch_os_environ():
    """no-op fixture,避免直接运行脚本时 pytest 报错。"""
    return None


# ------------------------------------------------------------------
# 主入口
# ------------------------------------------------------------------
def main():
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]    NovaChat MCP 集成验证测试[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]")

    results = []

    # 测试 1
    try:
        test_adapters_basic()
        results.append(("adapters - 工具转换", True))
    except Exception as exc:
        console.print(f"  [red]✗ 失败: {exc}[/red]")
        results.append(("adapters - 工具转换", False))

    # 测试 2
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            test_client_config_parsing(Path(td))
        results.append(("client - 配置解析", True))
    except Exception as exc:
        console.print(f"  [red]✗ 失败: {exc}[/red]")
        results.append(("client - 配置解析", False))

    # 测试 3
    try:
        ok = test_server_creation()
        results.append(("server - 创建实例", ok))
    except Exception as exc:
        console.print(f"  [red]✗ 失败: {exc}[/red]")
        results.append(("server - 创建实例", False))

    # 测试 4
    try:
        test_env_flag(None)
        results.append(("client - 环境变量开关", True))
    except Exception as exc:
        console.print(f"  [red]✗ 失败: {exc}[/red]")
        results.append(("client - 环境变量开关", False))

    # 汇总
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
    table = Table(title="测试结果汇总", show_header=True, header_style="bold magenta")
    table.add_column("测试项", style="cyan")
    table.add_column("状态", style="bold")
    for name, ok in results:
        table.add_row(name, "[green]✓ 通过[/green]" if ok else "[red]✗ 失败[/red]")
    console.print(table)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    console.print(f"\n[bold]通过 {passed}/{total} 项[/bold]\n")


if __name__ == "__main__":
    main()
