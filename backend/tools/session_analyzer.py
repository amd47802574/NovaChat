"""会话历史统计工具"""
from datetime import datetime, timedelta
from typing import Optional
from collections import Counter
import re

try:
    from langchain_core.tools import tool
except ImportError:
    from langchain_core.tools import tool

from backend.infra.database import SessionLocal
from backend.db.models import ChatMessage, ChatSession


def extract_keywords(text: str, top_n: int = 5) -> list:
    """从文本中简单提取关键词。"""
    # Remove common Chinese and English stop words
    stop_words = {
        '的', '了', '和', '是', '在', '有', '我', '他', '她', '它',
        '这', '那', '就', '也', '都', '还', '会', '能', '可以', '什么',
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'shall'
    }
    
    # Extract words (simplified approach)
    words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z]+', text.lower())
    
    # Filter and count
    filtered_words = [w for w in words if w not in stop_words and len(w) > 1]
    word_counts = Counter(filtered_words)
    
    return [word for word, _ in word_counts.most_common(top_n)]


@tool("analyze_conversation_history")
def analyze_conversation_history(
    session_id: Optional[str] = None,
    limit: int = 20,
    analysis_type: str = "summary"
) -> str:
    """
    分析会话历史的模式、主题和统计数据。
    使用此工具了解用户偏好和会话模式。

    Args:
        session_id: 指定要分析的会话 ID。若为 None，则分析最近的会话。
        limit: 要分析的最近消息数量（默认：20）。
        analysis_type: 分析类型 —— 'summary'、'topics' 或 'timeline'。

    Returns:
        分析结果，包含消息数量、热门主题和时间线。
    """
    try:
        with SessionLocal() as session:
            # Query messages
            query = session.query(ChatMessage).order_by(
                ChatMessage.timestamp.desc()
            )
            
            if session_id:
                # Join with ChatSession to filter by session_id
                query = query.join(ChatSession).filter(
                    ChatSession.session_id == session_id
                )
            
            messages = query.limit(limit).all()
            
            if not messages:
                return "未找到会话历史记录。"
            
            # Analysis
            message_count = len(messages)
            user_messages = [m for m in messages if m.message_type == 'human']
            ai_messages = [m for m in messages if m.message_type == 'ai']
            
            # Extract keywords from user messages
            all_text = ' '.join([m.content for m in user_messages])
            top_keywords = extract_keywords(all_text, top_n=10)
            
            # Time analysis
            oldest_msg = messages[-1]
            newest_msg = messages[0]
            time_span = newest_msg.timestamp - oldest_msg.timestamp
            
            # Build result based on analysis type
            if analysis_type == "summary":
                result = (
                    f"会话历史分析摘要\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"消息总数：{message_count} 条\n"
                    f"- 用户消息：{len(user_messages)} 条\n"
                    f"- AI回复：{len(ai_messages)} 条\n"
                    f"时间跨度：{time_span.days} 天 {time_span.seconds // 3600} 小时\n"
                    f"分析时段：{oldest_msg.timestamp.strftime('%Y-%m-%d %H:%M')} 至 {newest_msg.timestamp.strftime('%Y-%m-%d %H:%M')}\n"
                    f"热门关键词：{', '.join(top_keywords[:5]) if top_keywords else '无'}"
                )
                
            elif analysis_type == "topics":
                result = (
                    f"会话主题分析\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"提取的关键词：\n"
                )
                for i, keyword in enumerate(top_keywords, 1):
                    result += f"{i}. {keyword}\n"
                
                # Recent questions
                result += f"\n最近 {min(3, len(user_messages))} 个问题：\n"
                for i, msg in enumerate(user_messages[:3], 1):
                    preview = msg.content[:50] + '...' if len(msg.content) > 50 else msg.content
                    result += f"{i}. {preview}\n"
                    
            elif analysis_type == "timeline":
                result = (
                    f"会话时间线\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                )
                for i, msg in enumerate(messages[:10], 1):
                    time_str = msg.timestamp.strftime('%Y-%m-%d %H:%M')
                    role = "用户" if msg.message_type == 'human' else "AI"
                    preview = msg.content[:30] + '...' if len(msg.content) > 30 else msg.content
                    result += f"{i}. [{time_str}] {role}: {preview}\n"
            
            else:
                result = f"不支持的分析类型：{analysis_type}。请使用 summary、topics 或 timeline。"
            
            return result
            
    except Exception as e:
        return f"分析会话历史失败：{str(e)}"