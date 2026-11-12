"""服务端统一计分，使用明细快照；无计分结果与零分分别返回 None 和 0。"""

from decimal import Decimal, InvalidOperation

from app.utils.item_completion import resolve_check_type
from app.utils.item_stats import classify_item


def _decimal(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def calculate_total_score(items):
    total = None
    for item in items:
        weight = _decimal(getattr(item, "item_score_weight", None))
        default = _decimal(getattr(item, "item_default_score", None))
        kind = resolve_check_type(item)
        score = None
        if kind == "score":
            raw = _decimal(getattr(item, "score_value", None))
            if raw is None:
                raw = _decimal(getattr(item, "result_value", None))
            if raw is not None:
                score = raw * (weight if weight is not None else Decimal(1))
        elif kind in {"radio", "audit_3level"} and (weight is not None or default is not None):
            verdict = classify_item(item)
            if verdict == "pass":
                score = weight if weight is not None else default
            elif verdict == "fail":
                score = Decimal(0)
            elif verdict == "na":
                score = default
        if score is not None:
            total = (total if total is not None else Decimal(0)) + score
    return total
