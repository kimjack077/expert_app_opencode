"""媒体上传关联回归：仅 mock 会话、文件写入及审计，不访问数据库。"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import and_

from app.routers import media
from app.services import formal_audit_sync_service

pytestmark = pytest.mark.unit


@pytest.fixture
def upload_env(monkeypatch):
    objects = {}

    async def refresh(obj):
        obj.id = uuid4()
        obj.uploaded_at = datetime.now(timezone.utc)

    db = SimpleNamespace(
        get=AsyncMock(side_effect=lambda model, key: objects.get((model, str(key)))),
        execute=AsyncMock(side_effect=AssertionError("Unexpected SQL")),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(side_effect=refresh),
    )
    save = AsyncMock(return_value=("mock.jpg", "/uploads/inspections/mock.jpg", 12))
    access = AsyncMock(wraps=media.can_access_linked_task)
    monkeypatch.setattr(media, "save_upload_file", save)
    monkeypatch.setattr(media, "can_access_linked_task", access)
    monkeypatch.setattr(media.AuditService, "log_action", AsyncMock())
    monkeypatch.setattr(media, "ensure_project_access", AsyncMock())
    return SimpleNamespace(
        objects=objects,
        db=db,
        save=save,
        access=access,
        file=SimpleNamespace(filename="photo.jpg", content_type="image/jpeg"),
        user=SimpleNamespace(id=uuid4(), username="expert", role="expert"),
    )


def _link(env, source):
    task = SimpleNamespace(id=uuid4(), assigned_to=env.user.id, is_deleted=False, status="in_progress")
    item = SimpleNamespace(id=uuid4(), task_id=task.id, template_item_id=uuid4())
    env.objects[(media.InspectionTask, str(task.id))] = task
    if source == "task_only":
        record_id = None
    elif source == "direct":
        record_id = str(item.id)
        env.objects[(media.TaskItemRecord, record_id)] = item
    else:
        plan = SimpleNamespace(id=uuid4(), inspection_task_id=task.id)
        area = SimpleNamespace(
            id=uuid4(), plan_item_id=plan.id, project_id=uuid4(), recorded_by=env.user.id,
            co_recorders=[], status="draft",
        )
        record_id = str(uuid4())
        env.objects[(media.InspectionRecordItem, record_id)] = SimpleNamespace(
            audit_area_record_id=area.id, record_id=None, template_item_id=item.template_item_id,
        )
        env.objects[(media.AuditAreaRecord, str(area.id))] = area
        env.objects[(media.AuditPlanItem, str(plan.id))] = plan
        result = Mock()
        result.scalar_one_or_none.return_value = item
        env.db.execute.side_effect = None
        env.db.execute.return_value = result
    return task, item, record_id


def _upload(env, record_id=None, task_id=None):
    return asyncio.run(media.upload_file(
        file=env.file, task_id=task_id, record_id=record_id,
        db=env.db, current_user=env.user,
    ))


@pytest.mark.parametrize("source", ["direct", "formal"])
@pytest.mark.parametrize("supply_task", [False, True])
def test_record_upload_persists_real_task_and_item(upload_env, source, supply_task):
    env = upload_env
    task, item, record_id = _link(env, source)
    response = _upload(env, record_id, str(task.id) if supply_task else None)

    stored = env.db.add.call_args.args[0]
    assert stored.task_id == str(task.id)
    assert stored.record_id == str(item.id)
    assert response["data"]["task_id"] == task.id
    assert response["data"]["record_id"] == item.id
    env.access.assert_awaited_once_with(env.db, task, env.user)
    env.save.assert_awaited_once_with(env.file, "inspections")
    env.db.commit.assert_awaited_once()
    if source == "formal":
        env.db.execute.assert_awaited_once()
        query = env.db.execute.call_args.args[0]
        assert query.whereclause.compare(and_(
            media.TaskItemRecord.task_id == task.id,
            media.TaskItemRecord.template_item_id == item.template_item_id,
        ))


@pytest.mark.parametrize("source", ["direct", "formal"])
def test_mismatched_task_is_rejected_before_file_write(upload_env, source):
    env = upload_env
    _, _, record_id = _link(env, source)
    env.user.role = "admin"  # 管理员也不能写入相互矛盾的关联。

    with pytest.raises(HTTPException) as exc:
        _upload(env, record_id, str(uuid4()))

    assert exc.value.status_code == 400
    env.save.assert_not_awaited()
    env.db.add.assert_not_called()
    env.db.commit.assert_not_awaited()
    env.access.assert_not_awaited()
    env.db.execute.assert_not_awaited()


@pytest.mark.parametrize("source", ["direct", "formal", "task_only"])
@pytest.mark.parametrize("assigned", [False, True])
def test_final_task_uses_shared_assignment_permissions(upload_env, monkeypatch, source, assigned):
    env = upload_env
    task, _, record_id = _link(env, source)
    task.assigned_to = uuid4()
    plan = SimpleNamespace(assigned_member_ids=[env.user.id] if assigned else [uuid4()])
    get_plan = AsyncMock(return_value=plan)
    monkeypatch.setattr(formal_audit_sync_service, "get_linked_plan_item", get_plan)
    task_id = str(task.id) if source == "task_only" else None

    if assigned:
        response = _upload(env, record_id, task_id)
        assert response["data"]["task_id"] == task.id
        env.save.assert_awaited_once()
        env.db.commit.assert_awaited_once()
    else:
        with pytest.raises(HTTPException) as exc:
            _upload(env, record_id, task_id)
        assert exc.value.status_code == 403
        env.save.assert_not_awaited()
        env.db.add.assert_not_called()
        env.db.commit.assert_not_awaited()
    env.access.assert_awaited_once_with(env.db, task, env.user)
    get_plan.assert_awaited_once_with(env.db, task.id)


@pytest.mark.parametrize("source", ["direct", "formal", "task_only"])
@pytest.mark.parametrize("missing", [False, True])
def test_missing_or_deleted_final_task_cannot_receive_upload(upload_env, source, missing):
    env = upload_env
    task, _, record_id = _link(env, source)
    if missing:
        del env.objects[(media.InspectionTask, str(task.id))]
    else:
        task.is_deleted = True

    with pytest.raises(HTTPException) as exc:
        _upload(env, record_id, str(task.id) if source == "task_only" else None)

    assert exc.value.status_code == 404
    env.save.assert_not_awaited()
    env.db.commit.assert_not_awaited()
    env.access.assert_not_awaited()


@pytest.mark.parametrize("has_template", [False, True])
def test_independent_record_keeps_photos_url_flow_without_task(upload_env, has_template):
    env = upload_env
    record_id = str(uuid4())
    record = SimpleNamespace(
        record_id=uuid4(), audit_area_record_id=None,
        template_item_id=uuid4() if has_template else None,
        photos=["/uploads/inspections/existing.jpg"],
    )
    env.objects[(media.InspectionRecordItem, record_id)] = record
    env.objects[(media.InspectionRecord, str(record.record_id))] = SimpleNamespace(
        inspector_id=env.user.id, status="draft", is_deleted=False,
    )

    response = _upload(env, record_id)

    stored = env.db.add.call_args.args[0]
    assert stored.task_id is None
    assert stored.record_id is None
    assert response["data"]["file_path"] == "/uploads/inspections/mock.jpg"
    assert record.photos == ["/uploads/inspections/existing.jpg"]
    env.access.assert_not_awaited()
    env.db.execute.assert_not_awaited()
    env.db.commit.assert_awaited_once()


def test_formal_bridge_keeps_task_even_without_matching_task_item(upload_env):
    env = upload_env
    task, _, record_id = _link(env, "formal")
    env.db.execute.return_value.scalar_one_or_none.return_value = None

    response = _upload(env, record_id)

    assert response["data"]["task_id"] == task.id
    assert response["data"]["record_id"] is None
    env.access.assert_awaited_once_with(env.db, task, env.user)


def test_record_lookup_errors_are_not_silently_uploaded_unlinked(upload_env):
    env = upload_env
    env.db.get.side_effect = RuntimeError("lookup failed")

    with pytest.raises(RuntimeError, match="lookup failed"):
        _upload(env, str(uuid4()))

    env.save.assert_not_awaited()
    env.db.commit.assert_not_awaited()


@pytest.mark.parametrize(("case", "status"), [("other_owner", 403), ("submitted", 409), ("missing", 404)])
def test_independent_upload_enforces_parent_permissions(upload_env, case, status):
    env = upload_env
    item_id, record_id = str(uuid4()), uuid4()
    env.objects[(media.InspectionRecordItem, item_id)] = SimpleNamespace(
        record_id=record_id, audit_area_record_id=None, template_item_id=uuid4(),
    )
    if case != "missing":
        env.objects[(media.InspectionRecord, str(record_id))] = SimpleNamespace(
            inspector_id=uuid4() if case == "other_owner" else env.user.id,
            status="submitted" if case == "submitted" else "draft", is_deleted=False,
        )
    with pytest.raises(HTTPException) as exc:
        _upload(env, item_id)
    assert exc.value.status_code == status
    env.save.assert_not_awaited()
    env.db.commit.assert_not_awaited()


def test_unknown_record_id_never_becomes_unlinked_upload(upload_env):
    env = upload_env
    with pytest.raises(HTTPException) as exc:
        _upload(env, str(uuid4()))
    assert exc.value.status_code == 404
    env.save.assert_not_awaited()


def test_ended_task_rejects_upload_before_file_write(upload_env):
    env = upload_env
    task, _, record_id = _link(env, "direct")
    task.status = "completed"
    with pytest.raises(HTTPException) as exc:
        _upload(env, record_id)
    assert exc.value.status_code == 409
    env.save.assert_not_awaited()
