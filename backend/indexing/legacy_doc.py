"""旧版 Word (.doc) 二进制文档的文本提取。

.doc 是 OLE2 复合二进制格式（Word 97-2003），而 docx2txt 只支持 ZIP 结构的 .docx，
因此这里按 antiword → LibreOffice → Word COM → 纯 Python OLE 解析的顺序逐级降级提取文本，
任一方式成功即返回；全部失败时抛出带修复指引的 ValueError。

前三级依赖外部工具（antiword / LibreOffice / 本机 Word），最后一级是纯 Python 兜底：
直接解析 OLE2 容器内 WordDocument 流的 piece table，无需安装任何外部软件，
可覆盖绝大多数常规文档（含快速保存文档）；复杂排版（文本框、字段代码）可能混入少量噪音。
"""
from __future__ import annotations

import locale
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Callable

_EXTRACT_TIMEOUT_SECONDS = 120
# wdFormatDocumentDefault：另存为 .docx
_WD_FORMAT_XML_DOCUMENT = 16

_SOFFICE_FALLBACK_PATHS = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)


def _find_soffice() -> str | None:
    soffice = shutil.which("soffice") or shutil.which("soffice.exe")
    if soffice:
        return soffice
    for candidate in _SOFFICE_FALLBACK_PATHS:
        if os.path.isfile(candidate):
            return candidate
    return None


def _extract_with_antiword(file_path: str) -> str | None:
    """antiword 直接抽取文本（Linux/Windows 通用，要求 PATH 中存在 antiword）。"""
    exe = shutil.which("antiword")
    if not exe:
        return None
    result = subprocess.run(
        [exe, file_path],
        capture_output=True,
        timeout=_EXTRACT_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return result.stdout.decode(locale.getpreferredencoding(False), errors="replace")


def _convert_with_libreoffice(file_path: str) -> str | None:
    """LibreOffice 无头模式把 .doc 转成 .docx，再交给 docx2txt 提取。"""
    soffice = _find_soffice()
    if not soffice:
        return None
    with tempfile.TemporaryDirectory(prefix="novachat_doc_") as work_dir:
        # 独立用户配置目录，避免与正在运行的 LibreOffice 实例冲突
        profile_dir = Path(work_dir) / "profile"
        profile_dir.mkdir()
        result = subprocess.run(
            [
                soffice,
                f"-env:UserInstallation={profile_dir.as_uri()}",
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                work_dir,
                file_path,
            ],
            capture_output=True,
            timeout=_EXTRACT_TIMEOUT_SECONDS,
            check=False,
        )
        converted = Path(work_dir) / f"{Path(file_path).stem}.docx"
        if result.returncode != 0 or not converted.exists():
            return None

        import docx2txt

        return docx2txt.process(str(converted))


def _convert_with_word_com(file_path: str) -> str | None:
    """Windows 上借助本机 Word（COM 自动化）把 .doc 另存为 .docx 后提取。"""
    if sys.platform != "win32":
        return None
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return None

    pythoncom.CoInitialize()
    word = None
    try:
        try:
            # DispatchEx 启动独立实例，避免挂到用户已打开的 Word 窗口上
            word = win32com.client.DispatchEx("Word.Application")
        except Exception:
            return None
        word.Visible = False
        word.DisplayAlerts = 0
        with tempfile.TemporaryDirectory(prefix="novachat_doc_") as work_dir:
            docx_path = str(Path(work_dir) / f"{uuid.uuid4().hex}.docx")
            doc = word.Documents.Open(
                os.path.abspath(file_path),
                ConfirmConversions=False,
                ReadOnly=True,
                AddToRecentFiles=False,
                Visible=False,
            )
            try:
                try:
                    doc.SaveAs2(docx_path, FileFormat=_WD_FORMAT_XML_DOCUMENT)
                except Exception:
                    # SaveAs2 从 Word 2010 起才提供，老版本回退 SaveAs
                    doc.SaveAs(docx_path, FileFormat=_WD_FORMAT_XML_DOCUMENT)
            finally:
                doc.Close(False)

            import docx2txt

            return docx2txt.process(docx_path)
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                # Word 进程退出时偶发 RPC 失败，文件已转换完成，忽略即可
                pass
        pythoncom.CoUninitialize()


# ---- 纯 Python 兜底：直接解析 Word 97-2003 二进制格式 ----
# FIB（File Information Block）中的关键偏移，均位于 WordDocument 流内
_FIB_W_IDENT = 0xA5EC  # wIdent：Word 二进制格式魔数
_FIB_FLAGS_OFFSET = 0x000A  # FibBase.flags，bit 9 (0x0200) 指定表流为 1Table/0Table
_FIB_CCP_TEXT_OFFSET = 0x004C  # fibRgLw97.ccpText：主文档正文字符数
_FIB_FC_CLX_OFFSET = 0x01A2  # fibRgFcLcb97.fcClx/lcbClx：CLX 在表流中的位置


def _parse_doc_streams(word: bytes, table: bytes) -> str | None:
    """从 WordDocument 流与表流的原始字节解析主文档文本（piece table 方式）。

    仅实现 Word 97-2003 二进制格式的核心路径：FIB → CLX → PlcPcd → 文本片段，
    常规与快速保存文档均可覆盖；遇到无法识别的结构时返回 None 交由调用方降级。
    """
    if len(word) < _FIB_FC_CLX_OFFSET + 8:
        return None
    if struct.unpack_from("<H", word, 0x0000)[0] != _FIB_W_IDENT:
        return None

    ccp_text = struct.unpack_from("<I", word, _FIB_CCP_TEXT_OFFSET)[0]
    fc_clx, lcb_clx = struct.unpack_from("<II", word, _FIB_FC_CLX_OFFSET)
    if lcb_clx == 0 or fc_clx + lcb_clx > len(table):
        return None

    # CLX：跳过若干 Prc（0x01 前缀），定位 Pcdt（0x02 前缀，其后 4 字节为 PlcPcd 长度）
    pos, end = fc_clx, fc_clx + lcb_clx
    plc_pcd: bytes | None = None
    while pos < end:
        clxt = table[pos]
        if clxt == 0x01:
            # Prc：clxt + 保留字节 + cbGrpprl(2B) + GrpPrl(cbGrpprl 字节)
            if pos + 4 > end:
                return None
            cb = struct.unpack_from("<H", table, pos + 2)[0]
            pos += 4 + cb
        elif clxt == 0x02:
            if pos + 5 > end:
                return None
            lcb = struct.unpack_from("<I", table, pos + 1)[0]
            plc_pcd = table[pos + 5 : pos + 5 + lcb]
            break
        else:
            return None
    if not plc_pcd:
        return None

    # PlcPcd：(n+1) 个 CP(4B) + n 个 Pcd(8B)；Pcd 内 fc 字段位于偏移 +2
    if (len(plc_pcd) - 4) % 12 != 0:
        return None
    n = (len(plc_pcd) - 4) // 12
    if n <= 0:
        return None
    cps = struct.unpack_from(f"<{n + 1}I", plc_pcd, 0)
    if any(cps[i] >= cps[i + 1] for i in range(n)):
        return None

    pieces: list[str] = []
    for i in range(n):
        cp_start, cp_end = cps[i], cps[i + 1]
        fc_raw = struct.unpack_from("<I", plc_pcd, 4 * (n + 1) + i * 8 + 2)[0]
        fc = fc_raw & 0x3FFFFFFF
        if fc_raw & 0x40000000:
            # 8-bit 压缩文本：fc 为逻辑偏移（实际字节偏移为其一半），按 cp1252 解码
            offset, size = fc // 2, cp_end - cp_start
            if offset + size > len(word):
                return None
            pieces.append(word[offset : offset + size].decode("cp1252", errors="replace"))
        else:
            # 16-bit 文本：UTF-16LE，每字符 2 字节
            offset, size = fc, (cp_end - cp_start) * 2
            if offset + size > len(word):
                return None
            pieces.append(word[offset : offset + size].decode("utf-16-le", errors="replace"))

    full = "".join(pieces)
    # 主文档正文对应 CP [0, ccpText)，其后是脚注/页眉等附属文本
    if 0 < ccp_text < len(full):
        full = full[:ccp_text]

    # 规范化 Word 控制字符：\r 段落、\x07 表格单元格/行、\x0b 软换行、\x0c 分页
    for control in ("\x07", "\x0b", "\x0c"):
        full = full.replace(control, "\n")
    full = full.replace("\r", "\n")
    # 丢弃其余不可打印控制字符（字段标记 \x13-\x15、可选连字符 \x1e 等）
    cleaned = "".join(ch for ch in full if ch in "\t\n" or ch >= " ")
    return cleaned.strip() or None


def _extract_with_olefile(file_path: str) -> str | None:
    """纯 Python 兜底：用 olefile 读取 OLE2 容器，直接解析 WordDocument 流。"""
    try:
        import olefile
    except ImportError:
        return None

    try:
        with olefile.OleFileIO(file_path) as ole:
            if not ole.exists("WordDocument"):
                return None
            word = ole.openstream("WordDocument").read()
            if len(word) < _FIB_FC_CLX_OFFSET + 8:
                return None
            # fWhichTblStm（FibBase.flags bit 9）决定表流名，读不到时尝试另一个
            flags = struct.unpack_from("<H", word, _FIB_FLAGS_OFFSET)[0]
            table_name = "1Table" if flags & 0x0200 else "0Table"
            if not ole.exists(table_name):
                table_name = "1Table" if table_name == "0Table" else "0Table"
                if not ole.exists(table_name):
                    return None
            table = ole.openstream(table_name).read()
        return _parse_doc_streams(word, table)
    except Exception:
        return None


# (展示名称, 提取函数)，按优先级排列
_EXTRACTORS: tuple[tuple[str, Callable[[str], str | None]], ...] = (
    ("antiword", _extract_with_antiword),
    ("LibreOffice", _convert_with_libreoffice),
    ("Word COM", _convert_with_word_com),
    ("纯 Python OLE 解析", _extract_with_olefile),
)


def extract_legacy_doc_text(file_path: str) -> str:
    """提取旧版 .doc 的文本内容，所有方式均失败时抛出 ValueError。"""
    failures: list[str] = []
    for name, extract in _EXTRACTORS:
        try:
            text = extract(file_path)
        except Exception as exc:
            failures.append(f"{name} 调用异常: {exc}")
            continue
        if text and text.strip():
            return text
        failures.append(f"{name} 不可用或未提取到文本")

    raise ValueError(
        "旧版 Word (.doc) 解析失败，所有可用方式均未成功（"
        + "；".join(failures)
        + "）。请安装 antiword 或 LibreOffice，或将文档另存为 .docx 后重新上传。"
    )
