"""会议记录唯一性的契约门禁。

业务规则：**首次会议与末次会议在同一审核项目内只能有一条**——首次会议不能开两遍。

背景：这条校验原本只写在 REST 端点 ``audit_projects.create_meeting`` 里，
智审 Agent 的写入路径 ``agent_actions._action_create_meeting_record`` 没有这道关卡，
于是通过 Agent「确认录入」可以在同一项目下写入第二条「首次会议」。
两处必须同口径，统一走 ``app.utils.meeting_guard``。
"""

from pathlib import Path

import pytest

from app.utils.meeting_guard import (
    MEETING_TYPE_LABELS,
    UNIQUE_MEETING_TYPES,
    duplicate_meeting_message,
)

pytestmark = pytest.mark.contract

BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND_ROOT / "app"

#: 必须调用唯一性校验的两个写入路径
WRITE_PATHS = (
    "routers/audit_projects.py",
    "services/agent_actions.py",
)


def test_要求唯一的会议类型只有首末次():
    assert set(UNIQUE_MEETING_TYPES) == {"opening", "closing"}


def test_重复提示含中文会议名且不含英文枚举():
    for meeting_type in UNIQUE_MEETING_TYPES:
        message = duplicate_meeting_message(meeting_type)
        assert MEETING_TYPE_LABELS[meeting_type] in message
        assert "opening" not in message
        assert "closing" not in message


def test_两个写入路径都调用了统一校验():
    for rel in WRITE_PATHS:
        text = (APP_DIR / rel).read_text(encoding="utf-8", errors="ignore")
        assert "find_duplicate_meeting(" in text, (
            f"{rel} 未调用 find_duplicate_meeting，会议唯一性校验缺失"
        )
        assert "duplicate_meeting_message(" in text, (
            f"{rel} 未使用统一的重复提示文案"
        )


def test_不存在自建的会议重复校验():
    """不得再出现「就地 select 同类型会议」式的自建校验（口径会分叉）。

    判定特征：``select(CommunicationMeeting.id)`` —— 只取主键即为「查是否存在」，
    列表接口取的是整实体（``select(CommunicationMeeting)``），不在此列。
    """
    for rel in WRITE_PATHS:
        text = (APP_DIR / rel).read_text(encoding="utf-8", errors="ignore")
        assert "select(CommunicationMeeting.id)" not in text, (
            f"{rel} 出现自建的会议存在性查询，请改用 app.utils.meeting_guard"
        )
