"""
工具验证脚本（简化版）- 测试不依赖数据库的工具
运行方式：python test_tools_simple.py
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def test_tool(tool_name: str, test_func):
    """Test a tool and display results."""
    try:
        result = test_func()
        console.print(Panel(
            result,
            title=f"[bold green]✓ {tool_name}[/bold green]",
            border_style="green"
        ))
        return True
    except Exception as e:
        console.print(Panel(
            f"[red]错误：{str(e)}[/red]",
            title=f"[bold red]✗ {tool_name}[/bold red]",
            border_style="red"
        ))
        return False


def main():
    """Run tests for tools that don't require database."""
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]    NovaChat 工具验证测试（简化版）[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
    
    # Create results table
    results_table = Table(title="测试结果汇总", show_header=True, header_style="bold magenta")
    results_table.add_column("工具名称", style="cyan")
    results_table.add_column("测试状态", style="bold")
    
    test_results = []
    
    # Test 1: Current Time Tool
    console.print("\n[yellow]测试 1/4: 当前时间工具[/yellow]")
    def test_time():
        from backend.tools.datetime_tool import get_current_time
        return get_current_time("Asia/Shanghai")
    
    success = test_tool("get_current_time", test_time)
    test_results.append(("当前时间查询", success))
    
    # Test 2: Calculator Tool
    console.print("\n[yellow]测试 2/4: 数学计算工具[/yellow]")
    def test_calc():
        from backend.tools.calculator import calculate
        results = []
        test_cases = ["2 + 3 * 4", "sqrt(16)", "sin(pi/2)"]
        for expr in test_cases:
            results.append(calculate(expr))
        return "\n\n".join(results)
    
    success = test_tool("calculate", test_calc)
    test_results.append(("数学计算", success))
    
    # Test 3: Web Search Tool
    console.print("\n[yellow]测试 3/4: 网络搜索工具[/yellow]")
    console.print("[dim]注意：使用 DuckDuckGo API（无需密钥）[/dim]")
    def test_search():
        from backend.tools.web_search import web_search
        return web_search("Python编程", num_results=3)
    
    success = test_tool("web_search", test_search)
    test_results.append(("网络搜索", success))
    
    # Test 4: Text Analyzer Tool
    console.print("\n[yellow]测试 4/4: 文本分析工具[/yellow]")
    def test_text():
        from backend.tools.text_analyzer import analyze_text
        sample_text = "NovaChat是一个基于RAG的智能知识问答平台，支持混合检索和知识库管理。"
        result1 = analyze_text(sample_text, analysis_type="keywords", top_n=5)
        result2 = analyze_text("这是一个非常好的产品！", analysis_type="sentiment", use_llm=False)
        return f"{result1}\n\n{result2}"
    
    success = test_tool("analyze_text", test_text)
    test_results.append(("文本分析", success))
    
    # Display summary
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
    
    for tool_name, success in test_results:
        status = "[green]✓ 通过[/green]" if success else "[red]✗ 失败[/red]"
        results_table.add_row(tool_name, status)
    
    console.print(results_table)
    
    # Summary statistics
    passed = sum(1 for _, success in test_results if success)
    total = len(test_results)
    
    console.print(f"\n[bold]测试完成：{passed}/{total} 个工具通过测试[/bold]")
    
    if passed == total:
        console.print("[bold green]🎉 所有工具测试通过！[/bold green]")
    else:
        console.print(f"[bold yellow]⚠ {total - passed} 个工具测试失败[/bold yellow]")
    
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
    
    # Additional info
    console.print(Panel(
        "[bold]未测试的工具：[/bold]\n\n"
        "• 文档列表查询工具（需要数据库连接）\n"
        "• 会话历史统计工具（需要数据库连接）\n\n"
        "[bold]完整测试方法：[/bold]\n\n"
        "1. 确保数据库服务已启动（PostgreSQL + Redis）\n"
        "2. 安装依赖：pip install psycopg2-binary redis\n"
        "3. 配置 .env 文件（参考 .env.example）\n"
        "4. 运行完整测试：python test_tools.py",
        title="[bold yellow]说明[/bold yellow]",
        border_style="yellow"
    ))


if __name__ == "__main__":
    main()