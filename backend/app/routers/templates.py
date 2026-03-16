from datetime import datetime
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, or_
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
from app.services import AuditService

router = APIRouter()


def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.utcnow()
    )


def is_admin(user: User) -> bool:
    """检查用户是否为管理员"""
    return user.role in ["admin", "super_admin"]


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
    return str(template.created_by) == str(user.id)


@router.get("", response_model=ApiResponse)
async def get_templates(
    skip: int = 0,
    limit: int = 20,
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

    # 获取每个模板的统计信息
    template_list = []
    for t in templates:
        # 统计该模板的检查项目
        count_query = select(TemplateItem).where(TemplateItem.template_id == t.id)
        count_result = await db.execute(count_query)
        items = count_result.scalars().all()

        total_items = len(items)
        # 明确统计 is_category 为 True 和 False 的数量（处理 NULL 值）
        categories = sum(1 for item in items if item.is_category is True)
        check_items = sum(1 for item in items if item.is_category is not True)

        template_list.append({
            "id": str(t.id),
            "name": t.name,
            "code": t.code,
            "category": t.category,
            "version": t.version,
            "is_published": t.is_published,
            "is_public": t.is_public if t.is_public is not None else False,
            "is_quantified": t.is_quantified,
            "created_by": str(t.created_by) if t.created_by else None,
            "can_edit": can_modify_template(current_user, t),
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "stats": {
                "total_items": total_items,
                "categories": categories,
                "check_items": check_items,
            }
        })

    return make_response(data=template_list)


@router.post("", response_model=ApiResponse)
async def create_template(
    template_data: InspectionTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # 允许所有登录用户创建模板
):
    """创建检查模板

    权限规则：
    - 所有登录用户都可以创建模板
    - 专家创建的模板默认为个人模板(is_public=False)
    - 管理员可以创建公共模板
    """
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
    """
    template = await db.get(InspectionTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # 权限检查
    if not can_access_template(current_user, template):
        raise HTTPException(status_code=403, detail="您没有权限访问此模板")

    # 加载所有检查项目
    query = select(TemplateItem).where(TemplateItem.template_id == template_id).order_by(TemplateItem.sort_order)
    result = await db.execute(query)
    items = result.scalars().all()

    # 构建树形结构
    def build_tree(items: List[TemplateItem], parent_id: Optional[str] = None) -> List[dict]:
        tree = []
        for item in items:
            item_parent_id = str(item.parent_id) if item.parent_id else None
            if item_parent_id == parent_id:
                node = {
                    "id": str(item.id),
                    "parent_id": item_parent_id,
                    "title": item.title,
                    "description": item.description,
                    "check_method": item.check_method,
                    "legal_basis": item.legal_basis,
                    "standard_ref": item.standard_ref,
                    "result_type": item.result_type,
                    "result_options": item.result_options,
                    "min_value": float(item.min_value) if item.min_value else None,
                    "max_value": float(item.max_value) if item.max_value else None,
                    "unit": item.unit,
                    "is_required": item.is_required,
                    "use_ai": item.use_ai,
                    "risk_level": item.risk_level,
                    "is_category": item.is_category,
                    "score_weight": float(item.score_weight) if item.score_weight else None,
                    "default_score": float(item.default_score) if item.default_score else None,
                    "allow_attachment": item.allow_attachment,
                    "attachment_required": item.attachment_required,
                    "ai_prompt_template": item.ai_prompt_template,
                    "children": build_tree(items, str(item.id)),
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
    if not template:
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
    if not template:
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
    """删除模板（级联清理关联的检查记录项引用）

    权限规则：
    - 管理员：可以删除所有模板
    - 专家：只能删除自己创建的模板
    """
    template = await db.get(InspectionTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # 权限检查
    if not can_modify_template(current_user, template):
        raise HTTPException(status_code=403, detail="您没有权限删除此模板")

    # 找出该模板下所有 template_items
    items_result = await db.execute(
        select(TemplateItem).where(TemplateItem.template_id == template_id)
    )
    item_ids = [str(it.id) for it in items_result.scalars().all()]

    # (由于已经去除了 inspection_record_items 对 template_item_id 的强外键约束)
    # 历史检查记录中的数据将原样保留最初的 UUID 以支持快照匹配

    await db.delete(template)
    await db.commit()

    return make_response(message="Template deleted")


@router.post("/{template_id}/copy", response_model=ApiResponse)
async def copy_template(
    template_id: str,
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # 允许所有登录用户复制模板
):
    """复制模板（包含所有检查项目）

    权限规则：
    - 管理员：可以复制所有模板
    - 专家：只能复制公共模板和自己创建的模板
    """
    # 获取源模板
    source_template = await db.get(InspectionTemplate, template_id)
    if not source_template:
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
    query = select(TemplateItem).where(TemplateItem.template_id == template_id)
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
@router.post("/{template_id}/items", response_model=ApiResponse)
async def create_item(
    template_id: str,
    item_data: TemplateItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """在模板中添加检查项目

    权限规则：
    - 管理员：可以在所有模板中添加项目
    - 专家：只能在自己创建的模板中添加项目
    """
    template = await db.get(InspectionTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # 权限检查
    if not can_modify_template(current_user, template):
        raise HTTPException(status_code=403, detail="您没有权限修改此模板")

    item = TemplateItem(
        template_id=template_id,
        parent_id=item_data.parent_id,
        title=item_data.title,
        description=item_data.description,
        check_method=item_data.check_method,
        legal_basis=item_data.legal_basis,
        standard_ref=item_data.standard_ref,
        result_type=item_data.result_type or "pass_fail",
        result_options=item_data.result_options,
        min_value=item_data.min_value,
        max_value=item_data.max_value,
        unit=item_data.unit,
        is_required=item_data.is_required if item_data.is_required is not None else True,
        use_ai=item_data.use_ai if item_data.use_ai is not None else False,
        risk_level=item_data.risk_level or "medium",
        sort_order=item_data.sort_order or 0,
        is_category=item_data.is_category if item_data.is_category is not None else False,
        score_weight=item_data.score_weight,
        default_score=item_data.default_score,
        allow_attachment=item_data.allow_attachment if item_data.allow_attachment is not None else False,
        attachment_required=item_data.attachment_required if item_data.attachment_required is not None else False,
        ai_prompt_template=item_data.ai_prompt_template,
        created_by=current_user.id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return make_response(data={"id": str(item.id), "title": item.title})


@router.put("/items/{item_id}", response_model=ApiResponse)
async def update_item(
    item_id: str,
    item_data: TemplateItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新检查项目

    权限规则：
    - 管理员：可以更新所有检查项目
    - 专家：只能更新自己创建的模板中的项目
    """
    item = await db.get(TemplateItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # 获取所属模板进行权限检查
    template = await db.get(InspectionTemplate, item.template_id)
    if template and not can_modify_template(current_user, template):
        raise HTTPException(status_code=403, detail="您没有权限修改此模板的项目")

    update_data = item_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)

    return make_response(data={"id": str(item.id), "title": item.title})


@router.delete("/items/{item_id}", response_model=ApiResponse)
async def delete_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除检查项目（若为分类节点则级联删除所有子项，并解除 inspection_record_items 的引用）

    权限规则：
    - 管理员：可以删除所有检查项目
    - 专家：只能删除自己创建的模板中的项目
    """
    item = await db.get(TemplateItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # 获取所属模板进行权限检查
    template = await db.get(InspectionTemplate, item.template_id)
    if template and not can_modify_template(current_user, template):
        raise HTTPException(status_code=403, detail="您没有权限删除此模板的项目")

    # 递归收集所有子孙节点 ID（BFS）
    all_ids_to_delete: List[str] = [item_id]
    queue: List[str] = [item_id]
    while queue:
        current_ids = queue
        queue = []
        children_result = await db.execute(
            select(TemplateItem).where(
                TemplateItem.parent_id.in_([UUID(i) for i in current_ids])
            )
        )
        for child in children_result.scalars().all():
            child_id = str(child.id)
            all_ids_to_delete.append(child_id)
            queue.append(child_id)

    # (已去除外键约束，历史记录可自动留存 UUID 用于匹配模板快照，无需再置 NULL)

    # 按叶节点优先顺序（reverse 即可，BFS 最后加入的是最深层）删除
    for del_id in reversed(all_ids_to_delete):
        obj = await db.get(TemplateItem, del_id)
        if obj:
            await db.delete(obj)

    await db.commit()

    deleted_count = len(all_ids_to_delete)
    return make_response(
        message=f"已删除 {deleted_count} 个项目",
        data={"deleted_count": deleted_count},
    )