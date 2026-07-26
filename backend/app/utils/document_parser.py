import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException
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
        self.validate_document(file)
        
        content = await file.read()
        ext = Path(file.filename).suffix.lower() if file.filename else ""
        
        metadata = {
            "filename": file.filename,
            "size": len(content),
            "extension": ext,
        }

        text_content = ""

        # 这些解析器是同步 CPU 密集操作（PyMuPDF / python-docx / openpyxl），
        # 必须卸载到线程池；否则解析大文件期间整个事件循环被占用，
        # 所有并发请求（含 Agent SSE 流）都会卡住。
        if ext == ".txt":
            text_content = self._parse_text(content)
        elif ext == ".pdf":
            text_content = await run_in_threadpool(self._parse_pdf, content)
        elif ext in [".doc", ".docx"]:
            text_content = await run_in_threadpool(self._parse_word, content, ext)
        elif ext in [".xls", ".xlsx"]:
            text_content = await run_in_threadpool(self._parse_excel, content, ext)
        else:
            text_content = content.decode("utf-8", errors="ignore")

        return text_content, metadata

    def _parse_text(self, content: bytes) -> str:
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return content.decode("gbk")
            except UnicodeDecodeError:
                return content.decode("utf-8", errors="ignore")

    def _parse_pdf(self, content: bytes) -> str:
        try:
            import fitz
            
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                doc = fitz.open(tmp_path)
                text_parts = []
                for page in doc:
                    text_parts.append(page.get_text())
                doc.close()
                return "\n\n".join(text_parts)
            finally:
                os.unlink(tmp_path)

        except ImportError:
            return "[PDF解析需要安装PyMuPDF库: pip install PyMuPDF]"
        except Exception as e:
            return f"[PDF解析失败: {str(e)}]"

    def _parse_word(self, content: bytes, ext: str) -> str:
        try:
            from docx import Document
            
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                doc = Document(tmp_path)
                text_parts = []
                
                for para in doc.paragraphs:
                    if para.text.strip():
                        text_parts.append(para.text)

                for table in doc.tables:
                    text_parts.append("\n[表格内容]")
                    for row in table.rows:
                        row_text = " | ".join(cell.text.strip() for cell in row.cells)
                        if row_text.strip():
                            text_parts.append(row_text)

                return "\n".join(text_parts)
            finally:
                os.unlink(tmp_path)

        except ImportError:
            return "[Word解析需要安装python-docx库: pip install python-docx]"
        except Exception as e:
            return f"[Word解析失败: {str(e)}]"

    def _parse_excel(self, content: bytes, ext: str) -> str:
        try:
            import openpyxl
            
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                wb = openpyxl.load_workbook(tmp_path, data_only=True)
                text_parts = []

                for sheet_name in wb.sheetnames:
                    sheet = wb[sheet_name]
                    text_parts.append(f"\n[工作表: {sheet_name}]")
                    
                    for row in sheet.iter_rows(values_only=True):
                        row_text = " | ".join(
                            str(cell) if cell is not None else "" 
                            for cell in row
                        )
                        if row_text.strip():
                            text_parts.append(row_text)

                return "\n".join(text_parts)
            finally:
                os.unlink(tmp_path)

        except ImportError:
            return "[Excel解析需要安装openpyxl库: pip install openpyxl]"
        except Exception as e:
            return f"[Excel解析失败: {str(e)}]"


document_parser = DocumentParser()
