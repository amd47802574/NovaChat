"""聊天附件在流式对话中的端到端行为：模型输入增强 + 历史元数据落库。"""
from __future__ import annotations

import asyncio
import importlib
import json
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessageChunk

from backend.chat.attachments import AttachmentContent

service = importlib.import_module("backend.chat.service")


class FakeStorage:
    def __init__(self, messages=None, metadata=None):
        self.messages = list(messages or [])
        self.metadata = dict(metadata or {})
        self.saves = []

    def load_with_meta(self, user_id, session_id):
        return list(self.messages), dict(self.metadata)

    def save(self, user_id, session_id, messages, metadata=None, extra_message_data=None):
        self.messages = list(messages)
        if metadata is not None:
            self.metadata = {**self.metadata, **metadata}
        self.saves.append({
            "messages": list(messages),
            "metadata": metadata,
            "extra_message_data": extra_message_data,
        })

    def update_session(self, user_id, session_id, updates):
        self.metadata.update(updates)


class FakeStreamAgent:
    def __init__(self, ctx, captured, chunks=None):
        self.ctx = ctx
        self.captured = captured
        self.chunks = chunks or ["好的"]

    async def astream(self, payload, stream_mode=None, config=None):
        self.captured.append(payload["messages"][-1].content)
        for chunk in self.chunks:
            yield AIMessageChunk(content=chunk), {}


class FakeAttachment:
    def __init__(self, attachment_id, filename, kind, mime):
        self.id = attachment_id
        self.filename = filename
        self.kind = kind
        self.mime = mime


def _make_content(filename, kind, text="", image_url=""):
    attachment = FakeAttachment(f"id-{filename}", filename, kind, "text/plain")
    content = AttachmentContent(attachment=attachment)  # type: ignore[arg-type]
    content.text_block = text
    content.image_data_url = image_url
    return content


def _parse_sse_events(chunks):
    events = []
    for chunk in chunks:
        payload = chunk.strip()
        if not payload.startswith("data: "):
            continue
        data = payload[len("data: "):]
        events.append({"type": "DONE"} if data == "[DONE]" else json.loads(data))
    return events


async def _collect_stream(*args, **kwargs):
    chunks = []
    async for chunk in service.chat_with_agent_stream(*args, **kwargs):
        chunks.append(chunk)
    # 让会话标题任务及其完成回调在 patch 生效期间跑完，
    # 否则回调会落到真实数据库连接上并拖慢测试。
    await asyncio.sleep(0.05)
    return chunks


class ChatAttachmentStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_document_attachment_enriches_model_input_but_persists_plain_text(self):
        fake_storage = FakeStorage()
        captured: list = []
        doc_content = _make_content("报告.pdf", "document", text="报告正文：营收增长 20%。")

        with (
            patch.object(service, "storage", fake_storage),
            patch.object(service, "build_attachment_content", return_value=doc_content),
            patch.object(
                service,
                "create_agent_for_request",
                lambda ctx: FakeStreamAgent(ctx, captured),
            ),
            patch.object(service, "generate_session_title", AsyncMock(return_value="报告分析")),
            patch.object(service, "update_persistent_note", AsyncMock(return_value="note")),
        ):
            chunks = await _collect_stream("帮我总结", "u", "s", attachments=[object()])

        # 模型侧拿到的是带文档正文的内容
        self.assertEqual(1, len(captured))
        self.assertIsInstance(captured[0], str)
        self.assertIn("帮我总结", captured[0])
        self.assertIn("报告正文：营收增长 20%。", captured[0])

        # 历史落库保留纯文本，附件元数据挂在用户消息上
        self.assertEqual("帮我总结", fake_storage.messages[-2].content)
        extra = fake_storage.saves[-1]["extra_message_data"]
        self.assertEqual(len(fake_storage.messages), len(extra))
        user_meta = extra[-2]["attachments"]
        self.assertEqual("报告.pdf", user_meta[0]["filename"])
        self.assertEqual("document", user_meta[0]["kind"])
        self.assertEqual("id-报告.pdf", user_meta[0]["id"])

        # 前端「思考阶段」能看到附件解析过程
        events = _parse_sse_events(chunks)
        rag_labels = [
            event["step"]["label"]
            for event in events
            if event.get("type") == "rag_step"
        ]
        self.assertIn("解析附件 报告.pdf", rag_labels)

    async def test_image_attachment_produces_multimodal_message(self):
        fake_storage = FakeStorage()
        captured: list = []
        image_content = _make_content(
            "图.png", "image", image_url="data:image/png;base64,AAAA"
        )

        with (
            patch.object(service, "storage", fake_storage),
            patch.object(service, "build_attachment_content", return_value=image_content),
            patch("backend.chat.attachments.vision_enabled", return_value=True),
            patch.object(
                service,
                "create_agent_for_request",
                lambda ctx: FakeStreamAgent(ctx, captured),
            ),
            patch.object(service, "generate_session_title", AsyncMock(return_value="看图")),
            patch.object(service, "update_persistent_note", AsyncMock(return_value="note")),
        ):
            await _collect_stream("这张图是什么", "u", "s", attachments=[object()])

        self.assertEqual(1, len(captured))
        blocks = captured[0]
        self.assertIsInstance(blocks, list)
        self.assertEqual("text", blocks[0]["type"])
        self.assertEqual("这张图是什么", blocks[0]["text"])
        self.assertEqual("image_url", blocks[1]["type"])
        self.assertEqual("data:image/png;base64,AAAA", blocks[1]["image_url"]["url"])

        user_meta = fake_storage.saves[-1]["extra_message_data"][-2]["attachments"]
        self.assertEqual("image", user_meta[0]["kind"])

    async def test_no_attachments_keeps_plain_string_content(self):
        fake_storage = FakeStorage()
        captured: list = []

        with (
            patch.object(service, "storage", fake_storage),
            patch.object(
                service,
                "create_agent_for_request",
                lambda ctx: FakeStreamAgent(ctx, captured),
            ),
            patch.object(service, "generate_session_title", AsyncMock(return_value="标题")),
            patch.object(service, "update_persistent_note", AsyncMock(return_value="note")),
        ):
            await _collect_stream("普通问题", "u", "s")

        self.assertEqual("普通问题", captured[0])
        for slot in fake_storage.saves[-1]["extra_message_data"]:
            self.assertIsNone(slot or None)


class ErrorHumanizeTests(unittest.TestCase):
    def test_extracts_message_from_sse_error_payload(self):
        raw = (
            'data: {"error":{"code":"invalid_parameter_error","message":'
            '"The current model only supports text modality","type":"invalid_request_error"},'
            '"id":"chatcmpl-1"}'
        )
        self.assertEqual(
            service.humanize_provider_error(raw),
            "The current model only supports text modality",
        )

    def test_extracts_message_from_plain_json_error(self):
        self.assertEqual(
            service.humanize_provider_error('{"detail": "附件解析失败"}'),
            "附件解析失败",
        )

    def test_keeps_unparsable_text_unchanged(self):
        self.assertEqual(
            service.humanize_provider_error("connection reset by peer"),
            "connection reset by peer",
        )


class ExtraMessageDataTests(unittest.TestCase):
    def test_attachments_go_to_user_message_and_trace_to_ai_message(self):
        metas = [{"id": "a", "filename": "a.pdf", "kind": "document", "mime": None}]
        extra = service._build_extra_message_data(4, {"tool_used": True}, metas)

        self.assertEqual(4, len(extra))
        self.assertIsNone(extra[0])
        self.assertIsNone(extra[1])
        self.assertEqual(metas, extra[2]["attachments"])
        self.assertEqual({"tool_used": True}, extra[3]["rag_trace"])

    def test_without_attachments_only_trace_is_written(self):
        extra = service._build_extra_message_data(2, {"tool_used": False}, [])
        self.assertIsNone(extra[0])
        self.assertEqual({"tool_used": False}, extra[1]["rag_trace"])


if __name__ == "__main__":
    unittest.main()
