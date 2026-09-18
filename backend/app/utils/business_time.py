"""业务时区与「自然日」边界 —— 消除日期窗口的时区歧义。

═══════════════════════════════════════════════════════════════════════════
 为什么需要这个模块
═══════════════════════════════════════════════════════════════════════════
``POST /api/records`` 会「查找当天同企业同模板的草稿，找到就复用」。
原实现这样算当天边界::

    now_utc = datetime.now(timezone.utc)
    today_start = datetime(now_utc.year, now_utc.month, now_utc.day)   # 朴素 datetime

``created_at`` 是 ``DateTime(timezone=True)``（timestamptz），
把**朴素 datetime** 与 timestamptz 比较时，数据库按自身会话时区解释这个参数，
行为不确定。若被当作 UTC 解释，窗口就变成 UTC 的 00:00–24:00，
即北京时间 08:00–次日 08:00。后果：

    早上 7 点建的草稿，9 点再进来时落在窗口之外 → **又建一条重复草稿**，
    检查员看到两份待填记录，不知道填哪个；统计也会重复计数。

修法是让边界**显式带时区**，且按业务时区（中国标准时间）划分自然日 ——
"今天"对使用者而言是北京的今天，不是 UTC 的今天。

═══════════════════════════════════════════════════════════════════════════
 为什么用固定偏移而不是 zoneinfo
═══════════════════════════════════════════════════════════════════════════
中国自 1991 年起不再实行夏令时，全年恒为 UTC+8。使用固定偏移
既准确又免去 ``tzdata`` 依赖（Windows 上的 Python 默认不带 IANA 时区库，
``ZoneInfo("Asia/Shanghai")`` 会抛 ``ZoneInfoNotFoundError``）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

# 业务时区：中国标准时间 UTC+8（无夏令时）
BUSINESS_TZ = timezone(timedelta(hours=8), name="CST")


def business_now() -> datetime:
    """当前时刻，带业务时区。"""
    return datetime.now(BUSINESS_TZ)


def business_day_bounds(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """返回业务时区下「今天」的 ``[起, 止)`` 边界，**均为带时区 datetime**。

    ``now`` 可注入以便测试；传入朴素 datetime 时按业务时区解释。
    """
    if now is None:
        moment = business_now()
    elif now.tzinfo is None:
        moment = now.replace(tzinfo=BUSINESS_TZ)
    else:
        moment = now.astimezone(BUSINESS_TZ)

    start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)
