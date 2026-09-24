"""检查记录提交态与管理员更正入口的单元回归测试。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers.records import submit_record, update_record
from app.schemas.record import InspectionRecordItemCorrection, InspectionRecordUpdate


pytestmark = pytest.mark.unit


class _GetOnlyDb:
    def __init__(self, record):
        self.record = record

    async def get(self, _model, _object_id):
        return self.record


def _user(role: str = "expert"):
    return SimpleNamespace(id=uuid.uuid4(), username=f"{role}_user", role=role)


def _record(*, status: str, inspector_id=None, inspection_date=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        is_deleted=False,
        status=status,
        inspector_id=inspector_id,
        inspection_date=inspection_date,
    )


def test_submitted_record_cannot_be_reopened_through_update_endpoint():
    owner = _user()
    submitted_at = datetime(2026, 9, 20, 8, 30, tzinfo=timezone.utc)
    record = _record(
        status="submitted",
        inspector_id=owner.id,
        inspection_date=submitted_at,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            update_record(
                str(record.id),
                InspectionRecordUpdate(status="in_progress"),
                _GetOnlyDb(record),
                owner,
            )
        )

    assert exc_info.value.status_code == 409
    assert record.status == "submitted"
    assert record.inspection_date == submitted_at


def test_draft_status_cannot_be_changed_through_general_update_endpoint():
    owner = _user()
    record = _record(status="draft", inspector_id=owner.id)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            update_record(
                str(record.id),
                InspectionRecordUpdate(status="submitted"),
                _GetOnlyDb(record),
                owner,
            )
        )

    assert exc_info.value.status_code == 422
    assert record.status == "draft"


def test_admin_repeated_submit_does_not_overwrite_first_inspection_date():
    admin = _user("admin")
    submitted_at = datetime(2026, 9, 19, 3, 15, tzinfo=timezone.utc)
    record = _record(
        status="submitted",
        inspector_id=uuid.uuid4(),
        inspection_date=submitted_at,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(submit_record(str(record.id), _GetOnlyDb(record), admin))

    assert exc_info.value.status_code == 409
    assert record.inspection_date == submitted_at


def test_submitted_item_correction_requires_audit_reason():
    with pytest.raises(ValueError):
        InspectionRecordItemCorrection(reason="", radio_value="pass")
