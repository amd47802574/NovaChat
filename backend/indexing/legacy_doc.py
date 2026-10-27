"""旧版 Word (.doc) 二进制文档的文本提取。

.doc 是 OLE2 复合二进制格式（Word 97-2003），而 docx2txt 只支持 ZIP 结构的 .docx，
因此这里按 antiword → LibreOffice → Word COM 的顺序逐级降级提取文本，
任一方式成功即返回；全部失败时抛出带修复指引的 ValueError。
"""
from __future__ import annotations

import locale
import os
import shutil
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


# (展示名称, 提取函数)，按优先级排列
_EXTRACTORS: tuple[tuple[str, Callable[[str], str | None]], ...] = (
    ("antiword", _extract_with_antiword),
    ("LibreOffice", _convert_with_libreoffice),
    ("Word COM", _convert_with_word_com),
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
