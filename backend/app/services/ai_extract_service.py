import json
import re
import time
from typing import Optional, List, AsyncGenerator
from openai import AsyncOpenAI
from starlette.concurrency import run_in_threadpool

from app.config import settings


EXTRACT_TEMPLATE_ITEMS_PROMPT = """
你是一名专业的监督检查模板解析专家，具备丰富的行政执法、质量监督、安全生产检查领域经验。
请从用户提供的文档内容中，精准提取所有检查项目，并按照指定的JSON格式输出。

## 数据库字段说明（必须精确对应）

每个检查项需要对应以下数据库字段：

| 字段名 | 说明 | 示例 |
|--------|------|------|
| title | 检查项目标题（必填，精确提取原文） | "食品原料进货查验记录" |
| description | 检查项目详细描述/要求说明 | "查验供货者的许可证和食品合格证明文件" |
| check_method | 检查方法（如何检查） | "查阅进货台账、索证索票记录" |
| legal_basis | 法律法规依据（具体条文） | "《食品安全法》第五十条" |
| standard_ref | 标准编号依据 | "GB 14881-2013" |
| check_type | 检查类型（见下方说明） | "radio" |
| result_options | 合格/不合格判定选项（radio类专用） | 见下方 |
| min_value | 数值类型最小值 | 0 |
| max_value | 数值类型最大值 | 100 |
| unit | 数值单位 | "℃" |
| risk_level | 风险等级：low/medium/high | "high" |
| is_category | 是否为分类标题节点 | false |
| parent_title | 父级分类标题（建立层级） | "一、原料管理" |

## check_type 类型说明

- `radio`: 单选判定 —— 合格/不合格/不适用（**最常用**，用于"是否符合""有无"类检查）
- `numeric`: 数值测量 —— 需要填写具体数值（温度、重量、浓度等）
- `text`: 文字描述 —— 需要填写描述性文字
- `score`: 评分制 —— 打分评价
- `multi_check`: 多选项 —— 多个选项可同时选择

## 合格/不合格判定标准提取规则

**这是最重要的提取任务！** 对于文档中描述的合格与不合格判定标准：

1. **合格判定** (`pass`)：文档中描述"符合""有""达标""正常""规范"等表述的内容
2. **不合格判定** (`fail`)：文档中描述"不符合""无""超标""异常""违规"等表述的内容
3. **不适用** (`na`)：该项目在特定情况下不适用

对于 radio 类型，result_options 格式参考：
```json
{
  "options": [
    {"value": "pass", "label": "合格/符合", "criteria": "此处填写具体的合格判定标准"},
    {"value": "fail", "label": "不合格/不符合", "criteria": "此处填写具体的不合格判定标准"},
    {"value": "na", "label": "不适用"}
  ]
}
```

## 层级结构识别规则

1. **一级分类**（is_category=true）：如"一、基本条件""（一）人员管理""第一章 XXXX"等编号标题
2. **二级分类**（is_category=true）：如"1.1 XXX""（1）XXX"等次级标题
3. **具体检查项**（is_category=false）：表格中的行项、具体检查内容

## 表格检查记录表的提取规则

对于表格类文档（最常见形式）：
- **表头行**通常包含：序号 | 检查项目 | 检查方法/标准 | 法规依据 | 结论
- **数据行**：每行提取为一个独立检查项
- **检查方法列**：对应 check_method 字段
- **法规依据列**：对应 legal_basis 字段
- **标准列**：对应 standard_ref 字段
- **结论/判断列**：用于判断 check_type 和合格标准

## 风险等级判断标准

- `high`：直接影响人身安全、产品质量关键指标、法律强制性要求
- `medium`：影响产品质量的一般要求、管理规范性要求
- `low`：记录性要求、一般管理事项

## 输出格式

请严格按照以下JSON格式输出，不要包含任何其他说明文字：

```json
{
  "items": [
    {
      "title": "检查项目标题（必填）",
      "description": "检查要求描述",
      "check_method": "检查方法",
      "legal_basis": "法律依据",
      "standard_ref": "标准编号",
      "check_type": "radio",
      "result_options": {
        "options": [
          {"value": "pass", "label": "合格", "criteria": "具体合格标准"},
          {"value": "fail", "label": "不合格", "criteria": "具体不合格标准"},
          {"value": "na", "label": "不适用"}
        ]
      },
      "min_value": null,
      "max_value": null,
      "unit": null,
      "risk_level": "medium",
      "is_category": false,
      "parent_title": null,
      "sort_order": 1
    }
  ]
}
```

## 提取质量要求

1. **完整性**：文档中所有检查项必须全部提取，不能遗漏
2. **准确性**：标题、方法、依据等必须准确提取原文，不得随意改写
3. **结构性**：正确建立层级结构，parent_title 必须与对应的分类节点 title 完全一致
4. **判定标准**：尽可能从文档中提取具体的合格/不合格判定标准填入 criteria 字段
5. **法规完整**：法规依据和标准编号必须完整提取，包括条文编号

请直接输出JSON，不要包含任何markdown代码块以外的解释文字。
"""


class AIExtractService:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT,
        )
        self.model = settings.LLM_MODEL
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_BASE_URL

    async def _parse_file_bytes(self, file_content: bytes, filename: str) -> str:
        """从文件字节中提取文本内容（本地解析，无需上传到第三方）。

        解析本身是同步 CPU 密集操作，统一卸载到线程池，避免阻塞事件循环。
        """
        return await run_in_threadpool(self._parse_file_bytes_sync, file_content, filename)

    def _parse_file_bytes_sync(self, file_content: bytes, filename: str) -> str:
        from pathlib import Path
        import tempfile, os

        ext = Path(filename).suffix.lower()

        if ext == ".txt":
            for encoding in ["utf-8", "gbk", "latin-1"]:
                try:
                    return file_content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return file_content.decode("utf-8", errors="ignore")

        elif ext == ".pdf":
            try:
                import fitz
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(file_content)
                    tmp_path = tmp.name
                try:
                    doc = fitz.open(tmp_path)
                    parts = []
                    for page in doc:
                        parts.append(page.get_text())
                    doc.close()
                    return "\n\n".join(parts)
                finally:
                    os.unlink(tmp_path)
            except ImportError:
                return "[PDF解析需要安装PyMuPDF: pip install PyMuPDF]"
            except Exception as e:
                return f"[PDF解析失败: {e}]"

        elif ext in [".doc", ".docx"]:
            try:
                from docx import Document
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(file_content)
                    tmp_path = tmp.name
                try:
                    doc = Document(tmp_path)
                    parts = []
                    for para in doc.paragraphs:
                        if para.text.strip():
                            parts.append(para.text)
                    for table in doc.tables:
                        parts.append("\n[表格内容]")
                        for row in table.rows:
                            row_text = " | ".join(cell.text.strip() for cell in row.cells)
                            if row_text.strip():
                                parts.append(row_text)
                    return "\n".join(parts)
                finally:
                    os.unlink(tmp_path)
            except ImportError:
                return "[Word解析需要安装python-docx: pip install python-docx]"
            except Exception as e:
                return f"[Word解析失败: {e}]"

        elif ext in [".xls", ".xlsx"]:
            try:
                import openpyxl
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(file_content)
                    tmp_path = tmp.name
                try:
                    wb = openpyxl.load_workbook(tmp_path, data_only=True)
                    parts = []
                    for sheet_name in wb.sheetnames:
                        sheet = wb[sheet_name]
                        parts.append(f"\n[工作表: {sheet_name}]")
                        for row in sheet.iter_rows(values_only=True):
                            row_text = " | ".join(str(c) if c is not None else "" for c in row)
                            if row_text.strip():
                                parts.append(row_text)
                    return "\n".join(parts)
                finally:
                    os.unlink(tmp_path)
            except ImportError:
                return "[Excel解析需要安装openpyxl: pip install openpyxl]"
            except Exception as e:
                return f"[Excel解析失败: {e}]"

        else:
            return file_content.decode("utf-8", errors="ignore")

    async def extract_items_from_file(
        self,
        file_content: bytes,
        filename: str,
        template_context: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        yield {"type": "status", "stage": "parsing_doc", "message": "正在本地解析文档内容..."}

        doc_text = await self._parse_file_bytes(file_content, filename)

        if not doc_text or doc_text.startswith("["):
            yield {"type": "error", "content": f"文档解析失败: {doc_text}"}
            return

        yield {
            "type": "status",
            "stage": "sending",
            "message": f"文档解析完成（{len(doc_text)} 字符），正在调用 AI 分析...",
        }

        prompt = EXTRACT_TEMPLATE_ITEMS_PROMPT
        if template_context:
            prompt += f"\n\n## 模板上下文\n{template_context}"
        prompt += f"\n\n## 文档内容\n{doc_text}"

        full_content = ""
        try:
            yield {"type": "status", "stage": "ai_parsing", "message": "AI 正在深度分析检查记录表，提取结构化检查项..."}

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8192,
                temperature=0.2,
                top_p=0.95,
                stream=True,
            )

            char_count = 0
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    char_count += len(content)
                    # 每积累200字符发一次进度
                    if char_count % 200 < len(content):
                        yield {
                            "type": "status",
                            "stage": "streaming",
                            "message": f"AI 正在输出结果... (已生成 {char_count} 字符)",
                        }

            yield {"type": "status", "stage": "processing", "message": "正在解析 JSON 结构..."}

            parsed_result = self._parse_extracted_items(full_content)
            yield {
                "type": "done",
                "items": parsed_result,
                "raw_response": full_content,
            }

        except Exception as e:
            yield {"type": "error", "content": str(e)}

    async def extract_items_from_document(
        self,
        document_content: str,
        template_context: Optional[str] = None,
    ) -> dict:
        prompt = EXTRACT_TEMPLATE_ITEMS_PROMPT

        if template_context:
            prompt += f"\n\n## 模板上下文\n{template_context}"

        prompt += f"\n\n## 文档内容\n{document_content}"

        start_time = time.time()
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8192,
                temperature=0.2,
                top_p=0.95,
            )
            content = response.choices[0].message.content or ""
            duration_ms = int((time.time() - start_time) * 1000)
            
            parsed_result = self._parse_extracted_items(content)
            
            return {
                "success": True,
                "items": parsed_result,
                "raw_response": content,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "items": [],
            }

    async def extract_items_stream(
        self,
        document_content: str,
        template_context: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        prompt = EXTRACT_TEMPLATE_ITEMS_PROMPT

        if template_context:
            prompt += f"\n\n## 模板上下文\n{template_context}"

        prompt += f"\n\n## 文档内容\n{document_content}"

        full_content = ""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8192,
                temperature=0.2,
                top_p=0.95,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield {"type": "thinking", "content": content}

            parsed_result = self._parse_extracted_items(full_content)
            yield {
                "type": "done",
                "items": parsed_result,
                "raw_response": full_content,
            }

        except Exception as e:
            yield {"type": "error", "content": str(e)}

    async def refine_items(
        self,
        items: List[dict],
        instruction: str,
    ) -> dict:
        """使用AI优化/调整已提取的检查项"""
        items_json = json.dumps(items, ensure_ascii=False, indent=2)

        prompt = f"""
你是一个检查模板优化专家，熟悉行政执法、质量监督领域的检查规范。
请根据用户的优化指令，对以下检查项目列表进行优化调整。

## 当前的检查项目列表
```json
{items_json}
```

## 用户的优化指令
{instruction}

## 输出要求
1. 请输出优化后的完整检查项目列表
2. 保持原有的数据结构格式不变（所有字段名称不变）
3. 直接输出JSON格式，不要包含其他说明文字
4. 确保JSON格式正确，包含 "items" 数组

注意：
- 保留所有字段，包括 result_options 中的 criteria（合格/不合格判定标准）
- 如果优化指令要求补充法规依据，请根据实际法规填写
- 层级关系通过 parent_title 字段维护
"""

        client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT,
        )

        try:
            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8192,
                temperature=0.3,
            )

            content = response.choices[0].message.content or ""
            refined_items = self._parse_extracted_items(content)
            return {"success": True, "items": refined_items}

        except Exception as e:
            return {"success": False, "error": str(e), "items": items}

    def _parse_extracted_items(self, content: str) -> List[dict]:
        try:
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = content.strip()
                if json_str.startswith('{'):
                    pass
                else:
                    json_start = content.find('{')
                    json_end = content.rfind('}')
                    if json_start != -1 and json_end != -1:
                        json_str = content[json_start:json_end+1]

            data = json.loads(json_str)
            
            if isinstance(data, dict) and 'items' in data:
                items = data['items']
            elif isinstance(data, list):
                items = data
            else:
                items = []

            normalized_items = []
            for item in items:
                normalized_item = self._normalize_item(item)
                if normalized_item.get('title'):
                    normalized_items.append(normalized_item)

            return normalized_items

        except json.JSONDecodeError as e:
            print(f"[AIExtract] JSON parse error: {e}")
            return []
        except Exception as e:
            print(f"[AIExtract] Parse error: {e}")
            return []

    def _normalize_item(self, item: dict) -> dict:
        normalized = {
            "title": item.get("title", ""),
            "description": item.get("description"),
            "check_method": item.get("check_method"),
            "legal_basis": item.get("legal_basis"),
            "standard_ref": item.get("standard_ref"),
            "check_type": item.get("check_type", "radio"),
            "result_options": item.get("result_options"),
            "min_value": item.get("min_value"),
            "max_value": item.get("max_value"),
            "unit": item.get("unit"),
            "max_score": item.get("max_score"),
            "pass_score": item.get("pass_score"),
            "risk_level": item.get("risk_level", "medium"),
            "is_category": item.get("is_category", False),
            "parent_title": item.get("parent_title"),
            "sort_order": item.get("sort_order", 0),
        }

        # 默认的合格判定选项（当check_type为radio且无result_options时）
        if normalized["check_type"] == "radio" and not normalized["result_options"]:
            normalized["result_options"] = {
                "options": [
                    {"value": "pass", "label": "合格", "criteria": ""},
                    {"value": "fail", "label": "不合格", "criteria": ""},
                    {"value": "na", "label": "不适用"},
                ]
            }

        if isinstance(normalized["is_category"], str):
            normalized["is_category"] = normalized["is_category"].lower() == "true"

        valid_risk_levels = ["low", "medium", "high"]
        if normalized["risk_level"] not in valid_risk_levels:
            normalized["risk_level"] = "medium"

        valid_check_types = ["radio", "numeric", "text", "score", "multi_check"]
        if normalized["check_type"] not in valid_check_types:
            normalized["check_type"] = "radio"

        return normalized


ai_extract_service = AIExtractService()
