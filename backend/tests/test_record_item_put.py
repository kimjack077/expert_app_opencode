"""PUT 兼容入口的 ID 绑定、权限与提交态回归，不连接数据库。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.models.record import InspectionRecord
from app.routers import records
from app.schemas.record import InspectionRecordItemCreate


pytestmark = pytest.mark.unit


def _db(existing=None, record=None, template=None):
    db = SimpleNamespace(
        execute=AsyncMock(return_value=Mock(scalar_one_or_none=Mock(return_value=existing)))
    )
    db.get = AsyncMock(side_effect=lambda model, key: record if model is InspectionRecord else template)
    return db


def _call(record_id, item_id, payload, db, user=None):
    return asyncio.run(records.update_record_item_by_id(
        record_id, item_id, InspectionRecordItemCreate(**payload), db, user
    ))


def test_existing_record_item_uses_path_id(monkeypatch):
    record_id, item_id, template_item_id = uuid4(), uuid4(), uuid4()
    db = _db(existing=SimpleNamespace(template_item_id=template_item_id))
    save = AsyncMock(return_value={"saved": True})
    monkeypatch.setattr(records, "create_or_update_record_item", save)

    assert _call(record_id, item_id, {"radio_value": "pass"}, db) == {"saved": True}
    payload = save.call_args.kwargs["item_data"]
    assert payload.id == item_id
    assert save.call_args.kwargs["record_id"] == str(record_id)


def test_template_item_path_is_preserved_when_record_item_does_not_exist(monkeypatch):
    record_id, item_id = uuid4(), uuid4()
    save = AsyncMock(return_value={"saved": True})
    monkeypatch.setattr(records, "create_or_update_record_item", save)

    _call(record_id, item_id, {"template_item_id": item_id, "radio_value": "pass"}, _db())
    payload = save.call_args.kwargs["item_data"]
    assert payload.id is None
    assert payload.template_item_id == item_id


@pytest.mark.parametrize("existing", [False, True])
def test_body_cannot_redirect_path_to_another_record_item(monkeypatch, existing):
    record_id, item_id = uuid4(), uuid4()
    save = AsyncMock()
    monkeypatch.setattr(records, "create_or_update_record_item", save)
    db = _db(SimpleNamespace(template_item_id=uuid4()) if existing else None)

    with pytest.raises(HTTPException) as error:
        _call(record_id, item_id, {"id": uuid4(), "radio_value": "pass"}, db)
    assert error.value.status_code == 422
    save.assert_not_awaited()


@pytest.mark.parametrize("existing", [False, True])
def test_body_cannot_redirect_path_to_another_template_item(monkeypatch, existing):
    record_id, item_id = uuid4(), uuid4()
    save = AsyncMock()
    monkeypatch.setattr(records, "create_or_update_record_item", save)
    db = _db(SimpleNamespace(template_item_id=uuid4()) if existing else None)

    with pytest.raises(HTTPException) as error:
        _call(record_id, item_id, {"template_item_id": uuid4(), "radio_value": "pass"}, db)
    assert error.value.status_code == 422
    save.assert_not_awaited()


def test_missing_explicit_record_item_is_not_reinterpreted_as_template(monkeypatch):
    record_id, item_id = uuid4(), uuid4()
    save = AsyncMock()
    monkeypatch.setattr(records, "create_or_update_record_item", save)

    with pytest.raises(HTTPException) as error:
        _call(record_id, item_id, {"id": item_id, "radio_value": "pass"}, _db())
    assert error.value.status_code == 404
    save.assert_not_awaited()


@pytest.mark.parametrize("role,status,owned,expected", [
    ("expert", "submitted", True, 409),
    ("admin", "submitted", True, 409),
    ("auditor", "draft", True, 403),
    ("expert", "draft", False, 403),
])
def test_put_reuses_write_permission_and_submitted_record_guard(role, status, owned, expected):
    user = SimpleNamespace(id=uuid4(), role=role)
    record = SimpleNamespace(
        is_deleted=False, status=status, inspector_id=user.id if owned else uuid4()
    )

    with pytest.raises(HTTPException) as error:
        _call(uuid4(), uuid4(), {"radio_value": "pass"}, _db(record=record), user)
    assert error.value.status_code == expected


def test_template_from_another_record_is_rejected():
    user = SimpleNamespace(id=uuid4(), role="expert")
    record = SimpleNamespace(
        is_deleted=False, status="draft", inspector_id=user.id, template_id=uuid4()
    )
    template = SimpleNamespace(is_deleted=False, template_id=uuid4())

    with pytest.raises(HTTPException) as error:
        _call(uuid4(), uuid4(), {"radio_value": "pass"}, _db(record=record, template=template), user)
    assert error.value.status_code == 422


@pytest.mark.parametrize("record_id,item_id", [
    ("invalid", str(uuid4())), (str(uuid4()), "invalid"),
])
def test_invalid_uuid_paths_return_validation_errors(record_id, item_id):
    app = FastAPI()
    app.include_router(records.router, prefix="/records")
    db = _db()
    app.dependency_overrides[records.get_db] = lambda: db
    app.dependency_overrides[records.get_current_user] = lambda: SimpleNamespace(id=uuid4(), role="expert")
    with TestClient(app) as client:
        response = client.put(f"/records/{record_id}/items/{item_id}", json={"radio_value": "pass"})
    assert response.status_code == 422
    db.execute.assert_not_awaited()
