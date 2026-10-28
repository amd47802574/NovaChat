from fastapi import APIRouter, Depends, HTTPException

from backend.chat.storage import storage
from backend.db.models import User
from backend.infra.auth import get_current_user, require_conversation_access
from backend.schemas import (
    MessageInfo,
    SessionBatchDeleteRequest,
    SessionBatchDeleteResponse,
    SessionClearResponse,
    SessionDeleteResponse,
    SessionInfo,
    SessionListResponse,
    SessionMessagesResponse,
    SessionUpdateRequest,
    SessionUpdateResponse,
)

# 会话（历史）相关接口同样属于「对话功能」，统一拒绝超级管理员。
router = APIRouter(
    tags=["sessions"], dependencies=[Depends(require_conversation_access)]
)


@router.get("/sessions/{session_id}", response_model=SessionMessagesResponse)
async def get_session_messages(session_id: str, current_user: User = Depends(get_current_user)):
    try:
        messages = [
            MessageInfo(
                type=msg["type"],
                content=msg["content"],
                timestamp=msg["timestamp"],
                rag_trace=msg.get("rag_trace"),
                attachments=msg.get("attachments") or None,
            )
            for msg in storage.get_session_messages(current_user.username, session_id)
        ]
        return SessionMessagesResponse(messages=messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(current_user: User = Depends(get_current_user)):
    try:
        sessions = [SessionInfo(**item) for item in storage.list_session_infos(current_user.username)]
        sessions.sort(key=lambda x: (x.pinned, x.updated_at), reverse=True)
        return SessionListResponse(sessions=sessions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/sessions/{session_id}", response_model=SessionUpdateResponse)
async def update_session(
    session_id: str,
    payload: SessionUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    updates = {}
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="会话标题不能为空")
        updates["title"] = title[:80]
    if payload.pinned is not None:
        updates["pinned"] = payload.pinned
    if not updates:
        raise HTTPException(status_code=400, detail="没有可更新的内容")

    try:
        result = storage.update_session(current_user.username, session_id, updates)
        if not result:
            raise HTTPException(status_code=404, detail="会话不存在")
        return SessionUpdateResponse(**result, message="会话已更新")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions", response_model=SessionClearResponse)
async def clear_sessions(current_user: User = Depends(get_current_user)):
    try:
        deleted_count = storage.clear_sessions(current_user.username)
        return SessionClearResponse(deleted_count=deleted_count, message="历史会话已清空")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/batch", response_model=SessionBatchDeleteResponse)
async def batch_delete_sessions(
    payload: SessionBatchDeleteRequest,
    current_user: User = Depends(get_current_user),
):
    # 该路由必须注册在 ``/sessions/{session_id}`` 之前，否则 "batch" 会被当成 session_id 命中单条删除。
    if not payload.session_ids:
        raise HTTPException(status_code=400, detail="未提供要删除的会话")
    try:
        deleted_count = storage.delete_sessions_batch(current_user.username, payload.session_ids)
        return SessionBatchDeleteResponse(
            deleted_count=deleted_count,
            message=f"成功删除 {deleted_count} 个会话",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}", response_model=SessionDeleteResponse)
async def delete_session(session_id: str, current_user: User = Depends(get_current_user)):
    try:
        deleted = storage.delete_session(current_user.username, session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="会话不存在")
        return SessionDeleteResponse(session_id=session_id, message="成功删除会话")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
