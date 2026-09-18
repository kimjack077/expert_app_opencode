"""单元层测试：业务时区与自然日边界。

对应缺陷：「东八区早上 8 点前进入检查页，会重复创建当天草稿」。

成因是 ``POST /api/records`` 用 **UTC 的朴素 datetime** 去和 timestamptz 列比较，
窗口实际落在北京时间 08:00–次日 08:00，早 7 点建的草稿在 9 点时落在窗口外，
于是又建一条，检查员看到两份待填记录。

纯函数，无需数据库::

    .venv\\Scripts\\python.exe -m pytest tests/test_business_time.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.utils.business_time import (
    BUSINESS_TZ,
    business_day_bounds,
    business_now,
)

pytestmark = pytest.mark.unit


def test_business_tz_is_utc_plus_8():
    """业务时区为中国标准时间 UTC+8（无夏令时）。"""
    assert BUSINESS_TZ.utcoffset(None) == timedelta(hours=8)


def test_bounds_are_timezone_aware():
    """边界必须带时区 —— 朴素 datetime 与 timestamptz 比较是本次缺陷的根因。"""
    start, end = business_day_bounds()
    assert start.tzinfo is not None, "起始边界缺少时区信息"
    assert end.tzinfo is not None, "结束边界缺少时区信息"


def test_bounds_span_exactly_one_day():
    start, end = business_day_bounds()
    assert end - start == timedelta(days=1)


def test_bounds_align_to_business_midnight():
    start, end = business_day_bounds()
    assert (start.hour, start.minute, start.second, start.microsecond) == (0, 0, 0, 0)
    assert (end.hour, end.minute, end.second, end.microsecond) == (0, 0, 0, 0)


@pytest.mark.parametrize(
    ("label", "beijing_hour"),
    [("凌晨", 1), ("早七点", 7), ("上午", 10), ("午间", 12), ("晚间", 22), ("深夜", 23)],
)
def test_early_morning_and_late_night_belong_to_same_business_day(label, beijing_hour):
    """**核心回归**：北京时间的任意时刻都应落在「北京今天」这个窗口内。

    旧实现按 UTC 划分，北京时间 00:00–08:00 会落到前一天的窗口里。
    """
    moment = datetime(2026, 9, 17, beijing_hour, 0, tzinfo=BUSINESS_TZ)
    start, end = business_day_bounds(moment)

    assert start <= moment < end, (
        f"{label}（北京 {beijing_hour}:00）不在当天窗口 [{start}, {end}) 内"
    )
    assert start.date() == moment.date(), (
        f"{label} 被划到了 {start.date()}，而它属于 {moment.date()}"
    )


def test_regression_seven_am_draft_is_found_at_nine_am():
    """复现并锁死原缺陷：早 7 点与早 9 点必须落在**同一个**业务日窗口。"""
    seven_am = datetime(2026, 9, 17, 7, 0, tzinfo=BUSINESS_TZ)
    nine_am = datetime(2026, 9, 17, 9, 0, tzinfo=BUSINESS_TZ)

    start_7, end_7 = business_day_bounds(seven_am)
    start_9, end_9 = business_day_bounds(nine_am)

    assert (start_7, end_7) == (start_9, end_9), (
        "早 7 点与早 9 点被划入不同的业务日窗口 —— "
        "早上建的草稿在 9 点时会找不到，从而重复创建。"
    )

    # 旧实现的窗口（UTC 朴素 00:00–24:00）：7 点确实落在窗口外
    legacy_start = datetime(2026, 9, 17, 0, 0, tzinfo=timezone.utc)
    legacy_end = legacy_start + timedelta(days=1)
    assert not (legacy_start <= seven_am < legacy_end), (
        "本用例的前提失效：旧实现窗口本应漏掉北京时间早 7 点"
    )


def test_naive_input_is_interpreted_as_business_time():
    """传入朴素 datetime 时按业务时区解释，不得静默当成 UTC。"""
    naive = datetime(2026, 9, 17, 7, 0)
    start, end = business_day_bounds(naive)
    assert start.date() == naive.date()
    assert start.tzinfo is not None


def test_utc_input_is_converted_not_relabelled():
    """传入 UTC 时刻时按**换算**处理，而不是换掉时区标签。

    UTC 2026-09-16 23:00 == 北京 2026-09-17 07:00 → 应属于 9 月 17 日的窗口。
    """
    utc_late = datetime(2026, 9, 16, 23, 0, tzinfo=timezone.utc)
    start, _ = business_day_bounds(utc_late)
    assert start.date() == datetime(2026, 9, 17).date(), (
        "UTC 时刻未被换算到业务时区，边界会整体偏移 8 小时"
    )


def test_business_now_is_aware_and_close_to_utc_now():
    now = business_now()
    assert now.tzinfo is not None
    delta = abs((now - datetime.now(timezone.utc)).total_seconds())
    assert delta < 5, f"business_now 与 UTC 当前时刻相差 {delta:.1f} 秒"
