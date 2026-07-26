"""长期记忆服务（#5）。

此前 AgentMemory 表只有定义、零使用。本服务把它接上，让 Agent 成为"记得住的搭档"：

- **企业级记忆**：跨会话、跨审核员沉淀"这家企业反复出现的问题"（如某条款屡次不符合），
  下次审核该企业时自动带入准备简报，实现"AI 记得上次的坑"。
- **用户级记忆**：单个审核员的偏好（可后续扩展）。

检索采用"作用域过滤 + 重要度/时间排序"的稳健实现（不引入向量检索的额外成本，
embedding 字段保留给未来升级）。写入带幂等去重，避免同一事实反复堆积。
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import AgentMemory


class AgentMemoryService:
    async def remember_enterprise(
        self,
        db: AsyncSession,
        *,
        enterprise_id: UUID,
        content: str,
        user_id: UUID,
        memory_type: str = "inspection_pattern",
        importance: float = 0.6,
    ) -> Optional[AgentMemory]:
        """写入一条企业级长期记忆（带幂等去重）。"""
        content = (content or "").strip()
        if not content:
            return None

        # 幂等：同企业同内容已存在则只提升重要度与访问计数，不重复插入
        existing = (await db.execute(
            select(AgentMemory).where(
                AgentMemory.scope == "enterprise",
                AgentMemory.enterprise_id == enterprise_id,
                AgentMemory.content == content,
            ).limit(1)
        )).scalar_one_or_none()
        if existing:
            existing.importance_score = min(1.0, float(existing.importance_score or 0.5) + 0.05)
            existing.access_count = (existing.access_count or 0) + 1
            await db.flush()
            return existing

        mem = AgentMemory(
            user_id=user_id,
            enterprise_id=enterprise_id,
            scope="enterprise",
            memory_type=memory_type,
            content=content,
            importance_score=importance,
        )
        db.add(mem)
        await db.flush()
        return mem

    async def recall_for_enterprise(
        self, db: AsyncSession, enterprise_id: UUID, limit: int = 5
    ) -> list[dict[str, Any]]:
        """取该企业最重要/最新的长期记忆，用于审核准备与对话上下文。"""
        rows = (await db.execute(
            select(AgentMemory)
            .where(
                AgentMemory.scope == "enterprise",
                AgentMemory.enterprise_id == enterprise_id,
            )
            .order_by(
                AgentMemory.importance_score.desc().nullslast(),
                AgentMemory.created_at.desc(),
            )
            .limit(limit)
        )).scalars().all()

        # 记一次访问（用于后续按使用频率淘汰/加权）
        for m in rows:
            m.access_count = (m.access_count or 0) + 1
        if rows:
            await db.flush()

        return [
            {"type": m.memory_type, "content": m.content, "importance": float(m.importance_score or 0)}
            for m in rows
        ]

    async def recall_text(self, db: AsyncSession, enterprise_id: UUID, limit: int = 5) -> str:
        """把企业记忆拼成可直接嵌入提示词的一段文本；无记忆返回空串。"""
        memories = await self.recall_for_enterprise(db, enterprise_id, limit)
        if not memories:
            return ""
        lines = [f"- {m['content']}" for m in memories]
        return "该企业的历史记忆（来自既往审核沉淀）：\n" + "\n".join(lines)


agent_memory_service = AgentMemoryService()
