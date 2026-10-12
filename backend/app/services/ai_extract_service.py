import asyncio
import json
import re
import time
from typing import Optional, List, AsyncGenerator

from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.utils.llm_fallback import create_ai_extract_llm_client


EXTRACT_TEMPLATE_ITEMS_PROMPT = """
你是一名专业的监督检查与认证审核模板解析专家，具备丰富的行政执法、质量监督、安全生产检查领域经验。
请从用户提供的文档内容（尤其是表格检查记录表）中，精准提取所有检查项目，并按照指定的JSON格式输出。

## 提取关键规则（极为重要）：

1. **检查项目标题（title）**：
   - 对于包含【项目序号】和【检查内容】的表格，**title 必须包含具体的检查内容**（可带上序号前缀，如 "1.1 厂区无扬尘、无积水，厂区、车间卫生整洁。" 或 "厂区无扬尘、无积水，厂区、车间卫生整洁。"）。
   - **绝对不能只将 "1.1" 或 "*1.2" 作为标题！**
2. **重点项与风险等级（risk_level）**：
   - 凡是原表中带 `*` 号或标注"重点项"的项目，`risk_level` 设为 `"high"`。
   - 一般项 `risk_level` 设为 `"medium"` 或 `"low"`。
3. **层级与分类（is_category & parent_title）**：
   - 表格中的大类（如 "1、生产环境条件"、"2、进货查验结果"、"3、生产过程控制"）作为分类节点，`is_category: true`，`check_type: "radio"`。
   - 其下属的具体检查子项（如 1.1, 1.2 等），`is_category: false`，且 `parent_title` 填对应大类标题（如 "1、生产环境条件"）。
4. **合格/不合格判定标准（result_options）**：
   - 默认判定类型为 `radio`（单选判定：合格/不合格/不适用）。
   - 如果文档中有具体合格要求，写入 pass 项 criteria；若有违规判定说明，写入 fail 项 criteria。

## 数据库字段对应：

| 字段名 | 说明 |
|--------|------|
| title | 检查项目标题（必填，必须完整提取检查内容） |
| description | 检查项目详细说明/注记 |
| check_method | 检查方法（查阅台账/现场核查/抽样等） |
| legal_basis | 法律法规依据（如《食品安全法》等） |
| standard_ref | 标准编号依据（如 GB 14881 等） |
| check_type | 检查类型：radio / numeric / text / score / multi_check |
| result_options | 判定选项列表（包含 pass/fail/na 及判定准则） |
| min_value | 数值最小值（numeric专用） |
| max_value | 数值最大值（numeric专用） |
| unit | 单位 |
| risk_level | high（重点项） / medium（一般项） / low |
| is_category | 大类设为 true，具体检查子项设为 false |
| parent_title | 所属大分类的标题（用于构建树形层级） |
| sort_order | 排序序号（整数） |

## 输出格式：

请直接输出严格合法的 JSON 对象，不要包含 markdown 代码块以外的解释：

```json
{
  "items": [
    {
      "title": "1、生产环境条件",
      "description": "生产环境与厂区卫生条件检查",
      "check_method": null,
      "legal_basis": null,
      "standard_ref": null,
      "check_type": "radio",
      "result_options": null,
      "min_value": null,
      "max_value": null,
      "unit": null,
      "risk_level": "medium",
      "is_category": true,
      "parent_title": null,
      "sort_order": 1
    },
    {
      "title": "1.1 厂区无扬尘、无积水，厂区、车间卫生整洁。",
      "description": "厂区、车间卫生整洁度日常核查",
      "check_method": "现场观察厂区及车间卫生状况",
      "legal_basis": null,
      "standard_ref": "GB 14881",
      "check_type": "radio",
      "result_options": {
        "options": [
          {"value": "pass", "label": "合格", "criteria": "厂区无扬尘、无积水，卫生整洁"},
          {"value": "fail", "label": "不合格", "criteria": "存在扬尘、积水或卫生杂乱"},
          {"value": "na", "label": "不适用"}
        ]
      },
      "min_value": null,
      "max_value": null,
      "unit": null,
      "risk_level": "medium",
      "is_category": false,
      "parent_title": "1、生产环境条件",
      "sort_order": 2
    },
    {
      "title": "*1.2 厂区、车间与有毒、有害场所及其他污染源保持规定的距离。",
      "description": "污染源防护距离重点检查",
      "check_method": "现场核查与周边污染源距离",
      "legal_basis": "《食品安全法》",
      "standard_ref": "GB 14881",
      "check_type": "radio",
      "result_options": {
        "options": [
          {"value": "pass", "label": "合格", "criteria": "与污染源保持规定距离"},
          {"value": "fail", "label": "不合格", "criteria": "与污染源距离不足或存在交叉污染风险"},
          {"value": "na", "label": "不适用"}
        ]
      },
      "min_value": null,
      "max_value": null,
      "unit": null,
      "risk_level": "high",
      "is_category": false,
      "parent_title": "1、生产环境条件",
      "sort_order": 3
    }
  ]
}
```
"""


class AIExtractService:
    def __init__(self):
        self._init_clients()

    def _init_clients(self):
        # AI 文档解析专用模型：SenseNova deepseek-flash（原生支持多模态，流式稳定）
        # 配置了备用模型时自动启用降级（主 429/超时/断连 → edgefn DeepSeek-V4-Flash + reasoning_effort=none）
        self.client = create_ai_extract_llm_client()
        self.model = settings.AI_EXTRACT_LLM_MODEL

    async def _parse_file_bytes(self, file_content: bytes, filename: str) -> str:
        """从文件字节中提取文本内容（本地解析）。"""
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
                    for i, page in enumerate(doc):
                        text = page.get_text()
                        if text and text.strip():
                            parts.append(f"[第 {i+1} 页]\n{text.strip()}")
                    doc.close()
                    return "\n\n".join(parts)
                finally:
                    if os.path.exists(tmp_path):
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
                    if os.path.exists(tmp_path):
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
                    if os.path.exists(tmp_path):
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
        yield {
            "type": "status",
            "stage": "parsing_doc",
            "step": 1,
            "message": f"正在本地解析文档格式 ({filename})...",
        }

        doc_text = await self._parse_file_bytes(file_content, filename)

        if not doc_text or doc_text.startswith("[PDF解析失败") or doc_text.startswith("[Word解析失败") or doc_text.startswith("[Excel解析失败") or "需要安装" in doc_text:
            yield {"type": "error", "content": f"文档解析失败: {doc_text}"}
            return

        yield {
            "type": "status",
            "stage": "sending",
            "step": 2,
            "message": f"文档文本提取完成（共 {len(doc_text)} 字符），正在组织 AI 分析提示词...",
        }

        prompt = EXTRACT_TEMPLATE_ITEMS_PROMPT
        if template_context:
            prompt += f"\n\n## 模板上下文\n{template_context}"
        prompt += f"\n\n## 文档内容\n{doc_text}"

        yield {
            "type": "status",
            "stage": "ai_parsing",
            "step": 2,
            "message": "AI 正在深度分析检查记录表，开始全要素结构化抽取...",
        }

        # 流式调用 DeepSeek-V4-Flash-0731（1M 上下文，输出上限保持 65536 不截断）
        # 含：首字等待心跳、空闲超时、断连自动重试、部分结果恢复
        max_attempts = 3
        first_token_timeout = 300  # 首字最长等待
        idle_timeout = 120          # 流式数据空闲超时
        heartbeat_interval = 3.0    # 心跳间隔

        full_content = ""
        best_partial = ""
        success_stream = False

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                yield {
                    "type": "status",
                    "stage": "ai_parsing",
                    "step": 2,
                    "message": f"检测到网络波动，正在自动重试 (第 {attempt}/{max_attempts} 次)...",
                }

            attempt_content = ""
            extracted_titles = []
            stream = None
            anext_task = None
            create_task = None

            try:
                start_time = time.time()
                last_data_time = time.time()
                first_chunk_received = False
                reasoning_text = ""
                reasoning_sent = 0
                content_sent = 0

                # 建连/响应头等待阶段同样发送心跳（模型首字延迟可能较长）
                # 推理模型（deepseek-flash / DeepSeek-V4-Flash）传 reasoning_effort 会先输出 reasoning_content；
                # 备用降级时由 llm_fallback 强制传入 reasoning_effort=none 快速响应。
                # stream_options.include_usage 让最后一个 chunk 带 token 统计。
                reasoning_kwargs = settings.ai_extract_reasoning_kwargs
                print(f"[AIExtract] Calling {self.model} with reasoning_kwargs={reasoning_kwargs}")
                create_task = asyncio.ensure_future(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=32000,
                        temperature=0.2,
                        stream=True,
                        stream_options={"include_usage": True},
                        **reasoning_kwargs,
                    )
                )
                while True:
                    done, _ = await asyncio.wait({create_task}, timeout=heartbeat_interval)
                    if done:
                        stream = create_task.result()
                        create_task = None
                        break
                    waited = int(time.time() - start_time)
                    if waited >= first_token_timeout:
                        raise RuntimeError(f"等待 AI 响应超时（{waited} 秒）")
                    if reasoning_kwargs:
                        yield {
                            "type": "status",
                            "stage": "ai_parsing",
                            "step": 2,
                            "message": (
                                f"AI 模型 ({self.model}) 正在建立连接并启动深度推理，"
                                f"已等待 {waited} 秒（reasoning_effort={settings.AI_EXTRACT_LLM_REASONING_EFFORT}，"
                                f"网关暂未推送首字，思考完成后会立即开始流式输出）..."
                            ),
                        }
                    else:
                        yield {
                            "type": "status",
                            "stage": "ai_parsing",
                            "step": 2,
                            "message": (
                                f"AI 模型 ({self.model}) 正在响应中，已等待 {waited} 秒"
                                f"（非推理模型，网关建立连接后即开始流式输出）..."
                            ),
                        }

                while True:
                    if anext_task is None:
                        anext_task = asyncio.ensure_future(stream.__anext__())

                    # 等待下一个 chunk，超时则发心跳（不取消任务）
                    done, _ = await asyncio.wait({anext_task}, timeout=heartbeat_interval)

                    if not done:
                        waited = int(time.time() - start_time)
                        if not first_chunk_received:
                            if waited >= first_token_timeout:
                                raise RuntimeError(f"等待 AI 首字响应超时（{waited} 秒）")
                            if reasoning_text:
                                yield {
                                    "type": "status",
                                    "stage": "ai_parsing",
                                    "step": 2,
                                    "message": f"AI 正在深度思考中（已思考 {len(reasoning_text)} 字，已耗时 {waited} 秒）...",
                                }
                            else:
                                if reasoning_kwargs:
                                    yield {
                                        "type": "status",
                                        "stage": "ai_parsing",
                                        "step": 2,
                                        "message": (
                                            f"AI 模型 ({self.model}) 正在思考中，已等待 {waited} 秒"
                                            f"（reasoning_effort={settings.AI_EXTRACT_LLM_REASONING_EFFORT}，"
                                            f"网关在思考期间不推送数据，思考完成后会立即开始流式输出）..."
                                        ),
                                    }
                                else:
                                    yield {
                                        "type": "status",
                                        "stage": "ai_parsing",
                                        "step": 2,
                                        "message": f"AI 模型 ({self.model}) 正在响应中，已等待 {waited} 秒...",
                                    }
                        else:
                            idle = int(time.time() - last_data_time)
                            if idle >= idle_timeout:
                                raise RuntimeError(f"AI 流式响应空闲超时（{idle} 秒无数据）")
                            yield {
                                "type": "status",
                                "stage": "extracting",
                                "step": 2,
                                "message": f"AI 正在持续生成中 (已生成 {len(attempt_content)} 字符，已提取 {len(extracted_titles)} 项，已耗时 {waited} 秒)...",
                                "item_count": len(extracted_titles),
                            }
                        continue

                    task, anext_task = anext_task, None
                    try:
                        chunk = task.result()
                    except StopAsyncIteration:
                        break

                    if not chunk.choices:
                        # 带 usage 但无 choices 的末尾 chunk（include_usage=true 时常见）
                        if getattr(chunk, "usage", None):
                            print(f"[AIExtract] usage: prompt={chunk.usage.prompt_tokens} "
                                  f"completion={chunk.usage.completion_tokens} "
                                  f"total={chunk.usage.total_tokens}")
                        continue

                    delta = chunk.choices[0].delta
                    if delta is None:
                        continue

                    # 诊断日志：打印每个 chunk 的所有字段，便于确认网关是否流式推送 reasoning_content
                    _rc = getattr(delta, "reasoning_content", None)
                    _r = getattr(delta, "reasoning", None)
                    _c = delta.content
                    if _rc or _r or _c:
                        print(f"[AIExtract] chunk delta: reasoning_content={(_rc[:40] + '...') if _rc else None!r}, "
                              f"reasoning={(_r[:40] + '...') if _r else None!r}, "
                              f"content={(_c[:40] + '...') if _c else None!r}")

                    # 推理模型：先输出思考内容再输出正文
                    # SenseNova 网关用 "reasoning"，DeepSeek 风格用 "reasoning_content"
                    reasoning_piece = _rc or _r
                    if reasoning_piece:
                        reasoning_text += reasoning_piece
                        last_data_time = time.time()

                        # 增量推送思考文本给前端实时显示（攒够 24 字推一次，避免事件风暴）
                        if not first_chunk_received and len(reasoning_text) - reasoning_sent >= 24:
                            piece = reasoning_text[reasoning_sent:]
                            reasoning_sent = len(reasoning_text)
                            yield {
                                "type": "status",
                                "stage": "ai_parsing",
                                "step": 2,
                                "message": f"AI 正在深度思考中（已思考 {len(reasoning_text)} 字）...",
                                "reasoning_delta": piece,
                            }

                    content = _c
                    if content:
                        attempt_content += content
                        last_data_time = time.time()

                        if not first_chunk_received:
                            first_chunk_received = True
                            # 推送思考阶段剩余文本
                            if len(reasoning_text) > reasoning_sent:
                                yield {
                                    "type": "status",
                                    "stage": "ai_parsing",
                                    "step": 2,
                                    "reasoning_delta": reasoning_text[reasoning_sent:],
                                    "reasoning_done": True,
                                }
                                reasoning_sent = len(reasoning_text)
                            yield {
                                "type": "status",
                                "stage": "extracting",
                                "step": 2,
                                "message": "AI 思考完成，正在结构化输出检查项...",
                            }

                        # 增量推送正文（结构化 JSON）给前端实时显示
                        if len(attempt_content) - content_sent >= 48:
                            piece = attempt_content[content_sent:]
                            content_sent = len(attempt_content)
                            yield {
                                "type": "status",
                                "stage": "extracting",
                                "step": 2,
                                "item_count": len(extracted_titles),
                                "content_delta": piece,
                            }

                        # 实时监测已抽取的检查项标题
                        titles = re.findall(r'"title"\s*:\s*"([^"]+)"', attempt_content)
                        if len(titles) > len(extracted_titles):
                            extracted_titles = titles
                            latest_title = titles[-1]
                            short_title = latest_title if len(latest_title) <= 24 else latest_title[:24] + "..."
                            yield {
                                "type": "status",
                                "stage": "extracting",
                                "step": 2,
                                "message": f"正在提取第 {len(extracted_titles)} 项: {short_title}",
                                "item_count": len(extracted_titles),
                                "current_title": latest_title,
                            }

                if attempt_content.strip():
                    full_content = attempt_content
                    success_stream = True
                    # 推送正文剩余部分
                    if len(attempt_content) > content_sent:
                        yield {
                            "type": "status",
                            "stage": "extracting",
                            "step": 2,
                            "item_count": len(extracted_titles),
                            "content_delta": attempt_content[content_sent:],
                        }
                        content_sent = len(attempt_content)
                    break

                raise RuntimeError("AI 返回内容为空")

            except Exception as e:
                print(f"[AIExtract] Attempt {attempt}/{max_attempts} ({self.model}) failed: {e}")

                # 若本次已生成较完整内容，直接采用部分结果，避免全部重来
                if len(attempt_content) >= 3000 and attempt_content.count('"title"') >= 3:
                    print(f"[AIExtract] Recovering partial content: {len(attempt_content)} chars, "
                          f"{attempt_content.count(chr(34) + 'title' + chr(34))} items")
                    full_content = attempt_content
                    success_stream = True
                    yield {
                        "type": "status",
                        "stage": "processing",
                        "step": 3,
                        "message": "网络出现波动，已从已接收内容中恢复提取结果...",
                    }
                    break

                # 记录最长部分内容，供最终恢复兜底
                if len(attempt_content) > len(best_partial):
                    best_partial = attempt_content
                continue

            finally:
                if create_task is not None and not create_task.done():
                    create_task.cancel()
                if anext_task is not None and not anext_task.done():
                    anext_task.cancel()
                if stream is not None:
                    try:
                        await stream.close()
                    except Exception:
                        pass

        if not success_stream or not full_content:
            # 所有尝试均失败：尝试用已收到的最长部分内容恢复
            if len(best_partial) >= 1000 and best_partial.count('"title"') >= 2:
                yield {
                    "type": "status",
                    "stage": "processing",
                    "step": 3,
                    "message": f"网络不稳定，正在从已接收的 {len(best_partial)} 字符中尽力恢复提取结果...",
                }
                full_content = best_partial
            else:
                yield {"type": "error", "content": "AI 解析多次中断，模型服务暂时不稳定，请稍后重试"}
                return

        yield {
            "type": "status",
            "stage": "processing",
            "step": 3,
            "message": "正在解析 JSON 并构建检查项树形结构...",
        }

        parsed_result = self._parse_extracted_items(full_content)

        yield {
            "type": "done",
            "items": parsed_result,
            "item_count": len(parsed_result),
            "raw_response": full_content,
        }

    def _parse_extracted_items(self, content: str) -> List[dict]:
        """多策略容错 JSON 解析与检查项规范化。"""
        items = []

        # 策略 1：标准 JSON 解析
        try:
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                json_str = content.strip()
                if not json_str.startswith('{'):
                    start = json_str.find('{')
                    end = json_str.rfind('}')
                    if start != -1 and end != -1:
                        json_str = json_str[start:end+1]

            data = json.loads(json_str)
            if isinstance(data, dict) and 'items' in data:
                items = data['items']
            elif isinstance(data, list):
                items = data
        except Exception as e:
            print(f"[AIExtract] Direct JSON parse failed, trying balanced-brace recovery: {e}")

        # 策略 2：括号平衡扫描提取独立对象（针对截断/轻微语法错误的 JSON）
        if not items:
            pos = 0
            while True:
                idx = content.find('"title"', pos)
                if idx == -1:
                    break
                obj_start = content.rfind('{', 0, idx)
                if obj_start == -1:
                    pos = idx + 7
                    continue

                depth = 0
                obj_end = -1
                for i in range(obj_start, len(content)):
                    if content[i] == '{':
                        depth += 1
                    elif content[i] == '}':
                        depth -= 1
                        if depth == 0:
                            obj_end = i
                            break
                if obj_end != -1:
                    obj_str = content[obj_start:obj_end+1]
                    try:
                        obj_str_clean = re.sub(r',\s*\}', '}', obj_str)
                        obj_str_clean = re.sub(r',\s*\]', ']', obj_str_clean)
                        item = json.loads(obj_str_clean)
                        if isinstance(item, dict) and item.get('title'):
                            items.append(item)
                    except Exception:
                        pass
                    pos = obj_end + 1
                else:
                    pos = idx + 7

        normalized_items = []
        for idx, item in enumerate(items):
            normalized = self._normalize_item(item, default_sort=idx + 1)
            if normalized.get('title'):
                normalized_items.append(normalized)

        return normalized_items

    def _normalize_item(self, item: dict, default_sort: int = 1) -> dict:
        raw_title = str(item.get("title", "")).strip()

        # 判断是否为大类
        is_category = item.get("is_category", False)
        if isinstance(is_category, str):
            is_category = is_category.lower() == "true"

        # 如果标题类似 "1、生产环境条件" 或 "一、原料管理"，自动识别为分类节点
        if re.match(r'^[0-9一二三四五六七八九十]+[、.．]\s*[^0-9]', raw_title) and not item.get("check_method"):
            is_category = True

        # 重点项标记 *
        risk_level = item.get("risk_level", "medium")
        if "*" in raw_title or "重点" in raw_title:
            risk_level = "high"

        normalized = {
            "title": raw_title,
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
            "risk_level": risk_level,
            "is_category": is_category,
            "parent_title": item.get("parent_title"),
            "sort_order": item.get("sort_order") or default_sort,
        }

        # 默认合格判定选项
        if normalized["check_type"] == "radio" and not normalized["result_options"]:
            normalized["result_options"] = {
                "options": [
                    {"value": "pass", "label": "合格", "criteria": ""},
                    {"value": "fail", "label": "不合格", "criteria": ""},
                    {"value": "na", "label": "不适用"},
                ]
            }

        valid_risk_levels = ["low", "medium", "high"]
        if normalized["risk_level"] not in valid_risk_levels:
            normalized["risk_level"] = "medium"

        valid_check_types = ["radio", "numeric", "text", "score", "multi_check"]
        if normalized["check_type"] not in valid_check_types:
            normalized["check_type"] = "radio"

        return normalized

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
3. 直接输出JSON格式，包含 "items" 数组
"""
        try:
            # 该网关非流式请求易超时，统一使用流式
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=32000,
                temperature=0.2,
                stream=True,
            )

            parts = []
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                if delta.content:
                    parts.append(delta.content)

            content = "".join(parts)
            refined_items = self._parse_extracted_items(content)
            return {"success": True, "items": refined_items}

        except Exception as e:
            return {"success": False, "error": str(e), "items": items}

    async def refine_items_stream(
        self,
        items: List[dict],
        instruction: str,
    ) -> AsyncGenerator[dict, None]:
        """流式版精修：推送思考过程与结构化输出给前端实时显示。

        chunk 格式与 extract_items_from_file 一致：
        - {type: status, message, reasoning_delta, reasoning_done, content_delta, ...}
        - {type: done, items, item_count, raw_response}
        - {type: error, content}
        """
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
3. 直接输出JSON格式，包含 "items" 数组
"""
        yield {
            "type": "status",
            "stage": "sending",
            "step": 1,
            "message": f"已接收 {len(items)} 个检查项，正在组织精修提示词...",
        }

        # 与 extract 相同的流式容错策略：心跳、首字超时、空闲超时、重试、部分恢复
        max_attempts = 3
        first_token_timeout = 300
        idle_timeout = 120
        heartbeat_interval = 3.0

        full_content = ""
        best_partial = ""
        success_stream = False

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                yield {
                    "type": "status",
                    "stage": "ai_parsing",
                    "step": 1,
                    "message": f"检测到网络波动，正在自动重试 (第 {attempt}/{max_attempts} 次)...",
                }

            attempt_content = ""
            stream = None
            anext_task = None
            create_task = None

            try:
                start_time = time.time()
                last_data_time = time.time()
                first_chunk_received = False
                reasoning_text = ""
                reasoning_sent = 0
                content_sent = 0

                reasoning_kwargs = settings.ai_extract_reasoning_kwargs
                create_task = asyncio.ensure_future(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=32000,
                        temperature=0.2,
                        stream=True,
                        stream_options={"include_usage": True},
                        **reasoning_kwargs,
                    )
                )
                while True:
                    done, _ = await asyncio.wait({create_task}, timeout=heartbeat_interval)
                    if done:
                        stream = create_task.result()
                        create_task = None
                        break
                    waited = int(time.time() - start_time)
                    if waited >= first_token_timeout:
                        raise RuntimeError(f"等待 AI 响应超时（{waited} 秒）")
                    yield {
                        "type": "status",
                        "stage": "ai_parsing",
                        "step": 1,
                        "message": (
                            f"AI 模型 ({self.model}) 正在建立连接并启动推理，已等待 {waited} 秒"
                            f"（连接建立后会立即开始流式输出）..."
                        ),
                    }

                while True:
                    if anext_task is None:
                        anext_task = asyncio.ensure_future(stream.__anext__())

                    done, _ = await asyncio.wait({anext_task}, timeout=heartbeat_interval)

                    if not done:
                        waited = int(time.time() - start_time)
                        if not first_chunk_received:
                            if waited >= first_token_timeout:
                                raise RuntimeError(f"等待 AI 首字响应超时（{waited} 秒）")
                            if reasoning_text:
                                yield {
                                    "type": "status",
                                    "stage": "ai_parsing",
                                    "step": 1,
                                    "message": f"AI 正在深度思考中（已思考 {len(reasoning_text)} 字，已耗时 {waited} 秒）...",
                                }
                            else:
                                yield {
                                    "type": "status",
                                    "stage": "ai_parsing",
                                    "step": 1,
                                    "message": f"AI 模型 ({self.model}) 正在思考中，已等待 {waited} 秒...",
                                }
                        else:
                            idle = int(time.time() - last_data_time)
                            if idle >= idle_timeout:
                                raise RuntimeError(f"AI 流式响应空闲超时（{idle} 秒无数据）")
                            yield {
                                "type": "status",
                                "stage": "extracting",
                                "step": 1,
                                "message": f"AI 正在持续精修中 (已生成 {len(attempt_content)} 字符，已耗时 {waited} 秒)...",
                            }
                        continue

                    task, anext_task = anext_task, None
                    try:
                        chunk = task.result()
                    except StopAsyncIteration:
                        break

                    if not chunk.choices:
                        if getattr(chunk, "usage", None):
                            print(f"[AIRefine] usage: prompt={chunk.usage.prompt_tokens} "
                                  f"completion={chunk.usage.completion_tokens} "
                                  f"total={chunk.usage.total_tokens}")
                        continue

                    delta = chunk.choices[0].delta
                    if delta is None:
                        continue

                    # SenseNova 网关用 "reasoning"，DeepSeek 风格用 "reasoning_content"
                    reasoning_piece = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
                    if reasoning_piece:
                        reasoning_text += reasoning_piece
                        last_data_time = time.time()

                        # 增量推送思考文本（攒够 24 字推一次，避免事件风暴）
                        if not first_chunk_received and len(reasoning_text) - reasoning_sent >= 24:
                            piece = reasoning_text[reasoning_sent:]
                            reasoning_sent = len(reasoning_text)
                            yield {
                                "type": "status",
                                "stage": "ai_parsing",
                                "step": 1,
                                "message": f"AI 正在深度思考中（已思考 {len(reasoning_text)} 字）...",
                                "reasoning_delta": piece,
                            }

                    content = delta.content
                    if content:
                        attempt_content += content
                        last_data_time = time.time()

                        if not first_chunk_received:
                            first_chunk_received = True
                            # 推送思考阶段剩余文本
                            if len(reasoning_text) > reasoning_sent:
                                yield {
                                    "type": "status",
                                    "stage": "ai_parsing",
                                    "step": 1,
                                    "reasoning_delta": reasoning_text[reasoning_sent:],
                                    "reasoning_done": True,
                                }
                                reasoning_sent = len(reasoning_text)
                            yield {
                                "type": "status",
                                "stage": "extracting",
                                "step": 1,
                                "message": "AI 思考完成，正在结构化输出精修结果...",
                            }

                        # 增量推送正文（结构化 JSON）
                        if len(attempt_content) - content_sent >= 48:
                            piece = attempt_content[content_sent:]
                            content_sent = len(attempt_content)
                            yield {
                                "type": "status",
                                "stage": "extracting",
                                "step": 1,
                                "content_delta": piece,
                            }

                if attempt_content.strip():
                    full_content = attempt_content
                    success_stream = True
                    # 推送正文剩余部分
                    if len(attempt_content) > content_sent:
                        yield {
                            "type": "status",
                            "stage": "extracting",
                            "step": 1,
                            "content_delta": attempt_content[content_sent:],
                        }
                    break

                raise RuntimeError("AI 返回内容为空")

            except Exception as e:
                print(f"[AIRefine] Attempt {attempt}/{max_attempts} ({self.model}) failed: {e}")

                # 已生成较完整内容时直接采用部分结果
                if len(attempt_content) >= 2000 and attempt_content.count('"title"') >= 3:
                    print(f"[AIRefine] Recovering partial content: {len(attempt_content)} chars")
                    full_content = attempt_content
                    success_stream = True
                    yield {
                        "type": "status",
                        "stage": "processing",
                        "step": 2,
                        "message": "网络出现波动，已从已接收内容中恢复精修结果...",
                    }
                    break

                if len(attempt_content) > len(best_partial):
                    best_partial = attempt_content
                continue

            finally:
                if create_task is not None and not create_task.done():
                    create_task.cancel()
                if anext_task is not None and not anext_task.done():
                    anext_task.cancel()
                if stream is not None:
                    try:
                        await stream.close()
                    except Exception:
                        pass

        if not success_stream or not full_content:
            if len(best_partial) >= 800 and best_partial.count('"title"') >= 2:
                yield {
                    "type": "status",
                    "stage": "processing",
                    "step": 2,
                    "message": f"网络不稳定，正在从已接收的 {len(best_partial)} 字符中尽力恢复精修结果...",
                }
                full_content = best_partial
            else:
                yield {"type": "error", "content": "AI 精修多次中断，模型服务暂时不稳定，请稍后重试"}
                return

        yield {
            "type": "status",
            "stage": "processing",
            "step": 2,
            "message": "正在解析精修结果并构建检查项...",
        }

        parsed_result = self._parse_extracted_items(full_content)

        yield {
            "type": "done",
            "items": parsed_result,
            "item_count": len(parsed_result),
            "raw_response": full_content,
        }


ai_extract_service = AIExtractService()
