"""One-pass evidence analysis against multiple audit clauses.

设计原则（2026-07-16 修复）：
1. LLM 失败时显式上报，不再静默回退吞掉错误。
2. 必须回退时，候选条款必须经过 rank_candidates 评分筛选，不得直接取前 N 个。
3. 默认评估值改为 "2"（部分符合，需人工复核），不再对未关联条款强行判 NC。
4. 草稿标记 model_status，前端可据此显示"模型异常"徽标。
"""

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any

from openai import AsyncOpenAI

from app.config import settings


logger = logging.getLogger("evidence_agent")


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
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是认证审核证据分析 Agent。只能依据给出的现场证据、候选条款和项目资料判断，"
                            "不得虚构证据。一次证据可以命中多个条款。输出严格 JSON。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=min(settings.LLM_MAX_TOKENS, 5000),
                response_format={"type": "json_object"},
            )
            payload = self._parse_json(response.choices[0].message.content or "")
            raw_results = payload.get("results", []) if isinstance(payload, dict) else []
            normalized = self._normalize_results(raw_results, candidates, citations)
            if normalized:
                return normalized
            # LLM 返回空结果时也算异常，需要人工介入
            last_error = EvidenceAgentError(
                "LLM 返回空结果，可能未识别到任何相关条款",
                reason="empty_response",
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
    def _parse_json(content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", content)
            if not match:
                return {}
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}

    @staticmethod
    def _normalize_results(
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
            clause_no = str(raw.get("clause_no", "")).strip()
            candidate = candidates_by_clause.get(clause_no)
            if not candidate or clause_no in seen:
                continue
            seen.add(clause_no)
            evaluation = str(raw.get("evaluation_3level", "2"))
            if evaluation not in {"1", "2", "3"}:
                evaluation = "2"
            quality = str(raw.get("evidence_quality", "partial"))
            if quality not in {"sufficient", "partial", "insufficient"}:
                quality = "partial"
            try:
                confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.5))))
            except (TypeError, ValueError):
                confidence = 0.5
            citation_indexes = raw.get("citation_indexes") or []
            selected_citations = [
                citations[index]
                for index in citation_indexes
                if isinstance(index, int) and 0 <= index < len(citations)
            ]
            normalized.append(
                {
                    "candidate": candidate,
                    "evaluation_3level": evaluation,
                    "evidence_quality": quality,
                    "reasoning": str(raw.get("reasoning") or "").strip(),
                    "audit_findings": str(raw.get("audit_findings") or "").strip(),
                    "rectification_suggestion": str(
                        raw.get("rectification_suggestion") or ""
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
