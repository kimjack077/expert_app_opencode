"""
document_parser.py — 知识库文档解析引擎 (Markdown 优先)

解析策略：
- PDF    → pymupdf4llm.to_markdown()  （保留标题层级、表格、列表）
- DOCX   → markitdown                 （微软原生格式，层级还原好）
- DOC    → markitdown                 （旧格式，能力有限）
- XLSX   → markitdown                 （按工作表输出 Markdown 表格）
- TXT    → 简单包装，不做额外转换
- 其他   → 兜底：UTF-8 解码后包装

所有解析器均在线程池中运行，避免阻塞事件循环。
"""

import os
import re
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import settings

ALLOWED_DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx"}
ALLOWED_DOC_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class DocumentParser:
    def __init__(self):
        self.max_file_size = settings.MAX_FILE_SIZE

    def validate_document(self, file: UploadFile) -> None:
        if file.size and file.size > self.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"文件过大，最大支持 {self.max_file_size // 1024 // 1024}MB",
            )
        ext = Path(file.filename).suffix.lower() if file.filename else ""
        if ext not in ALLOWED_DOC_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型，支持: {', '.join(ALLOWED_DOC_EXTENSIONS)}",
            )

    async def parse_document(self, file: UploadFile) -> Tuple[str, dict]:
        """
        解析上传的文档，返回 (markdown_content, metadata)。
        metadata 包含 filename、size、extension、char_count。
        """
        self.validate_document(file)

        content = await file.read()
        ext = Path(file.filename).suffix.lower() if file.filename else ""

        metadata = {
            "filename": file.filename,
            "size": len(content),
            "extension": ext,
        }

        if ext == ".txt":
            md_content = self._txt_to_markdown(content)
        elif ext == ".pdf":
            md_content = await run_in_threadpool(self._pdf_to_markdown, content)
        elif ext in (".doc", ".docx"):
            md_content = await run_in_threadpool(self._word_to_markdown, content, ext)
        elif ext in (".xls", ".xlsx"):
            md_content = await run_in_threadpool(self._excel_to_markdown, content, ext)
        else:
            md_content = content.decode("utf-8", errors="ignore")

        metadata["char_count"] = len(md_content)
        return md_content, metadata

    # ------------------------------------------------------------------ #
    # PDF → Markdown (pymupdf4llm, 首选)                                   #
    # ------------------------------------------------------------------ #
    def _pdf_to_markdown(self, content: bytes) -> str:
        """使用 pymupdf4llm 将 PDF 转为结构化 Markdown。"""
        try:
            import pymupdf4llm  # noqa: PLC0415

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                md = pymupdf4llm.to_markdown(tmp_path, show_progress=False)
                return self._clean_markdown(md)
            finally:
                os.unlink(tmp_path)

        except ImportError:
            # 回退：PyMuPDF 原始文本，简单包装为 Markdown
            return self._pdf_fallback(content)
        except Exception as e:
            return f"[PDF解析失败: {e}]"

    def _pdf_fallback(self, content: bytes) -> str:
        """pymupdf4llm 不可用时的兜底：PyMuPDF 提取文本。"""
        try:
            import fitz  # noqa: PLC0415

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                doc = fitz.open(tmp_path)
                pages = []
                for i, page in enumerate(doc, 1):
                    text = page.get_text().strip()
                    if text:
                        pages.append(f"## 第 {i} 页\n\n{text}")
                doc.close()
                return "\n\n".join(pages)
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            return f"[PDF解析失败: {e}]"

    # ------------------------------------------------------------------ #
    # DOCX/DOC → Markdown (markitdown, 首选)                               #
    # ------------------------------------------------------------------ #
    def _word_to_markdown(self, content: bytes, ext: str) -> str:
        """使用 markitdown 将 Word 文档转为 Markdown。"""
        try:
            from markitdown import MarkItDown  # noqa: PLC0415

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                md_converter = MarkItDown()
                result = md_converter.convert(tmp_path)
                return self._clean_markdown(result.text_content)
            finally:
                os.unlink(tmp_path)

        except ImportError:
            return self._word_fallback(content, ext)
        except Exception as e:
            return self._word_fallback(content, ext)

    def _word_fallback(self, content: bytes, ext: str) -> str:
        """markitdown 不可用时的兜底：python-docx 提取文本，手工包装为 Markdown。"""
        try:
            from docx import Document  # noqa: PLC0415

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                doc = Document(tmp_path)
                parts = []

                for para in doc.paragraphs:
                    text = para.text.strip()
                    if not text:
                        continue
                    style_name = (para.style.name or "").lower()
                    if "heading 1" in style_name:
                        parts.append(f"# {text}")
                    elif "heading 2" in style_name:
                        parts.append(f"## {text}")
                    elif "heading 3" in style_name:
                        parts.append(f"### {text}")
                    elif "heading" in style_name:
                        parts.append(f"#### {text}")
                    else:
                        parts.append(text)

                for table in doc.tables:
                    if not table.rows:
                        continue
                    header = [cell.text.strip() for cell in table.rows[0].cells]
                    parts.append("\n| " + " | ".join(header) + " |")
                    parts.append("| " + " | ".join(["---"] * len(header)) + " |")
                    for row in table.rows[1:]:
                        cells = [cell.text.strip() for cell in row.cells]
                        parts.append("| " + " | ".join(cells) + " |")

                return "\n\n".join(parts)
            finally:
                os.unlink(tmp_path)
        except ImportError:
            return "[Word解析需要安装python-docx库: pip install python-docx]"
        except Exception as e:
            return f"[Word解析失败: {e}]"

    # ------------------------------------------------------------------ #
    # XLSX/XLS → Markdown (markitdown, 首选)                               #
    # ------------------------------------------------------------------ #
    def _excel_to_markdown(self, content: bytes, ext: str) -> str:
        """使用 markitdown 将 Excel 文件转为 Markdown 表格。"""
        try:
            from markitdown import MarkItDown  # noqa: PLC0415

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                md_converter = MarkItDown()
                result = md_converter.convert(tmp_path)
                return self._clean_markdown(result.text_content)
            finally:
                os.unlink(tmp_path)

        except ImportError:
            return self._excel_fallback(content, ext)
        except Exception as e:
            return self._excel_fallback(content, ext)

    def _excel_fallback(self, content: bytes, ext: str) -> str:
        """markitdown 不可用时的兜底：openpyxl 输出 Markdown 表格。"""
        try:
            import openpyxl  # noqa: PLC0415

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                wb = openpyxl.load_workbook(tmp_path, data_only=True)
                parts = []

                for sheet_name in wb.sheetnames:
                    sheet = wb[sheet_name]
                    parts.append(f"## 工作表：{sheet_name}\n")

                    rows_data = [
                        [str(cell) if cell is not None else "" for cell in row]
                        for row in sheet.iter_rows(values_only=True)
                    ]
                    # 过滤全空行
                    rows_data = [r for r in rows_data if any(c.strip() for c in r)]

                    if not rows_data:
                        continue

                    # 第一行作为表头
                    header = rows_data[0]
                    parts.append("| " + " | ".join(header) + " |")
                    parts.append("| " + " | ".join(["---"] * len(header)) + " |")
                    for row in rows_data[1:]:
                        parts.append("| " + " | ".join(row) + " |")

                return "\n\n".join(parts)
            finally:
                os.unlink(tmp_path)
        except ImportError:
            return "[Excel解析需要安装openpyxl库: pip install openpyxl]"
        except Exception as e:
            return f"[Excel解析失败: {e}]"

    # ------------------------------------------------------------------ #
    # TXT → Markdown                                                       #
    # ------------------------------------------------------------------ #
    def _txt_to_markdown(self, content: bytes) -> str:
        """将纯文本解码，简单识别标题行（全大写或短行后跟空行）包装为 Markdown。"""
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("gbk")
            except UnicodeDecodeError:
                text = content.decode("utf-8", errors="ignore")
        return text  # TXT 本身不做格式转换，直接返回

    # ------------------------------------------------------------------ #
    # 工具方法                                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clean_markdown(md: str) -> str:
        """清理 Markdown 文本：
        - 去除多余连续空行（超过 2 个合并为 2 个）
        - 去除纯分隔线堆叠
        - 去除行末多余空格
        """
        # 去除行末空格
        md = "\n".join(line.rstrip() for line in md.splitlines())
        # 多于 2 个连续空行合并为 2 个
        md = re.sub(r"\n{3,}", "\n\n", md)
        return md.strip()


document_parser = DocumentParser()
