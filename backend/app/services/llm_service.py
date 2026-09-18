import time
import re
from typing import Optional, Union, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.task import TaskItemRecord
from app.models.record import InspectionRecordItem
from app.models.template import TemplateItem
from app.models.audit import LLMCallLog
from app.utils.llm_fallback import (
    create_main_llm_client,
    served_model as fb_served_model,
    was_fallback as fb_was_fallback,
)
from app.utils.item_stats import classify_result


SUGGESTION_PROMPT = """
你是专业检查员助手。根据检查项信息，生成简洁的检查结论。

【检查项名称】{check_item_title}
【检查方法】{check_method}
【检查结果】{result}
【问题描述】{problem_description}
【法规依据】{legal_basis}

请生成检查结论（50字以内），要求：
1. 结论要明确、专业
2. 如发现问题，简要说明
3. 语言简洁，直接输出结论内容
"""

BASIS_PROMPT = """
你是法规专家。为检查项提供简要法规依据。

【检查项】：{check_item_title}
【说明】：{description}
【已知依据】：{legal_basis}

要求：列出2-3条最相关的法规/标准，每条不超过20字，总计不超过80字。
"""

FINAL_JUDGMENT_PROMPT = """
你是资深检查专家，根据检查结果生成最终判定。

【检查模板】{template_name}
【检查日期】{inspection_date}

【检查项汇总】（共 {total_items} 项）
{items_summary}

【统计结果】
- 符合项：{pass_count} 项
- 不符合项：{fail_count} 项
- 不适用项：{na_count} 项
- 其他类型项：{other_count} 项

【判定规则】
只要存在不符合项（不符合项数量大于 0），最终判定必须为“不合格”，不得判为“合格”或“基本合格”。

请按以下格式输出（纯文本，不要使用Markdown格式）：

检查结果：共检查 {total_items} 项，其中符合项 {pass_count} 项，不符合项 {fail_count} 项，不适用项 {na_count} 项。

总体评价：（200字以内，概括整体检查情况，指出主要问题和风险点）

最终判定：合格 或 基本合格 或 不合格
"""


class LLMService:
    def __init__(self):
        print(f"[LLM] Initializing with base_url={settings.LLM_BASE_URL}, model={settings.LLM_MODEL}")
        print(f"[LLM] API key configured: {bool(settings.LLM_API_KEY)}")
        self.client = create_main_llm_client()
        self.model = settings.LLM_MODEL

    async def get_suggestion(
        self,
        template_item: TemplateItem,
        record: Union[TaskItemRecord, InspectionRecordItem],
        db: AsyncSession,
        user_id: str,
        task_id: str,
        use_cache: bool = True,
    ) -> tuple[str, bool, int]:
        cached_suggestion = getattr(record, 'llm_suggestion', None) or getattr(record, 'ai_suggestion', None)
        if use_cache and cached_suggestion:
            return cached_suggestion, True, 0

        result_text = self._get_result_text(record)
        problem_description = (
            getattr(record, 'problem_description', None)
            or getattr(record, 'inspector_note', None)
            or "无"
        )

        prompt = SUGGESTION_PROMPT.format(
            check_item_title=template_item.title,
            result=result_text,
            problem_description=problem_description,
            check_method=template_item.check_method or "未指定",
            legal_basis=template_item.legal_basis or "无",
        )

        content, duration_ms = await self._call_llm(
            prompt, db, user_id, task_id, str(record.id), "suggestion"
        )

        final_content = self.extract_final_content(content)

        if hasattr(record, 'llm_suggestion'):
            record.llm_suggestion = final_content
        if hasattr(record, 'ai_suggestion'):
            record.ai_suggestion = final_content

        return final_content, False, duration_ms

    async def get_suggestion_stream(
        self,
        template_item: TemplateItem,
        record: Union[TaskItemRecord, InspectionRecordItem],
    ) -> AsyncGenerator[dict, None]:
        result_text = self._get_result_text(record)
        problem_description = (
            getattr(record, 'problem_description', None)
            or getattr(record, 'inspector_note', None)
            or "无"
        )

        prompt = SUGGESTION_PROMPT.format(
            check_item_title=template_item.title,
            result=result_text,
            problem_description=problem_description,
            check_method=template_item.check_method or "未指定",
            legal_basis=template_item.legal_basis or "无",
        )

        full_content = ""
        try:
            print(f"[LLM] Streaming API with model={self.model}")
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
                top_p=settings.LLM_TOP_P,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield {"type": "thinking", "content": content}

            final_content = self.extract_final_content(full_content)
            yield {"type": "done", "content": final_content, "full_content": full_content}

        except Exception as e:
            print(f"[LLM] Stream error: {e}")
            yield {"type": "error", "content": str(e)}

    async def get_basis(
        self,
        template_item: TemplateItem,
        record: Union[TaskItemRecord, InspectionRecordItem],
        db: AsyncSession,
        user_id: str,
        task_id: str,
        use_cache: bool = True,
    ) -> tuple[str, bool, int]:
        cached_basis = getattr(record, 'llm_basis', None) or getattr(record, 'ai_basis', None)
        if use_cache and cached_basis:
            return cached_basis, True, 0

        prompt = BASIS_PROMPT.format(
            check_item_title=template_item.title,
            description=template_item.description or "无",
            legal_basis=template_item.legal_basis or "待查询",
        )

        content, duration_ms = await self._call_llm(
            prompt, db, user_id, task_id, str(record.id), "basis"
        )

        final_content = self.extract_final_content(content)

        if hasattr(record, 'llm_basis'):
            record.llm_basis = final_content
        if hasattr(record, 'ai_basis'):
            record.ai_basis = final_content

        return final_content, False, duration_ms

    async def get_basis_stream(
        self,
        template_item: TemplateItem,
        record: Union[TaskItemRecord, InspectionRecordItem],
    ) -> AsyncGenerator[dict, None]:
        prompt = BASIS_PROMPT.format(
            check_item_title=template_item.title,
            description=template_item.description or "无",
            legal_basis=template_item.legal_basis or "待查询",
        )

        full_content = ""
        try:
            print(f"[LLM] Streaming basis API with model={self.model}")
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
                top_p=settings.LLM_TOP_P,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield {"type": "thinking", "content": content}

            final_content = self.extract_final_content(full_content)
            yield {"type": "done", "content": final_content, "full_content": full_content}

        except Exception as e:
            print(f"[LLM] Stream error: {e}")
            yield {"type": "error", "content": str(e)}

    def extract_final_content(self, content: str) -> str:
        if not content:
            return ""
        
        patterns = [
            r'<summary>\s*(.*?)\s*</summary>',
            r'\*\*结论[：:]\*\*\s*(.*?)(?=\n\n|\n\*\*|$)',
            r'\*\*检查结论[：:]\*\*\s*(.*?)(?=\n\n|\n\*\*|$)',
            r'\*\*最终结论[：:]\*\*\s*(.*?)(?=\n\n|\n\*\*|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        if '</think' in content.lower():
            parts = re.split(r'</think[^>]*>', content, flags=re.IGNORECASE)
            if len(parts) > 1:
                final_part = parts[-1].strip()
                final_part = re.sub(r'^\s*```.*?```\s*', '', final_part, flags=re.DOTALL)
                final_part = re.sub(r'\n\s*\n', '\n', final_part)
                return final_part.strip()
        
        lines = content.strip().split('\n')
        non_empty_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith('【')]
        
        if non_empty_lines:
            for line in reversed(non_empty_lines):
                if len(line) > 10 and not line.startswith('```'):
                    return line
        
        return content.strip()

    def _get_result_text(self, record: Union[TaskItemRecord, InspectionRecordItem]) -> str:
        if hasattr(record, 'radio_value') and record.radio_value:
            return self._radio_to_text(record.radio_value)
        if hasattr(record, 'result') and record.result:
            return self._result_to_text(record.result)
        if hasattr(record, 'score_value') and record.score_value is not None:
            return f"得分: {record.score_value}"
        if hasattr(record, 'numeric_value') and record.numeric_value:
            return f"测量值: {record.numeric_value}"
        if hasattr(record, 'text_value') and record.text_value:
            return record.text_value[:50] if len(record.text_value) > 50 else record.text_value
        return "未填写"

    async def _call_llm(
        self,
        prompt: str,
        db: AsyncSession,
        user_id: str,
        task_id: str,
        record_id: str,
        call_type: str,
    ) -> tuple[str, int]:
        start_time = time.time()
        error_msg = None
        content = ""
        tokens_used = 0
        served = self.model
        used_fallback = False

        try:
            print(f"[LLM] Calling API with model={self.model}, prompt length={len(prompt)}")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
                top_p=settings.LLM_TOP_P,
            )
            # BUG-15：主模型 429/超时降级后，日志必须记录真实提供服务的模型，
            # 而不是仍记主模型「成功」。
            served = fb_served_model(response, self.model)
            used_fallback = fb_was_fallback(response)
            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0
            print(f"[LLM] Response received (model={served}, fallback={used_fallback}): {content[:100]}...")
        except Exception as e:
            error_msg = str(e)
            print(f"[LLM] Error: {error_msg}")
            content = f"AI建议获取失败: {error_msg}"

        duration_ms = int((time.time() - start_time) * 1000)

        log = LLMCallLog(
            user_id=user_id,
            task_id=task_id,
            record_id=record_id,
            call_type=call_type,
            prompt=prompt,
            response=content,
            # 降级时显式标注真实模型，便于在 LLM 调用记录里区分主/备通道。
            model=(f"{served}（备用通道）" if used_fallback else served),
            tokens_used=tokens_used,
            duration_ms=duration_ms,
            is_success="false" if error_msg else "true",
            error_msg=error_msg,
        )
        db.add(log)

        return content, duration_ms

    def _result_to_text(self, result: Optional[str]) -> str:
        mapping = {
            "compliant": "合规",
            "non_compliant": "不合规",
            "not_applicable": "不适用",
            "pass": "合格",
            "fail": "不合格",
            "na": "不适用",
        }
        return mapping.get(result, "未填写")

    def _radio_to_text(self, radio_value: Optional[str]) -> str:
        mapping = {
            "pass": "合格",
            "fail": "不合格",
            "na": "不适用",
            "compliant": "合规",
            "non_compliant": "不合规",
            "not_applicable": "不适用",
        }
        return mapping.get(radio_value, radio_value or "未填写")

    async def get_final_judgment_stream(
        self,
        template_name: str,
        inspection_date: str,
        items: list,
    ) -> AsyncGenerator[dict, None]:
        items_summary = self._format_items_summary(items)

        pass_count = sum(1 for item in items if self._get_item_result_status(item) == "pass")
        fail_count = sum(1 for item in items if self._get_item_result_status(item) == "fail")
        na_count = sum(1 for item in items if self._get_item_result_status(item) == "na")
        other_count = len(items) - pass_count - fail_count - na_count

        prompt = FINAL_JUDGMENT_PROMPT.format(
            template_name=template_name or "未指定模板",
            inspection_date=inspection_date or "未指定日期",
            total_items=len(items),
            items_summary=items_summary,
            pass_count=pass_count,
            fail_count=fail_count,
            na_count=na_count,
            other_count=other_count,
        )

        full_content = ""
        try:
            print(f"[LLM] Streaming final judgment API with model={self.model}")
            print(f"[LLM] Prompt length: {len(prompt)} chars")
            
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=settings.LLM_TEMPERATURE,
                top_p=settings.LLM_TOP_P,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield {"type": "thinking", "content": content}

            final_content = self.extract_final_judgment(full_content)
            final_content = self._apply_final_judgment_rules(
                final_content, fail_count=fail_count
            )
            yield {"type": "done", "content": final_content.get("remarks", ""), "result": final_content.get("result", ""), "full_content": full_content}

        except Exception as e:
            print(f"[LLM] Final judgment stream error: {e}")
            yield {"type": "error", "content": str(e)}

    def _format_items_summary(self, items: list) -> str:
        if not items:
            return "无检查项"
        
        summary_lines = []
        for i, item in enumerate(items, 1):
            title = item.get('title', '未知检查项')
            result_status = self._get_item_result_status(item)
            result_text = self._get_item_result_text(item)
            risk_level = item.get('risk_level', '')
            problem = item.get('problem_description', '')
            
            risk_icon = {'high': '⚠️', 'medium': '⚡', 'low': '✓'}.get(risk_level, '')
            status_icon = {'pass': '✅', 'fail': '❌', 'na': '➖'}.get(result_status, '📝')
            
            line = f"{i}. {status_icon} {title}"
            if risk_icon:
                line += f" [{risk_icon}]"
            line += f" - {result_text}"
            if problem:
                problem_preview = problem[:50] + '...' if len(problem) > 50 else problem
                line += f" | 问题: {problem_preview}"
            
            summary_lines.append(line)
        
        return '\n'.join(summary_lines)

    def _get_item_result_status(self, item: dict) -> str:
        # 判定归类统一走 app.utils.item_stats，避免本地维护更窄的别名表
        # （原实现只认 pass/compliant、fail/non_compliant、na/not_applicable，
        #   会漏掉 qualified/unqualified/n/a 等历史写法）。
        radio_value = item.get('radio_value') or item.get('result')
        bucket = classify_result(radio_value)
        if bucket:
            return bucket

        score_value = item.get('score_value')
        if score_value is not None and score_value != '' and score_value != 'null':
            try:
                pass_score = item.get('pass_score', 60) or 60
                return 'pass' if float(score_value) >= float(pass_score) else 'fail'
            except (ValueError, TypeError):
                pass

        numeric_value = item.get('numeric_value')
        if numeric_value is not None and numeric_value != '' and numeric_value != 'null':
            min_val = item.get('min_value')
            max_val = item.get('max_value')
            if min_val is not None and max_val is not None:
                try:
                    val = float(numeric_value)
                    return 'pass' if min_val <= val <= max_val else 'fail'
                except (ValueError, TypeError):
                    pass

        return 'other'

    def _get_item_result_text(self, item: dict) -> str:
        radio_value = item.get('radio_value') or item.get('result')
        if radio_value:
            return self._radio_to_text(radio_value)
        
        score_value = item.get('score_value')
        if score_value is not None:
            max_score = item.get('max_score', 100)
            return f"{score_value}/{max_score}分"
        
        numeric_value = item.get('numeric_value')
        if numeric_value is not None:
            unit = item.get('unit', '')
            return f"{numeric_value}{unit}"
        
        text_value = item.get('text_value')
        if text_value:
            return text_value[:30] + '...' if len(text_value) > 30 else text_value
        
        multi_value = item.get('multi_value', [])
        if multi_value:
            return f"已选{len(multi_value)}项"
        
        return "未填写"

    def extract_final_judgment(self, content: str) -> dict:
        if not content:
            return {"result": "", "remarks": ""}

        result = ""
        patterns = [
            r'最终判定[：:]\s*(合格|基本合格|不合格)',
            r'判定结果[：:]\s*(合格|基本合格|不合格)',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                judgment_text = match.group(1).strip()
                if judgment_text == "合格":
                    result = "pass"
                elif judgment_text == "基本合格":
                    result = "partial_pass"
                elif judgment_text == "不合格":
                    result = "fail"
                break

        remarks = ""
        # 先尝试提取"检查结果"部分
        stats_match = re.search(r'检查结果[：:]\s*(.*?)(?=总体评价|最终判定|$)', content, re.DOTALL | re.IGNORECASE)
        stats_text = ""
        if stats_match:
            stats_text = stats_match.group(1).strip()

        # 提取"总体评价"部分
        eval_match = re.search(r'总体评价[：:]\s*(.*?)(?=最终判定|$)', content, re.DOTALL | re.IGNORECASE)
        if eval_match:
            eval_text = eval_match.group(1).strip()
            # 组合统计信息和评价
            if stats_text:
                remarks = f"检查结果：{stats_text}\n\n总体评价：{eval_text}"
            else:
                remarks = eval_text
        elif stats_text:
            remarks = stats_text

        # 清理格式
        remarks = re.sub(r'^\s*[\(（].*?[\)）]\s*', '', remarks)
        remarks = re.sub(r'^.*?字以内.*?[。，,]?\s*', '', remarks)
        remarks = re.sub(r'^#+\s*', '', remarks, flags=re.MULTILINE)
        remarks = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', remarks)
        remarks = re.sub(r'`{1,3}[^`]*`{1,3}', '', remarks)
        remarks = re.sub(r'\n{2,}', '\n', remarks)
        remarks = remarks.strip()

        return {"result": result, "remarks": remarks}

    def _apply_final_judgment_rules(self, judgment: dict, fail_count: int) -> dict:
        """应用不可交由模型自由发挥的最终判定规则。"""
        resolved = dict(judgment)
        if fail_count > 0:
            resolved["result"] = "fail"
        return resolved


llm_service = LLMService()
