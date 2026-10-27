from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from backend.chat.attachments import (
    MAX_CHARS_PER_DOCUMENT,
    MAX_TOTAL_DOCUMENT_CHARS,
    AttachmentContent,
    build_message_content,
    build_rag_steps,
    detect_kind,
    extension_of,
    mime_for,
    new_stored_name,
)


def _content(filename: str, kind: str, text: str = "", image_url: str = "") -> AttachmentContent:
    """构造不带数据库记录的 AttachmentContent，用于测试纯逻辑。"""

    class _FakeAttachment:
        def __init__(self):
            self.id = f"id-{filename}"
            self.filename = filename
            self.kind = kind
            self.mime = mime_for(filename)

    item = AttachmentContent(attachment=_FakeAttachment())  # type: ignore[arg-type]
    item.text_block = text
    item.image_data_url = image_url
    return item


class AttachmentTypeTests(unittest.TestCase):
    def test_detect_kind_by_extension(self):
        self.assertEqual(detect_kind("截图.PNG"), "image")
        self.assertEqual(detect_kind("report.pdf"), "document")
        self.assertEqual(detect_kind("说明.docx"), "document")
        self.assertEqual(detect_kind("数据.xlsx"), "document")
        self.assertIsNone(detect_kind("程序.exe"))
        self.assertIsNone(detect_kind("没有后缀"))

    def test_extension_and_mime(self):
        self.assertEqual(extension_of("a.TXT"), ".txt")
        self.assertEqual(mime_for("a.png"), "image/png")
        self.assertEqual(mime_for("a.docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertEqual(mime_for("a.unknownext"), "application/octet-stream")

    def test_stored_name_does_not_leak_original_name(self):
        stored = new_stored_name("../../etc/passwd.png")
        self.assertNotIn("/", stored)
        self.assertNotIn("..", stored)
        self.assertTrue(stored.endswith(".png"))
        self.assertNotEqual(stored, new_stored_name("../../etc/passwd.png"))


class BuildMessageContentTests(unittest.TestCase):
    def test_plain_text_only_when_no_attachments(self):
        self.assertEqual(build_message_content("你好", []), "你好")

    def test_document_text_is_inlined_with_filename(self):
        content = build_message_content(
            "帮我总结",
            [_content("报告.pdf", "document", text="这是正文内容。")],
        )
        self.assertIsInstance(content, str)
        self.assertIn("帮我总结", content)
        self.assertIn("【附件文档：报告.pdf】", content)
        self.assertIn("这是正文内容。", content)

    def test_image_becomes_multimodal_blocks(self):
        with patch("backend.chat.attachments.vision_enabled", return_value=True):
            content = build_message_content(
                "这张图里是什么",
                [_content("cat.png", "image", image_url="data:image/png;base64,AAA")],
            )
        self.assertIsInstance(content, list)
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[0]["text"], "这张图里是什么")
        self.assertEqual(content[1]["type"], "image_url")
        self.assertEqual(content[1]["image_url"]["url"], "data:image/png;base64,AAA")

    def test_mixed_document_and_image(self):
        with patch("backend.chat.attachments.vision_enabled", return_value=True):
            content = build_message_content(
                "对比一下",
                [
                    _content("a.pdf", "document", text="文档正文"),
                    _content("b.jpg", "image", image_url="data:image/jpeg;base64,BBB"),
                ],
            )
        self.assertIsInstance(content, list)
        self.assertIn("文档正文", content[0]["text"])
        self.assertEqual(content[1]["type"], "image_url")

    def test_image_is_skipped_with_notice_when_vision_disabled(self):
        with patch("backend.chat.attachments.vision_enabled", return_value=False):
            content = build_message_content(
                "看图",
                [_content("cat.png", "image", image_url="data:image/png;base64,AAA")],
            )
        self.assertIsInstance(content, str)
        self.assertIn("不支持图像理解", content)
        self.assertIn("cat.png", content)

    def test_single_document_truncation(self):
        long_text = "字" * (MAX_CHARS_PER_DOCUMENT + 500)
        item = _content("长文.txt", "document", text=long_text[:MAX_CHARS_PER_DOCUMENT])
        item.truncated = True
        content = build_message_content("总结", [item])
        self.assertIn("已截断", content)

    def test_total_document_budget_limits_content(self):
        # 两份各占一半预算的文档，第二份应因超预算被截断/省略
        half = "甲" * (MAX_TOTAL_DOCUMENT_CHARS // 2)
        contents = [
            _content("一.txt", "document", text=half),
            _content("二.txt", "document", text=half),
            _content("三.txt", "document", text="尾巴内容"),
        ]
        content = build_message_content("总结", contents)
        self.assertIn("【附件文档：一.txt】", content)
        self.assertIn("已省略", content)

    def test_failed_parse_document_is_skipped_from_content(self):
        item = _content("坏.pdf", "document")
        item.parse_error = "解析失败"
        self.assertEqual(build_message_content("问题", [item]), "问题")


class BuildRagStepsTests(unittest.TestCase):
    def test_steps_describe_each_attachment(self):
        ok_doc = _content("报告.pdf", "document", text="正文")
        ok_image = _content("图.png", "image", image_url="data:image/png;base64,AAA")
        bad_doc = _content("坏.docx", "document")
        bad_doc.parse_error = "解析附件失败"

        steps = build_rag_steps([ok_doc, ok_image, bad_doc])
        labels = [step["label"] for step in steps]

        self.assertEqual(labels, ["解析附件 报告.pdf", "读取图片 图.png", "解析附件 坏.docx"])
        self.assertIn("提取 2 字", steps[0]["detail"])
        self.assertEqual(steps[1]["detail"], "已转换为多模态输入")
        self.assertIn("解析附件失败", steps[2]["detail"])


class DocumentExtractionTests(unittest.TestCase):
    def test_txt_and_markdown_extraction(self):
        from backend.chat.attachments import extract_document_text

        with tempfile.TemporaryDirectory() as tmp:
            txt_path = Path(tmp) / "a.txt"
            txt_path.write_text("第一行\n第二行", encoding="utf-8")
            self.assertEqual(extract_document_text(str(txt_path), "a.txt"), "第一行\n第二行")

            md_path = Path(tmp) / "b.md"
            md_path.write_text("# 标题\n\n正文", encoding="utf-8")
            self.assertIn("# 标题", extract_document_text(str(md_path), "b.md"))

    def test_unsupported_extension_raises(self):
        from backend.chat.attachments import extract_document_text

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.bin"
            path.write_bytes(b"\x00\x01")
            with self.assertRaises(ValueError):
                extract_document_text(str(path), "a.bin")


if __name__ == "__main__":
    unittest.main()
