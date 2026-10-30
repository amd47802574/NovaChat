from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infra.database import Base
from backend.infra.timezone import now_for_db


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    # 资料创建时间，以东八区（UTC+8）为基准落库
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_for_db, nullable=False)
    # 资料更新时间（角色/状态变更时刷新），供超级管理员后台展示与审计；以东八区为基准
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_for_db, onupdate=now_for_db, nullable=False
    )
    # 最近一次成功登录时间，供数据面板统计活跃度
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 账号状态：is_active=False 表示被管理员禁用；is_locked=True 表示被锁定
    # （既可能是管理员手动锁定，也可能是连续登录失败触发的临时锁定）。
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 连续登录失败次数，成功后清零；达到阈值则触发临时锁定
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 临时锁定的到期时间（以东八区朴素时间存储）；为空表示未设置临时锁定
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (UniqueConstraint("user_id", "session_id", name="uq_user_session"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_for_db, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_for_db, nullable=False)

    user = relationship("User", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_ref_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=now_for_db, nullable=False)
    rag_trace: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 用户消息携带的聊天附件元数据列表（[{id, filename, kind, mime}]），AI 消息为空
    attachments: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    session = relationship("ChatSession", back_populates="messages")


class ChatAttachment(Base):
    """聊天附件：用户在对话中上传的图片或文档，落盘存储并登记归属。"""

    __tablename__ = "chat_attachments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # 相对于附件存储目录的文件名（uuid + 安全后缀），避免路径穿越
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # image / document
    mime: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 文档类附件在上传时提取的文本，发送时注入模型上下文；图片为空
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 是否已被某条聊天消息引用；未被引用的过期附件可安全清理
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_for_db, nullable=False)


class ParentChunk(Base):
    __tablename__ = "parent_chunks"

    chunk_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parent_chunk_id: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    root_chunk_id: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    chunk_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_for_db, nullable=False)


class AuditLog(Base):
    """安全审计日志：记录超级管理员后台的所有特权操作与关键登录事件。

    仅追加（append-only），不支持修改或删除，作为不可抵赖的操作留痕。
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # 操作发起者（超级管理员用户名）；登录类事件记录登录者自身
    actor: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), default="super_admin", nullable=False)
    # 动作类型，如 login / user_create / user_disable / user_enable / role_change 等
    action: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    # 操作对象类型与标识（如 user / document），便于按对象追溯
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 可读的变更细节（如「将角色 user -> admin」）
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 来源 IP，用于异地登录与异常操作溯源
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_for_db, index=True, nullable=False)
