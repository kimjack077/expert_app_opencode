import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, update
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.task import InspectionTask, TaskItemRecord
from app.models.media import MediaFile
from app.models.template import InspectionTemplate, TemplateItem
from app.schemas import (
    ApiResponse,
    InspectionTaskCreate,
    InspectionTaskUpdate,
    InspectionTaskResponse,
    InspectionRecordCreate,
    InspectionRecordUpdate,
    InspectionRecordResponse,
    InspectionSummary,
)
from app.utils.security import get_current_user, get_current_admin_user
from app.utils.roles import ADMIN_ROLES, RECORD_VIEW_ALL_ROLES, is_admin
from app.utils.item_completion import is_item_assessed, resolve_check_type
from app.utils.category import is_category_node, load_parent_ids
from app.utils.item_stats import classify_result
from app.services import AuditService
from app.services.formal_audit_sync_service import (
    can_access_linked_task,
    get_linked_plan_item,
    overall_from_remarks,
    sync_task_to_formal_record,
)
from app.services.llm_service import llm_service
from app.utils.response import make_response
from app.utils.business_time import business_day_bounds

# Alias for backward compatibility
InspectionRecord = TaskItemRecord

router = APIRouter()




async def _recalculate_task_statistics(
    db: AsyncSession,
    task: InspectionTask,
) -> None:
    """重新计算任务的统计数据并更新remarks。

    当记录被更新时调用，确保remarks中的统计数据与实际记录保持一致。
    """
    # 查询该任务的所有记录
    result = await db.execute(
        select(TaskItemRecord)
        .where(TaskItemRecord.task_id == task.id)
    )
    records = result.scalars().all()

    if not records:
        return

    # 统计各类结果：统一走 classify_result，兼容历史/外部写入的
    # ``not_applicable`` / ``compliant`` 等同义值（只认 "na" 会漏计）。
    pass_count = sum(1 for r in records if classify_result(r.result) == "pass")
    fail_count = sum(1 for r in records if classify_result(r.result) == "fail")
    na_count = sum(1 for r in records if classify_result(r.result) == "na")
    total = len(records)

    # 如果remarks存在且包含统计信息，则更新统计部分
    if task.remarks:
        # 更新统计数据：替换"符合项 X 项，不符合项 Y 项"的模式
        updated_remarks = re.sub(
            r'符合项\s*\d+\s*项',
            f'符合项 {pass_count} 项',
            task.remarks
        )
        updated_remarks = re.sub(
            r'不符合项\s*\d+\s*项',
            f'不符合项 {fail_count} 项',
            updated_remarks
        )
        updated_remarks = re.sub(
            r'不适用项\s*\d+\s*项',
            f'不适用项 {na_count} 项',
            updated_remarks
        )
        updated_remarks = re.sub(
            r'共检查\s*\d+\s*项',
            f'共检查 {total} 项',
            updated_remarks
        )

        # 根据不符合项数量更新判定结论
        if fail_count > 0:
            # 有不符合项：将"均符合要求"替换为实际情况
            if '均符合要求' in updated_remarks:
                updated_remarks = updated_remarks.replace(
                    '均符合要求',
                    f'发现 {fail_count} 项不符合要求'
                )
        else:
            # 无不符合项：将"发现X项不符合要求"还原为"均符合要求"
            updated_remarks = re.sub(
                r'发现\s*\d+\s*项不符合要求',
                '均符合要求',
                updated_remarks
            )

        task.remarks = updated_remarks


async def _normalize_numeric_verdict(
    db: AsyncSession,
    template_item_id: Optional[str],
    result: Optional[str],
    result_value: Optional[str],
) -> Optional[str]:
    """BUG-11 服务端兜底：数值/打分项的 pass 必须由阈值裁决得出。

    历史上客户端对任何数值录入都默认 ``result='pass'``，未配置阈值的项也被
    算进合格数，虚增合规率。规则：
    - 仅当客户端传入 ``pass`` 时才做收敛（显式 fail/na 等人工判定一律尊重）；
    - numeric：有任一阈值且在范围内 → pass，超界 → fail，无阈值 → None（计入「其他项」）；
    - score：有合格线 → 按线裁决，无合格线 → None。
    """
    if classify_result(result) != "pass" or not template_item_id:
        return result
    if result_value is None or str(result_value).strip() == "":
        return result
    try:
        item = await db.get(TemplateItem, UUID(str(template_item_id)))
    except (ValueError, TypeError):
        return result
    if item is None:
        return result
    check_type = resolve_check_type(item)
    if check_type not in {"numeric", "score"}:
        return result
    try:
        number = float(str(result_value).strip())
    except (TypeError, ValueError):
        return result
    if check_type == "score":
        if item.pass_score is None:
            return None
        return "pass" if number >= float(item.pass_score) else "fail"
    if item.min_value is None and item.max_value is None:
        return None
    in_range = (item.min_value is None or number >= float(item.min_value)) and (
        item.max_value is None or number <= float(item.max_value)
    )
    return "pass" if in_range else "fail"


async def _sync_reaudited_task_to_formal_record(
    db: AsyncSession,
    task: InspectionTask,
    current_user: User,
) -> None:
    """已完成任务的填报被再次修改后（复审/再认证场景），同步回正式审核记录。

    调用时机：**必须在记录本身的 commit 之后**。原因有二：

    1. ``AsyncSessionLocal`` 配置了 ``autoflush=False``，若在 commit 前同步，
       ``sync_task_to_formal_record`` 内部的 ``select(TaskItemRecord...)``
       读到的是**旧值**，会把未提交的修改漏在正式记录之外；
    2. 先落记录再同步，保证用户手上的填报不因同步失败而丢失——
       同步失败以 409 显式报错，用户重试即可，不会出现"两边都丢了"。

    错误语义（与 :func:`complete_task` 对齐，**绝不静默吞异常**）：

    - ``ValueError`` 是 ``sync_task_to_formal_record`` 的**面向用户的业务校验失败**
      （如"同一模板项存在重复检查记录"），转 409 抛给前端。
      旧实现 ``except Exception: pass`` 会把这类失败吞掉，正式审核记录与任务记录
      悄悄分叉，用户还以为同步成功了——这是本轮规范化要修的根问题；
    - 其余异常（网络/约束冲突等）原样上抛，由全局异常处理归类。

    未挂审核计划项的任务（普通巡检任务）没有"正式审核记录"可同步，直接返回。
    """
    if task.status != "completed":
        return

    plan_item = await get_linked_plan_item(db, task.id)
    if plan_item is None:
        return

    try:
        await sync_task_to_formal_record(db, task, plan_item, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"记录已保存，但同步到正式审核记录失败：{exc}",
        ) from exc

    # 审计留痕：复审同步是"改写已归档结论"的动作，必须可追溯。
    # 注意 log_action 只 flush 不 commit，必须在这里显式提交，
    # 否则随请求会话 close 一起回滚（complete_task 里的日志就有此问题）。
    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "sync_reaudited_task_to_formal_record",
        "task",
        str(task.id),
        detail={"plan_item_id": str(plan_item.id), "project_id": str(plan_item.project_id)},
    )
    await db.commit()


@router.get("", response_model=ApiResponse)
async def get_tasks(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="按标题/任务编号/检查对象/地点模糊搜索"),
    sort_by: Optional[str] = Query("created_at", description="排序字段: created_at / scheduled_at"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 条件构建一次，分页与计数共用，保证 total 与实际可见数据一致
    conditions = [InspectionTask.is_deleted == False]  # noqa: E712

    if current_user.role not in RECORD_VIEW_ALL_ROLES:
        conditions.append(InspectionTask.assigned_to == current_user.id)

    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                InspectionTask.title.ilike(pattern),
                InspectionTask.task_no.ilike(pattern),
                InspectionTask.target_name.ilike(pattern),
                InspectionTask.target_address.ilike(pattern),
            )
        )

    if status:
        if status == "todo":
            conditions.append(InspectionTask.status.in_(["pending", "in_progress"]))
        elif "," in status:
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            conditions.append(InspectionTask.status.in_(statuses))
        else:
            conditions.append(InspectionTask.status == status)

    order_col = (
        InspectionTask.scheduled_at.desc().nullslast()
        if sort_by == "scheduled_at"
        else InspectionTask.created_at.desc()
    )
    base_query = (
        select(InspectionTask)
        .where(*conditions)
        .order_by(order_col, InspectionTask.created_at.desc(), InspectionTask.id.desc())
    )

    # PERF：窗口函数随分页查询一次取回数据 + total，任何页都只需 1 次 DB 往返
    # （本地连公网远程库时每次往返 50~800ms；此前的 limit+1 试探只在首页且
    # 数据不满一页时才省一次 COUNT 查询，翻页仍需两次往返）。
    rows = (
        await db.execute(
            base_query.add_columns(func.count().over().label("_total"))
            .offset(skip)
            .limit(limit)
        )
    ).all()
    tasks = [row[0] for row in rows]
    total = int(rows[0][1]) if rows else 0

    # BUG-05：批量回填审核计划项关联字段（此前列表接口 plan_item_id/audit_project_id 恒为 null，
    # 与详情接口口径不一致），保证 Web / H5 任务卡片能展示所属项目与区域。
    from app.models.audit_project import AuditPlanItem

    plan_map: dict = {}
    task_ids = [t.id for t in tasks]
    if task_ids:
        plan_rows = await db.execute(
            select(AuditPlanItem).where(
                AuditPlanItem.inspection_task_id.in_(task_ids),
                AuditPlanItem.is_deleted == False,  # noqa: E712
            )
        )
        for pi in plan_rows.scalars().all():
            if pi.inspection_task_id:
                plan_map.setdefault(str(pi.inspection_task_id), pi)

    items = []
    for t in tasks:
        data = InspectionTaskResponse.model_validate(t).model_dump()
        pi = plan_map.get(str(t.id))
        if pi:
            data["audit_project_id"] = pi.project_id
            data["plan_item_id"] = pi.id
            data["area_name"] = pi.area_name
            data["clauses"] = pi.clauses
        items.append(data)

    return make_response(data={"items": items, "total": total})


@router.get("/statistics", response_model=ApiResponse)
async def get_task_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """任务状态统计。

    与列表接口使用完全一致的可见范围，供 H5 顶部汇总使用，
    避免前端基于分页数组累加导致「已完成 > 总数」的口径错误。
    """
    conditions = [InspectionTask.is_deleted == False]  # noqa: E712
    if current_user.role not in RECORD_VIEW_ALL_ROLES:
        conditions.append(InspectionTask.assigned_to == current_user.id)

    rows = await db.execute(
        select(InspectionTask.status, func.count(InspectionTask.id))
        .where(*conditions)
        .group_by(InspectionTask.status)
    )
    counts = {(status or "unknown"): count for status, count in rows.all()}
    total = sum(counts.values())
    today, tomorrow = business_day_bounds()
    completed_at = func.coalesce(InspectionTask.completed_at, InspectionTask.updated_at)
    day = func.date(func.timezone("Asia/Shanghai", completed_at))
    activity = (await db.execute(select(day, func.count(InspectionTask.id)).where(
        *conditions, InspectionTask.status == "completed",
        completed_at >= today - timedelta(days=6), completed_at < tomorrow,
    ).group_by(day).order_by(day))).all()

    return make_response(
        data={
            "total": total,
            "pending": counts.get("pending", 0),
            "in_progress": counts.get("in_progress", 0),
            "completed": counts.get("completed", 0),
            "cancelled": counts.get("cancelled", 0),
            "recent_activity": [{"date": str(day), "completed": count} for day, count in activity],
        }
    )


@router.post("", response_model=ApiResponse)
async def create_task(
    task_data: InspectionTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    # 如果指定了模板，检查模板是否存在且未删除
    if task_data.template_id:
        template = await db.get(InspectionTemplate, task_data.template_id)
        if not template or template.is_deleted:
            raise HTTPException(status_code=404, detail="Template not found")

    # 不能用 count(*)+1：并发创建会生成相同编号（且会把软删行计入，删除后编号回退重复）。
    # 改用随机短码，保证唯一且无需额外往返。
    task_no = f"TASK-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"

    task = InspectionTask(
        task_no=task_no,
        title=task_data.title,
        template_id=task_data.template_id,
        assigned_to=task_data.assigned_to,
        assigned_by=current_user.id,
        target_name=task_data.target_name,
        target_address=task_data.target_address,
        target_contact=task_data.target_contact,
        target_phone=task_data.target_phone,
        scheduled_at=task_data.scheduled_at,
        remarks=task_data.remarks,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    if task_data.template_id:
        # 分类目录（存在有效子节点的父节点）集合，统一走 app/utils/category
        parent_ids = await load_parent_ids(db, template_id=task_data.template_id)

        items_result = await db.execute(
            select(TemplateItem)
            .where(
                TemplateItem.template_id == task_data.template_id,
                TemplateItem.is_deleted == False,  # noqa: E712
                TemplateItem.is_category.is_not(True),
            )
            .order_by(TemplateItem.sort_order)
        )
        # 严格只为真正的叶子检查项创建填报记录，杜绝分类目录生成空记录
        leaf_items = [
            i for i in items_result.scalars().all()
            if not is_category_node(i, parent_ids)
        ]

        for item in leaf_items:
            record = InspectionRecord(
                task_id=task.id,
                template_item_id=item.id,
            )
            db.add(record)
        await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "create_task",
        "task",
        str(task.id),
    )

    return make_response(data=InspectionTaskResponse.model_validate(task).model_dump())


@router.get("/{task_id}", response_model=ApiResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view this task")

    # 查询关联的审核计划项信息，并兼容回填缺失的 template_id
    plan_item = None
    try:
        from app.models.audit_project import AuditPlanItem

        task_uuid = UUID(str(task_id))
        plan_result = await db.execute(
            select(AuditPlanItem).where(
                AuditPlanItem.inspection_task_id == task_uuid,
                AuditPlanItem.is_deleted == False,  # noqa: E712
            )
        )
        plan_item = plan_result.scalar_one_or_none()
        if plan_item and not task.template_id and plan_item.template_id:
            task.template_id = plan_item.template_id
            await db.commit()
            await db.refresh(task)
    except Exception:
        # 容错处理
        pass

    data = InspectionTaskResponse.model_validate(task).model_dump()
    if plan_item:
        data["audit_project_id"] = plan_item.project_id
        data["plan_item_id"] = plan_item.id
        data["area_name"] = plan_item.area_name
        data["clauses"] = plan_item.clauses

    # BUG-32：补充指派对象姓名，避免 H5 详情页误显示"未分配"
    if task.assigned_to:
        assignee = await db.get(User, task.assigned_to)
        if assignee and not assignee.is_deleted:
            data["assigned_to_name"] = assignee.full_name or assignee.username

    return make_response(data=data)


async def _validate_task_completion(
    db: AsyncSession,
    task: InspectionTask,
    *,
    remarks: Optional[str],
    template_id: Optional[UUID],
) -> None:
    records = (await db.execute(
        select(TaskItemRecord)
        .options(selectinload(TaskItemRecord.template_item))
        .where(TaskItemRecord.task_id == task.id)
    )).scalars().all()
    items = {
        str(rec.template_item_id): rec.template_item
        for rec in records if rec.template_item is not None
    }
    if template_id:
        template_items = (await db.execute(
            select(TemplateItem).where(
                TemplateItem.template_id == template_id,
                TemplateItem.is_deleted.is_(False),
            )
        )).scalars().all()
        items.update({str(item.id): item for item in template_items})
    template_ids = {
        item.template_id for item in items.values()
        if getattr(item, "template_id", None)
    }
    if template_id:
        template_ids.add(template_id)
    parent_ids = (
        await load_parent_ids(db, template_ids=template_ids) if template_ids else set()
    )
    filled_ids = {
        str(rec.template_item_id) for rec in records
        if any(value is not None and str(value).strip() for value in (
            rec.result, rec.result_value, rec.result_text,
        ))
    }
    missing = [
        item.title or item_id for item_id, item in items.items()
        if item.is_required and not getattr(item, "is_deleted", False)
        and not is_category_node(item, parent_ids) and item_id not in filled_ids
    ]
    if missing:
        preview = "、".join(missing[:3])
        suffix = f" 等 {len(missing)} 项" if len(missing) > 3 else ""
        raise HTTPException(
            status_code=409,
            detail=f"存在未填报的必填检查项，无法完成任务：{preview}{suffix}",
        )
    if overall_from_remarks(remarks) is None:
        raise HTTPException(
            status_code=409,
            detail="请先填写最终判定结论（合格/基本合格/不合格），再完成任务",
        )


@router.put("/{task_id}", response_model=ApiResponse)
async def update_task(
    task_id: str,
    task_data: InspectionTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.audit_project import AuditPlanItem

    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    # 状态机保护：cancelled 是终态，禁止任何修改；completed 禁止回退状态。
    # 此前 PUT 可把已完成任务改回 pending、把已取消任务复活，
    # 绕过 complete/cancel 端点的校验与计划项同步。
    if task.status == "cancelled":
        raise HTTPException(status_code=409, detail="任务已取消，不能修改")
    if task_data.status is not None and task_data.status not in (
        "pending",
        "in_progress",
        "completed",
    ):
        raise HTTPException(
            status_code=422,
            detail="无效的目标状态，取消任务请使用 POST /tasks/{id}/cancel",
        )
    if task.status == "completed":
        if task_data.status is not None and task_data.status != "completed":
            raise HTTPException(status_code=409, detail="任务已完成，不能回退状态")
        # 与记录写入口同一口径：复审修正仅管理角色放行
        if current_user.role not in ADMIN_ROLES:
            raise HTTPException(status_code=409, detail="任务已完成，不可再修改")

    update_data = task_data.model_dump(exclude_unset=True)
    if current_user.role == "expert":
        if not await can_access_linked_task(db, task, current_user):
            raise HTTPException(status_code=403, detail="Not authorized to update this task")
        update_data = {
            key: value for key, value in update_data.items()
            if key in {"status", "remarks", "template_id"} and value is not None
        }

    if task_data.status == "completed" and task.status != "completed":
        await _validate_task_completion(
            db, task,
            remarks=update_data.get("remarks", task.remarks),
            template_id=update_data.get("template_id", task.template_id),
        )

    for key, value in update_data.items():
        setattr(task, key, value)
    if task_data.status == "in_progress" and current_user.role == "expert":
        task.started_at = datetime.now(timezone.utc)
    elif task_data.status == "completed":
        task.completed_at = task.completed_at or datetime.now(timezone.utc)

    # 模板绑定与同步：若任务绑定了模板，自动同步至关联计划项，并在无检查项时自动补齐
    if task.template_id:
        try:
            task_uuid = UUID(task_id)
            plan_res = await db.execute(
                select(AuditPlanItem).where(
                    AuditPlanItem.inspection_task_id == task_uuid,
                    AuditPlanItem.is_deleted == False,  # noqa: E712
                )
            )
            linked_plan = plan_res.scalar_one_or_none()
            if linked_plan and not linked_plan.template_id:
                linked_plan.template_id = task.template_id
        except Exception:
            pass

        existing_items_count = (await db.execute(
            select(func.count(InspectionRecord.id)).where(InspectionRecord.task_id == task.id)
        )).scalar() or 0
        if existing_items_count == 0:
            template_parent_ids = await load_parent_ids(db, template_id=task.template_id)
            items_result = await db.execute(
                select(TemplateItem)
                .where(
                    TemplateItem.template_id == task.template_id,
                    TemplateItem.is_deleted == False,  # noqa: E712
                    TemplateItem.is_category.is_not(True),
                )
                .order_by(TemplateItem.sort_order)
            )
            leaf_items = [
                i for i in items_result.scalars().all()
                if not is_category_node(i, template_parent_ids)
            ]
            for it in leaf_items:
                db.add(InspectionRecord(task_id=task.id, template_item_id=it.id))

    # 完成任务和管理员修正已完成任务的备注，都同步正式记录。
    if task_data.status == "completed" or (
        task.status == "completed" and "remarks" in update_data
    ):
        await db.flush()
        try:
            linked_plan_item = await get_linked_plan_item(db, UUID(task_id))
        except ValueError:
            linked_plan_item = None
        if linked_plan_item:
            try:
                await sync_task_to_formal_record(
                    db,
                    task,
                    linked_plan_item,
                    current_user.id,
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            await _sync_project_status_after_plan_item(db, linked_plan_item.project_id)

    await db.commit()
    await db.refresh(task)

    return make_response(data=InspectionTaskResponse.model_validate(task).model_dump())


@router.post("/{task_id}/start", response_model=ApiResponse)
async def start_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.audit_project import AuditPlanItem, AuditProject

    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    # 管理员可以启动任何任务，专家只能启动分配给自己的任务
    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not assigned to you")

    if task.status != "pending":
        raise HTTPException(status_code=400, detail="Task cannot be started")

    task.status = "in_progress"
    task.started_at = datetime.now(timezone.utc)

    # 检查是否有关联的审核计划项，更新为进行中状态
    try:
        task_uuid = UUID(task_id)
        plan_item_result = await db.execute(
            select(AuditPlanItem).where(AuditPlanItem.inspection_task_id == task_uuid)
        )
        plan_item = plan_item_result.scalar_one_or_none()
    except ValueError:
        plan_item = None
    if plan_item:
        plan_item.status = "in_progress"
        # 更新审核项目状态
        project = await db.get(AuditProject, plan_item.project_id)
        if project and project.status == "planning":
            project.status = "in_progress"

    await db.commit()

    await AuditService.log_action(
        db, str(current_user.id), current_user.username, "start_task", "task", task_id
    )

    return make_response(message="Task started")


@router.post("/{task_id}/cancel", response_model=ApiResponse)
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消尚未完成的任务，并同步关联审核计划项状态。"""
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    if not is_admin(current_user.role) and not await can_access_linked_task(
        db, task, current_user
    ):
        raise HTTPException(status_code=403, detail="Not authorized to cancel this task")

    if task.status == "cancelled":
        raise HTTPException(status_code=409, detail="任务已取消，不能重复操作")
    if task.status == "completed":
        raise HTTPException(status_code=409, detail="任务已完成，不能取消")

    task.status = "cancelled"
    from app.models.audit_project import AuditPlanItem

    try:
        task_uuid = UUID(task_id)
    except ValueError:
        task_uuid = None
    if task_uuid:
        plan_item = (
            await db.execute(
                select(AuditPlanItem).where(
                    AuditPlanItem.inspection_task_id == task_uuid,
                    AuditPlanItem.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if plan_item:
            plan_item.status = "cancelled"

    await db.commit()
    await AuditService.log_action(
        db, str(current_user.id), current_user.username, "cancel_task", "task", task_id
    )
    await db.commit()
    return make_response(message="Task cancelled")


async def _sync_project_status_after_plan_item(db: AsyncSession, project_id) -> None:
    """计划项完成后回写审核项目状态。

    规则：
    - 还有未完成的计划项 → 项目置为进行中
    - 全部计划项完成 → 项目置为已完成，并补记 actual_end

    原实现只在任务开始时把项目置为 in_progress，**没有任何地方置 completed**，
    导致审核统计里「已完成」永远是 0（测试问题清单第 16 条）。
    """
    if not project_id:
        return

    from app.models.audit_project import AuditPlanItem, AuditProject

    project = await db.get(AuditProject, project_id)
    if not project or project.is_deleted:
        return
    # 已取消/已完成的项目不再被回写覆盖
    if project.status in ("cancelled", "completed"):
        return

    remaining = (
        await db.execute(
            select(func.count(AuditPlanItem.id)).where(
                AuditPlanItem.project_id == project_id,
                AuditPlanItem.is_deleted == False,  # noqa: E712
                AuditPlanItem.status != "completed",
            )
        )
    ).scalar() or 0

    if remaining == 0:
        project.status = "completed"
        if not project.actual_end:
            project.actual_end = datetime.now(timezone.utc)
    elif project.status == "planning":
        project.status = "in_progress"


@router.post("/{task_id}/complete", response_model=ApiResponse)
async def complete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "expert" and not await can_access_linked_task(
        db, task, current_user
    ):
        raise HTTPException(status_code=403, detail="Not assigned to you")

    if task.status == "cancelled":
        raise HTTPException(status_code=409, detail="任务已取消，不能完成")
    if task.status == "completed":
        raise HTTPException(status_code=409, detail="任务已完成，不能重复提交")

    await _validate_task_completion(
        db, task, remarks=task.remarks, template_id=task.template_id,
    )
    await db.flush()

    try:
        task_uuid = UUID(task_id)
        plan_item = await get_linked_plan_item(db, task_uuid)
    except ValueError:
        plan_item = None

    if plan_item:
        try:
            await sync_task_to_formal_record(
                db,
                task,
                plan_item,
                current_user.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        # 计划项完成后回写项目状态（全部完成 → 项目已完成）
        await _sync_project_status_after_plan_item(db, plan_item.project_id)
    else:
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)

    await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "complete_task",
        "task",
        task_id,
    )

    return make_response(message="Task completed")


@router.delete("/{task_id}", response_model=ApiResponse)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除检查任务（仅管理员可删除，软删除）"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only admin can delete tasks")

    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    from app.utils.soft_delete import soft_delete_cascade

    # 按级联策略表处理子行：task_item_records 硬删（无 is_deleted 列，
    # 留着会被明细级统计重复计入）、media_files 软删归档；
    # 计划项与整改记录按策略有意保留。
    await soft_delete_cascade(db, task, unique_fields=["task_no"])
    await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "delete_task",
        "task",
        task_id,
    )

    return make_response(message="Task deleted")


@router.get("/{task_id}/records", response_model=ApiResponse)
async def get_task_records(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(InspectionRecord)
        .options(selectinload(InspectionRecord.template_item))
        .where(InspectionRecord.task_id == task_id)
        .order_by(InspectionRecord.recorded_at)
    )
    records = result.scalars().all()

    # 若任务未设置 template_id，尝试从关联的审核计划项回填
    if not task.template_id:
        try:
            task_uuid = UUID(str(task_id))
            from app.models.audit_project import AuditPlanItem
            plan_res = await db.execute(
                select(AuditPlanItem).where(
                    AuditPlanItem.inspection_task_id == task_uuid,
                    AuditPlanItem.is_deleted == False,  # noqa: E712
                )
            )
            linked_plan = plan_res.scalar_one_or_none()
            if linked_plan and linked_plan.template_id:
                task.template_id = linked_plan.template_id
                await db.commit()
                await db.refresh(task)
        except Exception:
            pass

    # 任务已关联模板但没有可用检查项时，按模板自动补齐（兼容历史脏数据）
    has_linked_items = any(r.template_item_id for r in records)
    template_parent_ids = set()
    if task.template_id:
        template_parent_ids = await load_parent_ids(db, template_id=task.template_id)

    if task.template_id and not has_linked_items:
        items_result = await db.execute(
            select(TemplateItem)
            .where(
                TemplateItem.template_id == task.template_id,
                TemplateItem.is_deleted == False,  # noqa: E712
                TemplateItem.is_category.is_not(True),
            )
            .order_by(TemplateItem.sort_order)
        )
        template_items = [
            i for i in items_result.scalars().all()
            if not is_category_node(i, template_parent_ids)
        ]
        if template_items:
            # 清理无模板项关联的空记录，避免干扰
            for empty_rec in records:
                if not empty_rec.template_item_id and not empty_rec.result:
                    await db.delete(empty_rec)
            for item in template_items:
                db.add(
                    InspectionRecord(
                        task_id=task.id,
                        template_item_id=item.id,
                    )
                )
            await db.commit()
            result = await db.execute(
                select(InspectionRecord)
                .options(selectinload(InspectionRecord.template_item))
                .where(InspectionRecord.task_id == task_id)
                .order_by(InspectionRecord.recorded_at)
            )
            records = result.scalars().all()

    # 一次性取出本任务所有附件，按检查项分组。
    # 原实现不返回附件，前端 photos 只能恒为空，导致「上传后再次查看附件丢失」。
    record_ids = [r.id for r in records]
    photos_by_record: dict = {}
    if record_ids:
        media_rows = await db.execute(
            select(MediaFile.record_id, MediaFile.file_path)
            .where(
                MediaFile.record_id.in_(record_ids),
                MediaFile.is_deleted == False,  # noqa: E712
            )
            .order_by(MediaFile.uploaded_at)
        )
        for rec_id, file_path in media_rows.all():
            if rec_id and file_path:
                photos_by_record.setdefault(rec_id, []).append(file_path)

    payload = []
    for r in records:
        ti = r.template_item
        if ti is None:
            # 孤儿记录（关联模板项不存在或被删除）：直接跳过，避免引发树遍历死锁或前端白屏
            continue
        # 分类目录一律不参与检查项统计与展示：
        # 不论历史上是否被误填过结果，都不能作为检查项返回，
        # 否则条目总数会与模板叶子口径对不上（P0-02 / P0-03）。
        if is_category_node(ti, template_parent_ids):
            continue
        # 模板条目已被软删除且本记录未填写 → 孤儿空记录，一并剔除
        if ti.is_deleted and not r.result:
            continue

        item = InspectionRecordResponse.model_validate(r).model_dump()
        # 附件（现场照片等）随记录一起返回，供前端回显
        item["photos"] = photos_by_record.get(r.id, [])
        if r.template_item is not None:
            check_item = {
                "id": str(r.template_item.id),
                "title": r.template_item.title,
                "description": r.template_item.description,
                "check_method": r.template_item.check_method,
                "legal_basis": r.template_item.legal_basis,
                "standard_ref": r.template_item.standard_ref,
                "clause_no": r.template_item.clause_no,
                "template_id": str(r.template_item.template_id)
                if r.template_item.template_id
                else None,
                "is_category": bool(r.template_item.is_category),
                "result_type": r.template_item.result_type,
                "check_type": r.template_item.check_type,
                "result_options": r.template_item.result_options,
                "is_required": r.template_item.is_required,
                "attachment_required": bool(r.template_item.attachment_required),
                "allow_attachment": bool(r.template_item.allow_attachment)
                if r.template_item.allow_attachment is not None
                else True,
                "unit": r.template_item.unit,
                "parent_id": str(r.template_item.parent_id)
                if r.template_item.parent_id
                else None,
                "sort_order": r.template_item.sort_order
                if r.template_item.sort_order is not None
                else 0,
                "min_value": float(r.template_item.min_value)
                if r.template_item.min_value is not None
                else None,
                "max_value": float(r.template_item.max_value)
                if r.template_item.max_value is not None
                else None,
                "max_score": float(r.template_item.max_score)
                if r.template_item.max_score is not None
                else None,
                "score_step": float(r.template_item.score_step)
                if r.template_item.score_step is not None
                else None,
                "pass_score": float(r.template_item.pass_score)
                if r.template_item.pass_score is not None
                else None,
            }
            item["template_item"] = check_item
            # 兼容旧前端字段名 check_item
            item["check_item"] = check_item
        payload.append(item)

    # 先按模板 sort_order 排序，再按父子层级展开为树序（避免分类节点与子项错位）
    def _item_meta(raw):
        return raw.get("template_item") or raw.get("check_item") or {}

    children_by_parent = {}
    for item in payload:
        parent_key = _item_meta(item).get("parent_id")
        children_by_parent.setdefault(parent_key, []).append(item)
    for key in children_by_parent:
        children_by_parent[key].sort(
            key=lambda x: _item_meta(x).get("sort_order", 0) or 0
        )

    ordered = []

    def _walk(parent_key):
        for node in children_by_parent.get(parent_key, []):
            ordered.append(node)
            child_id = _item_meta(node).get("id")
            if child_id is not None:
                _walk(child_id)

    _walk(None)

    if len(ordered) != len(payload):
        # 兜底：存在父节点缺失的孤儿项时，按 sort_order 追加，避免条目被丢弃
        seen = {id(node) for node in ordered}
        ordered.extend(
            sorted(
                (x for x in payload if id(x) not in seen),
                key=lambda x: _item_meta(x).get("sort_order", 0) or 0,
            )
        )

    payload = ordered

    return make_response(data=payload)


@router.post("/{task_id}/records", response_model=ApiResponse)
async def create_or_update_record(
    task_id: str,
    record_data: InspectionRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    # 管理员可以为任何任务创建记录，专家只能为分配给自己的任务创建记录
    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not assigned to you")

    # 已取消的任务对所有人只读：取消即放弃执行，不存在复审修正场景。
    if task.status == "cancelled":
        raise HTTPException(status_code=409, detail="任务已取消，不能写入检查记录")

    # BUG-11：已完成的填报记录默认只读，防止事后篡改。
    # 复审/再认证场景由管理角色显式放行（修改会留审计痕并同步正式审核记录，
    # 见 _sync_reaudited_task_to_formal_record）；专家与普通用户一律拒绝。
    if task.status == "completed" and current_user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=409, detail="任务已完成，填报记录不可再修改")

    if not record_data.template_item_id:
        raise HTTPException(status_code=422, detail="template_item_id is required")

    tpl_item = await db.get(TemplateItem, record_data.template_item_id)
    if not tpl_item or tpl_item.is_deleted:
        raise HTTPException(status_code=404, detail="Template item not found")

    result = await db.execute(
        select(InspectionRecord).where(
            InspectionRecord.task_id == task_id,
            InspectionRecord.template_item_id == record_data.template_item_id,
        )
    )
    record = result.scalar_one_or_none()

    if record:
        if record_data.result is not None:
            record.result = await _normalize_numeric_verdict(
                db,
                record_data.template_item_id or record.template_item_id,
                record_data.result,
                record_data.result_value
                if record_data.result_value is not None
                else record.result_value,
            )
        if record_data.result_value is not None:
            record.result_value = record_data.result_value
        if record_data.result_text is not None:
            record.result_text = record_data.result_text
        if record_data.inspector_note is not None:
            record.inspector_note = record_data.inspector_note
        if record_data.media_ids:
            await db.execute(
                update(MediaFile)
                .where(
                    MediaFile.id.in_(record_data.media_ids),
                    MediaFile.task_id == task.id,
                    MediaFile.is_deleted == False,  # noqa: E712
                )
                .values(record_id=record.id)
            )
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)

        # 重新计算任务统计数据
        await _recalculate_task_statistics(db, task)
        await db.commit()

        # 复审场景：已完成任务的填报被修改后，同步回正式审核记录
        await _sync_reaudited_task_to_formal_record(db, task, current_user)

        return make_response(
            data=InspectionRecordResponse.model_validate(record).model_dump()
        )

    normalized_result = await _normalize_numeric_verdict(
        db,
        record_data.template_item_id,
        record_data.result,
        record_data.result_value,
    )
    record = InspectionRecord(
        task_id=task_id,
        template_item_id=record_data.template_item_id,
        result=normalized_result,
        result_value=record_data.result_value,
        result_text=record_data.result_text,
        inspector_note=record_data.inspector_note,
        recorded_by=current_user.id,
    )
    db.add(record)
    await db.flush()
    if record_data.media_ids:
        await db.execute(
            update(MediaFile)
            .where(
                MediaFile.id.in_(record_data.media_ids),
                MediaFile.task_id == task.id,
                MediaFile.is_deleted == False,  # noqa: E712
            )
            .values(record_id=record.id)
        )
    await db.commit()
    await db.refresh(record)

    # 重新计算任务统计数据
    await _recalculate_task_statistics(db, task)
    await db.commit()

    # 复审场景：已完成任务的填报被修改后，同步回正式审核记录
    await _sync_reaudited_task_to_formal_record(db, task, current_user)

    return make_response(
        data=InspectionRecordResponse.model_validate(record).model_dump()
    )


@router.put("/records/{record_id}", response_model=ApiResponse)
async def update_record(
    record_id: str,
    record_data: InspectionRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        record = await db.get(InspectionRecord, record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        # 默认拒绝：父任务缺失（孤儿记录）时不能放行，否则任何登录用户都能改
        task = await db.get(InspectionTask, record.task_id) if record.task_id else None
        if not task or task.is_deleted:
            raise HTTPException(status_code=404, detail="Parent task not found")
        if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
            raise HTTPException(status_code=403, detail="Not authorized")

        # 已取消的任务对所有人只读，同 create_or_update_record 的口径。
        if task.status == "cancelled":
            raise HTTPException(status_code=409, detail="任务已取消，不能写入检查记录")

        # BUG-11：已完成的填报记录默认只读，防止事后篡改。
        # 复审/再认证场景由管理角色显式放行，同 create_or_update_record 的口径。
        if task.status == "completed" and current_user.role not in ADMIN_ROLES:
            raise HTTPException(status_code=409, detail="任务已完成，填报记录不可再修改")

        update_data = record_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(record, key, value)
        if "result" in update_data or "result_value" in update_data:
            record.result = await _normalize_numeric_verdict(
                db,
                record.template_item_id,
                record.result,
                record.result_value,
            )
        record.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(record)

        # 复审场景：已完成任务的填报被修改后，同步回正式审核记录
        await _sync_reaudited_task_to_formal_record(db, task, current_user)

        return make_response(
            data=InspectionRecordResponse.model_validate(record).model_dump()
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR in update_record: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"更新记录失败: {str(e)}")


@router.get("/{task_id}/summary", response_model=ApiResponse)
async def get_task_summary(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    # 与 get_task / get_task_records 保持一致的访问控制（原先缺失导致可越权读他人任务汇总）
    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(InspectionRecord)
        .options(selectinload(InspectionRecord.template_item))
        .where(InspectionRecord.task_id == task_id)
    )
    records = result.scalars().all()

    # 判定口径统一走 app.utils.item_stats.classify_result，不再本地维护判定集合。
    # 历史上此处把 pending_rectification 算作「不合格」，而检查报告/记录详情按
    # 中间态处理，导致同一份数据在「任务汇总」与「检查报告」中数字不一致。
    #
    # 排除分类节点：只要节点下挂着有效子项（或显式标记分类），一律不计入统计；
    # 模板条目已删除且未填写的孤儿记录同样剔除。统一走 app/utils/category。
    parent_ids = (
        await load_parent_ids(db, template_id=task.template_id)
        if task.template_id
        else set()
    )
    countable = []
    for r in records:
        ti = r.template_item
        if ti is not None:
            if is_category_node(ti, parent_ids):
                continue
            if ti.is_deleted and not r.result:
                continue
        countable.append(r)

    total = len(countable)
    # 完成度口径统一走 app.utils.item_completion.is_item_assessed：
    # 判定型必须落到结论字段，描述型/数值型/打分型填了内容即算完成。
    # 历史上此处只认 r.result 非空，导致描述型/数值型项明明填了内容却算「未填写」，
    # 与 H5 现场端（按类型判定）给出不同的完成度。
    completed = sum(1 for r in countable if is_item_assessed(r.template_item, r))
    compliant = sum(1 for r in countable if classify_result(r.result) == "pass")
    non_compliant = sum(1 for r in countable if classify_result(r.result) == "fail")
    not_applicable = sum(1 for r in countable if classify_result(r.result) == "na")

    # 合规率分母仅计有效参评项（剔除不适用/未涉及项）
    applicable_evaluated = compliant + non_compliant
    compliance_rate = (compliant / applicable_evaluated * 100) if applicable_evaluated > 0 else 0

    summary = InspectionSummary(
        total=total,
        completed=completed,
        compliant=compliant,
        non_compliant=non_compliant,
        not_applicable=not_applicable,
        compliance_rate=round(compliance_rate, 2),
    )

    return make_response(data=summary.model_dump())


@router.get("/{task_id}/final-judgment-stream")
async def generate_task_final_judgment_stream(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """流式生成任务最终判定结论（与 H5/Web 任务检查共用 TaskItemRecord 数据链）"""
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(TaskItemRecord)
        .options(selectinload(TaskItemRecord.template_item))
        .where(TaskItemRecord.task_id == task_id)
        .order_by(TaskItemRecord.recorded_at)
    )
    task_items = result.scalars().all()

    # 分类目录不参与最终判定统计（含"有子节点但未标分类"的脏数据兜底）
    parent_ids = (
        await load_parent_ids(db, template_id=task.template_id)
        if task.template_id
        else set()
    )

    items_data = []
    for item in task_items:
        template_item = item.template_item
        if template_item is not None:
            if is_category_node(template_item, parent_ids):
                continue
            if template_item.is_deleted and not item.result:
                continue
        title = (
            template_item.title
            if template_item and template_item.title
            else "未知检查项"
        )
        items_data.append(
            {
                "title": title,
                "result": item.result,
                # 任务链字段映射到最终判定摘要使用的统一字段
                "radio_value": item.result,
                "score_value": item.result_value,
                "numeric_value": item.result_value,
                "text_value": item.result_text,
                "multi_value": [],
                "risk_level": template_item.risk_level if template_item else None,
                "problem_description": item.inspector_note,
                "pass_score": getattr(template_item, "pass_score", None)
                if template_item
                else None,
                "max_score": getattr(template_item, "max_score", None)
                if template_item
                else None,
                "min_value": template_item.min_value if template_item else None,
                "max_value": template_item.max_value if template_item else None,
                "unit": template_item.unit if template_item else None,
            }
        )

    template_name = task.title
    if task.template_id:
        template = await db.get(InspectionTemplate, task.template_id)
        if template and not template.is_deleted:
            template_name = template.name

    inspection_date = None
    if task.started_at:
        inspection_date = task.started_at.isoformat()
    elif task.scheduled_at:
        inspection_date = task.scheduled_at.isoformat()
    elif task.created_at:
        inspection_date = task.created_at.isoformat()

    async def generate():
        async for chunk in llm_service.get_final_judgment_stream(
            template_name=template_name,
            inspection_date=inspection_date,
            items=items_data,
        ):
            data = json.dumps(chunk, ensure_ascii=False)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{task_id}/records/{record_id}/ai-stream")
async def generate_task_item_ai_stream(
    task_id: str,
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """流式生成任务检查项 AI 建议（record_id 可为 TaskItemRecord.id 或 template_item_id）"""
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(TaskItemRecord)
        .options(selectinload(TaskItemRecord.template_item))
        .where(
            TaskItemRecord.task_id == task_id,
            (TaskItemRecord.id == record_id)
            | (TaskItemRecord.template_item_id == record_id),
        )
    )
    record_item = result.scalar_one_or_none()
    if not record_item:
        raise HTTPException(status_code=404, detail="Task item not found")

    template_item = record_item.template_item
    if not template_item:
        raise HTTPException(status_code=400, detail="Template item not found")

    async def generate():
        async for chunk in llm_service.get_suggestion_stream(
            template_item, record_item
        ):
            data = json.dumps(chunk, ensure_ascii=False)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
