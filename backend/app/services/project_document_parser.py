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
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".zip",
}
ARCHIVE_ONLY_PROJECT_EXTENSIONS = {".doc", ".xls"}
MAX_ARCHIVE_FILES = 100
MAX_ARCHIVE_EXPANDED_BYTES = settings.MAX_FILE_SIZE * 10

INDUSTRY_KEYWORD_GROUPS = {
    "coking": (
        "焦化",
        "焦炭",
        "焦炉",
        "煤焦油",
        "粗苯",
        "炼焦",
        "化产车间",
        "煤焦车间",
    ),
    "electronics_assembly": (
        "pcba",
        "贴片",
        "回流焊",
        "波峰焊",
        "电能表",
        "故障指示器",
        "智能断路器",
        "线路板",
        "老化室",
    ),
}


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

        # The server has no trustworthy legacy Office parser. Keep originals
        # in the archive without pretending that their contents are searchable.
        if extension in ARCHIVE_ONLY_PROJECT_EXTENSIONS:
            metadata = self.extract_metadata("", filename)
            metadata.update(
                {
                    "archive_only": True,
                    "searchable": False,
                    "warning": "旧格式仅归档，需转换后才能检索",
                }
            )
            return ParsedProjectDocument(text="", metadata=metadata)

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
        metadata = self.extract_metadata(text, filename)
        metadata.update({"archive_only": False, "searchable": True})
        return ParsedProjectDocument(text=text, metadata=metadata)

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
        text = re.sub(r"[\ue000-\uf8ff]", " ", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def extract_metadata(text: str, filename: str) -> dict[str, Any]:
        lowered = f"{filename}\n{text[:5000]}".lower()
        section_match = re.match(r"^\s*([ABCDEFGIZ])(?:\s+|[-_])", filename, re.IGNORECASE)
        archive_section = section_match.group(1).upper() if section_match else None
        category = "other"
        category_rules = (
            ("manual", ("管理手册", "质量手册", "体系手册")),
            ("procedure", ("程序文件", "管理程序", "控制程序")),
            ("audit_plan", ("审核计划", "审核任务书", "审核策划", "审核方案")),
            ("audit_report", ("审核报告", "再认证报告")),
            ("meeting", ("首次会议", "末次会议", "会议签到", "沟通会议")),
            ("nonconformity", ("不符合项", "整改汇总", "审定意见")),
            ("organization", ("认证申请书", "营业执照", "组织架构", "资质文件")),
            ("record", ("现场审核记录", "审核记录", "台账", "清单")),
            ("standard", ("产品执行标准", "gb/t", "iso ", "规范")),
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
        company_names = sorted(
            set(
                re.findall(
                    r"(?<![\u4e00-\u9fffA-Za-z0-9])"
                    r"([\u4e00-\u9fffA-Za-z0-9（）()·]{2,50}?"
                    r"(?:有限责任公司|股份有限公司|有限公司|集团公司|集团))"
                    r"(?![\u4e00-\u9fffA-Za-z0-9])",
                    f"{filename}\n{text[:20000]}",
                )
            )
        )[:20]
        industry_keywords = sorted(
            {
                keyword
                for keywords in INDUSTRY_KEYWORD_GROUPS.values()
                for keyword in keywords
                if keyword in lowered
            }
        )
        industry_profiles = sorted(
            profile
            for profile, keywords in INDUSTRY_KEYWORD_GROUPS.items()
            if any(keyword in lowered for keyword in keywords)
        )
        return {
            "category": category,
            "standards": standards,
            "systems": systems,
            "departments": departments,
            "dates": dates,
            "company_names": company_names,
            "industry_keywords": industry_keywords,
            "industry_profiles": industry_profiles,
            "archive_section": archive_section,
        }

    @classmethod
    def analyze_consistency(
        cls,
        text: str,
        *,
        expected_enterprise_name: str | None = None,
        expected_industry_keywords: list[str] | tuple[str, ...] | None = None,
        filename: str = "",
    ) -> dict[str, Any]:
        """Return a side-effect-free project contamination assessment.

        Upload routes can persist this result in ``ProjectDocument.metadata``
        and set ``quarantined`` when ``recommended_quarantine`` is true.
        A missing enterprise name is deliberately not a finding by itself.
        """

        metadata = cls.extract_metadata(text, filename)
        detected_names = metadata["company_names"]
        expected_name = cls._normalize_company_name(expected_enterprise_name or "")
        detected_normalized = {
            cls._normalize_company_name(name): name for name in detected_names
        }
        expected_name_present = bool(
            expected_name
            and any(
                expected_name in detected or detected in expected_name
                for detected in detected_normalized
            )
        )
        IGNORED_ORG_KEYWORDS = (
            "认证",
            "认可",
            "检验",
            "检测",
            "评定",
            "标准",
            "测试",
            "计量",
            "质量保证",
            "咨询",
            "委员会",
            "中心",
            "协会",
            "监督",
        )
        other_names = [
            original
            for detected, original in detected_normalized.items()
            if expected_name
            and expected_name not in detected
            and detected not in expected_name
            and not any(kw in original for kw in IGNORED_ORG_KEYWORDS)
        ]

        reasons: list[dict[str, Any]] = []
        has_industry_mismatch = False

        expected_text = " ".join(
            [expected_enterprise_name or "", *(expected_industry_keywords or [])]
        ).lower()
        expected_profiles = {
            profile
            for profile, keywords in INDUSTRY_KEYWORD_GROUPS.items()
            if any(keyword in expected_text for keyword in keywords)
        }
        if "焦化" in expected_text:
            expected_profiles.add("coking")
        observed_profiles = set(metadata["industry_profiles"])
        conflicting_profiles = {
            ("coking", "electronics_assembly"),
            ("electronics_assembly", "coking"),
        }
        for expected_profile, observed_profile in conflicting_profiles:
            if expected_profile in expected_profiles and observed_profile in observed_profiles:
                matches = [
                    keyword
                    for keyword in INDUSTRY_KEYWORD_GROUPS[observed_profile]
                    if keyword in f"{filename}\n{text}".lower()
                ]
                # Require more than a stray word before quarantining by industry.
                if len(set(matches)) >= 2:
                    has_industry_mismatch = True
                    reasons.append(
                        {
                            "code": "INDUSTRY_MISMATCH",
                            "message": "资料行业特征与项目行业明显不一致",
                            "expected_profile": expected_profile,
                            "observed_profile": observed_profile,
                            "matches": sorted(set(matches)),
                        }
                    )

        if other_names and not expected_name_present:
            reasons.append(
                {
                    "code": "OTHER_ENTERPRISE_NAME",
                    "message": f"资料出现其他企业名称：{'、'.join(other_names)}",
                    "matches": other_names,
                }
            )

        high_risk = has_industry_mismatch
        return {
            "risk_level": "high" if high_risk else ("medium" if reasons else "low"),
            "recommended_quarantine": high_risk,
            "expected_enterprise_name": expected_enterprise_name,
            "detected_company_names": detected_names,
            "industry_keywords": metadata["industry_keywords"],
            "reasons": reasons,
        }

    @staticmethod
    def _normalize_company_name(value: str) -> str:
        return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", value).lower()

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
