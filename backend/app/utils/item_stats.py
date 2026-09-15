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
PASS_VALUES = frozenset({"pass", "compliant", "qualified"})
FAIL_VALUES = frozenset({"fail", "non_compliant", "unqualified"})
NA_VALUES = frozenset({"na", "not_applicable", "not-applicable", "n/a"})

# 单独归类但不计入 pass/fail/na 的中间态（待整改、观察项等）。
# 保持与 PC 端 failItems 判定一致：它们不算「不合格」，只算「已填写但未归类」。
OTHER_VALUES = frozenset({"pending_rectification", "observe"})


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
    """合规率 = 合格项 /（合格项 + 不合格项）。

    分子分母均排除「不适用」与「未填写」，与工作台 /api/analytics/dashboard 口径一致。
    """
    rated = stats.get("pass", 0) + stats.get("fail", 0)
    if rated <= 0:
        return 0.0
    return round(stats["pass"] / rated * 100, 1)
