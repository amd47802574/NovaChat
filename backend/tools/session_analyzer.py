"""会话历史统计工具（严格会话作用域隔离）。

设计目标：本工具的分析范围**严格限定在「当前会话」内**，以请求上下文
`ChatRequestContext` 中携带的 `session_id` 作为唯一作用域。无论调用方传入
什么参数，都不会跨会话 ID 检索、合并或关联其他会话的数据。

会话边界判定规则
----------------
1. 唯一作用域：以 `ctx.session_id` 为分析边界；忽略任何不属于该 ID 的历史记录。
2. 数据隔离：消息通过外键 `ChatMessage.session_ref_id` 严格归属到当前会话行
   （`ChatSession.id`），查询时按 `user_id + session_id` 解析出唯一会话行后再
   以该行的主键过滤消息，从数据库层面杜绝跨会话 / 跨用户的数据混入。
3. 忽略跨会话请求：若调用方显式传入一个与当前会话不同的 `session_id`，视为
   「跨会话引用请求」，工具将**拒绝**该请求并仅提示当前会话，绝不读取其他会话。

异常场景与预期表现
------------------
- 会话 ID 缺失：`ctx.session_id` 为空或缺失 → 中止分析，不读取任何数据。
- 当前用户不存在：无法定位归属用户 → 中止分析。
- 当前会话不存在：解析不到对应会话行（如尚未产生任何消息）→ 返回空作用域提示。
- 会话标识歧义：同一 `user_id + session_id` 匹配到多条会话行 → 视为数据异常，
  中止分析，避免误将其他会话数据并入。
- 跨会话引用请求：传入的 `session_id` 与当前会话不一致 → 拒绝该引用，仅提示
  当前会话，不返回任何非当前会话数据。
- 数据库内部错误：捕获异常，返回错误提示且不泄露任何跨会话数据。

本工具**不**在 stateless 的 MCP Server 中暴露（与 `search_knowledge_base`
一致），因为它依赖每请求的 `ChatRequestContext` 来界定当前会话。
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Optional

from langchain_core.tools import tool

from backend.chat.request_context import ChatRequestContext
from backend.db.models import ChatMessage, ChatSession, User
from backend.infra.database import SessionLocal
from backend.infra.timezone import as_utc8

# ---------------------------------------------------------------------------
# 作用域 / 隔离相关的对外提示（带前缀，便于模型与调用方识别边界状态）
# ---------------------------------------------------------------------------

# 跨会话引用被拒绝：传入的 session_id 与当前会话不一致
SCOPE_DENIED_CROSS_SESSION = (
    "SCOPE_DENIED: 会话历史分析被严格限制在当前会话内。检测到请求引用了其他会话 ID，"
    "已忽略该跨会话请求，未读取任何非当前会话的数据。"
)

# 会话 ID 缺失
SCOPE_MISSING_SESSION_ID = (
    "SCOPE_ERROR: 当前请求缺少有效的会话 ID（session_id 为空或缺失），无法界定分析作用域。"
    "会话历史分析已中止，未读取任何会话数据。"
)

# 当前用户不存在（无法定位归属）
SCOPE_USER_NOT_FOUND = (
    "SCOPE_ERROR: 未找到当前用户的账户记录，无法定位所属会话。"
    "会话历史分析已中止，未读取任何会话数据。"
)

# 同 (user_id, session_id) 匹配到多条会话行 —— 数据异常，存在歧义
SCOPE_AMBIGUOUS = (
    "SCOPE_ERROR: 当前会话标识匹配到多条会话记录，存在数据歧义。"
    "为避免跨会话数据混入，分析已中止，未读取任何会话数据。"
)

# 数据库内部错误
SCOPE_DB_ERROR = (
    "SCOPE_ERROR: 分析当前会话历史时发生内部错误，未返回任何跨会话数据。"
)


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


def _resolve_current_session(session, ctx: ChatRequestContext):
    """解析出「当前会话」对应的 ChatSession 行主键。

    仅依据 `ctx.user_id`（用户名）+ `ctx.session_id` 定位唯一会话行，
    确保作用域严格绑定到当前用户 + 当前会话。

    Returns:
        (session_row_id: Optional[int], status: str)
        status 取值见下方常量：OK / MISSING_SESSION_ID / USER_NOT_FOUND /
        SESSION_NOT_FOUND / AMBIGUOUS
    """
    current_session_id = (ctx.session_id or "").strip()
    if not current_session_id:
        return None, "MISSING_SESSION_ID"

    # ctx.user_id 实际为用户名字符串（见 storage.py 约定），需先解析为整数 PK。
    user = session.query(User).filter(User.username == ctx.user_id).first()
    if user is None:
        return None, "USER_NOT_FOUND"

    rows = (
        session.query(ChatSession)
        .filter(ChatSession.user_id == user.id, ChatSession.session_id == current_session_id)
        .all()
    )

    if not rows:
        return None, "SESSION_NOT_FOUND"
    if len(rows) > 1:
        # 唯一约束 (user_id, session_id) 下理论上不会触发；一旦触发视为数据异常。
        return None, "AMBIGUOUS"

    return rows[0].id, "OK"


def _build_result(messages, analysis_type: str, scope_line: str) -> str:
    """基于当前会话的消息列表构造分析结果。"""
    message_count = len(messages)
    user_messages = [m for m in messages if m.message_type == 'human']
    ai_messages = [m for m in messages if m.message_type == 'ai']

    # Extract keywords from user messages
    all_text = ' '.join([m.content for m in user_messages])
    top_keywords = extract_keywords(all_text, top_n=10)

    result = scope_line

    if analysis_type == "summary":
        if message_count == 0:
            result += (
                "当前会话内暂无可分析的消息记录。\n"
                "（本工具仅读取当前会话数据，不会检索或关联其他会话。）"
            )
            return result

        oldest_msg = messages[-1]
        newest_msg = messages[0]
        time_span = newest_msg.timestamp - oldest_msg.timestamp
        result += (
            f"会话历史分析摘要\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"消息总数：{message_count} 条\n"
            f"- 用户消息：{len(user_messages)} 条\n"
            f"- AI回复：{len(ai_messages)} 条\n"
            f"时间跨度：{time_span.days} 天 {time_span.seconds // 3600} 小时\n"
            f"分析时段：{as_utc8(oldest_msg.timestamp).strftime('%Y-%m-%d %H:%M')} 至 {as_utc8(newest_msg.timestamp).strftime('%Y-%m-%d %H:%M')}\n"
            f"热门关键词：{', '.join(top_keywords[:5]) if top_keywords else '无'}"
        )

    elif analysis_type == "topics":
        result += f"会话主题分析\n━━━━━━━━━━━━━━━━━━\n提取的关键词：\n"
        if not top_keywords:
            result += "（当前会话暂无足够文本以提取关键词）\n"
        for i, keyword in enumerate(top_keywords, 1):
            result += f"{i}. {keyword}\n"

        recent_q = min(3, len(user_messages))
        result += f"\n最近 {recent_q} 个问题：\n"
        for i, msg in enumerate(user_messages[:3], 1):
            preview = msg.content[:50] + '...' if len(msg.content) > 50 else msg.content
            result += f"{i}. {preview}\n"

    elif analysis_type == "timeline":
        result += f"会话时间线\n━━━━━━━━━━━━━━━━━━\n"
        if message_count == 0:
            result += "（当前会话暂无消息）"
        for i, msg in enumerate(messages[:10], 1):
            time_str = as_utc8(msg.timestamp).strftime('%Y-%m-%d %H:%M')
            role = "用户" if msg.message_type == 'human' else "AI"
            preview = msg.content[:30] + '...' if len(msg.content) > 30 else msg.content
            result += f"{i}. [{time_str}] {role}: {preview}\n"

    else:
        result += (
            f"不支持的分析类型：{analysis_type}。请使用 summary、topics 或 timeline。"
        )

    return result


def make_analyze_conversation_history(ctx: ChatRequestContext):
    """工厂：返回一个绑定到「当前会话」的会话历史分析工具。

    Args:
        ctx: 每请求上下文，提供 `session_id`（当前会话唯一作用域）与 `user_id`。
    """

    @tool("analyze_conversation_history")
    def analyze_conversation_history(
        analysis_type: str = "summary",
        limit: int = 20,
        session_id: Optional[str] = None,
    ) -> str:
        """
        分析「当前会话」历史的模式、主题和统计数据。

        【作用域与数据隔离】
        - 本工具的分析范围**严格限定在当前会话内**，以请求上下文中的 session_id
          作为唯一作用域；不会跨会话 ID 检索或关联其他会话的数据。
        - 仅读取归属当前用户 + 当前会话的消息，其他会话数据一律隔离、忽略。
        - 若显式传入与当前会话不同的 session_id，将被视为「跨会话引用请求」并被
          拒绝，工具不会读取任何非当前会话的数据。

        Args:
            analysis_type: 分析类型 —— 'summary'、'topics' 或 'timeline'。
            limit: 当前会话内要分析的最近消息数量（默认：20）。
            session_id: 可选。若提供且等于当前会话 ID，则仍以当前会话为作用域；
                若提供但与当前会话不一致，将被拒绝（跨会话引用）。通常无需传此参数。

        Returns:
            分析结果（仅含当前会话数据），或在边界/异常场景下返回带 SCOPE_* 前缀的提示。
        """
        # 边界情况 1：会话 ID 缺失 —— 直接中止，不触碰任何数据。
        current_session_id = (ctx.session_id or "").strip()
        if not current_session_id:
            return SCOPE_MISSING_SESSION_ID

        # 边界情况 2：跨会话引用请求 —— 传入的 session_id 与当前会话不一致时拒绝。
        if session_id and session_id.strip() and session_id.strip() != current_session_id:
            return (
                f"{SCOPE_DENIED_CROSS_SESSION}\n"
                f"（当前会话：{current_session_id}；被拒绝的引用：{session_id}）"
            )

        try:
            with SessionLocal() as session:
                # 解析当前会话行（user_id + session_id 唯一），从数据库层面锁定作用域。
                session_row_id, status = _resolve_current_session(session, ctx)
                if status == "MISSING_SESSION_ID":
                    return SCOPE_MISSING_SESSION_ID
                if status == "USER_NOT_FOUND":
                    return SCOPE_USER_NOT_FOUND
                if status == "AMBIGUOUS":
                    return SCOPE_AMBIGUOUS
                if status == "SESSION_NOT_FOUND":
                    scope_line = (
                        f"[作用域] 当前会话：{current_session_id}｜"
                        f"数据隔离：仅读取本会话，已排除其他会话\n"
                    )
                    return (
                        scope_line
                        + f"当前会话（{current_session_id}）内暂无可分析的消息记录。"
                    )

                # 边界情况 3：多会话数据混入 —— 仅靠外键 session_ref_id 严格过滤，
                # 即便底层数据混杂，也只取归属当前会话行的消息。
                limit = max(1, int(limit))
                messages = (
                    session.query(ChatMessage)
                    .filter(ChatMessage.session_ref_id == session_row_id)
                    .order_by(ChatMessage.timestamp.desc())
                    .limit(limit)
                    .all()
                )
                # 二次防御：丢弃任何不属于当前会话行的消息（理论不会发生，纯属安全冗余）。
                messages = [m for m in messages if m.session_ref_id == session_row_id]
                messages = list(reversed(messages))  # 升序呈现时间线

                scope_line = (
                    f"[作用域] 当前会话：{current_session_id}｜"
                    f"数据隔离：仅包含本会话消息，已排除其他会话\n"
                )
                return _build_result(messages, analysis_type, scope_line)

        except Exception:
            return SCOPE_DB_ERROR

    return analyze_conversation_history
