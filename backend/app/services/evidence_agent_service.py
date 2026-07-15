"""One-pass evidence analysis against multiple audit clauses."""

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from openai import AsyncOpenAI

from app.config import settings


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
        except Exception as exc:
            print(f"[EvidenceAgent] model analysis failed: {type(exc).__name__}: {exc}")
        return self._fallback(evidence, candidates, citations)

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
                }
            )
        return normalized

    @staticmethod
    def _fallback(
        evidence: str,
        candidates: list[EvidenceCandidate],
        citations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        is_negative = any(term in evidence for term in NEGATIVE_TERMS)
        quality = "partial" if len(evidence.strip()) < 40 else "sufficient"
        evaluation = "3" if is_negative else ("2" if quality == "partial" else "1")
        results = []
        for candidate in candidates[:5]:
            results.append(
                {
                    "candidate": candidate,
                    "evaluation_3level": evaluation,
                    "evidence_quality": quality,
                    "reasoning": "模型不可用，已按证据关键词和候选条款进行保守判断，需人工复核。",
                    "audit_findings": evidence if is_negative else "",
                    "rectification_suggestion": "请补充客观证据并由审核员确认。" if is_negative else "",
                    "confidence": 0.45,
                    "citations": citations[:2],
                }
            )
        return results


evidence_agent_service = EvidenceAgentService()
