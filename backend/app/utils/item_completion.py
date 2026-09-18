"""检查项「是否已评定」的口径**唯一来源**（后端）。

业务口径（2026-09-18 确认）：

- **合格 / 不合格 / 不适用** —— 都算「已完成」
- **描述型 / 数值型 / 打分型 / 多选型** —— 只要填了内容就算「已完成」
- **全部为空** —— 「未评定」，不算完成

与前端 `web-admin/src/utils/completion.ts`、`h5-app` 的 `isItemCompleted`
保持同一判据。历史上后端 `GET /tasks/{id}/summary` 与前端任务详情页都只认
``result`` 字段非空，导致描述型/数值型检查项明明填了内容却显示「未评定」，
同一任务在 H5（按类型判定，4/4）与 Web（只认 result，3/4）给出不同完成度。

注意：两套记录模型字段名不同，本模块同时兼容：

- ``task_item_records``（H5 表格式检查）：result / result_value / result_text
- ``inspection_record_items``（Web 检查记录）：radio_value / numeric_value /
  text_value / score_value / multi_value
"""

from typing import Any

#: 判定型结论字段的候选顺序（radio_value 优先，其次 result）
_VERDICT_FIELDS = ("radio_value", "result", "evaluation_3level")


def _has(value: Any) -> bool:
    """非空判定：None / 空串 / 字面量 "null" / 空容器都视为空。"""
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    text = str(value).strip()
    return text != "" and text.lower() != "null"


def resolve_check_type(item: Any) -> str:
    """取检查项的真实类型。

    ``template_items`` 上 ``check_type`` 与 ``result_type`` **两个字段并存**，且各自
    带一个默认值：

    - ``check_type`` 默认 ``'radio'``（列默认值，模板编辑器并不写它）
    - ``result_type`` 默认 ``'pass_fail'``（模板编辑器实际写的是它）

    实测：某模板的「数值」「文字描述」检查项在库里是
    ``check_type='radio', result_type='numeric'/'text'``——只看 ``check_type``
    会把描述型/数值型误判为判定型。因此本函数取**非默认**的那个字段；
    两个都非默认时以 ``check_type`` 为准（它是较新的字段，AI 导入路径写它）。

    ``item`` 可以是模型对象，也可以是普通 dict。
    """

    def _pick(source: Any, keys: tuple) -> str:
        for key in keys:
            value = (
                source.get(key) if isinstance(source, dict) else getattr(source, key, None)
            )
            if value:
                return str(value).strip().lower()
        return ""

    check_type = _pick(item, ("check_type", "item_check_type"))
    result_type = _pick(item, ("result_type",))

    # 默认值不算「有效取值」
    if check_type and check_type != "radio":
        return _normalize(check_type)
    if result_type and result_type != "pass_fail":
        return _normalize(result_type)
    return "radio"


def _normalize(kind: str) -> str:
    """归一为记录项快照沿用的词表：radio/score/numeric/text/multi_check/audit_3level。"""
    if kind in ("", "radio", "pass_fail"):
        return "radio"
    if kind == "score":
        return "score"
    if kind == "numeric":
        return "numeric"
    if kind in ("text", "textarea"):
        return "text"
    if kind in ("multi", "multiselect", "multi_check"):
        return "multi_check"
    if kind == "audit_3level":
        return "audit_3level"
    return "radio"


def _get(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def is_item_assessed(item: Any, record: Any = None) -> bool:
    """该检查项是否已评定。

    :param item: 承载检查项类型（check_type / result_type）的对象
    :param record: 承载结果值的对象；省略时用 ``item`` 自身
    """
    target = record if record is not None else item
    if target is None:
        return False

    kind = resolve_check_type(item)

    if kind == "radio":
        # 判定型：必须有明确结论（合格/不合格/不适用），仅写备注不算完成
        return any(_has(_get(target, field)) for field in _VERDICT_FIELDS)
    if kind == "score":
        return _has(_get(target, "score_value")) or _has(_get(target, "result_value"))
    if kind == "numeric":
        return _has(_get(target, "numeric_value")) or _has(_get(target, "result_value"))
    if kind == "text":
        return _has(_get(target, "text_value")) or _has(_get(target, "result_text"))
    if kind == "multi_check":
        return _has(_get(target, "multi_value"))
    # audit_3level 等其余类型：有结论即算完成
    return _has(_get(target, "result")) or _has(_get(target, "evaluation_3level"))
