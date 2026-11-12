"""高性能树形结构构建工具 —— 替代 O(N²) 递归遍历。

原 `build_tree` 函数每次递归都遍历整个列表，对于 100 个节点的树会产生
数千次迭代。现在预先构建父子索引，时间复杂度降为 O(N)。

同时添加循环引用检测，防止脏数据导致无限递归崩溃。
"""

from typing import Any, Dict, List, Optional, Set, Callable

from app.utils.item_completion import resolve_check_type


def build_tree_fast(
    items: List[Any],
    get_id: Callable[[Any], str],
    get_parent_id: Callable[[Any], Optional[str]],
    build_node: Callable[[Any, List[dict]], dict],
    parent_id: Optional[str] = None,
) -> List[dict]:
    """快速构建树形结构（O(N) 时间复杂度）。

    Args:
        items: 扁平列表
        get_id: 从 item 中提取 ID 的函数
        get_parent_id: 从 item 中提取 parent_id 的函数
        build_node: 构建单个节点的函数 (item, children) -> dict
        parent_id: 根节点的 parent_id（默认 None）

    Returns:
        树形结构列表
    """
    if not items:
        return []

    # 1. 预先构建父子索引
    children_by_parent: Dict[Optional[str], List[Any]] = {}
    item_by_id: Dict[str, Any] = {}

    for item in items:
        item_id = get_id(item)
        item_parent = get_parent_id(item)
        item_by_id[item_id] = item
        children_by_parent.setdefault(item_parent, []).append(item)

    # 2. 循环引用检测
    def has_cycle(item_id: str, visited: Set[str]) -> bool:
        """检测从 item_id 开始是否存在循环引用"""
        if item_id in visited:
            return True
        visited.add(item_id)
        item = item_by_id.get(item_id)
        if not item:
            return False
        parent = get_parent_id(item)
        if parent and parent in item_by_id:
            return has_cycle(parent, visited)
        return False

    # 过滤掉有循环引用的节点
    valid_items = []
    for item in items:
        item_id = get_id(item)
        if not has_cycle(item_id, set()):
            valid_items.append(item)
        else:
            # 记录错误但不崩溃
            print(f"WARNING: Circular reference detected for item {item_id}")

    # 重建索引（只包含有效节点）
    children_by_parent.clear()
    for item in valid_items:
        item_parent = get_parent_id(item)
        children_by_parent.setdefault(item_parent, []).append(item)

    # 3. 递归构建树（现在是 O(N) 因为每个节点只访问一次）
    def _build(parent_key: Optional[str]) -> List[dict]:
        result = []
        for item in children_by_parent.get(parent_key, []):
            item_id = get_id(item)
            children = _build(item_id)
            node = build_node(item, children)
            result.append(node)
        return result

    return _build(parent_id)


def build_inspection_record_tree(
    template_items: List[Any],
    record_item_map: Dict[str, Any],
    record_item_title_map: Dict[str, Any],
) -> List[dict]:
    """构建检查记录的树形结构（专用于 records.py 的 get_record 端点）。

    Args:
        template_items: 模板检查项列表（可以是 TemplateItem 对象或 SnapshotItem）
        record_item_map: {template_item_id: record_item} 映射
        record_item_title_map: {item_title: record_item} 映射（fallback）

    Returns:
        树形结构列表
    """

    def get_id(item: Any) -> str:
        return str(item.id) if hasattr(item, "id") else str(getattr(item, "id", ""))

    def get_parent_id(item: Any) -> Optional[str]:
        parent = getattr(item, "parent_id", None)
        return str(parent) if parent else None

    def build_node(template_item: Any, children: List[dict]) -> dict:
        # 查找对应的记录项
        record_item = record_item_map.get(str(template_item.id))
        if not record_item and hasattr(template_item, "title") and template_item.title:
            record_item = record_item_title_map.get(template_item.title)

        # 构建节点字段（与原逻辑一致）
        title = (
            record_item.item_title
            if record_item and record_item.item_title
            else getattr(template_item, "title", "")
        )
        description = (
            record_item.item_description
            if record_item and record_item.item_title
            else getattr(template_item, "description", "")
        )
        check_method = (
            record_item.item_check_method
            if record_item and record_item.item_title
            else getattr(template_item, "check_method", "")
        )
        legal_basis = (
            record_item.item_legal_basis
            if record_item and record_item.item_title
            else getattr(template_item, "legal_basis", "")
        )
        standard_ref = (
            record_item.item_standard_ref
            if record_item and record_item.item_title
            else getattr(template_item, "standard_ref", "")
        )
        result_options = (
            record_item.item_result_options
            if record_item and record_item.item_title
            else getattr(template_item, "result_options", None)
        )

        min_value = (
            float(record_item.item_min_value)
            if record_item and record_item.item_min_value is not None
            else (
                float(template_item.min_value)
                if hasattr(template_item, "min_value") and template_item.min_value is not None
                else None
            )
        )
        max_value = (
            float(record_item.item_max_value)
            if record_item and record_item.item_max_value is not None
            else (
                float(template_item.max_value)
                if hasattr(template_item, "max_value") and template_item.max_value is not None
                else None
            )
        )
        unit = (
            record_item.item_unit
            if record_item and record_item.item_title
            else getattr(template_item, "unit", "")
        )
        score_weight = (
            float(record_item.item_score_weight)
            if record_item and record_item.item_score_weight is not None
            else (
                float(template_item.score_weight)
                if hasattr(template_item, "score_weight") and template_item.score_weight is not None
                else None
            )
        )
        default_score = (
            float(record_item.item_default_score)
            if record_item and record_item.item_default_score is not None
            else (
                float(template_item.default_score)
                if hasattr(template_item, "default_score") and template_item.default_score is not None
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
        # 类型口径与写入侧一致：快照 item_check_type 落库时已经过
        # resolve_check_type 归一；无快照时实时解析，避免 check_type 恒为
        # 列默认值 'radio' 把数值/文本/打分项误判成单选。
        check_type = (
            record_item.item_check_type
            if record_item and record_item.item_title and record_item.item_check_type
            else resolve_check_type(template_item)
        )

        def _num_attr(name: str) -> Optional[float]:
            value = getattr(template_item, name, None)
            return float(value) if value is not None else None

        return {
            "id": str(record_item.id) if record_item else str(template_item.id),
            "template_item_id": str(template_item.id),
            "parent_id": str(template_item.parent_id)
            if getattr(template_item, "parent_id", None)
            else None,
            "title": title,
            "description": description,
            "check_method": check_method,
            "legal_basis": legal_basis,
            "standard_ref": standard_ref,
            "check_type": check_type,
            "result_type": getattr(template_item, "result_type", "pass_fail"),
            "result_options": result_options,
            "min_value": min_value,
            "max_value": max_value,
            "unit": unit,
            "score_weight": score_weight,
            "default_score": default_score,
            "max_score": _num_attr("max_score"),
            "pass_score": _num_attr("pass_score"),
            "score_step": _num_attr("score_step"),
            # 与后端提交校验同一口径（is_required is not False），
            # 前端 `is_required !== false` 依赖真实布尔值。
            "is_required": getattr(template_item, "is_required", None) is not False,
            "sort_order": getattr(template_item, "sort_order", 0) or 0,
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
            "inspector_note": record_item.inspector_note if record_item else None,
            "problem_description": record_item.problem_description if record_item else None,
            "rectification_suggestion": record_item.rectification_suggestion
            if record_item
            else None,
            "ai_suggestion": record_item.ai_suggestion if record_item else None,
            "photos": record_item.photos or [] if record_item else [],
            # 动态纠偏：只要挂了子节点就一律按分类目录返回
            "is_category": bool(getattr(template_item, "is_category", False))
            or len(children) > 0,
            "children": children,
        }

    return build_tree_fast(
        template_items,
        get_id=get_id,
        get_parent_id=get_parent_id,
        build_node=build_node,
    )
