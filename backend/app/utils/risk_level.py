"""企业风险等级口径的**唯一来源**。

业务语义（与 web-admin 企业档案列表的标签一致）：

===========  ==============  ==============
等级          含义             风险桶
===========  ==============  ==============
``A``         低风险           ``low``
``B``         一般（中风险）    ``medium``
``C``         较高风险         ``high``
``D``         高风险           ``high``
===========  ==============  ==============

历史缺陷：``analytics.py`` 与 ``enterprises.py`` 各自实现过一份映射，且都把
``A`` 归为 ``high``、把 ``C``/``D`` 归为 ``low``，与前端语义**完全倒挂**——
工作台「风险预警企业」因此把低风险企业算成高风险，而真正的高风险企业反而
不会触发预警。本模块收敛该口径，两处调用点统一引用，不得再各写一份。
"""

from typing import Optional

#: 等级 → 风险桶
LEVEL_TO_BUCKET: dict[str, str] = {
    "A": "low",
    "B": "medium",
    "C": "high",
    "D": "high",
}

#: 风险桶 → 该桶包含的等级字面量（供 SQL ``IN`` 使用；``None`` 表示未评级）
BUCKET_LEVELS: dict[str, tuple] = {
    "high": ("C", "D"),
    "medium": ("B",),
    "low": ("A", None),
}

#: 等级 → 中文标签（与前端 Enterprises 列表逐字一致）
LEVEL_LABELS: dict[str, str] = {
    "A": "A级（低风险）",
    "B": "B级（一般）",
    "C": "C级（较高风险）",
    "D": "D级（高风险）",
}

RISK_BUCKETS = ("high", "medium", "low")


def normalize_risk_bucket(level: Optional[str]) -> str:
    """把企业风险等级（A/B/C/D）归一为 ``high`` / ``medium`` / ``low``。

    未评级（``None`` / 空串）按 ``low`` 处理，与历史行为保持一致；
    已是 ``high`` / ``medium`` / ``low`` 的值原样返回（幂等）。
    """
    if level is None:
        return "low"
    key = str(level).strip()
    if not key:
        return "low"
    if key in LEVEL_TO_BUCKET:
        return LEVEL_TO_BUCKET[key]
    lowered = key.lower()
    if lowered in RISK_BUCKETS:
        return lowered
    # 未知取值不放大风险，也不静默归为高风险
    return "low"


def levels_in_bucket(bucket: str) -> tuple:
    """返回某风险桶对应的等级字面量元组，供 SQL ``IN`` 使用。"""
    return BUCKET_LEVELS.get(bucket, ())


def risk_level_label(level: Optional[str]) -> str:
    """返回等级的中文标签；未知取值原样返回，便于排查脏数据。"""
    if level is None:
        return "未评级"
    key = str(level).strip()
    return LEVEL_LABELS.get(key, key or "未评级")
