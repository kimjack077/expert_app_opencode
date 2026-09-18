"""2026-09-18 全功能实测修复的无数据库单元测试。

覆盖：
- BUG-09：会议时间必须收敛进项目审核排期窗口（business_time.meeting_time_for_schedule）
- BUG-14：不符合项条款号展示层清洗（statistics._normalize_clause_no）
- BUG-11：数值/打分项的 pass 必须由阈值裁决（tasks._normalize_numeric_verdict）
- BUG-02：项目报告 PDF 使用注册的中文字体（report_generator._ensure_cjk_font）
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# BUG-09 会议时间排期收敛
# ---------------------------------------------------------------------------

class TestMeetingTimeForSchedule:
    def _project(self, start="2026-09-20", end="2026-09-22"):
        return SimpleNamespace(
            scheduled_start=datetime.fromisoformat(start) if start else None,
            scheduled_end=datetime.fromisoformat(end) if end else None,
            actual_start=None,
            actual_end=None,
        )

    def test_in_window_proposed_time_kept(self):
        from app.utils.business_time import meeting_time_for_schedule

        kept, adjusted = meeting_time_for_schedule(
            self._project(), "opening", datetime(2026, 9, 21, 14, 0)
        )
        assert adjusted is False
        assert kept.day == 21 and kept.hour == 14

    def test_out_of_window_opening_clamped_to_first_day_morning(self):
        from app.utils.business_time import meeting_time_for_schedule

        # LLM 给出提前一年的时间，必须拉回排期首日 08:30
        kept, adjusted = meeting_time_for_schedule(
            self._project(), "opening", datetime(2025, 9, 21, 14, 0)
        )
        assert adjusted is True
        assert (kept.year, kept.month, kept.day, kept.hour, kept.minute) == (2026, 9, 20, 8, 30)

    def test_out_of_window_closing_clamped_to_last_day_afternoon(self):
        from app.utils.business_time import meeting_time_for_schedule

        kept, adjusted = meeting_time_for_schedule(
            self._project(), "closing", datetime(2030, 1, 1, 9, 0)
        )
        assert adjusted is True
        assert (kept.year, kept.month, kept.day, kept.hour, kept.minute) == (2026, 9, 22, 16, 0)

    def test_default_uses_window_start_when_no_proposal(self):
        from app.utils.business_time import meeting_time_for_schedule

        kept, adjusted = meeting_time_for_schedule(self._project(), "opening", None)
        assert adjusted is True
        assert (kept.month, kept.day, kept.hour, kept.minute) == (9, 20, 8, 30)

    def test_no_schedule_trusts_explicit_proposal(self):
        # 项目完全没有排期时，显式给出的历史时间应保留（无法判定越界，不能强行改成今天）
        from app.utils.business_time import meeting_time_for_schedule

        project = self._project(start=None, end=None)
        proposed = datetime(2026, 8, 21, 8, 30)
        kept, adjusted = meeting_time_for_schedule(project, "opening", proposed)
        assert adjusted is False
        assert (kept.year, kept.month, kept.day) == (2026, 8, 21)


# ---------------------------------------------------------------------------
# BUG-14 条款号清洗
# ---------------------------------------------------------------------------

class TestNormalizeClauseNo:
    def test_dirty_chinese_rejected(self):
        from app.routers.statistics import _normalize_clause_no

        assert _normalize_clause_no("把控1") is None
        assert _normalize_clause_no("") is None
        assert _normalize_clause_no("   ") is None
        assert _normalize_clause_no(None) is None

    def test_separator_normalized(self):
        from app.routers.statistics import _normalize_clause_no

        assert _normalize_clause_no("2·2") == "2.2"
        assert _normalize_clause_no("8．5．2") == "8.5.2"

    def test_standard_clause_kept(self):
        from app.routers.statistics import _normalize_clause_no

        assert _normalize_clause_no("10.88") == "10.88"
        assert _normalize_clause_no("8.5.2") == "8.5.2"


# ---------------------------------------------------------------------------
# BUG-11 数值/打分项服务端裁决
# ---------------------------------------------------------------------------

class TestNormalizeNumericVerdict:
    def _run(self, *, check_type, result, result_value, min_v=None, max_v=None, pass_score=None):
        from app.routers.tasks import _normalize_numeric_verdict

        item = SimpleNamespace(
            check_type=check_type,
            result_type=None,
            min_value=min_v,
            max_value=max_v,
            pass_score=pass_score,
        )
        db = AsyncMock()
        db.get = AsyncMock(return_value=item)
        return asyncio.run(
            _normalize_numeric_verdict(db, "00000000-0000-0000-0000-000000000001", result, result_value)
        )

    def test_numeric_in_range_is_pass(self):
        assert self._run(check_type="numeric", result="pass", result_value="50", min_v=0, max_v=100) == "pass"

    def test_numeric_out_of_range_becomes_fail(self):
        assert self._run(check_type="numeric", result="pass", result_value="150", min_v=0, max_v=100) == "fail"

    def test_numeric_without_threshold_pass_stripped(self):
        # 未配置阈值时，客户端默认的 pass 必须被剥掉（计入「其他项」，不虚增合规率）
        assert self._run(check_type="numeric", result="pass", result_value="42") is None

    def test_score_below_pass_line_becomes_fail(self):
        assert self._run(check_type="score", result="pass", result_value="59", pass_score=60) == "fail"

    def test_explicit_fail_is_respected(self):
        assert self._run(check_type="numeric", result="fail", result_value="150", min_v=0, max_v=100) == "fail"

    def test_radio_item_untouched(self):
        assert self._run(check_type="radio", result="pass", result_value=None) == "pass"


# ---------------------------------------------------------------------------
# BUG-02 项目报告 PDF 中文字体
# ---------------------------------------------------------------------------

class TestProjectReportCjkFont:
    def test_cjk_font_registered(self):
        from app.services.report_generator import _ensure_cjk_font

        name = _ensure_cjk_font()
        # 仓库自带 NotoSansSC，任何环境下都不应回退到 Helvetica
        assert name != "Helvetica"
