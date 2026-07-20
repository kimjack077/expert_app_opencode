import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.routers.tasks import complete_task, update_task
from app.schemas.task import InspectionTaskUpdate
from app.services.formal_audit_sync_service import (
    can_access_linked_task,
    legacy_result_to_evaluation,
    sync_task_to_formal_record,
)


def make_task(user_id, status="in_progress"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        is_deleted=False,
        task_no="TASK-ROUTE-TEST",
        title="route test",
        template_id=None,
        assigned_to=user_id,
        assigned_by=user_id,
        target_name=None,
        target_address=None,
        target_contact=None,
        target_phone=None,
        scheduled_at=None,
        started_at=now,
        completed_at=None,
        status=status,
        remarks=None,
        created_at=now,
        updated_at=now,
    )


def test_all_plan_assignees_can_access_shared_legacy_task():
    user_id = uuid4()
    task = SimpleNamespace(id=uuid4(), assigned_to=uuid4())
    user = SimpleNamespace(id=user_id, role="expert")
    plan = SimpleNamespace(assigned_member_ids=[uuid4(), user_id])

    with patch(
        "app.services.formal_audit_sync_service.get_linked_plan_item",
        AsyncMock(return_value=plan),
    ):
        allowed = asyncio.run(can_access_linked_task(SimpleNamespace(), task, user))

    assert allowed is True


def test_formal_sync_rejects_task_without_completed_rows():
    rows_result = Mock()
    rows_result.scalars.return_value.unique.return_value.all.return_value = []
    db = SimpleNamespace(execute=AsyncMock(return_value=rows_result))
    task = SimpleNamespace(id=uuid4())
    plan = SimpleNamespace()

    with pytest.raises(ValueError, match="至少一项"):
        asyncio.run(sync_task_to_formal_record(db, task, plan, uuid4()))


def test_post_complete_route_runs_formal_sync_before_commit():
    user = SimpleNamespace(id=uuid4(), role="admin", username="admin")
    task = make_task(user.id)
    plan = SimpleNamespace(id=uuid4())
    db = SimpleNamespace(
        get=AsyncMock(return_value=task),
        commit=AsyncMock(),
    )

    with (
        patch("app.routers.tasks.get_linked_plan_item", AsyncMock(return_value=plan)),
        patch("app.routers.tasks.sync_task_to_formal_record", AsyncMock()) as sync,
        patch("app.routers.tasks.AuditService.log_action", AsyncMock()),
    ):
        result = asyncio.run(
            complete_task(str(task.id), db=db, current_user=user)
        )

    sync.assert_awaited_once_with(db, task, plan, user.id)
    db.commit.assert_awaited_once()
    assert result.code == 200


def test_put_completed_route_cannot_bypass_formal_sync():
    user = SimpleNamespace(id=uuid4(), role="expert", username="expert")
    task = make_task(user.id)
    plan = SimpleNamespace(id=uuid4(), project_id=uuid4(), status="in_progress")
    project = SimpleNamespace(status="planning")
    plan_result = Mock()
    plan_result.scalar_one_or_none.return_value = plan
    db = SimpleNamespace(
        get=AsyncMock(side_effect=[task, project]),
        execute=AsyncMock(return_value=plan_result),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    with (
        patch("app.routers.tasks.can_access_linked_task", AsyncMock(return_value=True)),
        patch("app.routers.tasks.get_linked_plan_item", AsyncMock(return_value=plan)),
        patch("app.routers.tasks.sync_task_to_formal_record", AsyncMock()) as sync,
    ):
        result = asyncio.run(
            update_task(
                str(task.id),
                InspectionTaskUpdate(status="completed"),
                db=db,
                current_user=user,
            )
        )

    sync.assert_awaited_once_with(db, task, plan, user.id)
    db.commit.assert_awaited_once()
    assert task.status == "completed"
    assert result.code == 200


@pytest.mark.parametrize(
    ("legacy_result", "expected"),
    [
        ("pass", "1"),
        ("compliant", "1"),
        ("qualified", "1"),
        ("1", "1"),
        ("fail", "3"),
        ("non_compliant", "3"),
        ("unqualified", "3"),
        ("pending_rectification", "3"),
        ("3", "3"),
        ("not_applicable", None),
        ("na", None),
        ("不适用", None),
        ("partial_pass", "2"),
        (None, "2"),
    ],
)
def test_legacy_result_mapping_covers_all_client_values(legacy_result, expected):
    assert legacy_result_to_evaluation(legacy_result) == expected
