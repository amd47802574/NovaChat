import json
import os
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse

from backend.db.models import ChatAttachment, User
from backend.infra.auth import get_current_user, require_conversation_access
from backend.infra.database import SessionLocal
from backend.schemas import ChatRequest, ChatResponse

# 对话相关接口统一要求「非超级管理员」权限：超级管理员为纯治理角色，不参与对话。
# 权限在校服务端校验，与前端是否渲染对话界面无关。
router = APIRouter(
    tags=["chat"], dependencies=[Depends(require_conversation_access)]
)


async def _save_upload_with_limit(file: UploadFile, path, max_bytes: int) -> int:
    """分块落盘并强制大小上限，超限抛出 HTTPException。"""
    size = 0
    try:
        with open(path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件过大，最大支持 {max_bytes // (1024 * 1024)}MB",
                    )
                f.write(chunk)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except Exception as e:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"文件保存失败: {e}")
    return size


@router.get("/chat/capabilities")
async def chat_capabilities(_: User = Depends(get_current_user)):
    """前端据此决定附件选择器是否接受图片（图像理解依赖多模态模型）。"""
    from backend.chat.attachments import vision_enabled

    return {"vision_enabled": vision_enabled()}


@router.post("/chat/attachments")
async def upload_chat_attachment(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
):
    """上传聊天附件（图片/文档），返回附件 id 供聊天请求引用。"""
    from backend.api.resources import CHAT_UPLOAD_DIR, ensure_chat_upload_dir
    from backend.chat.attachments import (
        detect_kind,
        extract_document_text,
        max_bytes_for,
        mime_for,
        new_stored_name,
        vision_enabled,
    )

    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    kind = detect_kind(filename)
    if not kind:
        raise HTTPException(
            status_code=400,
            detail="不支持的附件类型：图片支持 png/jpg/jpeg/gif/webp/bmp，文档支持 pdf/doc/docx/txt/md/xls/xlsx",
        )
    if kind == "image" and not vision_enabled():
        raise HTTPException(
            status_code=400,
            detail=(
                "当前模型不支持图像理解，暂时只能上传文档。"
                "如需使用图片，请切换到多模态模型并设置 CHAT_VISION_ENABLED=1。"
            ),
        )

    ensure_chat_upload_dir()
    stored_name = new_stored_name(filename)
    file_path = CHAT_UPLOAD_DIR / stored_name
    size = await _save_upload_with_limit(file, file_path, max_bytes_for(kind))
    if size == 0:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="文件内容为空")

    extracted_text = None
    if kind == "document":
        try:
            extracted_text = await run_in_threadpool(extract_document_text, str(file_path), filename)
        except Exception as e:
            file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"附件解析失败：{e}")

    attachment = ChatAttachment(
        id=uuid.uuid4().hex,
        user_id=current_user.id,
        filename=filename[:255],
        stored_name=stored_name,
        kind=kind,
        mime=mime_for(filename),
        size_bytes=size,
        extracted_text=extracted_text,
        used=False,
    )

    db = SessionLocal()
    try:
        db.add(attachment)
        db.commit()
    except Exception:
        db.rollback()
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="附件登记失败，请重试")
    finally:
        db.close()

    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "kind": attachment.kind,
        "mime": attachment.mime,
        "size_bytes": attachment.size_bytes,
        "text_chars": len(extracted_text or ""),
    }


@router.get("/chat/attachments/{attachment_id}/file")
async def download_chat_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
):
    """下载/预览自己会话中上传过的附件（图片气泡展示走该接口）。"""
    from backend.api.resources import CHAT_UPLOAD_DIR
    from backend.chat.attachments import attachment_disk_path

    db = SessionLocal()
    try:
        attachment = (
            db.query(ChatAttachment)
            .filter(ChatAttachment.id == attachment_id, ChatAttachment.user_id == current_user.id)
            .first()
        )
    finally:
        db.close()
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    path = attachment_disk_path(attachment)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="附件文件已丢失")
    return FileResponse(
        path,
        media_type=attachment.mime or "application/octet-stream",
        filename=attachment.filename,
    )


def _resolve_request_attachments(request: ChatRequest, current_user: User) -> list:
    """校验聊天请求中的附件引用；无效引用直接 400，避免静默丢弃。"""
    from backend.chat.attachments import resolve_chat_attachments

    if not request.attachments:
        return []
    try:
        return resolve_chat_attachments(
            current_user.username,
            [ref.id for ref in request.attachments],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, current_user: User = Depends(get_current_user)):
    from backend.chat import chat_with_agent
    from backend.chat.service import humanize_provider_error

    try:
        session_id = request.session_id or "default_session"
        attachments = _resolve_request_attachments(request, current_user)
        resp = chat_with_agent(
            request.message,
            current_user.username,
            session_id,
            attachments=attachments,
        )
        if isinstance(resp, dict):
            return ChatResponse(**resp)
        return ChatResponse(response=resp)
    except HTTPException:
        raise
    except Exception as e:
        raw_message = str(e)
        message = humanize_provider_error(raw_message)
        match = re.search(r"Error code:\s*(\d{3})", raw_message)
        if match:
            code = int(match.group(1))
            if code == 429:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "上游模型服务触发限流/额度限制（429）。请检查账号额度/模型状态。\n"
                        f"原始错误：{message}"
                    ),
                )
            if code in (401, 403):
                raise HTTPException(status_code=code, detail=message)
            raise HTTPException(status_code=code, detail=message)
        raise HTTPException(status_code=500, detail=message)


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest, current_user: User = Depends(get_current_user)):
    from backend.chat import chat_with_agent_stream

    try:
        # 附件校验放在流式响应开始前，失败时能以标准 HTTP 错误返回给前端
        attachments = _resolve_request_attachments(request, current_user)
    except HTTPException:
        raise

    async def event_generator():
        try:
            session_id = request.session_id or "default_session"
            async for chunk in chat_with_agent_stream(
                request.message,
                current_user.username,
                session_id,
                attachments=attachments,
            ):
                yield chunk
        except Exception as e:
            error_data = {"type": "error", "content": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
