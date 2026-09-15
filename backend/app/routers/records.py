from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload
import json

from app.database import get_db
from app.models.user import User
from app.models.record import InspectionRecord, InspectionRecordItem
from app.models.template import InspectionTemplate, TemplateItem
from app.models.enterprise import Enterprise
from app.schemas import (
    ApiResponse,
    RecordCreate,
    RecordUpdate,
    RecordResponse,
    InspectionRecordDetail,
    InspectionRecordItemCreate,
    InspectionRecordItemUpdate,
    InspectionRecordItemResponse,
    InspectionRecordListQuery,
)
from app.utils.security import get_current_user, get_current_admin_user
from app.utils.roles import ADMIN_ROLES, RECORD_VIEW_ALL_ROLES
from app.utils.category import is_category_node, load_parent_ids
from app.utils.item_stats import calculate_item_stats
from app.services import AuditService
from app.services.llm_service import llm_service

router = APIRouter()


def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.now(timezone.utc)
    )


@router.get("", response_model=ApiResponse)
async def get_records(
    template_id: Optional[str] = Query(None),
    enterprise_id: Optional[str] = Query(None),
    inspector_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    overall_result: Optional[str] = Query(None, description="总体结果: pass, partial_pass, fail"),
    enterprise_name: Optional[str] = Query(None, description="企业名称模糊搜索"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort_by: Optional[str] = Query(
        None, description="排序字段: inspection_date, created_at, total_score"
    ),
    sort_order: Optional[str] = Query(None, description="排序方向: asc, desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取检查记录列表"""
    # 筛选条件只构建一次，分页查询与计数查询共用，避免两边漂移
    # （历史上正是因为两处各写一份，导致角色过滤条件不一致）。
    conditions = [InspectionRecord.is_deleted == False]  # noqa: E712

    # 仅检查员受限于「只看自己的记录」；管理员/超管/审核员（只读复核角色）可看全部
    if current_user.role not in RECORD_VIEW_ALL_ROLES:
        conditions.append(InspectionRecord.inspector_id == current_user.id)

    if template_id:
        conditions.append(InspectionRecord.template_id == template_id)
    if enterprise_id:
        conditions.append(InspectionRecord.enterprise_id == enterprise_id)
    if inspector_id:
        conditions.append(InspectionRecord.inspector_id == inspector_id)
    if status:
        conditions.append(InspectionRecord.status == status)
    if overall_result:
        conditions.append(InspectionRecord.overall_result == overall_result)
    if enterprise_name:
        # 搜索企业名称：检查手动输入的 enterprise_name 或关联的企业名称
        conditions.append(
            or_(
                InspectionRecord.enterprise_name.ilike(f"%{enterprise_name}%"),
                Enterprise.name.ilike(f"%{enterprise_name}%")
            )
        )
    if start_date:
        try:
            conditions.append(
                InspectionRecord.inspection_date
                >= datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            )
        except ValueError:
            pass
    if end_date:
        try:
            conditions.append(
                InspectionRecord.inspection_date
                <= datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            )
        except ValueError:
            pass

    query = select(InspectionRecord).options(
        selectinload(InspectionRecord.template),
        selectinload(InspectionRecord.enterprise),
        selectinload(InspectionRecord.inspector),
    )
    count_query = select(func.count(InspectionRecord.id))
    # 按企业名称筛选时两个查询都需要 join Enterprise 表
    if enterprise_name:
        query = query.outerjoin(Enterprise, InspectionRecord.enterprise_id == Enterprise.id)
        count_query = count_query.outerjoin(
            Enterprise, InspectionRecord.enterprise_id == Enterprise.id
        )

    query = query.where(*conditions)
    count_query = count_query.where(*conditions)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # 排序
    sort_column = InspectionRecord.inspection_date
    if sort_by == "created_at":
        sort_column = InspectionRecord.created_at
    elif sort_by == "total_score":
        sort_column = InspectionRecord.total_score

    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # 分页
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    records = result.scalars().all()

    record_list = []
    for r in records:
        data = {
            "id": str(r.id),
            "template_id": str(r.template_id),
            "enterprise_id": str(r.enterprise_id) if r.enterprise_id else None,
            "enterprise_name": r.enterprise_name,
            "enterprise_address": r.enterprise_address,
            "contact_person": r.contact_person,
            "contact_phone": r.contact_phone,
            "inspector_id": str(r.inspector_id),
            "inspection_date": r.inspection_date.isoformat()
            if r.inspection_date
            else None,
            "status": r.status,
            "overall_result": r.overall_result,
            "total_score": float(r.total_score) if r.total_score is not None else None,
            "remarks": r.remarks,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "template": {
                "id": str(r.template.id),
                "name": r.template.name,
                "category": r.template.category,
            }
            if r.template
            else None,
            "enterprise": {
                "id": str(r.enterprise.id),
                "name": r.enterprise.name,
            }
            if r.enterprise
            else None,
            "inspector": {
                "id": str(r.inspector.id),
                "username": r.inspector.username,
                "full_name": r.inspector.full_name,
            }
            if r.inspector
            else None,
        }
        record_list.append(data)

    return make_response(data={"items": record_list, "total": total})


@router.post("", response_model=ApiResponse)
async def create_record(
    record_data: RecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建检查记录（自动查找当天草稿）"""
    from datetime import timedelta

    # 验证模板存在
    template = await db.get(InspectionTemplate, record_data.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # 如果提供了企业 ID，验证企业存在
    if record_data.enterprise_id:
        enterprise = await db.get(Enterprise, record_data.enterprise_id)
        if not enterprise:
            raise HTTPException(status_code=404, detail="Enterprise not found")

    # 查找当天是否存在相同企业、相同模板的草稿（使用 UTC 时间）
    now_utc = datetime.now(timezone.utc)
    today_start = datetime(now_utc.year, now_utc.month, now_utc.day)
    tomorrow_start = today_start + timedelta(days=1)

    query = select(InspectionRecord).where(
        InspectionRecord.inspector_id == current_user.id,
        InspectionRecord.template_id == record_data.template_id,
        InspectionRecord.status == "draft",
        InspectionRecord.is_deleted == False,  # noqa: E712
        InspectionRecord.created_at >= today_start,
        InspectionRecord.created_at < tomorrow_start,
    )

    # 如果有企业ID，也匹配企业
    if record_data.enterprise_id:
        query = query.where(InspectionRecord.enterprise_id == record_data.enterprise_id)
    elif record_data.enterprise_name:
        # 手动输入的企业名称也匹配
        query = query.where(
            InspectionRecord.enterprise_name == record_data.enterprise_name
        )

    # 按创建时间降序，取最新的一条
    query = query.order_by(InspectionRecord.created_at.desc())
    result = await db.execute(query)
    existing_draft = result.scalar()

    # 如果找到当天的草稿，直接返回
    if existing_draft:
        return make_response(data={"id": str(existing_draft.id), "is_draft": True})

    # 获取模板所有检查项以生成快照（排除软删除项，保证快照与当前模板一致）
    all_items_result = await db.execute(
        select(TemplateItem)
        .where(
            TemplateItem.template_id == record_data.template_id,
            TemplateItem.is_deleted == False,  # noqa: E712
        )
        .order_by(TemplateItem.sort_order)
    )
    all_template_items = all_items_result.scalars().all()

    # 分类目录集合：显式标记 或 存在有效子节点（统一走 app/utils/category）
    parent_ids = await load_parent_ids(db, template_id=record_data.template_id)

    # 构建模板快照 JSON
    template_snapshot = {
        "id": str(template.id),
        "name": template.name,
        "category": template.category,
        "version": template.version,
        "is_quantified": template.is_quantified,
        "items": [
            {
                "id": str(ti.id),
                "parent_id": str(ti.parent_id) if ti.parent_id else None,
                "title": ti.title,
                "description": ti.description,
                "check_method": ti.check_method,
                "legal_basis": ti.legal_basis,
                "standard_ref": ti.standard_ref,
                "check_type": ti.check_type,
                "result_type": ti.result_type,
                "result_options": ti.result_options,
                "min_value": str(ti.min_value) if ti.min_value is not None else None,
                "max_value": str(ti.max_value) if ti.max_value is not None else None,
                "unit": ti.unit,
                "risk_level": ti.risk_level,
                "is_category": bool(ti.is_category) or ti.id in parent_ids,
                "sort_order": ti.sort_order,
                "score_weight": str(ti.score_weight)
                if ti.score_weight is not None
                else None,
                "default_score": str(ti.default_score)
                if ti.default_score is not None
                else None,
                "allow_attachment": ti.allow_attachment,
                "attachment_required": ti.attachment_required,
                "ai_prompt_template": ti.ai_prompt_template,
                "use_ai": getattr(ti, "use_ai", False),
            }
            for ti in all_template_items
        ],
    }

    # 创建新记录，存入快照
    record = InspectionRecord(
        template_id=record_data.template_id,
        enterprise_id=record_data.enterprise_id,
        enterprise_name=record_data.enterprise_name,
        enterprise_address=record_data.enterprise_address,
        contact_person=record_data.contact_person,
        contact_phone=record_data.contact_phone,
        inspector_id=current_user.id,
        inspection_date=record_data.inspection_date or datetime.now(timezone.utc),
        remarks=record_data.remarks,
        status="draft",
        template_snapshot=template_snapshot,
    )
    db.add(record)
    await db.flush()  # flush以获取 record.id

    # 创建检查记录项，只针对真正的叶子检查项（分类目录一律不生成空记录）
    for item in all_template_items:
        if not is_category_node(item, parent_ids):
            record_item = InspectionRecordItem(
                record_id=record.id,
                template_item_id=item.id,
                item_title=item.title,
                item_description=item.description,
                item_check_method=item.check_method,
                item_legal_basis=item.legal_basis,
                item_standard_ref=item.standard_ref,
                item_risk_level=item.risk_level,
                item_check_type=item.check_type,
                item_result_options=item.result_options,
                item_min_value=item.min_value,
                item_max_value=item.max_value,
                item_unit=item.unit,
                item_score_weight=item.score_weight,
                item_default_score=item.default_score,
                item_allow_attachment=item.allow_attachment,
                item_attachment_required=item.attachment_required,
                item_ai_prompt_template=item.ai_prompt_template,
                item_use_ai=item.use_ai,
            )
            db.add(record_item)

    await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "create_record",
        "inspection_record",
        str(record.id),
    )

    return make_response(data={"id": str(record.id), "is_draft": False})


@router.get("/{record_id}", response_model=ApiResponse)
async def get_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取检查记录详情"""
    # 预加载关联对象
    result = await db.execute(
        select(InspectionRecord)
        .options(
            selectinload(InspectionRecord.template),
            selectinload(InspectionRecord.enterprise),
            selectinload(InspectionRecord.inspector),
        )
        .where(
            InspectionRecord.id == record_id,
            InspectionRecord.is_deleted == False,  # noqa: E712
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # 权限检查
    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    # 加载关联数据
    items_result = await db.execute(
        select(InspectionRecordItem)
        .options(selectinload(InspectionRecordItem.template_item))
        .where(InspectionRecordItem.record_id == record_id)
        .order_by(InspectionRecordItem.recorded_at)
    )
    items = items_result.scalars().all()

    # 获取模板的层级结构（优先从记录的快照中读取，否则从当前模板读取）
    if record.template_snapshot and "items" in record.template_snapshot:

        class SnapshotItem:
            def __init__(self, d):
                self.id = d.get("id")
                self.parent_id = d.get("parent_id")
                self.title = d.get("title")
                self.description = d.get("description")
                self.check_method = d.get("check_method")
                self.legal_basis = d.get("legal_basis")
                self.standard_ref = d.get("standard_ref")
                self.check_type = d.get("check_type")
                self.result_type = d.get("result_type")
                self.result_options = d.get("result_options")
                self.min_value = d.get("min_value")
                self.max_value = d.get("max_value")
                self.max_score = d.get("max_score")
                self.score_step = d.get("score_step")
                self.pass_score = d.get("pass_score")
                self.unit = d.get("unit")
                self.is_required = d.get("is_required")
                self.risk_level = d.get("risk_level")
                self.is_category = d.get("is_category")
                self.score_weight = d.get("score_weight")
                self.default_score = d.get("default_score")
                self.allow_attachment = d.get("allow_attachment")
                self.attachment_required = d.get("attachment_required")
                self.ai_prompt_template = d.get("ai_prompt_template")
                self.use_ai = d.get("use_ai", False)

        template_items = [SnapshotItem(i) for i in record.template_snapshot["items"]]
    else:
        template_items_result = await db.execute(
            select(TemplateItem)
            .where(TemplateItem.template_id == record.template_id)
            .order_by(TemplateItem.sort_order)
        )
        template_items = template_items_result.scalars().all()

    # 创建记录项映射
    record_item_map = {}
    record_item_title_map = {}
    for item in items:
        if item.template_item_id:
            record_item_map[str(item.template_item_id)] = item
        if item.item_title:
            record_item_title_map[item.item_title] = item

    # 构建树形结构（使用模板结构，填充记录数据）
    def build_tree(items, parent_id=None):
        tree = []
        for template_item in items:
            item_parent_id = (
                str(template_item.parent_id) if template_item.parent_id else None
            )
            if item_parent_id == parent_id:
                # 查找对应的记录项：先按ID查找，如果找不到且标题存在，按标题 fallback（防止项被删后因 FK 置空导致的数据断连）
                record_item = record_item_map.get(str(template_item.id))
                if not record_item and template_item.title:
                    record_item = record_item_title_map.get(template_item.title)

                # 若记录中有冗余字段则优先使用（保护历史记录不因为模板修改而改变显示）
                title = (
                    record_item.item_title
                    if record_item and record_item.item_title
                    else template_item.title
                )
                description = (
                    record_item.item_description
                    if record_item and record_item.item_title
                    else template_item.description
                )
                check_method = (
                    record_item.item_check_method
                    if record_item and record_item.item_title
                    else template_item.check_method
                )
                legal_basis = (
                    record_item.item_legal_basis
                    if record_item and record_item.item_title
                    else template_item.legal_basis
                )
                standard_ref = (
                    record_item.item_standard_ref
                    if record_item and record_item.item_title
                    else template_item.standard_ref
                )
                result_options = (
                    record_item.item_result_options
                    if record_item and record_item.item_title
                    else template_item.result_options
                )
                min_value = (
                    float(record_item.item_min_value)
                    if record_item and record_item.item_min_value is not None
                    else (
                        float(template_item.min_value)
                        if template_item.min_value is not None
                        else None
                    )
                )
                max_value = (
                    float(record_item.item_max_value)
                    if record_item and record_item.item_max_value is not None
                    else (
                        float(template_item.max_value)
                        if template_item.max_value is not None
                        else None
                    )
                )
                unit = (
                    record_item.item_unit
                    if record_item and record_item.item_title
                    else template_item.unit
                )
                score_weight = (
                    float(record_item.item_score_weight)
                    if record_item and record_item.item_score_weight is not None
                    else (
                        float(template_item.score_weight)
                        if getattr(template_item, "score_weight", None) is not None
                        else None
                    )
                )
                default_score = (
                    float(record_item.item_default_score)
                    if record_item and record_item.item_default_score is not None
                    else (
                        float(template_item.default_score)
                        if getattr(template_item, "default_score", None) is not None
                        else None
                    )
                )
                allow_attachment = (
                    record_item.item_allow_attachment
                    if record_item and record_item.item_title
                    else getattr(template_item, "allow_attachment", False)
                )
                attachment_required = (
                    record_item.item_attachment_required
                    if record_item and record_item.item_title
                    else getattr(template_item, "attachment_required", False)
                )
                ai_prompt_template = (
                    record_item.item_ai_prompt_template
                    if record_item and record_item.item_title
                    else getattr(template_item, "ai_prompt_template", None)
                )
                use_ai = (
                    record_item.item_use_ai
                    if record_item and record_item.item_title
                    else getattr(template_item, "use_ai", False)
                )

                children = build_tree(items, str(template_item.id))
                node = {
                    "id": str(record_item.id) if record_item else str(template_item.id),
                    "template_item_id": str(template_item.id),
                    "title": title,
                    "description": description,
                    "check_method": check_method,
                    "legal_basis": legal_basis,
                    "standard_ref": standard_ref,
                    "result_type": template_item.result_type,
                    "result_options": result_options,
                    "min_value": min_value,
                    "max_value": max_value,
                    "unit": unit,
                    "score_weight": score_weight,
                    "default_score": default_score,
                    "allow_attachment": allow_attachment,
                    "attachment_required": attachment_required,
                    "ai_prompt_template": ai_prompt_template,
                    "use_ai": use_ai,
                    "result": record_item.result if record_item else None,
                    "result_value": record_item.result_value if record_item else None,
                    "result_text": record_item.result_text if record_item else None,
                    "radio_value": record_item.radio_value if record_item else None,
                    "score_value": float(record_item.score_value)
                    if record_item
                    and record_item.score_value is not None
                    and record_item.score_value != ""
                    else None,
                    "numeric_value": float(record_item.numeric_value)
                    if record_item
                    and record_item.numeric_value is not None
                    and record_item.numeric_value != ""
                    else None,
                    "text_value": record_item.text_value if record_item else None,
                    "multi_value": record_item.multi_value if record_item else None,
                    "inspector_note": record_item.inspector_note
                    if record_item
                    else None,
                    "problem_description": record_item.problem_description
                    if record_item
                    else None,
                    "rectification_suggestion": record_item.rectification_suggestion
                    if record_item
                    else None,
                    "ai_suggestion": record_item.ai_suggestion if record_item else None,
                    "photos": record_item.photos or [] if record_item else [],
                    # 动态纠偏：只要挂了子节点就一律按分类目录返回，
                    # 兼容历史脏数据，保证前端不会把根节点当检查项渲染。
                    "is_category": bool(template_item.is_category) or len(children) > 0,
                    "children": children,
                }
                tree.append(node)
        return tree

    def build_template_tree(items, parent_id=None):
        tree = []
        for item in items:
            item_parent_id = str(item.parent_id) if item.parent_id else None
            if item_parent_id == parent_id:
                children = build_template_tree(items, str(item.id))
                node = {
                    "id": str(item.id),
                    "parent_id": item_parent_id,
                    "title": item.title,
                    "description": item.description,
                    "check_method": item.check_method,
                    "legal_basis": item.legal_basis,
                    "standard_ref": item.standard_ref,
                    "check_type": item.check_type,
                    "result_type": item.result_type,
                    "result_options": item.result_options,
                    "min_value": float(item.min_value) if item.min_value else None,
                    "max_value": float(item.max_value) if item.max_value else None,
                    "max_score": float(item.max_score) if item.max_score else None,
                    "score_step": float(item.score_step) if item.score_step else None,
                    "pass_score": float(item.pass_score) if item.pass_score else None,
                    "unit": item.unit,
                    "score_weight": float(item.score_weight)
                    if item.score_weight
                    else None,
                    "default_score": float(item.default_score)
                    if item.default_score
                    else None,
                    "allow_attachment": item.allow_attachment,
                    "attachment_required": item.attachment_required,
                    "ai_prompt_template": item.ai_prompt_template,
                    "use_ai": getattr(item, "use_ai", False),
                    "is_required": item.is_required,
                    "risk_level": item.risk_level,
                    "is_category": bool(item.is_category) or len(children) > 0,
                    "children": children,
                }
                tree.append(node)
        return tree

    template_data = None
    if record.template:
        template_data = {
            "id": str(record.template.id),
            "name": record.template.name,
            "category": record.template.category,
            "version": record.template.version,
            "is_quantified": record.template.is_quantified,
            "items": build_tree(template_items),
        }
    elif record.template_snapshot:
        template_data = {
            "id": record.template_snapshot.get("id"),
            "name": record.template_snapshot.get("name"),
            "category": record.template_snapshot.get("category"),
            "version": record.template_snapshot.get("version"),
            "is_quantified": record.template_snapshot.get("is_quantified", False),
            "items": build_tree(template_items),
        }

    record_data = {
        "id": str(record.id),
        "template_id": str(record.template_id),
        "enterprise_id": str(record.enterprise_id) if record.enterprise_id else None,
        "enterprise_name": record.enterprise_name,
        "enterprise_address": record.enterprise_address,
        "contact_person": record.contact_person,
        "contact_phone": record.contact_phone,
        "inspector_id": str(record.inspector_id),
        "inspection_date": record.inspection_date.isoformat()
        if record.inspection_date
        else None,
        "status": record.status,
        "overall_result": record.overall_result,
        "total_score": float(record.total_score)
        if record.total_score is not None
        else None,
        "remarks": record.remarks,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "template": template_data,
        # 同步返回扁平 items，便于 H5/Web 明细页与 Agent 写回定位
        "items": [
            {
                "id": str(i.id),
                "template_item_id": str(i.template_item_id)
                if i.template_item_id
                else None,
                "radio_value": i.radio_value,
                "score_value": float(i.score_value)
                if i.score_value is not None and i.score_value != ""
                else None,
                "numeric_value": float(i.numeric_value)
                if i.numeric_value is not None and i.numeric_value != ""
                else None,
                "text_value": i.text_value,
                "multi_value": i.multi_value or [],
                "problem_description": i.problem_description,
                "result": i.result,
                "item_title": i.item_title,
            }
            for i in items
        ],
        "enterprise": {
            "id": str(record.enterprise.id),
            "name": record.enterprise.name,
        }
        if record.enterprise
        else None,
        "inspector": {
            "id": str(record.inspector.id),
            "username": record.inspector.username,
            "real_name": record.inspector.full_name,
        }
        if record.inspector
        else None,
        "stats": _calculate_item_stats(items),
    }

    return make_response(data=record_data)


def _calculate_item_stats(items: list) -> dict:
    """计算检查项统计数据。

    统一走 ``app.utils.item_stats``——此前本函数只认 ``"na"``，
    而写入侧落库的是 ``not_applicable``，导致「不适用项」恒为 0，
    与检查报告的数字对不上（详见该模块 docstring）。
    """
    return calculate_item_stats(items)


@router.put("/{record_id}", response_model=ApiResponse)
async def update_record(
    record_id: str,
    record_data: RecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新检查记录"""
    record = await db.get(InspectionRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Record not found")

    # 权限检查
    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    # 更新字段
    update_data = record_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)

    await db.commit()
    await db.refresh(record)

    return make_response(data={"id": str(record.id)})


def _has_value(value) -> bool:
    """记录项字段是否算「已填写」。空字符串、空数组都不算。"""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def _record_item_filled(item: InspectionRecordItem) -> bool:
    return any(
        _has_value(getattr(item, field, None))
        for field in (
            "radio_value",
            "result",
            "numeric_value",
            "score_value",
            "text_value",
            "multi_value",
        )
    )


async def _collect_submit_blockers(
    db: AsyncSession, record: InspectionRecord
) -> List[str]:
    """提交前完整性校验：返回阻断项描述列表。

    原实现完全依赖前端校验，而前端用的是 `!== undefined`，
    接口返回 null 时判断恒真，等于没有校验，
    结果落库了一批「已提交但没结论、检查项也没填」的记录。
    """
    blockers: List[str] = []

    if not _has_value(record.overall_result):
        blockers.append("尚未填写「最终判定结论」")

    if not record.template_id:
        return blockers

    template_items = (
        (
            await db.execute(
                select(TemplateItem).where(
                    TemplateItem.template_id == record.template_id,
                    TemplateItem.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    if not template_items:
        return blockers

    parent_ids = await load_parent_ids(db, template_id=record.template_id)

    record_items = (
        (
            await db.execute(
                select(InspectionRecordItem).where(
                    InspectionRecordItem.record_id == record.id
                )
            )
        )
        .scalars()
        .all()
    )
    filled_template_ids = {
        str(ri.template_item_id)
        for ri in record_items
        if ri.template_item_id and _record_item_filled(ri)
    }

    missing = [
        (ti.title or "未命名检查项")
        for ti in template_items
        if not is_category_node(ti, parent_ids)
        and ti.is_required is not False
        and str(ti.id) not in filled_template_ids
    ]
    if missing:
        preview = "、".join(missing[:5])
        suffix = f" 等 {len(missing)} 项" if len(missing) > 5 else ""
        blockers.append(f"以下必填检查项尚未填写：{preview}{suffix}")

    return blockers


@router.post("/{record_id}/submit", response_model=ApiResponse)
async def submit_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交检查记录"""
    record = await db.get(InspectionRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Record not found")

    # 权限检查
    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    # BUG-12：已提交记录不允许重复提交
    if record.status == "submitted":
        raise HTTPException(status_code=409, detail="该检查记录已提交，请勿重复提交")

    # 完整性校验：结论 + 必填检查项
    blockers = await _collect_submit_blockers(db, record)
    if blockers:
        raise HTTPException(
            status_code=422,
            detail="；".join(blockers) + "，无法提交",
        )

    record.status = "submitted"
    record.inspection_date = datetime.now(timezone.utc)
    await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "submit_record",
        "inspection_record",
        record_id,
    )

    return make_response(message="Record submitted")


@router.delete("/{record_id}", response_model=ApiResponse)
async def delete_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """删除检查记录（仅管理员，软删除）"""
    record = await db.get(InspectionRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Record not found")

    from app.utils.soft_delete import soft_delete

    await soft_delete(db, record)
    await db.commit()

    return make_response(message="Record deleted")


# 检查记录项管理
@router.post("/{record_id}/items", response_model=ApiResponse)
async def create_or_update_record_item(
    record_id: str,
    item_data: InspectionRecordItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建或更新检查记录项"""
    record = await db.get(InspectionRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Record not found")

    # 权限检查
    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    # BUG-12：已提交记录为只读，禁止再修改检查条目
    if record.status == "submitted":
        raise HTTPException(status_code=409, detail="该检查记录已提交，条目不可再修改")

    # 查找是否已存在（优先按 id 查找，其次按 template_item_id 查找）
    record_item = None
    if item_data.id:
        result = await db.execute(
            select(InspectionRecordItem).where(
                InspectionRecordItem.record_id == record_id,
                InspectionRecordItem.id == item_data.id,
            )
        )
        record_item = result.scalar_one_or_none()
    elif item_data.template_item_id:
        result = await db.execute(
            select(InspectionRecordItem).where(
                InspectionRecordItem.record_id == record_id,
                InspectionRecordItem.template_item_id == item_data.template_item_id,
            )
        )
        record_item = result.scalar_one_or_none()

    if record_item:
        # 更新现有记录
        update_fields = [
            "result",
            "result_value",
            "result_text",
            "score_value",
            "radio_value",
            "multi_value",
            "numeric_value",
            "text_value",
            "problem_description",
            "rectification_suggestion",
            "ai_generated",
            "ai_suggestion",
            "ai_basis",
            "inspector_note",
            "photos",
        ]
        for field in update_fields:
            value = getattr(item_data, field, None)
            if value is not None:
                setattr(record_item, field, value)
        record_item.updated_at = datetime.now(timezone.utc)
    else:
        # 创建新记录
        record_item = InspectionRecordItem(
            record_id=record_id,
            template_item_id=item_data.template_item_id,
            result=item_data.result,
            result_value=item_data.result_value,
            result_text=item_data.result_text,
            score_value=item_data.score_value,
            radio_value=item_data.radio_value,
            multi_value=item_data.multi_value,
            numeric_value=item_data.numeric_value,
            text_value=item_data.text_value,
            problem_description=item_data.problem_description,
            rectification_suggestion=item_data.rectification_suggestion,
            ai_generated=item_data.ai_generated,
            ai_suggestion=item_data.ai_suggestion,
            ai_basis=item_data.ai_basis,
            inspector_note=item_data.inspector_note,
            photos=item_data.photos or [],
        )
        db.add(record_item)

    await db.commit()
    await db.refresh(record_item)

    return make_response(
        data={
            "id": str(record_item.id),
            "template_item_id": str(record_item.template_item_id),
        }
    )


@router.get("/{record_id}/items", response_model=ApiResponse)
async def get_record_items(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取检查记录的所有项目"""
    record = await db.get(InspectionRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Record not found")

    # 权限检查
    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(InspectionRecordItem)
        .options(selectinload(InspectionRecordItem.template_item))
        .where(InspectionRecordItem.record_id == record_id)
        .order_by(InspectionRecordItem.recorded_at)
    )
    items = result.scalars().all()

    item_list = []
    for item in items:
        # 如果存在冗余字段或 template_item 被删除了，使用冗余数据作为展示依据
        t_item = item.template_item
        title = (
            item.item_title
            if item.item_title
            else (t_item.title if t_item else "【检查项已删除】")
        )
        description = (
            item.item_description
            if item.item_title
            else (t_item.description if t_item else "")
        )
        check_method = (
            item.item_check_method
            if item.item_title
            else (t_item.check_method if t_item else "")
        )
        legal_basis = (
            item.item_legal_basis
            if item.item_title
            else (t_item.legal_basis if t_item else "")
        )
        standard_ref = (
            item.item_standard_ref
            if item.item_title
            else (t_item.standard_ref if t_item else "")
        )
        check_type = (
            item.item_check_type
            if item.item_title
            else (
                t_item.check_type
                if t_item
                else (t_item.result_type if t_item else "radio")
            )
        )
        result_type = t_item.result_type if t_item else "pass_fail"
        result_options = (
            item.item_result_options
            if item.item_title
            else (t_item.result_options if t_item else None)
        )

        min_value = (
            float(item.item_min_value)
            if item.item_min_value is not None
            else (
                float(t_item.min_value)
                if t_item and t_item.min_value is not None
                else None
            )
        )
        max_value = (
            float(item.item_max_value)
            if item.item_max_value is not None
            else (
                float(t_item.max_value)
                if t_item and t_item.max_value is not None
                else None
            )
        )
        unit = item.item_unit if item.item_title else (t_item.unit if t_item else "")
        risk_level = (
            item.item_risk_level
            if item.item_title
            else (t_item.risk_level if t_item else "medium")
        )

        max_score = float(t_item.max_score) if t_item and t_item.max_score else None
        score_step = float(t_item.score_step) if t_item and t_item.score_step else None
        pass_score = float(t_item.pass_score) if t_item and t_item.pass_score else None
        is_required = t_item.is_required if t_item else True

        item_list.append(
            {
                "id": str(item.id),
                "template_item_id": str(item.template_item_id)
                if item.template_item_id
                else None,
                "title": title,
                "description": description,
                "check_method": check_method,
                "legal_basis": legal_basis,
                "standard_ref": standard_ref,
                "check_type": check_type,
                "result_type": result_type,
                "result_options": result_options,
                "min_value": min_value,
                "max_value": max_value,
                "max_score": max_score,
                "score_step": score_step,
                "pass_score": pass_score,
                "unit": unit,
                "is_required": is_required,
                "risk_level": risk_level,
                # 结果数据
                "result": item.result,
                "result_value": item.result_value,
                "result_text": item.result_text,
                "score_value": item.score_value,
                "radio_value": item.radio_value,
                "multi_value": item.multi_value or [],
                "numeric_value": item.numeric_value,
                "text_value": item.text_value,
                "problem_description": item.problem_description,
                "rectification_suggestion": item.rectification_suggestion,
                # AI 相关
                "ai_generated": item.ai_generated or False,
                "ai_suggestion": item.ai_suggestion,
                "ai_basis": item.ai_basis,
                # 其他
                "inspector_note": item.inspector_note,
                "photos": item.photos or [],
            }
        )

    return make_response(data=item_list)


@router.get("/{record_id}/items/{item_id}", response_model=ApiResponse)
async def get_record_item(
    record_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个检查记录项详情"""
    record = await db.get(InspectionRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Record not found")

    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(InspectionRecordItem)
        .options(selectinload(InspectionRecordItem.template_item))
        .where(InspectionRecordItem.record_id == record_id)
        .where(
            (InspectionRecordItem.id == item_id)
            | (InspectionRecordItem.template_item_id == item_id)
        )
    )
    record_item = result.scalar_one_or_none()
    if not record_item:
        raise HTTPException(status_code=404, detail="Item not found")

    t_item = record_item.template_item
    title = (
        record_item.item_title
        if record_item.item_title
        else (t_item.title if t_item else "【检查项已删除】")
    )
    description = (
        record_item.item_description
        if record_item.item_title
        else (t_item.description if t_item else "")
    )
    check_method = (
        record_item.item_check_method
        if record_item.item_title
        else (t_item.check_method if t_item else "")
    )
    legal_basis = (
        record_item.item_legal_basis
        if record_item.item_title
        else (t_item.legal_basis if t_item else "")
    )
    standard_ref = (
        record_item.item_standard_ref
        if record_item.item_title
        else (t_item.standard_ref if t_item else "")
    )
    check_type = (
        record_item.item_check_type
        if record_item.item_title
        else (
            t_item.check_type if t_item else (t_item.result_type if t_item else "radio")
        )
    )
    result_type = t_item.result_type if t_item else "pass_fail"
    result_options = (
        record_item.item_result_options
        if record_item.item_title
        else (t_item.result_options if t_item else None)
    )

    min_value = (
        float(record_item.item_min_value)
        if record_item.item_min_value is not None
        else (
            float(t_item.min_value) if t_item and t_item.min_value is not None else None
        )
    )
    max_value = (
        float(record_item.item_max_value)
        if record_item.item_max_value is not None
        else (
            float(t_item.max_value) if t_item and t_item.max_value is not None else None
        )
    )
    unit = (
        record_item.item_unit
        if record_item.item_title
        else (t_item.unit if t_item else "")
    )
    risk_level = (
        record_item.item_risk_level
        if record_item.item_title
        else (t_item.risk_level if t_item else "medium")
    )

    max_score = float(t_item.max_score) if t_item and t_item.max_score else None
    score_step = float(t_item.score_step) if t_item and t_item.score_step else None
    pass_score = float(t_item.pass_score) if t_item and t_item.pass_score else None
    is_required = t_item.is_required if t_item else True
    allow_attachment = (
        t_item.allow_attachment
        if t_item and hasattr(t_item, "allow_attachment")
        else False
    )
    attachment_required = (
        t_item.attachment_required
        if t_item and hasattr(t_item, "attachment_required")
        else False
    )

    item_data = {
        "id": str(record_item.id),
        "record_id": str(record_item.record_id),
        "template_item_id": str(record_item.template_item_id)
        if record_item.template_item_id
        else None,
        # 模板项信息 (降级到冗余字段)
        "title": title,
        "description": description,
        "check_method": check_method,
        "legal_basis": legal_basis,
        "standard_ref": standard_ref,
        "check_type": check_type,
        "result_type": result_type,
        "result_options": result_options,
        "min_value": min_value,
        "max_value": max_value,
        "max_score": max_score,
        "score_step": score_step,
        "pass_score": pass_score,
        "unit": unit,
        "is_required": is_required,
        "allow_attachment": allow_attachment,
        "attachment_required": attachment_required,
        "risk_level": risk_level,
        "use_ai": record_item.item_use_ai
        if record_item.item_use_ai is not None
        else (t_item.use_ai if t_item else False),
        "ai_prompt_template": record_item.item_ai_prompt_template
        if record_item.item_title
        else (t_item.ai_prompt_template if t_item else None),
        # 检查结果
        "result": record_item.result,
        "result_value": record_item.result_value,
        "result_text": record_item.result_text,
        "score_value": record_item.score_value,
        "radio_value": record_item.radio_value,
        "multi_value": record_item.multi_value or [],
        "numeric_value": record_item.numeric_value,
        "text_value": record_item.text_value,
        "problem_description": record_item.problem_description,
        "rectification_suggestion": record_item.rectification_suggestion,
        # AI相关
        "ai_generated": record_item.ai_generated,
        "ai_suggestion": record_item.ai_suggestion,
        "ai_basis": record_item.ai_basis,
        # 其他
        "inspector_note": record_item.inspector_note,
        "photos": record_item.photos or [],
        "recorded_at": record_item.recorded_at.isoformat()
        if record_item.recorded_at
        else None,
        "updated_at": record_item.updated_at.isoformat()
        if record_item.updated_at
        else None,
    }

    return make_response(data=item_data)


@router.post("/{record_id}/items/{item_id}/ai", response_model=ApiResponse)
async def generate_ai_suggestion(
    record_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """为检查记录项生成AI建议"""
    record = await db.get(InspectionRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Record not found")

    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(InspectionRecordItem)
        .options(selectinload(InspectionRecordItem.template_item))
        .where(InspectionRecordItem.record_id == record_id)
        .where(
            (InspectionRecordItem.id == item_id)
            | (InspectionRecordItem.template_item_id == item_id)
        )
    )
    record_item = result.scalar_one_or_none()
    if not record_item:
        raise HTTPException(status_code=404, detail="Item not found")

    if not record_item.template_item:

        class MockTemplateItemStream:
            pass

        template_item = MockTemplateItemStream()
        template_item.title = record_item.item_title
        template_item.description = record_item.item_description
        template_item.check_method = record_item.item_check_method
        template_item.legal_basis = record_item.item_legal_basis
        template_item.standard_ref = record_item.item_standard_ref
        template_item.risk_level = record_item.item_risk_level
    else:
        template_item = record_item.template_item
    try:
        suggestion, from_cache, duration_ms = await llm_service.get_suggestion(
            template_item=template_item,
            record=record_item,
            db=db,
            user_id=str(current_user.id),
            task_id=record_id,
            use_cache=False,
        )

        basis, _, _ = await llm_service.get_basis(
            template_item=template_item,
            record=record_item,
            db=db,
            user_id=str(current_user.id),
            task_id=record_id,
            use_cache=False,
        )

        await db.commit()

        return make_response(
            data={
                "suggestion": suggestion,
                "basis": basis,
                "from_cache": from_cache,
                "duration_ms": duration_ms,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/{record_id}/items/{item_id}/accept-ai", response_model=ApiResponse)
async def accept_ai_suggestion(
    record_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """采纳AI建议"""
    record = await db.get(InspectionRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Record not found")

    # 权限检查
    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(InspectionRecordItem)
        .where(InspectionRecordItem.id == item_id)
        .where(InspectionRecordItem.record_id == record_id)
    )
    record_item = result.scalar_one_or_none()
    if not record_item:
        raise HTTPException(status_code=404, detail="Item not found")

    if record_item.ai_suggestion:
        record_item.text_value = record_item.ai_suggestion
        record_item.ai_generated = True
        await db.commit()

    return make_response(message="AI suggestion accepted")


@router.get("/{record_id}/items/{item_id}/ai-stream")
async def generate_ai_suggestion_stream(
    record_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """流式生成AI建议"""
    record = await db.get(InspectionRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Record not found")

    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(InspectionRecordItem)
        .options(selectinload(InspectionRecordItem.template_item))
        .where(InspectionRecordItem.record_id == record_id)
        .where(
            (InspectionRecordItem.id == item_id)
            | (InspectionRecordItem.template_item_id == item_id)
        )
    )
    record_item = result.scalar_one_or_none()
    if not record_item:
        raise HTTPException(status_code=404, detail="Item not found")

    if not record_item.template_item:

        class MockTemplateItemStream:
            pass

        template_item = MockTemplateItemStream()
        template_item.title = record_item.item_title
        template_item.description = record_item.item_description
        template_item.check_method = record_item.item_check_method
        template_item.legal_basis = record_item.item_legal_basis
        template_item.standard_ref = record_item.item_standard_ref
        template_item.risk_level = record_item.item_risk_level
    else:
        template_item = record_item.template_item

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


@router.get("/{record_id}/final-judgment-stream")
async def generate_final_judgment_stream(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """流式生成最终判定结论"""
    result = await db.execute(
        select(InspectionRecord)
        .options(
            selectinload(InspectionRecord.template),
            selectinload(InspectionRecord.enterprise),
        )
        .where(
            InspectionRecord.id == record_id,
            InspectionRecord.is_deleted == False,  # noqa: E712
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    items_result = await db.execute(
        select(InspectionRecordItem)
        .options(selectinload(InspectionRecordItem.template_item))
        .where(InspectionRecordItem.record_id == record_id)
    )
    record_items = items_result.scalars().all()

    items_data = []
    for item in record_items:
        template_item = item.template_item
        items_data.append(
            {
                "title": item.item_title
                if item.item_title
                else (template_item.title if template_item else "未知检查项"),
                "result": item.result,
                "radio_value": item.radio_value,
                "score_value": item.score_value,
                "numeric_value": item.numeric_value,
                "text_value": item.text_value,
                "multi_value": item.multi_value or [],
                "risk_level": item.item_risk_level
                if item.item_title
                else (template_item.risk_level if template_item else None),
                "problem_description": item.problem_description,
                "pass_score": template_item.pass_score if template_item else None,
                "max_score": template_item.max_score if template_item else None,
                "min_value": item.item_min_value
                if item.item_title
                else (template_item.min_value if template_item else None),
                "max_value": item.item_max_value
                if item.item_title
                else (template_item.max_value if template_item else None),
                "unit": item.item_unit
                if item.item_title
                else (template_item.unit if template_item else None),
            }
        )

    enterprise_name = (
        record.enterprise.name if record.enterprise else record.enterprise_name
    )
    template_name = (
        record.template.name
        if record.template
        else (
            record.template_snapshot.get("name") if record.template_snapshot else None
        )
    )
    inspection_date = (
        record.inspection_date.isoformat() if record.inspection_date else None
    )

    async def generate(template_name, inspection_date, items_data):
        async for chunk in llm_service.get_final_judgment_stream(
            template_name=template_name,
            inspection_date=inspection_date,
            items=items_data,
        ):
            data = json.dumps(chunk, ensure_ascii=False)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        generate(template_name, inspection_date, items_data),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{record_id}/items/{item_id}/history-stats", response_model=ApiResponse)
async def get_item_history_stats(
    record_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取检查项的历史统计信息

    返回该企业针对该检查项的历史检查记录：
    - 总检查次数
    - 不合格次数
    - 不合格率
    - 最近一次检查结果
    - 最近几次检查记录详情
    """
    record = await db.get(InspectionRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Record not found")

    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(InspectionRecordItem)
        .where(InspectionRecordItem.record_id == record_id)
        .where(
            (InspectionRecordItem.id == item_id)
            | (InspectionRecordItem.template_item_id == item_id)
        )
    )
    current_item = result.scalar_one_or_none()
    if not current_item:
        raise HTTPException(status_code=404, detail="Item not found")

    template_item_id = current_item.template_item_id
    enterprise_id = record.enterprise_id

    if not enterprise_id:
        return make_response(
            data={
                "total_inspections": 0,
                "fail_count": 0,
                "pass_count": 0,
                "na_count": 0,
                "fail_rate": 0,
                "last_result": None,
                "last_inspection_date": None,
                "history_records": [],
                "has_history": False,
                "message": "该检查记录未关联企业，无法查询历史",
            }
        )

    history_query = (
        select(InspectionRecordItem)
        .join(InspectionRecord, InspectionRecordItem.record_id == InspectionRecord.id)
        .where(InspectionRecord.enterprise_id == enterprise_id)
        .where(InspectionRecord.status == "submitted")
        .where(InspectionRecordItem.template_item_id == template_item_id)
        .where(InspectionRecord.id != record_id)
        .options(
            selectinload(InspectionRecordItem.record).selectinload(
                InspectionRecord.inspector
            )
        )
        .order_by(desc(InspectionRecord.inspection_date))
    )

    history_result = await db.execute(history_query)
    history_items = history_result.scalars().all()

    total_inspections = len(history_items)
    fail_count = 0
    pass_count = 0
    na_count = 0
    history_records = []

    for idx, item in enumerate(history_items):
        radio_value = item.radio_value
        if radio_value == "fail":
            fail_count += 1
        elif radio_value == "pass":
            pass_count += 1
        elif radio_value == "na":
            na_count += 1

        history_records.append(
            {
                "record_id": str(item.record_id),
                "inspection_date": item.record.inspection_date.isoformat()
                if item.record and item.record.inspection_date
                else None,
                "result": radio_value,
                "problem_description": item.problem_description,
                "inspector_name": item.record.inspector.full_name
                if item.record and item.record.inspector
                else None,
                "is_recent": idx < 3,
            }
        )

    fail_rate = (
        round(fail_count / total_inspections * 100, 1) if total_inspections > 0 else 0
    )

    last_result = None
    last_inspection_date = None
    if history_items:
        last_item = history_items[0]
        last_result = last_item.radio_value
        last_inspection_date = (
            last_item.record.inspection_date.isoformat()
            if last_item.record and last_item.record.inspection_date
            else None
        )

    return make_response(
        data={
            "total_inspections": total_inspections,
            "fail_count": fail_count,
            "pass_count": pass_count,
            "na_count": na_count,
            "fail_rate": fail_rate,
            "last_result": last_result,
            "last_inspection_date": last_inspection_date,
            "history_records": history_records[:5],
            "has_history": total_inspections > 0,
            "item_title": current_item.item_title,
            "enterprise_name": record.enterprise_name,
        }
    )


@router.get("/{record_id}/report", response_model=ApiResponse)
async def get_report_data(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取检查报告数据（用于前端预览）
    """
    from app.services.report_service import report_service

    result = await db.execute(
        select(InspectionRecord)
        .options(
            selectinload(InspectionRecord.template).selectinload(InspectionTemplate.items),
            selectinload(InspectionRecord.enterprise),
            selectinload(InspectionRecord.inspector),
            selectinload(InspectionRecord.items),
        )
        .where(
            InspectionRecord.id == record_id,
            InspectionRecord.is_deleted == False,  # noqa: E712
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    report_data = report_service.generate_report_data(record)
    return make_response(data=report_data)


@router.get("/{record_id}/report/pdf")
async def download_report_pdf(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    下载检查报告PDF
    """
    from app.services.report_service import report_service
    from fastapi.responses import Response

    result = await db.execute(
        select(InspectionRecord)
        .options(
            selectinload(InspectionRecord.template),
            selectinload(InspectionRecord.enterprise),
            selectinload(InspectionRecord.inspector),
        )
        .where(
            InspectionRecord.id == record_id,
            InspectionRecord.is_deleted == False,  # noqa: E712
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if current_user.role not in ("admin", "super_admin") and str(
        record.inspector_id
    ) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    pdf_bytes = report_service.generate_pdf(record)

    from urllib.parse import quote
    enterprise_name = record.enterprise_name or (
        record.enterprise.name if record.enterprise else "未知企业"
    )
    filename = f"检查报告_{enterprise_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    encoded_filename = quote(filename)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"report.pdf\"; filename*=UTF-8''{encoded_filename}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
