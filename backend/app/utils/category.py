"""分类目录（父节点）判定工具。

业务规则（老杨 2026-09-11 确认，A 类主线治理依据）：
    只要某个节点下存在有效子节点，该节点就**必须**是分类目录（is_category=True），
    不允许录入检查项内容，不参与打分，也不计入合规率的分子与分母。

历史背景：早期实现里"节点是目录还是检查项"只依赖 is_category 字段，
一旦该字段与真实层级不一致（脏数据、AI 抽取、历史遗留），
就会出现"根节点被当成检查项显示未填写""数量 6 vs 8"一整串问题。

因此本模块提供统一判定入口，所有需要区分"分类 / 检查项"的地方
（树构建、记录生成、统计口径）都必须走这里，禁止再各写一套。
"""
from typing import Iterable, Optional, Set

from sqlalchemy import select

from app.models.template import TemplateItem
from app.utils.soft_delete import not_deleted


def is_category_node(item, parent_ids: Optional[Iterable] = None) -> bool:
    """判定单个模板条目是否为分类目录（Python 侧）。

    Args:
        item: TemplateItem 实例或具备 id / is_category 属性的对象
        parent_ids: "存在有效子节点"的父节点 ID 集合，
                    由 :func:`load_parent_ids` 或 SQL 侧等价子查询得到

    Returns:
        True 表示该节点应作为分类目录处理
    """
    if item is None:
        return False
    if getattr(item, "is_category", None) is True:
        return True
    if parent_ids:
        return getattr(item, "id", None) in parent_ids
    return False


def parent_id_subquery():
    """返回"存在有效子节点"的父节点 ID 子查询（SQL 侧）。

    用法::

        stmt = select(TemplateItem).where(
            not_deleted(TemplateItem),
            TemplateItem.id.not_in(parent_id_subquery()),
        )

    这样即使 is_category 字段是脏的，也能在 SQL 层准确剔除父节点。
    """
    return (
        select(TemplateItem.parent_id)
        .where(
            TemplateItem.parent_id.is_not(None),
            not_deleted(TemplateItem),
        )
        .scalar_subquery()
    )


async def load_parent_ids(db, template_id=None, template_ids=None) -> Set:
    """查询"存在有效子节点"的父节点 ID 集合（异步）。

    Args:
        db: AsyncSession
        template_id: 限定单个模板
        template_ids: 限定多个模板

    Returns:
        set[UUID]：可作为分类目录的节点 ID 集合
    """
    stmt = select(TemplateItem.parent_id).where(
        TemplateItem.parent_id.is_not(None),
        not_deleted(TemplateItem),
    )
    if template_id is not None:
        stmt = stmt.where(TemplateItem.template_id == template_id)
    elif template_ids:
        stmt = stmt.where(TemplateItem.template_id.in_(list(template_ids)))

    rows = await db.execute(stmt)
    return {row[0] for row in rows.all() if row[0]}


def clear_check_item_fields(payload: dict, *, keep_title: bool = True) -> dict:
    """把字典形式的节点数据清洗为"纯分类目录"。

    用于 ORM 之外的场景（如快照 JSON 组装）。
    """
    for field in (
        "check_method",
        "legal_basis",
        "standard_ref",
        "result_type",
        "result_options",
        "min_value",
        "max_value",
        "unit",
        "score_weight",
        "default_score",
        "ai_prompt_template",
        "risk_level",
    ):
        if field in payload:
            payload[field] = None
    for field in ("is_required", "use_ai", "attachment_required", "allow_attachment"):
        if field in payload:
            payload[field] = False
    payload["is_category"] = True
    return payload


#: 分类目录必须清空 / 置否的字段全集。
#: 所有"把节点升级为分类目录"的地方都必须使用这一份定义，
#: 避免出现"某处漏了 is_required"这类字段清单漂移。
CATEGORY_FIELD_OVERRIDES: dict = {
    "is_category": True,
    "result_type": None,
    "result_options": None,
    "min_value": None,
    "max_value": None,
    "unit": None,
    "score_weight": None,
    "default_score": None,
    "check_method": None,
    "legal_basis": None,
    "standard_ref": None,
    "ai_prompt_template": None,
    "use_ai": False,
    "attachment_required": False,
    "allow_attachment": False,
    "is_required": False,
    "risk_level": None,
}


def normalize_as_category(item) -> None:
    """把 ORM 条目就地规范化为"纯分类目录"（清空所有检查项属性）。

    只对对象上真实存在的属性赋值，避免 AttributeError。
    """
    for field, value in CATEGORY_FIELD_OVERRIDES.items():
        if hasattr(item, field):
            setattr(item, field, value)
