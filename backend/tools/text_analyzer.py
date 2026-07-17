"""文本分析工具"""
import os
import re
from collections import Counter
from typing import Optional

try:
    from langchain_core.tools import tool
except ImportError:
    from langchain_core.tools import tool

from langchain.chat_models import init_chat_model

# Get model configuration
API_KEY = os.getenv("ARK_API_KEY")
FAST_MODEL = os.getenv("FAST_MODEL") or os.getenv("MODEL")
BASE_URL = os.getenv("BASE_URL")


def extract_keywords_simple(text: str, top_n: int = 10) -> list:
    """Simple keyword extraction without LLM."""
    stop_words = {
        '的', '了', '和', '是', '在', '有', '我', '他', '她', '它',
        '这', '那', '就', '也', '都', '还', '会', '能', '可以', '什么',
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'shall', 'to', 'of',
        'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into'
    }
    
    words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z]+', text.lower())
    filtered_words = [w for w in words if w not in stop_words and len(w) > 1]
    word_counts = Counter(filtered_words)
    
    return [word for word, _ in word_counts.most_common(top_n)]


def analyze_with_llm(text: str, analysis_type: str) -> str:
    """Use LLM for advanced text analysis."""
    try:
        model = init_chat_model(
            model=FAST_MODEL,
            model_provider="openai",
            api_key=API_KEY,
            base_url=BASE_URL,
            temperature=0.3,
        )
        
        if analysis_type == "summary":
            prompt = f"""请用简洁的语言总结以下文本的核心内容（不超过100字）：

文本：
{text}

摘要："""
            
        elif analysis_type == "sentiment":
            prompt = f"""请分析以下文本的情感倾向（积极/消极/中性），并简要说明理由：

文本：
{text}

情感分析："""
            
        else:
            return "不支持的分析类型"
        
        response = model.invoke(prompt)
        return response.content
        
    except Exception as e:
        raise Exception(f"LLM 分析失败：{str(e)}")


@tool("analyze_text")
def analyze_text(
    text: str,
    analysis_type: str = "keywords",
    top_n: int = 10,
    use_llm: bool = False
) -> str:
    """
    Analyze text for summary, keywords, or sentiment.
    Use this tool to quickly extract key information from long text.
    
    Args:
        text: Text content to analyze.
        analysis_type: Type of analysis - 'keywords', 'summary', or 'sentiment'.
        top_n: Number of keywords to extract (default: 10, for keywords analysis).
        use_llm: Use LLM for advanced analysis (for summary and sentiment, default: False).
    
    Returns:
        Analysis results based on the specified type.
    """
    try:
        # Validate inputs
        if not text or not text.strip():
            return "错误：文本内容不能为空"
        
        text = text.strip()
        
        # Truncate very long text
        max_length = 5000
        if len(text) > max_length:
            text = text[:max_length] + "..."
            truncated_msg = f"\n（文本过长，已截取前 {max_length} 字符）\n"
        else:
            truncated_msg = ""
        
        if analysis_type == "keywords":
            # Simple keyword extraction
            keywords = extract_keywords_simple(text, top_n)
            
            if not keywords:
                return "未提取到关键词"
            
            result = f"关键词提取结果\n━━━━━━━━━━━━━━━━━━\n"
            result += f"文本长度：{len(text)} 字符\n"
            result += f"提取关键词：{top_n} 个\n\n"
            for i, keyword in enumerate(keywords, 1):
                result += f"{i}. {keyword}\n"
            
            return result + truncated_msg
            
        elif analysis_type == "summary":
            if use_llm:
                summary = analyze_with_llm(text, "summary")
                return f"文本摘要\n━━━━━━━━━━━━━━━━━━\n{summary}{truncated_msg}"
            else:
                # Simple extraction-based summary
                words = text.split()
                if len(words) <= 50:
                    return f"文本较短，无需摘要：\n\n{text[:200]}..."
                else:
                    # Extract first 50 words
                    simple_summary = ' '.join(words[:50]) + "..."
                    return f"简单摘要（前50词）：\n{simple_summary}{truncated_msg}"
                    
        elif analysis_type == "sentiment":
            if use_llm:
                sentiment = analyze_with_llm(text, "sentiment")
                return f"情感分析\n━━━━━━━━━━━━━━━━━━\n{sentiment}{truncated_msg}"
            else:
                # Simple rule-based sentiment analysis
                positive_words = {'好', '棒', '优秀', '喜欢', '满意', '开心', '高兴', '成功'}
                negative_words = {'差', '坏', '糟糕', '讨厌', '失望', '难过', '失败', '问题'}
                
                words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z]+', text.lower())
                pos_count = sum(1 for w in words if w in positive_words)
                neg_count = sum(1 for w in words if w in negative_words)
                
                if pos_count > neg_count:
                    sentiment_result = "积极（正向情感词较多）"
                elif neg_count > pos_count:
                    sentiment_result = "消极（负向情感词较多）"
                else:
                    sentiment_result = "中性（情感倾向不明显）"
                
                return f"简单情感分析\n━━━━━━━━━━━━━━━━━━\n情感倾向：{sentiment_result}\n正向词：{pos_count} 个，负向词：{neg_count} 个{truncated_msg}"
        
        else:
            return f"不支持的分析类型：{analysis_type}。请使用 keywords、summary 或 sentiment。"
            
    except Exception as e:
        return f"文本分析失败：{str(e)}"