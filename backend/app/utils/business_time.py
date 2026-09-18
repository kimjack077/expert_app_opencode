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

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional, Tuple

# 业务时区：中国标准时间 UTC+8（无夏令时）
BUSINESS_TZ = timezone(timedelta(hours=8), name="CST")

# 首/末次会议的默认钟点（现场审核惯例：首次早 8:30，末次下午 16:00）
OPENING_CLOCK = time(8, 30)
CLOSING_CLOCK = time(16, 0)
INTERIM_CLOCK = time(10, 0)


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


def _as_aware(value: Any) -> Optional[datetime]:
    """把 date/datetime 统一成业务时区的 aware datetime；None 原样返回。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=BUSINESS_TZ)
        return value.astimezone(BUSINESS_TZ)
    if isinstance(value, date):
        return datetime.combine(value, time(0, 0), BUSINESS_TZ)
    return None


def project_schedule_window(project: Any) -> Tuple[Optional[datetime], Optional[datetime]]:
    """取项目审核排期窗口（优先实际起止，其次计划起止），均为业务时区 aware 值。"""
    start = _as_aware(getattr(project, "actual_start", None)) or _as_aware(
        getattr(project, "scheduled_start", None)
    )
    end = _as_aware(getattr(project, "actual_end", None)) or _as_aware(
        getattr(project, "scheduled_end", None)
    )
    if start and end and end < start:
        start, end = end, start
    return start, end


def meeting_time_for_schedule(
    project: Any,
    meeting_type: str = "opening",
    proposed: Optional[datetime] = None,
) -> Tuple[datetime, bool]:
    """把会议时间收敛进项目审核排期窗口。

    BUG-09：Agent 生成的会议时间可能严重偏离排期（实测曾提前一整年），
    用户在确认卡片上不易察觉。规则：
    - 项目有排期且提议时间落在窗口内 → 原样采用；
    - 落在窗口外（或未提供）→ 首次会议取窗口首日 08:30，末次取末日 16:00，
      其余沟通取首日 10:00；起止同日时末次不早于首次钟点；
    - 项目完全没有排期 → 首次/沟通取今天对应钟点，末次取今天 16:00。

    返回 ``(aware_datetime, adjusted)``，``adjusted=True`` 表示发生过纠偏，
    调用方可据此在确认卡片上提示用户核对。
    """
    mtype = str(meeting_type or "opening").lower()
    window_start, window_end = project_schedule_window(project)

    if proposed is not None:
        candidate = _as_aware(proposed)
        if candidate is None:
            raise ValueError("proposed 必须是 datetime/date")
        in_window = (
            window_start is None
            or (window_start <= candidate and (window_end is None or candidate <= window_end))
        )
        if in_window:
            return candidate, False

    if window_start is None:
        base = business_now()
        if mtype == "closing":
            return base.replace(hour=16, minute=0, second=0, microsecond=0), True
        clock = OPENING_CLOCK if mtype == "opening" else INTERIM_CLOCK
        return base.replace(hour=clock.hour, minute=clock.minute, second=0, microsecond=0), True

    if mtype == "closing" and window_end is not None:
        chosen = window_end.replace(hour=16, minute=0, second=0, microsecond=0)
        if chosen < window_start:
            chosen = window_start
    else:
        clock = OPENING_CLOCK if mtype == "opening" else INTERIM_CLOCK
        chosen = window_start.replace(hour=clock.hour, minute=clock.minute, second=0, microsecond=0)
        if window_end is not None and chosen > window_end:
            chosen = window_end
    return chosen, True

