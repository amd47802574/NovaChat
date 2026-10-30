from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

from backend.indexing.document_loader import DocumentLoader
from backend.indexing.legacy_doc import _parse_doc_streams, extract_legacy_doc_text

SAMPLE_TEXT = (
    "NovaChat 旧版 Word 兼容性测试。\r"
    "这是一段用于验证 .doc 解析的中文文本。\r"
    "第二段落：系统应能提取此内容。"
)


def _build_streams(text: str, *, compressed: bool = False) -> tuple[bytes, bytes]:
    """构造最小合法的 WordDocument 流与表流字节（单 piece，文本从 0x0200 开始）。"""
    if compressed:
        raw = text.encode("cp1252")
        fc_raw = 0x0200 * 2 | 0x40000000
    else:
        raw = text.encode("utf-16-le")
        fc_raw = 0x0200

    # PlcPcd：CP[0]=0, CP[1]=n_chars；Pcd = flags(2B) + fc(4B) + prm(2B)
    plc_pcd = struct.pack("<II", 0, len(text)) + struct.pack("<HIH", 0, fc_raw, 0)
    # 表流：Pcdt = 0x02 + lcb(4B) + PlcPcd
    table = struct.pack("<BI", 0x02, len(plc_pcd)) + plc_pcd

    word = bytearray(0x0200)
    struct.pack_into("<H", word, 0x0000, 0xA5EC)  # wIdent
    struct.pack_into("<H", word, 0x0002, 0x00C1)  # nFib（Word 97）
    struct.pack_into("<H", word, 0x000A, 0x0000)  # flags → 0Table
    struct.pack_into("<I", word, 0x004C, len(text))  # ccpText
    struct.pack_into("<II", word, 0x01A2, 0, len(table))  # fcClx=0, lcbClx
    word += raw
    return bytes(word), table


class PieceTableParsingTests(unittest.TestCase):
    """纯 Python 兜底解析器：直接喂 WordDocument/表流字节验证 piece table 解析。"""

    def test_parses_utf16_text(self) -> None:
        word, table = _build_streams("Hello 中文文本")
        self.assertEqual(_parse_doc_streams(word, table), "Hello 中文文本")

    def test_parses_8bit_compressed_text(self) -> None:
        word, table = _build_streams("Legacy cp1252 text", compressed=True)
        self.assertEqual(_parse_doc_streams(word, table), "Legacy cp1252 text")

    def test_normalizes_word_control_chars(self) -> None:
        word, table = _build_streams("第一段\r第二段\x07表格\x0c尾")
        self.assertEqual(_parse_doc_streams(word, table), "第一段\n第二段\n表格\n尾")

    def test_truncates_to_main_document_text(self) -> None:
        # ccpText 小于全部文本长度时，只保留主文档正文
        word, table = _build_streams("正文内容页眉噪音")
        word = bytearray(word)
        struct.pack_into("<I", word, 0x004C, 4)
        self.assertEqual(_parse_doc_streams(bytes(word), table), "正文内容")

    def test_rejects_wrong_magic(self) -> None:
        word, table = _build_streams("x")
        word = bytearray(word)
        struct.pack_into("<H", word, 0x0000, 0x1234)
        self.assertIsNone(_parse_doc_streams(bytes(word), table))

    def test_returns_none_when_piece_out_of_range(self) -> None:
        word, table = _build_streams("x")
        # 把 fc 指到 WordDocument 流之外
        plc_pcd = struct.pack("<II", 0, 1) + struct.pack("<HIH", 0, 0x7FFFFFF0, 0)
        table = struct.pack("<BI", 0x02, len(plc_pcd)) + plc_pcd
        self.assertIsNone(_parse_doc_streams(word, table))

    def test_returns_none_on_empty_text(self) -> None:
        word, table = _build_streams("   ")
        self.assertIsNone(_parse_doc_streams(word, table))


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
            patch("backend.indexing.legacy_doc._extract_with_olefile", return_value=None),
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

    def test_pure_python_fallback_extracts_real_doc(self) -> None:
        """屏蔽全部外部工具，验证纯 Python OLE 解析能读取 Word 生成的真实 .doc。"""
        with (
            patch("backend.indexing.legacy_doc._extract_with_antiword", return_value=None),
            patch("backend.indexing.legacy_doc._convert_with_libreoffice", return_value=None),
            patch("backend.indexing.legacy_doc._convert_with_word_com", return_value=None),
        ):
            text = extract_legacy_doc_text(self.doc_path)
        self.assertIn("NovaChat 旧版 Word 兼容性测试", text)
        self.assertIn("第二段落", text)

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
