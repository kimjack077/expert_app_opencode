"""不依赖数据库的 2026-09-23 后端缺陷回归测试。"""

from __future__ import annotations

import asyncio
import inspect
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.models.template import TemplateItem
from app.main import request_validation_error_handler
from app.routers.industries import (
    create_industry,
    delete_industry,
    update_industry,
)
from app.routers.templates import (
    can_modify_template,
    copy_template,
    create_template,
    get_template,
    get_template_items,
)
from app.routers.users import create_user, update_user
from app.schemas.task import InspectionRecordCreate, InspectionRecordUpdate
from app.schemas.template import InspectionTemplateCreate
from app.schemas.user import UserCreate, UserUpdate
from app.services.report_service import report_service
from app.utils.security import get_current_admin_user


pytestmark = pytest.mark.unit


def test_report_flattens_unloaded_orm_children_without_io():
    """模板项是全量扁平 ORM 列表时，不应读取未加载的 children 关系。"""
    category_id = uuid.uuid4()
    leaf_id = uuid.uuid4()
    category = TemplateItem(
        id=category_id,
        title="分类",
        is_category=True,
        sort_order=0,
    )
    leaf = TemplateItem(
        id=leaf_id,
        parent_id=category_id,
        title="检查项",
        is_category=False,
        sort_order=1,
    )

    flattened = report_service._flatten_items([category, leaf])

    assert [item["id"] for item in flattened] == [str(leaf_id)]
    assert flattened[0]["category_name"] == "分类"


@pytest.mark.parametrize(
    "endpoint",
    [create_industry, update_industry, delete_industry],
)
def test_industry_writes_use_admin_dependency(endpoint):
    dependency = inspect.signature(endpoint).parameters["current_user"].default
    assert dependency.dependency is get_current_admin_user


class _ExistingResult:
    @staticmethod
    def scalar_one_or_none():
        return object()


class _DuplicateUsernameDb:
    def __init__(self, user=None):
        self.user = user

    async def execute(self, _query):
        return _ExistingResult()

    async def get(self, _model, _user_id):
        return self.user


def test_duplicate_username_create_returns_conflict():
    data = UserCreate(username="duplicate_user", password="secret123")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_user(data, _DuplicateUsernameDb(), object()))
    assert exc_info.value.status_code == 409


def test_duplicate_username_update_returns_conflict():
    user = SimpleNamespace(id=uuid.uuid4(), username="original_user", is_deleted=False)
    data = UserUpdate(username="duplicate_user")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(update_user(user.id, data, _DuplicateUsernameDb(user), object()))
    assert exc_info.value.status_code == 409


@pytest.mark.parametrize("schema", [InspectionRecordCreate, InspectionRecordUpdate])
def test_task_record_schema_rejects_unknown_result_fields(schema):
    payload = {"radio_value": "pass"}
    if schema is InspectionRecordCreate:
        payload["template_item_id"] = uuid.uuid4()
    with pytest.raises(ValidationError) as exc_info:
        schema.model_validate(payload)
    assert any(err["type"] == "extra_forbidden" for err in exc_info.value.errors())


class _GetOnlyDb:
    def __init__(self, value):
        self.value = value

    async def get(self, _model, _object_id):
        return self.value


@pytest.mark.parametrize("endpoint", [get_template, get_template_items])
def test_soft_deleted_template_read_returns_not_found(endpoint):
    template = SimpleNamespace(id=uuid.uuid4(), is_deleted=True)
    user = SimpleNamespace(id=uuid.uuid4(), role="admin")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(endpoint(str(template.id), _GetOnlyDb(template), user))
    assert exc_info.value.status_code == 404


def test_auditor_cannot_create_or_copy_templates():
    auditor = SimpleNamespace(id=uuid.uuid4(), role="auditor")
    template_data = InspectionTemplateCreate(name="只读角色不得创建")

    with pytest.raises(HTTPException) as create_error:
        asyncio.run(create_template(template_data, object(), auditor))
    assert create_error.value.status_code == 403

    with pytest.raises(HTTPException) as copy_error:
        asyncio.run(copy_template(str(uuid.uuid4()), None, object(), auditor))
    assert copy_error.value.status_code == 403

    owned_template = SimpleNamespace(created_by=auditor.id)
    assert can_modify_template(auditor, owned_template) is False


def test_path_uuid_validation_error_returns_not_found():
    error = RequestValidationError(
        [
            {
                "type": "uuid_parsing",
                "loc": ("path", "resource_id"),
                "msg": "Input should be a valid UUID",
                "input": "not-a-uuid",
            }
        ]
    )
    response = asyncio.run(request_validation_error_handler(None, error))
    assert response.status_code == 404


def test_body_validation_error_remains_unprocessable_entity():
    error = RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", "name"),
                "msg": "Field required",
                "input": {},
            }
        ]
    )
    response = asyncio.run(request_validation_error_handler(None, error))
    assert response.status_code == 422


def test_inspection_record_create_requires_template_item_id():
    """P1-A: InspectionRecordCreate 必须校验 template_item_id 为必填。"""
    with pytest.raises(ValidationError) as exc_info:
        InspectionRecordCreate.model_validate({})
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("template_item_id",) and err["type"] == "missing" for err in errors)


def test_task_walk_prevents_infinite_recursion_on_null_id():
    """P1-B: _walk 在遇到 _item_meta 返回空或 id 为 None 时不得无限递归。"""
    children_by_parent = {
        None: [
            {"template_item": None, "check_item": None},
            {"template_item": {"id": "leaf-1", "sort_order": 1}},
        ],
        "leaf-1": [],
    }

    def _item_meta(raw):
        return raw.get("template_item") or raw.get("check_item") or {}

    ordered = []

    def _walk(parent_key):
        for node in children_by_parent.get(parent_key, []):
            ordered.append(node)
            child_id = _item_meta(node).get("id")
            if child_id is not None:
                _walk(child_id)

    # 之前这行代码会触发 RecursionError: maximum recursion depth exceeded
    _walk(None)
    assert len(ordered) == 2
