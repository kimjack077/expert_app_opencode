"""Authorization helpers for project-scoped audit Agent features."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_project import AuditProject, AuditTeamMember
from app.models.user import User


PRIVILEGED_ROLES = {"super_admin", "admin"}


async def get_project_or_404(
    db: AsyncSession,
    project_id: UUID | str,
) -> AuditProject:
    result = await db.execute(
        select(AuditProject).where(AuditProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="审核项目不存在")
    return project

async def ensure_project_access(
    db: AsyncSession,
    project_id: UUID | str,
    user: User,
    *,
    require_manage: bool = False,
) -> AuditProject:
    """Return the project after enforcing project membership.

    Project creators, team leaders and assigned team members may use the
    project Agent.  Destructive/approval operations additionally require an
    administrator, the project creator, or the team leader.
    """

    project = await get_project_or_404(db, project_id)
    if user.role in PRIVILEGED_ROLES:
        return project

    user_id = str(user.id)
    is_creator = bool(project.created_by) and str(project.created_by) == user_id
    is_leader = bool(project.team_leader_id) and str(project.team_leader_id) == user_id
    if require_manage and not (is_creator or is_leader):
        raise HTTPException(status_code=403, detail="仅项目负责人可执行此操作")

    if is_creator or is_leader:
        return project

    member_result = await db.execute(
        select(AuditTeamMember.id).where(
            AuditTeamMember.project_id == project.id,
            AuditTeamMember.member_id == user.id,
        )
    )
    if member_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="无权访问此审核项目")
    return project
