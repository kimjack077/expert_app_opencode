"""可调用工具注册表。

对话 Agent 与规划器（planner）共用同一批「读取/推理」工具，避免两代 Agent 各自造轮子。
每个工具声明：名称、给模型看的描述、参数 JSON Schema、执行函数、成本档位、是否只读。

注意分工：本注册表只放**读取/检索/推理**类工具（不落库）。真正的写入由
``services.agent_actions`` 的动作注册表负责，且必须经用户确认。因此这里的工具
可以被规划器自由编排，不存在"模型自己把数据改了"的风险。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

ToolHandler = Callable[[AsyncSession, User, dict], Awaitable[Any]]


@dataclass
class AgentTool:
    name: str
    description: str
    parameters: dict  # JSON Schema (OpenAI function-calling 风格)
    handler: ToolHandler
    read_only: bool = True
    tier: str = "cheap"

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[AgentTool]:
        return self._tools.get(name)

    def list(self) -> list[AgentTool]:
        return list(self._tools.values())

    def openai_schemas(self) -> list[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def catalog(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "read_only": t.read_only}
            for t in self._tools.values()
        ]

    async def execute(
        self, name: str, db: AsyncSession, user: User, args: dict
    ) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            return {"error": f"未知工具: {name}"}
        try:
            return await tool.handler(db, user, args or {})
        except Exception as exc:  # 工具失败不应中断整个规划
            return {"error": f"{type(exc).__name__}: {exc}"}


tool_registry = ToolRegistry()


# ----------------------------------------------------------------------------
# 工具实现（复用现有服务/模型）
# ----------------------------------------------------------------------------


def _uuid(value: Any) -> Optional[UUID]:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (ValueError, TypeError):
        return None


async def _tool_enterprise_history(db: AsyncSession, user: User, args: dict) -> Any:
    """某企业的历史检查/审核概况与遗留不符合项。"""
    from app.models.enterprise import Enterprise
    from app.models.audit_project import AuditProject, Nonconformity

    ent_id = _uuid(args.get("enterprise_id"))
    if not ent_id:
        return {"error": "缺少 enterprise_id"}
    ent = await db.get(Enterprise, ent_id)
    if not ent:
        return {"error": "企业不存在"}

    ncs = (await db.execute(
        select(Nonconformity)
        .join(AuditProject, Nonconformity.project_id == AuditProject.id)
        .where(AuditProject.enterprise_id == ent_id)
        .order_by(Nonconformity.created_at.desc())
        .limit(20)
    )).scalars().all()

    return {
        "enterprise": ent.name,
        "last_audit_date": str(getattr(ent, "last_audit_date", None) or ""),
        "risk_level": getattr(ent, "risk_level", None),
        "historical_nonconformities": [
            {
                "clause_no": nc.clause_no,
                "severity": nc.severity,
                "description": (nc.description or "")[:200],
                "status": nc.status,
            }
            for nc in ncs
        ],
        "open_nc_count": sum(1 for nc in ncs if nc.status not in ("verified", "closed")),
    }


async def _tool_search_regulations(db: AsyncSession, user: User, args: dict) -> Any:
    """在知识库中语义检索法规/标准条款。"""
    from app.services.rag_service import rag_service

    query = str(args.get("query") or "").strip()
    if not query:
        return {"error": "缺少 query"}
    try:
        results = await rag_service.search_knowledge(query, db, top_k=int(args.get("top_k") or 5))
    except Exception as exc:
        return {"error": f"检索失败: {exc}"}
    return {"query": query, "results": results}


async def _tool_project_status(db: AsyncSession, user: User, args: dict) -> Any:
    """审核项目的进度与质量门禁快照（还差什么才能出案卷）。"""
    from app.services.project_access_service import ensure_project_access
    from app.services.project_artifact_service import project_artifact_service

    pid = _uuid(args.get("project_id"))
    if not pid:
        return {"error": "缺少 project_id"}
    await ensure_project_access(db, pid, user)
    quality = await project_artifact_service.quality_check(db, pid)
    return {
        "passed": quality.get("passed"),
        "archive_completeness_score": quality.get("archive_completeness_score"),
        "blockers": quality.get("blockers", [])[:10],
        "warnings": quality.get("warnings", [])[:10],
    }


def _register_default_tools() -> None:
    tool_registry.register(AgentTool(
        name="get_enterprise_history",
        description="查询某企业的历史审核概况、风险等级与遗留不符合项。用于审核准备。",
        parameters={
            "type": "object",
            "properties": {"enterprise_id": {"type": "string", "description": "企业 UUID"}},
            "required": ["enterprise_id"],
        },
        handler=_tool_enterprise_history,
    ))
    tool_registry.register(AgentTool(
        name="search_regulations",
        description="在知识库中语义检索相关法规、标准条款，返回带来源的片段。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索问题或关键词"},
                "top_k": {"type": "integer", "description": "返回条数，默认 5"},
            },
            "required": ["query"],
        },
        handler=_tool_search_regulations,
    ))
    tool_registry.register(AgentTool(
        name="get_project_status",
        description="获取审核项目的完成度、质量门禁阻断项与提醒项（还差什么才能出案卷）。",
        parameters={
            "type": "object",
            "properties": {"project_id": {"type": "string", "description": "审核项目 UUID"}},
            "required": ["project_id"],
        },
        handler=_tool_project_status,
    ))


_register_default_tools()
