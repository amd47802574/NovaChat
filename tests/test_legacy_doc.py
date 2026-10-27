from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from backend.indexing.document_loader import DocumentLoader
from backend.indexing.legacy_doc import extract_legacy_doc_text

SAMPLE_TEXT = (
    "NovaChat 旧版 Word 兼容性测试。\r"
    "这是一段用于验证 .doc 解析的中文文本。\r"
    "第二段落：系统应能提取此内容。"
)


class LegacyDocRoutingTests(unittest.TestCase):
    """验证 .doc 走专用提取链，且不依赖外部工具即可测试路由与分片。"""

    def test_load_document_routes_doc_through_legacy_extractor(self) -> None:
        with patch(
            "backend.indexing.legacy_doc.extract_legacy_doc_text",
            return_value=SAMPLE_TEXT,
        ) as extractor:
            chunks = DocumentLoader().load_document("fake/path/旧文档.doc", "旧文档.doc")

        extractor.assert_called_once_with("fake/path/旧文档.doc")
        self.assertTrue(chunks)
        self.assertTrue(all(chunk["file_type"] == "Word" for chunk in chunks))
        self.assertTrue(all(chunk["page_number"] == 0 for chunk in chunks))
        joined = "\n".join(chunk["text"] for chunk in chunks)
        self.assertIn("NovaChat 旧版 Word 兼容性测试", joined)

    def test_docx_still_uses_docx2txt_loader(self) -> None:
        with patch(
            "backend.indexing.legacy_doc.extract_legacy_doc_text"
        ) as extractor:
            with self.assertRaises(Exception):
                DocumentLoader().load_document("fake/path/文档.docx", "文档.docx")
        extractor.assert_not_called()

    def test_extract_raises_actionable_error_when_all_channels_fail(self) -> None:
        with (
            patch("backend.indexing.legacy_doc._extract_with_antiword", return_value=None),
            patch("backend.indexing.legacy_doc._convert_with_libreoffice", return_value=None),
            patch("backend.indexing.legacy_doc._convert_with_word_com", return_value=None),
        ):
            with self.assertRaises(ValueError) as ctx:
                extract_legacy_doc_text("whatever.doc")

        message = str(ctx.exception)
        self.assertIn("antiword", message)
        self.assertIn("LibreOffice", message)
        self.assertIn(".docx", message)


@unittest.skipUnless(
    sys.platform == "win32",
    "需要 Windows 上的 Word COM 生成真实 .doc 测试文件",
)
class LegacyDocRealFileTests(unittest.TestCase):
    """集成测试：用本机 Word 生成真实 .doc，走完整提取链（本机命中 antiword）。"""

    temp_dir: str
    doc_path: str

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import pythoncom
            import win32com.client
        except ImportError:
            raise unittest.SkipTest("未安装 pywin32，无法生成 .doc 测试文件")

        cls.temp_dir = tempfile.mkdtemp(prefix="novachat_doc_test_")
        cls.doc_path = os.path.join(cls.temp_dir, "兼容性测试.doc")

        pythoncom.CoInitialize()
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            try:
                doc = word.Documents.Add()
                doc.Content.Text = SAMPLE_TEXT
                try:
                    doc.SaveAs2(cls.doc_path, FileFormat=0)
                except Exception:
                    doc.SaveAs(cls.doc_path, FileFormat=0)
                doc.Close(False)
            finally:
                try:
                    word.Quit()
                except Exception:
                    pass
        except Exception as exc:
            raise unittest.SkipTest(f"本机 Word COM 不可用，跳过集成测试: {exc}") from exc

    @classmethod
    def tearDownClass(cls) -> None:
        if os.path.exists(cls.doc_path):
            os.remove(cls.doc_path)
        os.rmdir(cls.temp_dir)

    def test_extract_real_doc_text(self) -> None:
        text = extract_legacy_doc_text(self.doc_path)
        self.assertIn("NovaChat 旧版 Word 兼容性测试", text)

    def test_load_document_end_to_end(self) -> None:
        chunks = DocumentLoader().load_document(self.doc_path, "兼容性测试.doc")
        self.assertTrue(chunks)
        self.assertTrue(all(chunk["file_type"] == "Word" for chunk in chunks))
        leaf_chunks = [chunk for chunk in chunks if chunk["chunk_level"] == 3]
        self.assertTrue(leaf_chunks)
        joined = "\n".join(chunk["text"] for chunk in chunks)
        self.assertIn("第二段落", joined)


if __name__ == "__main__":
    unittest.main()
