"""AI 草稿反馈闭环（#1）。

系统每天都在产生一份天然标注：每条 AI 草稿被审核员 **直接采纳 / 改后采纳 / 拒绝**。
本服务把这份信号聚合出来（按体系/条款/prompt 版本），用于：

1. 观测——哪些条款/哪个提示词版本 AI 靠谱，哪些经常被改被拒；
2. A/B——`prompt_version` 现在带内容指纹，可直接对比不同版本的采纳率；
3. 回流——把最近被拒/被大改的例子作为 few-shot 反馈给证据分析提示词。

术语（基于 AiDraftRecord.status + was_edited）：
- 采纳(confirmed, 未改)  → AI 直接对
- 修改采纳(confirmed, edited) → AI 半对
- 拒绝(rejected)          → AI 错
- 被替代(superseded)      → 重新生成，不计入分母
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence_agent import AiDraftRecord


def _rate(numer: int, denom: int) -> float:
    return round(numer / denom, 4) if denom else 0.0


async def _grouped_counts(
    db: AsyncSession, group_col, project_id: Optional[UUID]
) -> dict[str, dict[str, int]]:
    stmt = select(
        group_col,
        AiDraftRecord.status,
        func.coalesce(AiDraftRecord.was_edited, False),
        func.count(AiDraftRecord.id),
    )
    if project_id:
        stmt = stmt.where(AiDraftRecord.project_id == project_id)
    stmt = stmt.group_by(group_col, AiDraftRecord.status, AiDraftRecord.was_edited)

    buckets: dict[str, dict[str, int]] = {}
    for key, status, edited, count in (await db.execute(stmt)).all():
        k = str(key) if key is not None else "(未标注)"
        b = buckets.setdefault(k, {"confirmed": 0, "edited": 0, "rejected": 0, "superseded": 0, "draft": 0})
        if status == "confirmed" and edited:
            b["edited"] += count
        elif status in b:
            b[status] += count
    return buckets


def _summarize(buckets: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    rows = []
    for key, b in buckets.items():
        # 分母 = 已决定的草稿（采纳/修改采纳/拒绝），不含仍是 draft / 被替代
        decided = b["confirmed"] + b["edited"] + b["rejected"]
        rows.append({
            "key": key,
            "confirmed": b["confirmed"],
            "edited": b["edited"],
            "rejected": b["rejected"],
            "pending": b["draft"],
            "decided": decided,
            "accept_rate": _rate(b["confirmed"], decided),        # 直接采纳率
            "edit_rate": _rate(b["edited"], decided),             # 修改采纳率
            "reject_rate": _rate(b["rejected"], decided),         # 拒绝率
        })
    # 拒绝率高的排前面，便于发现"AI 常出错"的地方
    rows.sort(key=lambda r: (r["reject_rate"] + r["edit_rate"], r["decided"]), reverse=True)
    return rows


class AgentFeedbackService:
    async def stats(
        self, db: AsyncSession, project_id: Optional[UUID] = None
    ) -> dict[str, Any]:
        """返回按体系 / 条款 / prompt 版本的采纳/修改/拒绝率。"""
        by_system = _summarize(await _grouped_counts(db, AiDraftRecord.certification_system, project_id))
        by_clause = _summarize(await _grouped_counts(db, AiDraftRecord.primary_clause_no, project_id))
        by_prompt = _summarize(await _grouped_counts(db, AiDraftRecord.prompt_version, project_id))

        total = {"confirmed": 0, "edited": 0, "rejected": 0, "decided": 0}
        for row in by_system:
            for k in total:
                total[k] += row[k]
        total["accept_rate"] = _rate(total["confirmed"], total["decided"])
        total["edit_rate"] = _rate(total["edited"], total["decided"])
        total["reject_rate"] = _rate(total["rejected"], total["decided"])

        return {
            "overall": total,
            "by_certification_system": by_system,
            "by_clause": by_clause[:30],
            "by_prompt_version": by_prompt,
            # 采纳率明显偏低（拒绝+修改 > 50% 且样本≥5）的条款，值得人工调提示词/候选匹配
            "low_quality_clauses": [
                r for r in by_clause
                if r["decided"] >= 5 and (r["reject_rate"] + r["edit_rate"]) > 0.5
            ][:15],
        }

    async def few_shot_examples(
        self,
        db: AsyncSession,
        certification_system: Optional[str] = None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """取最近被拒绝/被修改的草稿作为负面 few-shot，用于回流改进提示词。

        返回精简后的 {条款, AI原判定, AI理由, 结局}，供证据分析在下次生成时
        作为"以下情况 AI 曾判错，请注意"注入提示词。
        """
        stmt = (
            select(AiDraftRecord)
            .where(AiDraftRecord.status.in_(("rejected",)))
            .order_by(AiDraftRecord.confirmed_at.desc().nullslast(), AiDraftRecord.updated_at.desc())
            .limit(limit * 3)
        )
        if certification_system:
            stmt = stmt.where(AiDraftRecord.certification_system == certification_system)
        rows = (await db.execute(stmt)).scalars().all()

        examples = []
        for d in rows[:limit]:
            examples.append({
                "clause_no": d.primary_clause_no,
                "ai_evaluation": str(d.evaluation),
                "ai_reasoning": (d.reasoning or "")[:200],
                "outcome": "被审核员拒绝",
            })
        return examples


agent_feedback_service = AgentFeedbackService()
