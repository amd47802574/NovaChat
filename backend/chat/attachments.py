"""聊天附件（图片 / 文档）服务。

负责四件事：
1. 类型识别与白名单校验（图片走多模态输入，文档提取文本注入上下文）；
2. 文档文本提取（复用知识库索引侧的解析能力）；
3. 按归属校验聊天请求里的附件引用，并构建发给模型的多模态消息内容；
4. 清理从未被消息引用的过期附件。
"""
from __future__ import annotations

import base64
import os
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from backend.db.models import ChatAttachment, User
from backend.indexing.document_loader import sanitize_text
from backend.infra.database import SessionLocal
from backend.infra.timezone import now_for_db

# 图片扩展名：以 OpenAI 兼容的 image_url(data URL) 形式发给多模态模型
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
# 文档扩展名：上传时提取纯文本，发送时以文本块注入模型上下文
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md", ".xls", ".xlsx"}

MAX_IMAGE_BYTES = 8 * 1024 * 1024       # 单张图片 8MB
MAX_DOCUMENT_BYTES = 30 * 1024 * 1024   # 单个文档 30MB
MAX_ATTACHMENTS_PER_MESSAGE = 6         # 单条消息最多携带的附件数
MAX_CHARS_PER_DOCUMENT = 30000          # 单个文档注入上下文的字符上限
MAX_TOTAL_DOCUMENT_CHARS = 60000        # 单条消息所有文档合计字符上限
STALE_UNUSED_TTL = timedelta(hours=24)  # 未被消息引用的附件保留时长

# 图像理解依赖多模态模型：text-only 模型（如 deepseek-chat）不能接收 image 内容块，
# 需要部署方按所用模型显式开启，未开启时直接拒绝图片上传并给出明确提示。
_VISION_TRUTHY = {"1", "true", "yes", "on"}


def vision_enabled() -> bool:
    return os.getenv("CHAT_VISION_ENABLED", "0").strip().lower() in _VISION_TRUTHY

# 显式维护 MIME 映射，避免依赖各平台 mimetypes 注册表差异
_MIME_BY_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_SAFE_EXTENSION_RE = re.compile(r"[^a-z0-9]")


def extension_of(filename: str) -> str:
    """提取小写安全后缀（只保留字母数字），无法识别时返回空串。"""
    suffix = Path(filename or "").suffix.lower().lstrip(".")
    return f".{_SAFE_EXTENSION_RE.sub('', suffix)}" if suffix else ""


def detect_kind(filename: str) -> str | None:
    """按扩展名识别附件类型：image / document，不在白名单内返回 None。"""
    ext = extension_of(filename)
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in DOCUMENT_EXTENSIONS:
        return "document"
    return None


def mime_for(filename: str) -> str:
    return _MIME_BY_EXTENSION.get(extension_of(filename), "application/octet-stream")


def max_bytes_for(kind: str) -> int:
    return MAX_IMAGE_BYTES if kind == "image" else MAX_DOCUMENT_BYTES


def new_stored_name(filename: str) -> str:
    """生成落盘文件名：uuid + 白名单后缀，与原始文件名解耦防路径穿越。"""
    ext = extension_of(filename)
    return f"{uuid.uuid4().hex}{ext}"


def extract_document_text(file_path: str, filename: str) -> str:
    """提取文档附件的纯文本，复用知识库索引侧同一套解析与净化能力。"""
    ext = extension_of(filename)
    if ext in (".txt", ".md"):
        try:
            text = Path(file_path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = Path(file_path).read_text(encoding="gb18030", errors="replace")
    elif ext == ".pdf":
        from langchain_community.document_loaders import PyPDFLoader

        pages = PyPDFLoader(file_path).load()
        text = "\n\n".join((page.page_content or "").strip() for page in pages)
    elif ext == ".docx":
        import docx2txt

        text = docx2txt.process(file_path)
    elif ext == ".doc":
        from backend.indexing.legacy_doc import extract_legacy_doc_text

        text = extract_legacy_doc_text(file_path)
    elif ext in (".xls", ".xlsx"):
        from langchain_community.document_loaders import UnstructuredExcelLoader

        sheets = UnstructuredExcelLoader(file_path).load()
        text = "\n\n".join((sheet.page_content or "").strip() for sheet in sheets)
    else:
        raise ValueError(f"不支持的附件类型: {filename}")
    return sanitize_text(text or "").strip()


@dataclass
class AttachmentContent:
    """单个附件构建出的模型侧内容与展示元数据。"""

    attachment: ChatAttachment
    text_block: str = ""        # 文档文本块（含标题分隔行），图片为空
    image_data_url: str = ""    # 图片 data URL，文档为空
    parse_error: str = ""       # 解析失败原因（失败时内容为空）
    truncated: bool = False     # 文本块是否被截断

    @property
    def meta(self) -> dict:
        return {
            "id": self.attachment.id,
            "filename": self.attachment.filename,
            "kind": self.attachment.kind,
            "mime": self.attachment.mime,
        }


def resolve_chat_attachments(username: str, attachment_ids: list[str]) -> list[ChatAttachment]:
    """按 id 加载当前用户名下的附件（保持顺序、去重），并标记为已被消息引用。

    任一 id 不存在、不属于该用户或文件已丢失时抛出 ValueError，由路由层转成 400。
    """
    ids: list[str] = []
    for attachment_id in attachment_ids:
        cleaned = str(attachment_id or "").strip()
        if cleaned and cleaned not in ids:
            ids.append(cleaned)
    if not ids:
        return []
    if len(ids) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise ValueError(f"单条消息最多携带 {MAX_ATTACHMENTS_PER_MESSAGE} 个附件")

    db = SessionLocal()
    try:
        rows = (
            db.query(ChatAttachment)
            .join(User, ChatAttachment.user_id == User.id)
            .filter(ChatAttachment.id.in_(ids), User.username == username)
            .all()
        )
        rows_by_id = {row.id: row for row in rows}
        missing = [item for item in ids if item not in rows_by_id]
        if missing:
            raise ValueError("附件不存在或已过期，请重新上传")
        resolved = [rows_by_id[item] for item in ids]
        for row in resolved:
            if not os.path.isfile(attachment_disk_path(row)):
                raise ValueError(f"附件文件已丢失：{row.filename}，请重新上传")
            row.used = True
        db.commit()
        return resolved
    finally:
        db.close()


def attachment_disk_path(attachment: ChatAttachment) -> str:
    from backend.api.resources import CHAT_UPLOAD_DIR

    return str(CHAT_UPLOAD_DIR / attachment.stored_name)


def build_attachment_content(attachment: ChatAttachment) -> AttachmentContent:
    """把单个附件转换为模型侧内容：图片转 data URL，文档取提取文本。"""
    content = AttachmentContent(attachment=attachment)
    path = attachment_disk_path(attachment)
    if attachment.kind == "image":
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            content.parse_error = f"读取图片失败：{exc}"
            return content
        mime = attachment.mime or "image/png"
        content.image_data_url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
        return content

    text = (attachment.extracted_text or "").strip()
    if not text:
        # 兼容早期只落盘未提取文本的附件记录
        try:
            text = extract_document_text(path, attachment.filename)
        except Exception as exc:
            content.parse_error = f"解析附件失败：{exc}"
            return content
    if len(text) > MAX_CHARS_PER_DOCUMENT:
        text = text[:MAX_CHARS_PER_DOCUMENT]
        content.truncated = True
    content.text_block = text
    return content


def build_message_content(
    user_text: str,
    contents: list[AttachmentContent],
) -> str | list[dict]:
    """组装发給模型的消息内容：文本与文档提取合并为一个文本块，图片转为 image_url 块。"""
    doc_blocks: list[str] = []
    remaining = MAX_TOTAL_DOCUMENT_CHARS
    for content in contents:
        if not content.text_block:
            continue
        if remaining <= 0:
            doc_blocks.append(f"【附件文档：{content.attachment.filename}】内容过长，已省略。")
            continue
        text = content.text_block
        if len(text) > remaining:
            text = text[:remaining] + "\n（内容过长，已截断）"
            remaining = 0
        else:
            remaining -= len(text)
        suffix = "\n（内容过长，已截断）" if content.truncated else ""
        doc_blocks.append(f"【附件文档：{content.attachment.filename}】\n{text}{suffix}")

    full_text = user_text
    if doc_blocks:
        full_text = f"{user_text}\n\n---\n以下是用户随消息附上的文档内容：\n\n" + "\n\n".join(doc_blocks)

    image_blocks = []
    skipped_images: list[str] = []
    for content in contents:
        if not content.image_data_url:
            continue
        if not vision_enabled():
            # 上传后开关被关闭等极端情况下不静默丢图，明确告知模型当前只能看到文件名
            skipped_images.append(content.attachment.filename)
            continue
        image_blocks.append(
            {"type": "image_url", "image_url": {"url": content.image_data_url}}
        )
    if skipped_images:
        full_text = (
            f"{full_text}\n\n（用户还上传了图片：{'、'.join(skipped_images)}，"
            "但当前配置的模型不支持图像理解，仅有图片文件名可用。）"
        )
    if not image_blocks:
        return full_text
    return [{"type": "text", "text": full_text}, *image_blocks]


def build_rag_steps(contents: list[AttachmentContent]) -> list[dict]:
    """把附件解析过程转成前端「思考阶段」可视化的 rag_step 事件。"""
    steps: list[dict] = []
    for content in contents:
        filename = content.attachment.filename
        if content.attachment.kind == "image":
            if content.parse_error:
                steps.append({
                    "icon": "image",
                    "label": f"读取图片 {filename}",
                    "detail": content.parse_error,
                })
            else:
                steps.append({
                    "icon": "image",
                    "label": f"读取图片 {filename}",
                    "detail": "已转换为多模态输入",
                })
        elif content.parse_error:
            steps.append({
                "icon": "file-lines",
                "label": f"解析附件 {filename}",
                "detail": content.parse_error,
            })
        else:
            detail = f"提取 {len(content.text_block)} 字"
            if content.truncated:
                detail += "（已截断）"
            steps.append({
                "icon": "file-lines",
                "label": f"解析附件 {filename}",
                "detail": detail,
            })
    return steps


def prune_stale_attachments() -> int:
    """删除超过保留期仍未被任何消息引用的附件（含磁盘文件），避免上传后弃用造成堆积。"""
    deadline = now_for_db() - STALE_UNUSED_TTL
    db = SessionLocal()
    try:
        stale_rows = (
            db.query(ChatAttachment)
            .filter(ChatAttachment.used.is_(False), ChatAttachment.created_at < deadline)
            .all()
        )
        removed = 0
        for row in stale_rows:
            try:
                os.remove(attachment_disk_path(row))
            except OSError:
                pass
            db.delete(row)
            removed += 1
        db.commit()
        return removed
    except Exception as exc:
        db.rollback()
        print(f"清理过期聊天附件失败: {exc}")
        return 0
    finally:
        db.close()
