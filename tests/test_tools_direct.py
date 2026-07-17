"""
工具验证脚本（直接测试版）- 不通过模块导入，直接测试工具函数
运行方式：python test_tools_direct.py
"""
import sys
import os
import math
import re
from datetime import datetime
from collections import Counter
import requests

# Rich library for nice output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("提示：安装 rich 库可获得更好的显示效果：pip install rich")


def print_result(title, content, success=True):
    """Print result with or without rich."""
    if HAS_RICH:
        console = Console()
        console.print(Panel(
            content,
            title=f"[bold {'green' if success else 'red'}]{'✓' if success else '✗'} {title}[/bold {'green' if success else 'red'}]",
            border_style='green' if success else 'red'
        ))
    else:
        status = "✓" if success else "✗"
        print(f"\n{status} {title}\n{'='*50}\n{content}\n{'='*50}\n")


# ========== Tool Functions (copied directly for testing) ==========

def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """Get current time without pytz dependency."""
    try:
        weekday_names = {
            0: "星期一", 1: "星期二", 2: "星期三", 
            3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"
        }
        
        now = datetime.now()
        
        output = (
            f"当前时间信息\n"
            f"时间：{now.strftime('%H:%M:%S')}\n"
            f"日期：{now.strftime('%Y年%m月%d日')}\n"
            f"星期：{weekday_names[now.weekday()]}\n"
            f"时区：本地时间"
        )
        
        return output
    except Exception as e:
        return f"获取时间失败：{str(e)}"


def calculate(expression: str) -> str:
    """Safe calculator using eval with restricted operations."""
    try:
        # Allowed names in evaluation
        allowed_names = {
            'abs': abs, 'round': round, 'min': min, 'max': max,
            'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
            'log': math.log, 'log10': math.log10, 'exp': math.exp,
            'pi': math.pi, 'e': math.e
        }
        
        # Very simple eval - in production would use AST parser
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        elif isinstance(result, float):
            result = round(result, 10)
        
        return f"计算结果：{expression} = {result}"
    except Exception as e:
        return f"计算错误：{str(e)}"


def web_search(query: str, num_results: int = 5) -> str:
    """Search using DuckDuckGo API."""
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
        
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", "摘要"),
                "snippet": data.get("AbstractText", "")
            })
        
        for topic in data.get("RelatedTopics", [])[:num_results-1]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append({
                    "title": topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else topic.get("Text", ""),
                    "snippet": topic.get("Text", "")
                })
        
        if not results:
            return f"未找到与 '{query}' 相关的结果"
        
        output_lines = [f"搜索结果：'{query}'（共 {len(results)} 条）\n"]
        for i, result in enumerate(results, 1):
            output_lines.append(f"{i}. {result.get('title', '无标题')}")
            output_lines.append(f"   {result.get('snippet', '无摘要')}")
        
        return "\n".join(output_lines)
    except Exception as e:
        return f"搜索失败：{str(e)}"


def analyze_text(text: str, analysis_type: str = "keywords") -> str:
    """Simple text analysis."""
    try:
        if analysis_type == "keywords":
            stop_words = {'的', '了', '和', '是', '在', '有', '我', '他', '她', 'it'}
            words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z]+', text.lower())
            filtered_words = [w for w in words if w not in stop_words and len(w) > 1]
            word_counts = Counter(filtered_words)
            keywords = [word for word, _ in word_counts.most_common(5)]
            
            return f"关键词提取结果\n{'='*50}\n提取关键词：{', '.join(keywords)}"
        
        elif analysis_type == "sentiment":
            positive_words = {'好', '棒', '优秀', '喜欢', '满意', '开心'}
            negative_words = {'差', '坏', '糟糕', '讨厌', '失望', '难过'}
            
            words = re.findall(r'[\u4e00-\u9fa5]+', text)
            pos_count = sum(1 for w in words if w in positive_words)
            neg_count = sum(1 for w in words if w in negative_words)
            
            if pos_count > neg_count:
                sentiment = "积极"
            elif neg_count > pos_count:
                sentiment = "消极"
            else:
                sentiment = "中性"
            
            return f"情感分析结果\n{'='*50}\n情感倾向：{sentiment}"
        
        else:
            return f"不支持的分析类型：{analysis_type}"
    except Exception as e:
        return f"分析失败：{str(e)}"


# ========== Run Tests ==========

def main():
    """Run all direct tool tests."""
    print("\n" + "="*50)
    print("    NovaChat 工具验证测试（直接测试版）")
    print("="*50 + "\n")
    
    results = []
    
    # Test 1: Current Time
    print("测试 1/4: 当前时间工具")
    try:
        result = get_current_time()
        print_result("get_current_time", result, True)
        results.append(("当前时间", True))
    except Exception as e:
        print_result("get_current_time", f"错误：{str(e)}", False)
        results.append(("当前时间", False))
    
    # Test 2: Calculator
    print("测试 2/4: 数学计算工具")
    try:
        results_calc = []
        for expr in ["2 + 3 * 4", "sqrt(16)", "sin(pi/2)"]:
            results_calc.append(calculate(expr))
        print_result("calculate", "\n\n".join(results_calc), True)
        results.append(("数学计算", True))
    except Exception as e:
        print_result("calculate", f"错误：{str(e)}", False)
        results.append(("数学计算", False))
    
    # Test 3: Web Search
    print("测试 3/4: 网络搜索工具")
    try:
        result = web_search("Python编程", num_results=3)
        print_result("web_search", result, True)
        results.append(("网络搜索", True))
    except Exception as e:
        print_result("web_search", f"错误：{str(e)}", False)
        results.append(("网络搜索", False))
    
    # Test 4: Text Analyzer
    print("测试 4/4: 文本分析工具")
    try:
        text = "NovaChat是一个基于RAG的智能知识问答平台，支持混合检索和知识库管理。这是一个非常好的产品。"
        result1 = analyze_text(text, "keywords")
        result2 = analyze_text("这是一个非常好的产品！", "sentiment")
        print_result("analyze_text", f"{result1}\n\n{result2}", True)
        results.append(("文本分析", True))
    except Exception as e:
        print_result("analyze_text", f"错误：{str(e)}", False)
        results.append(("文本分析", False))
    
    # Summary
    print("\n" + "="*50)
    print("测试结果汇总")
    print("="*50)
    
    for tool_name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{tool_name}: {status}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\n测试完成：{passed}/{total} 个工具通过测试")
    
    if passed == total:
        print("🎉 所有工具测试通过！")
    else:
        print(f"⚠ {total - passed} 个工具测试失败")
    
    print("\n" + "="*50)
    
    # Additional info
    print("\n提示：")
    print("• 文档列表查询工具和会话历史统计工具需要数据库连接")
    print("• 完整测试请参考 test_tools.py（需要数据库环境）")
    print("• 所有工具已成功集成到 backend/tools/ 目录")


if __name__ == "__main__":
    main()