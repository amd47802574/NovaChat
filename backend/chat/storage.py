from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.db.models import ChatMessage, ChatSession, User
from backend.infra.cache import cache
from backend.infra.database import SessionLocal
from backend.infra.timezone import now_for_db, to_utc8_iso


def _isoformat_utc(dt: datetime) -> str:
    """把时间戳序列化为东八区（UTC+8）ISO 字符串（含 +08:00 偏移）。

    数据库时间统一以「东八区朴素时间」存储，直接 isoformat() 会丢失时区标记，
    前端 new Date() 将按浏览器本地时区解析而产生偏差。这里统一补上 +08:00 偏移，
    使前端在任何时区下都能显式按东八区展示。
    """
    return to_utc8_iso(dt)


class ConversationStorage:
    """对话存储（PostgreSQL + Redis）。"""

    @staticmethod
    def _messages_cache_key(user_id: str, session_id: str) -> str:
        return f"chat_messages:{user_id}:{session_id}"

    @staticmethod
    def _sessions_cache_key(user_id: str) -> str:
        return f"chat_sessions:{user_id}"

    @staticmethod
    def _to_langchain_messages(records: list[dict]) -> list:
        messages = []
        for msg_data in records:
            msg_type = msg_data.get("type")
            content = msg_data.get("content", "")
            if msg_type == "human":
                messages.append(HumanMessage(content=content))
            elif msg_type == "ai":
                messages.append(AIMessage(content=content))
            elif msg_type == "system":
                messages.append(SystemMessage(content=content))
        return messages

    def save(
        self,
        user_id: str,
        session_id: str,
        messages: list,
        metadata: dict = None,
        extra_message_data: list = None,
    ):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                return

            session = (
                db.query(ChatSession)
                .filter(ChatSession.user_id == user.id, ChatSession.session_id == session_id)
                .first()
            )
            if not session:
                session = ChatSession(user_id=user.id, session_id=session_id, metadata_json=metadata or {})
                db.add(session)
                db.flush()
            elif metadata is not None:
                existing_meta = session.metadata_json or {}
                session.metadata_json = {**existing_meta, **metadata}

            # save 采用「整段删后重插」，旧消息的 rag_trace / 附件元数据需要按下标继承，
            # 否则每开新一轮都会把这些历史展示数据清空。
            existing_rows = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_ref_id == session.id)
                .order_by(ChatMessage.id.asc())
                .all()
            )
            carried_extras = [(row.rag_trace, row.attachments) for row in existing_rows]

            db.query(ChatMessage).filter(ChatMessage.session_ref_id == session.id).delete(synchronize_session=False)

            serialized = []
            now = now_for_db()
            for idx, msg in enumerate(messages):
                rag_trace = None
                attachments = None
                if extra_message_data and idx < len(extra_message_data):
                    extra = extra_message_data[idx] or {}
                    rag_trace = extra.get("rag_trace")
                    attachments = extra.get("attachments") or None

                carried_trace, carried_attachments = (
                    carried_extras[idx] if idx < len(carried_extras) else (None, None)
                )
                if rag_trace is None:
                    rag_trace = carried_trace
                if attachments is None:
                    attachments = carried_attachments

                db.add(
                    ChatMessage(
                        session_ref_id=session.id,
                        message_type=msg.type,
                        content=str(msg.content),
                        timestamp=now,
                        rag_trace=rag_trace,
                        attachments=attachments,
                    )
                )
                serialized.append(
                    {
                        "type": msg.type,
                        "content": str(msg.content),
                        "timestamp": _isoformat_utc(now),
                        "rag_trace": rag_trace,
                        "attachments": attachments,
                    }
                )

            session.updated_at = now
            db.commit()

            cache.set_json(self._messages_cache_key(user_id, session_id), serialized)
            cache.delete(self._sessions_cache_key(user_id))
        finally:
            db.close()

    def load(self, user_id: str, session_id: str) -> list:
        cached = cache.get_json(self._messages_cache_key(user_id, session_id))
        if cached is not None:
            return self._to_langchain_messages(cached)

        records = self.get_session_messages(user_id, session_id)
        cache.set_json(self._messages_cache_key(user_id, session_id), records)
        return self._to_langchain_messages(records)

    def load_with_meta(self, user_id: str, session_id: str) -> tuple[list, dict]:
        """加载对话消息及会话元数据（标题、持久化笔记等）。"""
        messages = self.load(user_id, session_id)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                return messages, {}
            session = (
                db.query(ChatSession)
                .filter(ChatSession.user_id == user.id, ChatSession.session_id == session_id)
                .first()
            )
            if not session:
                return messages, {}
            return messages, dict(session.metadata_json or {})
        finally:
            db.close()

    def list_sessions(self, user_id: str) -> list:
        return [item["session_id"] for item in self.list_session_infos(user_id)]

    def list_session_infos(self, user_id: str) -> list[dict]:
        cached = cache.get_json(self._sessions_cache_key(user_id))
        if cached is not None:
            return cached

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                return []

            sessions = (
                db.query(ChatSession)
                .filter(ChatSession.user_id == user.id)
                .order_by(ChatSession.updated_at.desc())
                .all()
            )
            result = []
            for s in sessions:
                count = db.query(ChatMessage).filter(ChatMessage.session_ref_id == s.id).count()
                meta = s.metadata_json or {}
                result.append(
                    {
                        "session_id": s.session_id,
                        "title": meta.get("title") or s.session_id,
                        "pinned": bool(meta.get("pinned", False)),
                        "updated_at": _isoformat_utc(s.updated_at),
                        "message_count": count,
                    }
                )
            cache.set_json(self._sessions_cache_key(user_id), result)
            return result
        finally:
            db.close()

    def get_session_messages(self, user_id: str, session_id: str) -> list[dict]:
        cached = cache.get_json(self._messages_cache_key(user_id, session_id))
        if cached is not None:
            return cached

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                return []
            session = (
                db.query(ChatSession)
                .filter(ChatSession.user_id == user.id, ChatSession.session_id == session_id)
                .first()
            )
            if not session:
                return []

            rows = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_ref_id == session.id)
                .order_by(ChatMessage.id.asc())
                .all()
            )
            result = [
                {
                    "type": row.message_type,
                    "content": row.content,
                    "timestamp": _isoformat_utc(row.timestamp),
                    "rag_trace": row.rag_trace,
                    "attachments": row.attachments,
                }
                for row in rows
            ]
            cache.set_json(self._messages_cache_key(user_id, session_id), result)
            return result
        finally:
            db.close()

    def delete_session(self, user_id: str, session_id: str) -> bool:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                return False
            session = (
                db.query(ChatSession)
                .filter(ChatSession.user_id == user.id, ChatSession.session_id == session_id)
                .first()
            )
            if not session:
                return False

            db.delete(session)
            db.commit()
            cache.delete(self._messages_cache_key(user_id, session_id))
            cache.delete(self._sessions_cache_key(user_id))
            return True
        finally:
            db.close()

    def update_session(self, user_id: str, session_id: str, updates: dict) -> dict | None:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                return None
            session = (
                db.query(ChatSession)
                .filter(ChatSession.user_id == user.id, ChatSession.session_id == session_id)
                .first()
            )
            if not session:
                return None

            metadata = dict(session.metadata_json or {})
            metadata.update(updates)
            session.metadata_json = metadata
            session.updated_at = now_for_db()
            db.commit()
            cache.delete(self._sessions_cache_key(user_id))
            return {
                "session_id": session_id,
                "title": metadata.get("title") or session_id,
                "pinned": bool(metadata.get("pinned", False)),
            }
        finally:
            db.close()

    def clear_sessions(self, user_id: str) -> int:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                return 0
            sessions = db.query(ChatSession).filter(ChatSession.user_id == user.id).all()
            session_ids = [session.session_id for session in sessions]
            deleted_count = len(sessions)
            for session in sessions:
                db.delete(session)
            db.commit()
            for session_id in session_ids:
                cache.delete(self._messages_cache_key(user_id, session_id))
            cache.delete(self._sessions_cache_key(user_id))
            return deleted_count
        finally:
            db.close()

    def delete_sessions_batch(self, user_id: str, session_ids: list[str]) -> int:
        """批量删除属于该用户的多个会话，仅删除确实存在的会话，返回实际删除数量。"""
        if not session_ids:
            return 0
        # 去重，避免同一 id 重复传入导致误判。
        unique_ids = list({sid for sid in session_ids if sid})
        if not unique_ids:
            return 0

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                return 0
            sessions = (
                db.query(ChatSession)
                .filter(
                    ChatSession.user_id == user.id,
                    ChatSession.session_id.in_(unique_ids),
                )
                .all()
            )
            deleted_ids = [session.session_id for session in sessions]
            deleted_count = len(sessions)
            for session in sessions:
                db.delete(session)
            db.commit()
            for session_id in deleted_ids:
                cache.delete(self._messages_cache_key(user_id, session_id))
            cache.delete(self._sessions_cache_key(user_id))
            return deleted_count
        finally:
            db.close()


storage = ConversationStorage()
