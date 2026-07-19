"""One-pass evidence analysis against multiple audit clauses.

设计原则（2026-07-16 修复）：
1. LLM 失败时显式上报，不再静默回退吞掉错误。
2. 必须回退时，候选条款必须经过 rank_candidates 评分筛选，不得直接取前 N 个。
3. 默认评估值改为 "2"（部分符合，需人工复核），不再对未关联条款强行判 NC。
4. 草稿标记 model_status，前端可据此显示"模型异常"徽标。

2026-07-19 补充：
5. 多条款 JSON 输出必须使用足够的 max_tokens；全局 LLM_MAX_TOKENS=512 会截断导致空结果。
6. 区分 finish_reason=length / 空 content / clause 不匹配，给出可读错误原因。
7. DeepSeek V4（思考/非思考双模式 + 内置 JSON Output）：结构化任务关闭 thinking，
   仅消费 content；thinking 结果在 reasoning_content，不得当最终 JSON 解析。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any

from openai import AsyncOpenAI

from app.config import settings


logger = logging.getLogger("evidence_agent")

# 多条款分析输出较长（多条 reasoning + findings + citations），不可被全局 512 截断。
# DeepSeek 最大输出可达 64K；此处取业务平衡值，避免超时与成本过高。
EVIDENCE_AGENT_MIN_MAX_TOKENS = 3500
EVIDENCE_AGENT_MAX_MAX_TOKENS = 8000


@dataclass
class EvidenceCandidate:
    item_id: str | None
    template_item_id: str | None
    clause_no: str
    title: str
    description: str = ""
    check_method: str = ""
    evidence_hint: str = ""
    risk_level: str = "medium"
    attachment_required: bool = False
    certification_system: str | None = None


NEGATIVE_TERMS = (
    "未提供",
    "缺失",
    "无记录",
    "未执行",
    "不符合",
    "过期",
    "超期",
    "失效",
    "遗漏",
)


class EvidenceAgentError(RuntimeError):
    """Raised when the evidence agent cannot produce reliable results."""

    def __init__(self, message: str, *, reason: str = "model_unavailable") -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


class EvidenceAgentService:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT,
        )
        self.model = settings.LLM_MODEL

    @staticmethod
    def _analysis_max_tokens() -> int:
        """Ensure multi-clause JSON is not truncated by a low global token cap."""
        configured = int(settings.LLM_MAX_TOKENS or 0)
        return max(
            EVIDENCE_AGENT_MIN_MAX_TOKENS,
            min(configured if configured > 0 else EVIDENCE_AGENT_MIN_MAX_TOKENS, EVIDENCE_AGENT_MAX_MAX_TOKENS),
        )

    @staticmethod
    def _is_deepseek_model(model: str | None = None) -> bool:
        name = (model or settings.LLM_MODEL or "").lower()
        return "deepseek" in name

    @classmethod
    def _structured_call_kwargs(cls, *, max_tokens: int) -> dict[str, Any]:
        """OpenAI-compatible kwargs for strict JSON evidence analysis.

        DeepSeek V4 notes (via SenseNova gateway probe 2026-07-19):
        - Built-in JSON Output works with response_format=json_object.
        - Default may emit reasoning_content (thinking mode); content still holds JSON.
        - For structured multi-clause tasks, disable thinking to cut latency/cost and
          avoid token budget spent on chain-of-thought.
        """
        kwargs: dict[str, Any] = {
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if cls._is_deepseek_model():
            # Official-style toggle used by DeepSeek-compatible gateways
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        return kwargs

    @staticmethod
    def _message_text(message: Any) -> str:
        """Prefer final answer content; never treat thinking/reasoning as JSON body."""
        if message is None:
            return ""
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content
        # Some gateways put structured parts in list content
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict) and part.get("type") in {None, "text", "output_text"}:
                    text = part.get("text") or part.get("content") or ""
                    if text:
                        parts.append(str(text))
            joined = "".join(parts).strip()
            if joined:
                return joined
        # Do NOT fall back to reasoning_content — that is chain-of-thought, not JSON
        return ""

    @staticmethod
    def rank_candidates(
        evidence: str,
        candidates: list[EvidenceCandidate],
        limit: int = 12,
    ) -> list[EvidenceCandidate]:
        evidence_lower = evidence.lower()
        evidence_tokens = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", evidence_lower))

        def score(candidate: EvidenceCandidate) -> tuple[float, str]:
            haystack = " ".join(
                (
                    candidate.clause_no,
                    candidate.title,
                    candidate.description,
                    candidate.check_method,
                    candidate.evidence_hint,
                )
            ).lower()
            tokens = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", haystack))
            overlap = len(evidence_tokens & tokens)
            clause_bonus = 8 if candidate.clause_no and candidate.clause_no in evidence else 0
            title_bonus = 3 if candidate.title and candidate.title.lower() in evidence_lower else 0
            risk_bonus = 0.2 if candidate.risk_level in {"high", "A", "高风险"} else 0
            return overlap + clause_bonus + title_bonus + risk_bonus, candidate.clause_no

        ranked = sorted(candidates, key=score, reverse=True)
        positive = [candidate for candidate in ranked if score(candidate)[0] > 0]
        return (positive or ranked)[:limit]

    @staticmethod
    def _normalize_clause_key(value: str) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"[\s\-_/／、,，.。:：;；()（）\[\]【】]", "", text)
        text = text.replace("条款", "").replace("标准", "").replace("要求", "")
        return text

    def _resolve_candidate(
        self,
        clause_no: str,
        candidates_by_clause: dict[str, EvidenceCandidate],
        candidates: list[EvidenceCandidate],
    ) -> EvidenceCandidate | None:
        if not clause_no:
            return None
        direct = candidates_by_clause.get(clause_no)
        if direct:
            return direct
        # exact case-insensitive
        for key, candidate in candidates_by_clause.items():
            if key.lower() == clause_no.lower():
                return candidate
        normalized = self._normalize_clause_key(clause_no)
        if not normalized:
            return None
        for candidate in candidates:
            cand_key = self._normalize_clause_key(candidate.clause_no)
            if not cand_key:
                continue
            if cand_key == normalized or cand_key in normalized or normalized in cand_key:
                return candidate
            title_key = self._normalize_clause_key(candidate.title)
            if title_key and (title_key == normalized or normalized in title_key):
                return candidate
        return None

    async def analyze(
        self,
        evidence: str,
        candidates: list[EvidenceCandidate],
        citations: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        citations = citations or []
        prompt = self._build_prompt(evidence, candidates, citations)
        last_error: Exception | None = None
        max_tokens = self._analysis_max_tokens()
        try:
            call_kwargs = self._structured_call_kwargs(max_tokens=max_tokens)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是认证审核证据分析 Agent。只能依据给出的现场证据、候选条款和项目资料判断，"
                            "不得虚构证据。一次证据可以命中多个条款。输出严格 JSON，不要输出思考过程。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                **call_kwargs,
            )
            choice = response.choices[0] if response.choices else None
            message = choice.message if choice else None
            raw_content = self._message_text(message)
            finish_reason = getattr(choice, "finish_reason", None) if choice else None
            reasoning_len = len(str(getattr(message, "reasoning_content", None) or ""))

            if not raw_content.strip():
                last_error = EvidenceAgentError(
                    (
                        f"LLM 返回空内容（finish_reason={finish_reason or 'unknown'}"
                        f", reasoning_len={reasoning_len}）"
                    ),
                    reason="empty_content",
                )
            else:
                payload = self._parse_json(raw_content)
                raw_results = self._extract_results_list(payload)
                normalized = self._normalize_results(raw_results, candidates, citations)
                if normalized:
                    if finish_reason == "length":
                        logger.warning(
                            "[EvidenceAgent] response truncated but partial results kept: count=%s max_tokens=%s",
                            len(normalized),
                            max_tokens,
                        )
                    return normalized

                # 无法规范化时给出可诊断原因
                if finish_reason == "length":
                    last_error = EvidenceAgentError(
                        f"LLM 输出被截断（max_tokens={max_tokens}），JSON 不完整无法解析",
                        reason="truncated",
                    )
                elif not payload:
                    last_error = EvidenceAgentError(
                        f"LLM 返回无法解析的 JSON（content_len={len(raw_content)}）",
                        reason="invalid_json",
                    )
                elif not raw_results:
                    last_error = EvidenceAgentError(
                        "LLM 未输出 results 列表（可能未识别到相关条款，或结构字段名不一致）",
                        reason="empty_results",
                    )
                else:
                    sample = [
                        str(item.get("clause_no", "")).strip()
                        for item in raw_results[:5]
                        if isinstance(item, dict)
                    ]
                    last_error = EvidenceAgentError(
                        f"LLM 返回的条款号无法匹配候选（sample={sample}）",
                        reason="clause_mismatch",
                    )
                logger.warning(
                    "[EvidenceAgent] empty normalized results: reason=%s finish_reason=%s content_preview=%s",
                    getattr(last_error, "reason", "unknown"),
                    finish_reason,
                    raw_content[:300].replace("\n", " "),
                )
        except EvidenceAgentError as exc:
            last_error = exc
        except Exception as exc:
            last_error = exc
            logger.error(
                "[EvidenceAgent] model analysis failed: %s: %s",
                type(exc).__name__,
                exc,
            )

        # 回退路径：不再静默生成"看似可信"的草稿，而是显式标记 model_status
        # 并基于 rank_candidates 的评分筛选候选，避免无关条款被强行匹配。
        return self._fallback(
            evidence,
            candidates,
            citations,
            error_message=str(last_error) if last_error else "LLM 调用失败",
        )

    @staticmethod
    def _extract_results_list(payload: Any) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        for key in ("results", "items", "data", "clauses", "matches"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        # 单条结果包在顶层
        if any(k in payload for k in ("clause_no", "evaluation_3level", "evidence_quality")):
            return [payload]
        return []

    @staticmethod
    def _build_prompt(
        evidence: str,
        candidates: list[EvidenceCandidate],
        citations: list[dict[str, Any]],
    ) -> str:
        candidate_payload = [asdict(candidate) for candidate in candidates]
        citation_payload = [
            {
                "index": index,
                "document_id": citation.get("document_id"),
                "document_title": citation.get("document_title"),
                "chunk_index": citation.get("chunk_index"),
                "content": citation.get("content", "")[:700],
            }
            for index, citation in enumerate(citations)
        ]
        return f"""现场证据：
{evidence}

候选审核条款：
{json.dumps(candidate_payload, ensure_ascii=False)}

项目资料引用候选（index 用于 citation_indexes）：
{json.dumps(citation_payload, ensure_ascii=False)}

请找出证据真正支持或暴露问题的所有条款。每个命中条款输出一条结果；不要为了凑数强行匹配。
clause_no 必须与候选审核条款中的 clause_no 完全一致。
JSON 格式：
{{
  "results": [
    {{
      "clause_no": "候选中的条款号",
      "evaluation_3level": "1/2/3",
      "evidence_quality": "sufficient/partial/insufficient",
      "reasoning": "判断理由",
      "audit_findings": "审核发现，无问题时可为空",
      "rectification_suggestion": "整改建议，无问题时可为空",
      "confidence": 0.0,
      "citation_indexes": [0]
    }}
  ]
}}

评价规则：1=符合，2=基本符合/证据部分充分，3=不符合。证据不足不能直接推定符合。"""

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any] | list[Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", content)
            if not match:
                return {}
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                # 尝试截断修复：去掉末尾不完整片段
                text = match.group(0)
                for end in range(len(text), max(len(text) - 400, 0), -1):
                    snippet = text[:end].rstrip().rstrip(",")
                    if not snippet:
                        continue
                    # 补齐括号
                    opens = snippet.count("{") - snippet.count("}")
                    opens_b = snippet.count("[") - snippet.count("]")
                    repaired = snippet + ("}" * max(opens, 0)) + ("]" * max(opens_b, 0))
                    try:
                        return json.loads(repaired)
                    except json.JSONDecodeError:
                        continue
                return {}

    def _normalize_results(
        self,
        raw_results: list[Any],
        candidates: list[EvidenceCandidate],
        citations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        candidates_by_clause = {candidate.clause_no: candidate for candidate in candidates}
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            clause_no = str(
                raw.get("clause_no")
                or raw.get("clause")
                or raw.get("clauseNo")
                or raw.get("standard_clause")
                or ""
            ).strip()
            candidate = self._resolve_candidate(clause_no, candidates_by_clause, candidates)
            if not candidate or candidate.clause_no in seen:
                continue
            seen.add(candidate.clause_no)
            evaluation = str(
                raw.get("evaluation_3level")
                or raw.get("evaluation")
                or raw.get("result")
                or "2"
            )
            if evaluation not in {"1", "2", "3"}:
                # 兼容文字评价
                eval_map = {
                    "符合": "1",
                    "合格": "1",
                    "pass": "1",
                    "基本符合": "2",
                    "部分符合": "2",
                    "partial": "2",
                    "不符合": "3",
                    "不合格": "3",
                    "fail": "3",
                }
                evaluation = eval_map.get(evaluation.strip().lower(), "2")
            quality = str(
                raw.get("evidence_quality")
                or raw.get("quality")
                or raw.get("evidenceQuality")
                or "partial"
            )
            if quality not in {"sufficient", "partial", "insufficient"}:
                quality_map = {
                    "充分": "sufficient",
                    "足够": "sufficient",
                    "部分充分": "partial",
                    "部分": "partial",
                    "不足": "insufficient",
                    "不充分": "insufficient",
                }
                quality = quality_map.get(quality.strip().lower(), "partial")
            try:
                confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.5))))
            except (TypeError, ValueError):
                confidence = 0.5
            citation_indexes = raw.get("citation_indexes") or raw.get("citations") or []
            selected_citations = []
            if isinstance(citation_indexes, list):
                for index in citation_indexes:
                    if isinstance(index, int) and 0 <= index < len(citations):
                        selected_citations.append(citations[index])
                    elif isinstance(index, dict):
                        selected_citations.append(index)
            normalized.append(
                {
                    "candidate": candidate,
                    "evaluation_3level": evaluation,
                    "evidence_quality": quality,
                    "reasoning": str(raw.get("reasoning") or raw.get("reason") or "").strip(),
                    "audit_findings": str(
                        raw.get("audit_findings") or raw.get("findings") or ""
                    ).strip(),
                    "rectification_suggestion": str(
                        raw.get("rectification_suggestion")
                        or raw.get("suggestion")
                        or raw.get("rectification")
                        or ""
                    ).strip(),
                    "confidence": confidence,
                    "citations": selected_citations,
                    "model_status": "ok",
                }
            )
        return normalized

    @staticmethod
    def _fallback(
        evidence: str,
        candidates: list[EvidenceCandidate],
        citations: list[dict[str, Any]],
        error_message: str = "模型不可用",
    ) -> list[dict[str, Any]]:
        """保守回退路径。

        关键修复：
        1. 候选条款必须经过 rank_candidates 评分筛选，不再直接取 candidates[:5]。
        2. 默认 evaluation 改为 "2"（部分符合，需人工复核），不再对全部候选判 NC。
        3. 只有当证据明确包含负面词且候选条款与证据有相关性时，才输出 NC。
        4. 草稿标记 model_status="fallback" 让前端显示「模型异常」徽标。
        5. confidence 降至 0.2，避免被 safe_only 模式自动采纳。
        """
        # 关键修复：基于评分筛选候选，避免无关条款被强行匹配
        ranked = EvidenceAgentService.rank_candidates(evidence, candidates, limit=5)
        is_negative = any(term in evidence for term in NEGATIVE_TERMS)
        quality = "partial" if len(evidence.strip()) < 40 else "sufficient"
        results = []
        for candidate in ranked:
            # 默认评估为"部分符合，需人工复核"，不再强行判 NC
            evaluation = "2"
            audit_findings = ""
            rectification = "请补充客观证据并由审核员确认。"
            # 只有当证据含负面词且条款被 rank 评分命中（score>0）时才提示风险
            if is_negative:
                # 注意：这里仍不直接判 NC（evaluation=3），只标记需重点复核
                # 真正的 NC 必须由 LLM 或人工判断
                audit_findings = f"证据包含负面关键词，请重点复核条款 {candidate.clause_no}。原始证据：{evidence[:200]}"
            results.append(
                {
                    "candidate": candidate,
                    "evaluation_3level": evaluation,
                    "evidence_quality": quality,
                    "reasoning": f"模型不可用（{error_message}），已按候选评分排序输出，默认为部分符合，需人工复核。",
                    "audit_findings": audit_findings,
                    "rectification_suggestion": rectification,
                    "confidence": 0.2,
                    "citations": citations[:2],
                    "model_status": "fallback",
                }
            )
        return results


evidence_agent_service = EvidenceAgentService()
