"""Safe local parsing helpers for project knowledge documents."""

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from app.config import settings


SUPPORTED_PROJECT_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".zip",
}
MAX_ARCHIVE_FILES = 100
MAX_ARCHIVE_EXPANDED_BYTES = settings.MAX_FILE_SIZE * 10


@dataclass
class ParsedProjectDocument:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ProjectDocumentParser:
    def parse(self, content: bytes, filename: str) -> ParsedProjectDocument:
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_PROJECT_EXTENSIONS:
            raise ValueError(f"不支持的项目资料格式: {extension or '未知'}")
        if len(content) > settings.MAX_FILE_SIZE:
            raise ValueError("项目资料超过允许的文件大小")

        if extension in {".txt", ".md"}:
            text = self._decode_text(content)
        elif extension == ".csv":
            text = self._parse_csv(content)
        elif extension == ".json":
            text = self._parse_json(content)
        elif extension == ".pdf":
            text = self._parse_pdf(content)
        elif extension == ".docx":
            text = self._parse_docx(content)
        elif extension == ".xlsx":
            text = self._parse_xlsx(content)
        else:
            text = self._parse_zip(content)

        text = self._normalize_text(text)
        if not text:
            raise ValueError("未能从项目资料中提取有效文本")
        return ParsedProjectDocument(
            text=text,
            metadata=self.extract_metadata(text, filename),
        )

    @staticmethod
    def _decode_text(content: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")

    def _parse_csv(self, content: bytes) -> str:
        decoded = self._decode_text(content)
        rows = csv.reader(io.StringIO(decoded))
        return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)

    def _parse_json(self, content: bytes) -> str:
        value = json.loads(self._decode_text(content))
        return json.dumps(value, ensure_ascii=False, indent=2)

    @staticmethod
    def _parse_pdf(content: bytes) -> str:
        import fitz

        with fitz.open(stream=content, filetype="pdf") as document:
            return "\n\n".join(page.get_text("text") for page in document)

    @staticmethod
    def _parse_docx(content: bytes) -> str:
        from docx import Document

        document = Document(io.BytesIO(content))
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    parts.append(" | ".join(cells))
        return "\n".join(parts)

    @staticmethod
    def _parse_xlsx(content: bytes) -> str:
        import openpyxl

        workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        parts: list[str] = []
        try:
            for worksheet in workbook.worksheets:
                parts.append(f"[工作表: {worksheet.title}]")
                for row in worksheet.iter_rows(values_only=True):
                    values = ["" if value is None else str(value) for value in row]
                    if any(values):
                        parts.append(" | ".join(values))
        finally:
            workbook.close()
        return "\n".join(parts)

    def _parse_zip(self, content: bytes) -> str:
        parts: list[str] = []
        expanded_bytes = 0
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = [member for member in archive.infolist() if not member.is_dir()]
            if len(members) > MAX_ARCHIVE_FILES:
                raise ValueError("ZIP 内文件数量超过限制")
            for member in members:
                member_path = PurePosixPath(member.filename.replace("\\", "/"))
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ValueError("ZIP 包含不安全的文件路径")
                expanded_bytes += member.file_size
                if expanded_bytes > MAX_ARCHIVE_EXPANDED_BYTES:
                    raise ValueError("ZIP 解压后总大小超过限制")
                extension = member_path.suffix.lower()
                if extension not in SUPPORTED_PROJECT_EXTENSIONS - {".zip"}:
                    continue
                nested = archive.read(member)
                parsed = self.parse(nested, member_path.name)
                parts.append(f"\n[文件: {member.filename}]\n{parsed.text}")
        if not parts:
            raise ValueError("ZIP 中没有可解析的项目资料")
        return "\n".join(parts)

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\x00", "")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def extract_metadata(text: str, filename: str) -> dict[str, Any]:
        lowered = f"{filename}\n{text[:5000]}".lower()
        category = "other"
        category_rules = (
            ("standard", ("标准", "gb/t", "iso ", "规范")),
            ("procedure", ("程序文件", "管理程序", "控制程序")),
            ("manual", ("管理手册", "质量手册", "体系手册")),
            ("record", ("记录", "台账", "清单")),
            ("previous_audit", ("审核报告", "不符合项", "审核发现")),
        )
        for candidate, keywords in category_rules:
            if any(keyword in lowered for keyword in keywords):
                category = candidate
                break

        standards = sorted(
            set(
                re.findall(
                    r"(?:GB/T|GB|ISO|ISO/IEC)\s*\d+(?:\.\d+)?(?:[-:]\d{4})?",
                    text,
                    flags=re.IGNORECASE,
                )
            )
        )
        systems = []
        for code, keywords in {
            "Q": ("质量管理体系", "iso 9001", "gb/t 19001"),
            "E": ("环境管理体系", "iso 14001", "gb/t 24001"),
            "S": ("职业健康安全", "iso 45001", "gb/t 45001"),
            "En": ("能源管理体系", "iso 50001", "gb/t 23331"),
        }.items():
            if any(keyword in lowered for keyword in keywords):
                systems.append(code)

        departments = sorted(
            set(
                re.findall(
                    r"([\u4e00-\u9fff]{2,12}(?:部|处|科|室|车间|中心|办公室))",
                    text[:20000],
                )
            )
        )[:30]
        dates = sorted(
            set(re.findall(r"(?:20\d{2})[-/.年](?:0?[1-9]|1[0-2])[-/.月](?:0?[1-9]|[12]\d|3[01])日?", text))
        )[:20]
        return {
            "category": category,
            "standards": standards,
            "systems": systems,
            "departments": departments,
            "dates": dates,
        }

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
        if len(text) <= chunk_size:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            if end < len(text):
                boundary = max(
                    text.rfind("\n", start + chunk_size // 2, end),
                    text.rfind("。", start + chunk_size // 2, end),
                )
                if boundary > start:
                    end = boundary + 1
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
        return chunks


project_document_parser = ProjectDocumentParser()
