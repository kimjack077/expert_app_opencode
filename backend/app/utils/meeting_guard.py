"""会议记录唯一性口径的**唯一来源**。

业务规则：首次会议与末次会议在**同一审核项目内只能有一条**——
"首次会议不能开两遍"。阶段沟通、内部会议等类型允许多次。

历史上这条校验只写在 REST 端点 ``audit_projects.create_meeting`` 里，
智审 Agent 的写入路径（``agent_actions._action_create_meeting_record``）
没有这道关卡，于是通过 Agent「确认录入」可以在同一项目下写入第二条
首次会议。两处必须同口径，故收敛到本模块。
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_project import CommunicationMeeting

#: 同一项目内只允许存在一条的会议类型
UNIQUE_MEETING_TYPES: tuple[str, ...] = ("opening", "closing")

#: 会议类型中文名
MEETING_TYPE_LABELS: dict[str, str] = {
    "opening": "首次会议",
    "closing": "末次会议",
    "interim": "阶段沟通",
    "internal": "内部会议",
}


async def find_duplicate_meeting(
    db: AsyncSession, project_id: UUID, meeting_type: str
) -> Optional[UUID]:
    """返回同项目、同类型会议的已有记录 id。

    该类型不要求唯一（如阶段沟通）或尚无记录时返回 ``None``。
    """
    if meeting_type not in UNIQUE_MEETING_TYPES:
        return None
    result = await db.execute(
        select(CommunicationMeeting.id)
        .where(
            CommunicationMeeting.project_id == project_id,
            CommunicationMeeting.meeting_type == meeting_type,
        )
        .limit(1)
    )
    return result.scalars().first()


def duplicate_meeting_message(meeting_type: str) -> str:
    """生成用户可读的重复提示，两个写入路径共用，避免文案分叉。"""
    label = MEETING_TYPE_LABELS.get(meeting_type, "同类型会议")
    return f"该项目已存在{label}记录，请编辑已有记录或选择其他会议类型"
