"""检查项结果统计的统一口径。

历史上 `routers/records.py` 与 `services/report_service.py` 各写了一份统计，
枚举集合不一致——一处只认 ``"na"``，另一处认 ``"na"`` / ``"not_applicable"``。
而写入侧实际落库的是 ``not_applicable``（全库 489 条明细中 ``na`` 为 0 条），
于是同一份记录在「检查记录详情」里"不适用项"恒为 0，与「检查报告」对不上。

本模块是唯一口径来源，所有涉及合格/不合格/不适用计数的接口都必须调用它，
不要再各自写一套。
"""

from typing import Any, Iterable, Optional

# 判定值集合。与写入侧（前端选项 value）保持一致，同时兼容历史/外部集成写入的同义值。
#   · "1" / "3" —— 早期三级评价（evaluation_3level）的编码，历史数据与旧客户端可能存在
#   · "不适用"  —— 中文写法，旧数据中存在
#   · "n/a" / "not-applicable" —— 外部集成的写法
PASS_VALUES = frozenset({"pass", "compliant", "qualified", "1"})
FAIL_VALUES = frozenset({"fail", "non_compliant", "unqualified", "3"})
NA_VALUES = frozenset({"na", "not_applicable", "not-applicable", "n/a", "不适用"})

# 单独归类但不计入 pass/fail/na 的中间态（待整改、观察项等）。
# 保持与 PC 端 failItems 判定一致：它们不算「不合格」，只算「已填写但未归类」。
OTHER_VALUES = frozenset({"pending_rectification", "observe"})

# 三级评价编码（evaluation_3level）—— 认证审核材料里的「符合/基本符合/不符合」。
# 与 radio_value 的区别只在 "2"：三级评价把「基本符合」也算合格。
# 因此**不能**直接并入 PASS_VALUES，否则 radio_value="2" 会被误判为合格。
EVAL3_PASS_VALUES = frozenset({"1", "2"})
EVAL3_FAIL_VALUES = frozenset({"3"})

_BUCKET_VALUES = {
    "pass": PASS_VALUES,
    "fail": FAIL_VALUES,
    "na": NA_VALUES,
}

# 承载判定值的字段名。三套并行记录模型字段名不一致，这里集中登记。
# 顺序即优先级：radio_value（PC/H5 主路径）→ result（App 路径）→ evaluation_3level（认证审核）。
RESULT_FIELDS = ("radio_value", "result", "evaluation_3level")


def classify_result(value: Optional[Any]) -> Optional[str]:
    """把检查项判定值归类为 ``pass`` / ``fail`` / ``na``；无法归类返回 ``None``。"""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in PASS_VALUES:
        return "pass"
    if text in FAIL_VALUES:
        return "fail"
    if text in NA_VALUES:
        return "na"
    return None


def radio_value_of(item: Any) -> Optional[str]:
    """兼容 ORM 对象与 dict 两种入参形态。"""
    if isinstance(item, dict):
        return item.get("radio_value")
    return getattr(item, "radio_value", None)


def _raw_of(item: Any, field: str) -> Optional[Any]:
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field, None)


def classify_evaluation_3level(value: Optional[Any]) -> Optional[str]:
    """把三级评价编码（1 符合 / 2 基本符合 / 3 不符合）归类为 pass / fail。

    与 :func:`classify_result` 的唯一差别：「2（基本符合）」算合格。
    因此本函数必须独立存在，不能复用 ``classify_result``。
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text in EVAL3_PASS_VALUES:
        return "pass"
    if text in EVAL3_FAIL_VALUES:
        return "fail"
    return None


def classify_item(item: Any) -> Optional[str]:
    """归类**任意模型**的检查项明细 —— 跨模型唯一归类入口。

    三套并行记录模型的判定字段不同：``InspectionRecordItem`` / ``TaskItemRecord``
    用 ``radio_value`` 或 ``result``，认证审核路径还会写 ``evaluation_3level``。
    按 :data:`RESULT_FIELDS` 的优先级取**第一个能归类**的值，
    避免出现「同时命中合格与不合格」的双计（旧实现用 ``or`` 连接，确有此缺陷）。

    无法归类（未填写、空串、未知值）返回 ``None``。
    """
    for field in RESULT_FIELDS:
        raw = _raw_of(item, field)
        if raw is None or not str(raw).strip():
            continue
        bucket = (
            classify_evaluation_3level(raw)
            if field == "evaluation_3level"
            else classify_result(raw)
        )
        if bucket:
            return bucket
    return None


def result_in(column: Any, bucket: str):
    """生成 SQL 判定表达式：``result_in(InspectionRecordItem.radio_value, "fail")``。

    用于把 ``.where(col == "fail")`` 这类**只认单一字面量**的查询
    换成覆盖全部别名的 ``IN`` 查询——这是「列表计数与明细列表对不上」的根因之一。
    """
    values = _BUCKET_VALUES.get(bucket)
    if values is None:
        raise ValueError(f"未知归类：{bucket!r}，可选 {sorted(_BUCKET_VALUES)}")
    return column.in_(sorted(values))


def is_pass(value: Optional[Any]) -> bool:
    """判定值是否属于「合格」。"""
    return classify_result(value) == "pass"


def is_fail(value: Optional[Any]) -> bool:
    """判定值是否属于「不合格」。"""
    return classify_result(value) == "fail"


def is_na(value: Optional[Any]) -> bool:
    """判定值是否属于「不适用」。"""
    return classify_result(value) == "na"


def calculate_item_stats(items: Optional[Iterable[Any]]) -> dict:
    """统计检查项结果分布。

    ``items`` 支持 ORM 对象（``InspectionRecordItem``）或 dict（报告装配后的模板项）。
    返回 ``total`` / ``pass`` / ``fail`` / ``na`` / ``filled`` / ``unfilled``。
    """
    stats = {"total": 0, "pass": 0, "fail": 0, "na": 0}
    for item in items or []:
        stats["total"] += 1
        bucket = classify_result(radio_value_of(item))
        if bucket:
            stats[bucket] += 1
    stats["filled"] = stats["pass"] + stats["fail"] + stats["na"]
    stats["unfilled"] = stats["total"] - stats["filled"]
    return stats


def compliance_rate(stats: dict) -> float:
    """合规率 = 合格项 /（总项数 - 不适用项）。

    排除「不适用项」，文本/数值等有效项均计入分母，与用户业务规则定义保持一致。
    """
    total = stats.get("total", 0)
    na = stats.get("na", 0)
    denom = total - na
    if denom <= 0:
        return 0.0
    return round(stats.get("pass", 0) / denom * 100, 1)
