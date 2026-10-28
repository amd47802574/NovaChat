"""
工具验证脚本 - 测试所有新增的工具功能
运行方式：python test_tools.py
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Import tools
from backend.tools.documents import list_documents
from backend.tools.datetime_tool import get_current_time
from backend.tools.calculator import calculate
from backend.tools.session_analyzer import make_analyze_conversation_history
from backend.tools.web_search import web_search
from backend.tools.text_analyzer import analyze_text
from backend.chat.request_context import ChatRequestContext

console = Console()


def test_tool(tool_name: str, tool_func, *args, **kwargs):
    """Test a tool and display results."""
    try:
        result = tool_func(*args, **kwargs)
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
    """Run all tool tests."""
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]    NovaChat 工具验证测试[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
    
    # Create results table
    results_table = Table(title="测试结果汇总", show_header=True, header_style="bold magenta")
    results_table.add_column("工具名称", style="cyan")
    results_table.add_column("测试状态", style="bold")
    
    test_results = []
    
    # Test 1: Document List Tool
    console.print("\n[yellow]测试 1/6: 文档列表查询工具[/yellow]")
    success = test_tool("list_documents", list_documents, detailed=False)
    test_results.append(("文档列表查询", success))
    
    # Test 2: Current Time Tool
    console.print("\n[yellow]测试 2/6: 当前时间工具[/yellow]")
    success = test_tool("get_current_time", get_current_time, timezone="Asia/Shanghai")
    test_results.append(("当前时间查询", success))
    
    # Test 3: Calculator Tool
    console.print("\n[yellow]测试 3/6: 数学计算工具[/yellow]")
    test_cases = [
        ("简单计算", "2 + 3 * 4"),
        ("数学函数", "sqrt(16)"),
        ("复杂表达式", "sin(pi/2) + cos(0)"),
    ]
    
    calc_success = True
    for name, expression in test_cases:
        console.print(f"\n[dim]{name}：{expression}[/dim]")
        success = test_tool(f"calculate({expression})", calculate, expression)
        if not success:
            calc_success = False
    test_results.append(("数学计算", calc_success))
    
    # Test 4: Session Analyzer Tool
    console.print("\n[yellow]测试 4/6: 会话历史统计工具[/yellow]")
    # 该工具已改为「绑定当前会话作用域」的工厂,需要传入每请求上下文。
    analyze_tool = make_analyze_conversation_history(
        ChatRequestContext.for_sync(user_id="test_user", session_id="test-session")
    )
    success = test_tool("analyze_conversation_history", analyze_tool,
                       analysis_type="summary", limit=10)
    test_results.append(("会话历史统计", success))
    
    # Test 5: Web Search Tool
    console.print("\n[yellow]测试 5/6: 网络搜索工具[/yellow]")
    console.print("[dim]注意：如果未配置 SERPER_API_KEY，将使用 DuckDuckGo（可能返回有限结果）[/dim]")
    success = test_tool("web_search", web_search, query="Python编程", num_results=3)
    test_results.append(("网络搜索", success))
    
    # Test 6: Text Analyzer Tool
    console.print("\n[yellow]测试 6/6: 文本分析工具[/yellow]")
    sample_text = """
    NovaChat是一个基于RAG的智能知识问答平台，支持混合检索、结果重排、来源引用、多轮会话与知识库管理。
    该系统采用前后端分离架构，后端使用FastAPI框架，前端使用Vue 3 + TypeScript。
    系统支持PDF、Word、Excel等多种文档格式的解析和向量化处理。
    """
    
    # Test keywords extraction
    success_keywords = test_tool("analyze_text (keywords)", analyze_text, 
                                text=sample_text, analysis_type="keywords", top_n=5)
    
    # Test sentiment analysis (without LLM)
    success_sentiment = test_tool("analyze_text (sentiment)", analyze_text,
                                  text="这是一个非常好的产品，我非常喜欢！",
                                  analysis_type="sentiment", use_llm=False)
    
    test_results.append(("文本分析", success_keywords and success_sentiment))
    
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
        console.print(f"[bold yellow]⚠ {total - passed} 个工具测试失败，请检查配置或代码[/bold yellow]")
    
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
    
    # Additional info
    console.print(Panel(
        "[bold]提示：[/bold]\n\n"
        "1. 文档列表工具需要先上传文档才能显示内容\n"
        "2. 会话历史工具需要有历史对话记录\n"
        "3. 网络搜索工具推荐配置 SERPER_API_KEY（见 .env.example）\n"
        "4. 文本分析工具的高级功能（use_llm=True）需要配置模型API\n"
        "5. 当前时间工具如需支持更多时区，请安装 pytz：pip install pytz",
        title="[bold yellow]使用提示[/bold yellow]",
        border_style="yellow"
    ))


if __name__ == "__main__":
    main()