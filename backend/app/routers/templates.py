from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, or_, func, Integer, case
from sqlalchemy.orm import selectinload

# RELOADED_MARKER_V3

from app.database import get_db
from app.models.user import User
from app.models.template import InspectionTemplate, TemplateItem
from app.schemas import (
    ApiResponse,
    InspectionTemplateCreate,
    InspectionTemplateUpdate,
    InspectionTemplateResponse,
    TemplateItemCreate,
    TemplateItemUpdate,
    TemplateItemResponse,
)
from app.utils.security import get_current_user, get_current_admin_user
from app.utils.category import (
    CATEGORY_FIELD_OVERRIDES,
    normalize_as_category,
    parent_id_subquery,
)
from app.services import AuditService
from app.utils.response import make_response
from app.utils.roles import FIELD_ROLES, is_admin as is_admin_role

router = APIRouter()




def is_admin(user: User) -> bool:
    """检查用户是否为管理员"""
    return is_admin_role(user.role)


def can_access_template(user: User, template: InspectionTemplate) -> bool:
    """检查用户是否可以访问模板"""
    # 管理员可以访问所有模板
    if is_admin(user):
        return True
    # 专家可以访问公共模板或自己创建的模板
    if template.is_public:
        return True
    if str(template.created_by) == str(user.id):
        return True
    return False


def can_modify_template(user: User, template: InspectionTemplate) -> bool:
    """检查用户是否可以修改模板"""
    # 管理员可以修改所有模板
    if is_admin(user):
        return True
    # 专家只能修改自己创建的模板
    return user.role in FIELD_ROLES and str(template.created_by) == str(user.id)


@router.get("", response_model=ApiResponse)
async def get_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    is_published: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取检查模板列表

    权限规则：
    - 管理员：可以看到所有模板
    - 专家：只能看到公共模板(is_public=True)和自己创建的模板
    """
    query = select(InspectionTemplate)

    # 过滤软删除的模板
    query = query.where(InspectionTemplate.is_deleted == False)  # noqa: E712

    # 非管理员只能看到公共模板或自己创建的模板
    if not is_admin(current_user):
        query = query.where(
            or_(
                InspectionTemplate.is_public == True,
                InspectionTemplate.created_by == current_user.id
            )
        )

    if category:
        query = query.where(InspectionTemplate.category == category)
    if is_published is not None:
        query = query.where(InspectionTemplate.is_published == is_published)

    query = query.order_by(InspectionTemplate.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    templates = result.scalars().all()

    if not templates:
        return make_response(data=[])

    template_ids = [t.id for t in templates]

    # 性能优化：先查出当前这批模板中哪些节点是父节点，而不是用全局子查询
    # 旧的 parent_id_subquery() 会扫描所有模板，导致查询慢（9秒+）
    parent_ids_result = await db.execute(
        select(TemplateItem.parent_id)
        .where(
            TemplateItem.template_id.in_(template_ids),
            TemplateItem.parent_id.is_not(None),
            TemplateItem.is_deleted == False,
        )
        .distinct()
    )
    parent_ids = {row[0] for row in parent_ids_result.all() if row[0]}

    # 统计口径统一（老杨 2026-09-11 确认）：
    #   total_items = 有效条目数（不含软删除）
    #   categories  = 分类目录数（显式标记 is_category，或存在有效子节点的父节点）
    #   check_items = 真正的叶子检查项数，分类目录不计入
    # 三者满足 total_items = categories + check_items，杜绝"6 vs 8"式对不上账。
    is_cat_expr = or_(
        TemplateItem.is_category.is_(True),
        TemplateItem.id.in_(parent_ids) if parent_ids else False,
    )
    items_count_query = select(
        TemplateItem.template_id,
        func.count(TemplateItem.id).label('total_items'),
        func.sum(case((is_cat_expr, 1), else_=0)).label('categories'),
        func.sum(case((is_cat_expr, 0), else_=1)).label('check_items'),
    ).where(
        TemplateItem.template_id.in_(template_ids),
        TemplateItem.is_deleted == False,  # noqa: E712
    ).group_by(TemplateItem.template_id)
    
    items_result = await db.execute(items_count_query)
    stats_map = {row.template_id: {'total_items': row.total_items, 'categories': row.categories or 0, 'check_items': row.check_items or 0} for row in items_result.all()}

    template_list = []
    for t in templates:
        stats = stats_map.get(t.id, {'total_items': 0, 'categories': 0, 'check_items': 0})
        template_list.append({
            'id': str(t.id),
            'name': t.name,
            'code': t.code,
            'category': t.category,
            'version': t.version,
            'is_published': t.is_published,
            'is_public': t.is_public if t.is_public is not None else False,
            'is_quantified': t.is_quantified,
            'created_by': str(t.created_by) if t.created_by else None,
            'can_edit': can_modify_template(current_user, t),
            'created_at': t.created_at.isoformat() if t.created_at else None,
            'stats': stats
        })

    return make_response(data=template_list)


@router.post("", response_model=ApiResponse)
async def create_template(
    template_data: InspectionTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建检查模板

    权限规则：
    - 管理员与专家可以创建模板；只读复核角色不可写入
    - 专家创建的模板默认为个人模板(is_public=False)
    - 管理员可以创建公共模板
    """
    if not is_admin(current_user) and current_user.role not in FIELD_ROLES:
        raise HTTPException(status_code=403, detail="只读复核角色不能创建模板")

    # 检查 code 唯一性（如果提供了 code）
    if template_data.code:
        existing = await db.execute(
            select(InspectionTemplate).where(
                InspectionTemplate.code == template_data.code,
                InspectionTemplate.is_deleted == False,  # noqa: E712
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"模板编码 '{template_data.code}' 已存在")

    template = InspectionTemplate(
        name=template_data.name,
        code=template_data.code,
        description=template_data.description,
        category=template_data.category,
        version=template_data.version or "1.0",
        is_quantified=template_data.is_quantified if template_data.is_quantified is not None else False,
        is_public=template_data.is_public if is_admin(current_user) else False,  # 只有管理员可以设置公共模板
        created_by=current_user.id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "create_template",
        "inspection_template",
        str(template.id),
    )

    return make_response(data={"id": str(template.id), "name": template.name})


@router.get("/{template_id}", response_model=ApiResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取模板详情（包含所有检查项目）

    权限规则：
    - 管理员：可以查看所有模板
    - 专家：只能查看公共模板和自己创建的模板
    - 额外：若专家被分配了使用该模板的检查任务，也允许查看（现场执行需要）
    """
    template = await db.get(InspectionTemplate, template_id)
    if not template or template.is_deleted:
        raise HTTPException(status_code=404, detail="Template not found")

    from app.models.task import InspectionTask

    if current_user.role == "expert":
        related = await db.execute(
            select(InspectionTask.id)
            .where(
                InspectionTask.template_id == template.id,
                InspectionTask.assigned_to == current_user.id,
                InspectionTask.is_deleted == False,  # noqa: E712
            )
            .limit(1)
        )
    else:
        related = await db.execute(
            select(InspectionTask.id)
            .where(
                InspectionTask.template_id == template.id,
                InspectionTask.is_deleted == False,  # noqa: E712
            )
            .limit(1)
        )
    has_related_task = related.scalar_one_or_none() is not None

    # 权限检查；关联任务只为有效模板补充现场执行只读权限。
    if not can_access_template(current_user, template) and not has_related_task:
        raise HTTPException(status_code=403, detail="您没有权限访问此模板")

    query = select(TemplateItem).where(
        TemplateItem.template_id == template_id,
        TemplateItem.is_deleted == False,  # noqa: E712
    ).order_by(TemplateItem.sort_order)
    result = await db.execute(query)
    items = result.scalars().all()

    # 构建树形结构
    def build_tree(items: List[TemplateItem], parent_id: Optional[str] = None) -> List[dict]:
        tree = []
        for item in items:
            item_parent_id = str(item.parent_id) if item.parent_id else None
            if item_parent_id == parent_id:
                children = build_tree(items, str(item.id))
                is_cat = bool(item.is_category) or len(children) > 0
                node = {
                    "id": str(item.id),
                    "parent_id": item_parent_id,
                    "title": item.title,
                    "description": item.description,
                    "check_method": None if is_cat else item.check_method,
                    "legal_basis": None if is_cat else item.legal_basis,
                    "standard_ref": None if is_cat else item.standard_ref,
                    "result_type": None if is_cat else item.result_type,
                    "result_options": None if is_cat else item.result_options,
                    "min_value": None if is_cat else (float(item.min_value) if item.min_value else None),
                    "max_value": None if is_cat else (float(item.max_value) if item.max_value else None),
                    "unit": None if is_cat else item.unit,
                    "is_required": False if is_cat else item.is_required,
                    "use_ai": False if is_cat else item.use_ai,
                    "risk_level": item.risk_level,
                    "is_category": is_cat,
                    "score_weight": None if is_cat else (float(item.score_weight) if item.score_weight else None),
                    "default_score": None if is_cat else (float(item.default_score) if item.default_score else None),
                    "allow_attachment": False if is_cat else item.allow_attachment,
                    "attachment_required": False if is_cat else item.attachment_required,
                    "ai_prompt_template": None if is_cat else item.ai_prompt_template,
                    "children": children,
                }
                tree.append(node)
        return tree

    return make_response(data={
        "id": str(template.id),
        "name": template.name,
        "code": template.code,
        "description": template.description,
        "category": template.category,
        "version": template.version,
        "is_published": template.is_published,
        "is_public": template.is_public if template.is_public is not None else False,
        "is_quantified": template.is_quantified,
        "created_by": str(template.created_by) if template.created_by else None,
        "can_edit": can_modify_template(current_user, template),
        "items": build_tree(items),
    })


@router.put("/{template_id}", response_model=ApiResponse)
async def update_template(
    template_id: str,
    template_data: InspectionTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新模板基本信息

    权限规则：
    - 管理员：可以更新所有模板
    - 专家：只能更新自己创建的模板
    """
    template = await db.get(InspectionTemplate, template_id)
    if not template or template.is_deleted:
        raise HTTPException(status_code=404, detail="Template not found")

    # 权限检查
    if not can_modify_template(current_user, template):
        raise HTTPException(status_code=403, detail="您没有权限修改此模板")

    update_data = template_data.model_dump(exclude_unset=True)
    # 只有管理员可以修改 is_public 字段
    if "is_public" in update_data and not is_admin(current_user):
        del update_data["is_public"]

    for field, value in update_data.items():
        setattr(template, field, value)

    await db.commit()
    await db.refresh(template)

    return make_response(data={"id": str(template.id), "name": template.name})


@router.post("/{template_id}/publish", response_model=ApiResponse)
async def publish_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发布模板

    权限规则：
    - 管理员：可以发布所有模板
    - 专家：只能发布自己创建的模板
    """
    template = await db.get(InspectionTemplate, template_id)
    if not template or template.is_deleted:
        raise HTTPException(status_code=404, detail="Template not found")

    # 权限检查
    if not can_modify_template(current_user, template):
        raise HTTPException(status_code=403, detail="您没有权限发布此模板")

    template.is_published = True
    await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "publish_template",
        "inspection_template",
        str(template.id),
    )

    return make_response(message="Template published")


@router.delete("/{template_id}", response_model=ApiResponse)
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除模板（软删除）

    权限规则：
    - 管理员：可以删除所有模板
    - 专家：只能删除自己创建的模板

    说明：
    - 采用软删除（is_deleted=True），保留模板及其检查项的原始数据
    - 历史检查记录、审核计划等引用此模板的记录仍可正常访问
    - 唯一字段 code 会被重命名以避免阻塞新模板创建

    级联：走 ``soft_delete_cascade``，但 ``FK_CASCADE_POLICY`` 中所有指向
    ``inspection_templates`` 的关系都登记为 **PRESERVE**——即此处**有意不级联**。
    走统一入口是为了让策略表成为唯一权威：将来若某个关系需要改判，
    改策略表即可，不必回来改这个端点。
    ``test_history_preserving_relations_are_not_cascaded`` 守住这条约定。
    """
    from app.utils.soft_delete import soft_delete_cascade

    template = await db.get(InspectionTemplate, template_id)
    if not template or template.is_deleted:
        raise HTTPException(status_code=404, detail="Template not found")

    # 权限检查
    if not can_modify_template(current_user, template):
        raise HTTPException(status_code=403, detail="您没有权限删除此模板")

    # 软删除：设置标记并重命名唯一字段
    affected = await soft_delete_cascade(db, template, unique_fields=["code"])

    await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "delete_template",
        "inspection_template",
        str(template.id),
    )

    return make_response(message="Template deleted", data={"cascaded": affected})



@router.post("/{template_id}/copy", response_model=ApiResponse)
async def copy_template(
    template_id: str,
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """复制模板（包含所有检查项目）

    权限规则：
    - 管理员：可以复制所有模板
    - 专家：只能复制公共模板和自己创建的模板
    - 只读复核角色不可复制
    """
    if not is_admin(current_user) and current_user.role not in FIELD_ROLES:
        raise HTTPException(status_code=403, detail="只读复核角色不能复制模板")

    # 获取源模板
    source_template = await db.get(InspectionTemplate, template_id)
    if not source_template or source_template.is_deleted:
        raise HTTPException(status_code=404, detail="Source template not found")

    # 权限检查
    if not can_access_template(current_user, source_template):
        raise HTTPException(status_code=403, detail="您没有权限复制此模板")

    # 创建新模板
    new_template = InspectionTemplate(
        name=name if name else f"{source_template.name}（副本）",
        code=None,  # 不复制 code，避免唯一约束冲突
        description=source_template.description,
        category=source_template.category,
        version=source_template.version,
        is_quantified=source_template.is_quantified,
        is_public=False,  # 复制的模板默认为个人模板
        created_by=current_user.id,
    )
    db.add(new_template)
    await db.flush()  # 获取新模板的 ID

    # 获取源模板的所有检查项目
    query = select(TemplateItem).where(
        TemplateItem.template_id == template_id,
        TemplateItem.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(query)
    source_items = result.scalars().all()

    # 构建 ID 映射（旧 ID -> 新 ID），用于处理父子关系
    id_mapping = {}

    # 先创建所有项目（不设置 parent_id）
    for item in source_items:
        new_item = TemplateItem(
            template_id=new_template.id,
            title=item.title,
            description=item.description,
            check_method=item.check_method,
            legal_basis=item.legal_basis,
            standard_ref=item.standard_ref,
            result_type=item.result_type,
            result_options=item.result_options,
            min_value=item.min_value,
            max_value=item.max_value,
            unit=item.unit,
            is_required=item.is_required,
            use_ai=item.use_ai,
            risk_level=item.risk_level,
            sort_order=item.sort_order,
            is_category=item.is_category,
            score_weight=item.score_weight,
            default_score=item.default_score,
            allow_attachment=item.allow_attachment,
            attachment_required=item.attachment_required,
            ai_prompt_template=item.ai_prompt_template,
            created_by=current_user.id,
        )
        db.add(new_item)
        await db.flush()  # 获取新项目的 ID
        id_mapping[str(item.id)] = str(new_item.id)

    # 更新父子关系
    for item in source_items:
        if item.parent_id:
            new_item_id = id_mapping.get(str(item.id))
            new_parent_id = id_mapping.get(str(item.parent_id))
            if new_item_id and new_parent_id:
                # 更新 parent_id，需要转换为 UUID
                item_to_update = await db.get(TemplateItem, new_item_id)
                if item_to_update:
                    item_to_update.parent_id = UUID(new_parent_id)

    # 统一规范化：复制后若某节点成为父节点，必须升级为分类目录
    # （源模板若存在"有子项但未标分类"的脏数据，直接复制不会把它洗干净）
    copied_parent_ids = {
        item.parent_id for item in source_items if item.parent_id is not None
    }
    for old_parent_id in copied_parent_ids:
        new_parent_id = id_mapping.get(str(old_parent_id))
        if not new_parent_id:
            continue
        copied_parent = await db.get(TemplateItem, new_parent_id)
        if copied_parent:
            normalize_as_category(copied_parent)

    await db.commit()
    await db.refresh(new_template)

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "copy_template",
        "inspection_template",
        str(new_template.id),
        detail={"source_template_id": str(template_id)},
    )

    return make_response(data={"id": str(new_template.id), "name": new_template.name})


# 检查项目管理
@router.get("/{template_id}/items", response_model=ApiResponse)
async def get_template_items(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取模板的所有检查项目（树形结构）"""
    template = await db.get(InspectionTemplate, template_id)
    if not template or template.is_deleted:
        raise HTTPException(status_code=404, detail="Template not found")

    from app.models.task import InspectionTask

    if current_user.role == "expert":
        related = await db.execute(
            select(InspectionTask.id)
            .where(
                InspectionTask.template_id == template.id,
                InspectionTask.assigned_to == current_user.id,
                InspectionTask.is_deleted == False,  # noqa: E712
            )
            .limit(1)
        )
    else:
        related = await db.execute(
            select(InspectionTask.id)
            .where(
                InspectionTask.template_id == template.id,
                InspectionTask.is_deleted == False,  # noqa: E712
            )
            .limit(1)
        )
    has_related_task = related.scalar_one_or_none() is not None

    if not can_access_template(current_user, template) and not has_related_task:
        raise HTTPException(status_code=403, detail="您没有权限访问此模板")

    query = select(TemplateItem).where(
        TemplateItem.template_id == template_id,
        TemplateItem.is_deleted == False,  # noqa: E712
    ).order_by(TemplateItem.sort_order)
    result = await db.execute(query)
    items = result.scalars().all()

    def build_tree(item_list: List[TemplateItem], parent_id: Optional[str] = None) -> List[dict]:
        tree = []
        for item in item_list:
            if (item.parent_id and str(item.parent_id) == parent_id) or (not item.parent_id and not parent_id):
                children = build_tree(item_list, str(item.id))
                is_cat = bool(item.is_category) or len(children) > 0
                tree.append({
                    "id": str(item.id),
                    "title": item.title,
                    "check_method": None if is_cat else item.check_method,
                    "result_type": None if is_cat else item.result_type,
                    "is_required": False if is_cat else item.is_required,
                    "is_category": is_cat,
                    "sort_order": item.sort_order,
                    "parent_id": str(item.parent_id) if item.parent_id else None,
                    "children": children,
                })
        return tree

    return make_response(data=build_tree(items))


@router.post("/{template_id}/items", response_model=ApiResponse)
async def create_item(
    template_id: str,
    item_data: TemplateItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """在模板中添加检查项目

    权限与业务规则：
    - 管理员可以在所有模板中添加项目，专家只能在自己创建的模板中添加项目
    - 若指定了 parent_id，其父节点自动升级为分类目录（is_category=True），且清空检查项属性
    - 若新增节点本身为分类目录，禁止录入检查项内容
    """
    template = await db.get(InspectionTemplate, template_id)
    if not template or template.is_deleted:
        raise HTTPException(status_code=404, detail="Template not found")

    # 权限检查
    if not can_modify_template(current_user, template):
        raise HTTPException(status_code=403, detail="您没有权限修改此模板")

    is_category = bool(item_data.is_category)

    # BUG-20：父节点必须真实存在且属于同一模板，否则给出明确的 404 而非落库后的外键冲突 409
    parent_item = None
    if item_data.parent_id:
        parent_item = await db.get(TemplateItem, item_data.parent_id)
        if (
            not parent_item
            or parent_item.is_deleted
            or str(parent_item.template_id) != str(template_id)
        ):
            raise HTTPException(status_code=404, detail="父节点不存在或不属于当前模板")

    item = TemplateItem(
        template_id=template_id,
        parent_id=item_data.parent_id,
        title=item_data.title,
        description=item_data.description,
        check_method=None if is_category else item_data.check_method,
        legal_basis=None if is_category else item_data.legal_basis,
        standard_ref=None if is_category else item_data.standard_ref,
        result_type=None if is_category else (item_data.result_type or "pass_fail"),
        result_options=None if is_category else item_data.result_options,
        min_value=None if is_category else item_data.min_value,
        max_value=None if is_category else item_data.max_value,
        unit=None if is_category else item_data.unit,
        is_required=False if is_category else (item_data.is_required if item_data.is_required is not None else True),
        use_ai=False if is_category else (item_data.use_ai if item_data.use_ai is not None else False),
        risk_level=None if is_category else (item_data.risk_level or "medium"),
        sort_order=item_data.sort_order or 0,
        is_category=is_category,
        score_weight=None if is_category else item_data.score_weight,
        default_score=None if is_category else item_data.default_score,
        allow_attachment=False if is_category else (item_data.allow_attachment if item_data.allow_attachment is not None else False),
        attachment_required=False if is_category else (item_data.attachment_required if item_data.attachment_required is not None else False),
        ai_prompt_template=None if is_category else item_data.ai_prompt_template,
        created_by=current_user.id,
    )
    db.add(item)

    # 若添加了子节点，自动将父节点规范升级为分类目录，并清空其检查项属性
    if parent_item:
        normalize_as_category(parent_item)

    await db.commit()
    await db.refresh(item)

    # BUG-37：回传完整字段（此前只回 {id,title}，调用方无法确认落库结果）
    return make_response(data=_item_payload(item))


def _item_payload(item: TemplateItem) -> dict:
    """模板项的完整扁平序列化（创建/更新响应共用）"""
    return {
        "id": str(item.id),
        "template_id": str(item.template_id),
        "parent_id": str(item.parent_id) if item.parent_id else None,
        "title": item.title,
        "description": item.description,
        "check_method": item.check_method,
        "legal_basis": item.legal_basis,
        "standard_ref": item.standard_ref,
        "result_type": item.result_type,
        "check_type": item.check_type,
        "is_required": item.is_required,
        "is_category": bool(item.is_category),
        "risk_level": item.risk_level,
        "sort_order": item.sort_order,
        "use_ai": item.use_ai,
        "allow_attachment": item.allow_attachment,
        "attachment_required": item.attachment_required,
        "ai_prompt_template": item.ai_prompt_template,
    }


@router.put("/items/{item_id}", response_model=ApiResponse)
async def update_item(
    item_id: str,
    item_data: TemplateItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新检查项目

    业务规则：
    - 只要该节点下存在有效子项，一律强制为分类目录（is_category=True），禁止录入检查项内容
    """
    item = await db.get(TemplateItem, item_id)
    if not item or getattr(item, "is_deleted", False):
        raise HTTPException(status_code=404, detail="Item not found")

    # 获取所属模板进行权限检查
    template = await db.get(InspectionTemplate, item.template_id)
    if not template or template.is_deleted:
        raise HTTPException(status_code=404, detail="Template not found")
    if not can_modify_template(current_user, template):
        raise HTTPException(status_code=403, detail="您没有权限修改此模板的项目")

    # 检查该节点是否拥有子节点
    children_count_res = await db.execute(
        select(func.count(TemplateItem.id)).where(
            TemplateItem.parent_id == item.id,
            TemplateItem.is_deleted == False,  # noqa: E712
        )
    )
    has_children = (children_count_res.scalar() or 0) > 0

    update_data = item_data.model_dump(exclude_unset=True)

    # 只要有子节点，或者主动设置为分类目录，强制规范化为纯净目录。
    # 字段清单统一取自 app/utils/category，避免各处清单漂移。
    if has_children or update_data.get("is_category") is True:
        update_data.update(CATEGORY_FIELD_OVERRIDES)

    for field, value in update_data.items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)

    # BUG-37：回传完整字段（此前只回 {id,title}，调用方无法确认落库结果）
    return make_response(data=_item_payload(item))


@router.delete("/items/{item_id}", response_model=ApiResponse)
async def delete_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除检查项目（软删除，若为分类节点则级联软删除所有子项）

    权限规则：
    - 管理员：可以删除所有检查项目
    - 专家：只能删除自己创建的模板中的项目
    """
    from app.utils.soft_delete import soft_delete

    item = await db.get(TemplateItem, item_id)
    if not item or item.is_deleted:
        raise HTTPException(status_code=404, detail="Item not found")

    # 获取所属模板进行权限检查
    template = await db.get(InspectionTemplate, item.template_id)
    if not template or template.is_deleted:
        raise HTTPException(status_code=404, detail="Template not found")
    if not can_modify_template(current_user, template):
        raise HTTPException(status_code=403, detail="您没有权限删除此模板的项目")

    # 递归收集所有子孙节点 ID（BFS）
    all_ids_to_delete: List[str] = [item_id]
    queue: List[str] = [item_id]
    while queue:
        current_ids = queue
        queue = []
        children_result = await db.execute(
            select(TemplateItem).where(
                TemplateItem.parent_id.in_([UUID(i) for i in current_ids]),
                TemplateItem.is_deleted == False,  # noqa: E712
            )
        )
        for child in children_result.scalars().all():
            child_id = str(child.id)
            all_ids_to_delete.append(child_id)
            queue.append(child_id)

    # 软删除所有收集到的节点（按任意顺序，软删除不会触发外键问题）
    for del_id in reversed(all_ids_to_delete):
        obj = await db.get(TemplateItem, del_id)
        if obj and not obj.is_deleted:
            await soft_delete(db, obj)

    await db.commit()

    deleted_count = len(all_ids_to_delete)
    return make_response(
        message=f"已删除 {deleted_count} 个项目",
        data={"deleted_count": deleted_count},
    )
