"""不依赖数据库的 2026-09-23 后端缺陷回归测试。"""

from __future__ import annotations

import asyncio
import inspect
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

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


def test_template_copy_preserves_industry_and_item_configuration():
    from app.models.template import InspectionTemplate
    from app.routers.templates import _item_payload

    user = SimpleNamespace(id=uuid.uuid4(), role="admin", username="admin")
    source = InspectionTemplate(
        id=uuid.uuid4(), name="计分模板", industry_id=uuid.uuid4(), is_deleted=False,
        description="说明", category="quality", version="2.0", is_quantified=True,
    )
    parent = TemplateItem(id=uuid.uuid4(), title="分类", is_category=True)
    leaf = TemplateItem(
        id=uuid.uuid4(), parent_id=parent.id, title="打分项", check_type="score",
        result_type="score", clause_no="8.1", applicable_systems=["Q"],
        evidence_hint="查验记录", tags=["质量"], result_options={"options": []},
        min_value=0, max_value=10, max_score=10, pass_score=0, score_step=0.5,
        default_score=0, score_weight=0, is_required=False, allow_attachment=True,
    )
    added = []

    def add(obj):
        obj.id = uuid.uuid4()
        added.append(obj)

    async def get(model, key):
        if model is InspectionTemplate:
            return source
        return next(obj for obj in added if str(obj.id) == str(key))

    rows = Mock()
    rows.scalars.return_value.all.return_value = [parent, leaf]
    db = SimpleNamespace(
        get=AsyncMock(side_effect=get), execute=AsyncMock(return_value=rows),
        add=Mock(side_effect=add), flush=AsyncMock(), commit=AsyncMock(), refresh=AsyncMock(),
    )
    with patch("app.routers.templates.AuditService.log_action", AsyncMock()):
        result = asyncio.run(copy_template(str(source.id), None, db, user))

    assert result["code"] == 200
    assert added[0].industry_id == source.industry_id
    assert added[2].parent_id == added[1].id
    actual, expected = _item_payload(added[2]), _item_payload(leaf)
    for field in (
        "clause_no", "applicable_systems", "evidence_hint", "tags", "check_type",
        "result_type", "result_options", "max_score", "score_step", "pass_score",
        "min_value", "max_value", "default_score", "score_weight", "is_required",
        "allow_attachment",
    ):
        assert actual[field] == expected[field], field
    assert actual["pass_score"] == 0
    assert actual["default_score"] == 0


@pytest.mark.parametrize("check_type", ["radio", "score", "numeric", "text", "multi_check"])
def test_ai_import_preserves_input_type(check_type):
    from app.routers.ai_extract import apply_extracted_items

    rows = Mock()
    rows.scalars.return_value.all.return_value = []
    added = []

    def add(obj):
        obj.id = uuid.uuid4()
        added.append(obj)

    db = SimpleNamespace(
        get=AsyncMock(return_value=object()), execute=AsyncMock(return_value=rows),
        add=Mock(side_effect=add), flush=AsyncMock(), commit=AsyncMock(),
    )
    user = SimpleNamespace(id=uuid.uuid4(), username="admin")
    with patch("app.routers.ai_extract.AuditService.log_action", AsyncMock()):
        response = asyncio.run(apply_extracted_items(
            str(uuid.uuid4()), [{"title": "检查项", "check_type": check_type, "score_step": 0.5}], db, user,
        ))
    assert response["data"]["created_count"] == 1
    assert not response["data"]["errors"]
    assert added[0].result_type == ("pass_fail" if check_type == "radio" else check_type)
    assert added[0].score_step == 0.5


def test_removed_members_are_excluded_from_project_visibility_and_access():
    from app.services.project_access_service import ensure_project_access, project_visibility_condition

    user = SimpleNamespace(id=uuid.uuid4(), role="expert")
    condition = str(project_visibility_condition(user))
    assert "audit_team_members.is_deleted = false" in condition
    project = SimpleNamespace(id=uuid.uuid4(), created_by=uuid.uuid4(), team_leader_id=None)
    project_rows, member_rows = Mock(), Mock()
    project_rows.scalar_one_or_none.return_value = project
    member_rows.scalars.return_value.first.return_value = None
    db = SimpleNamespace(execute=AsyncMock(side_effect=[project_rows, member_rows]))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ensure_project_access(db, project.id, user))
    assert exc.value.status_code == 403
    query = str(db.execute.await_args_list[1].args[0])
    assert "audit_team_members.is_deleted = false" in query


@pytest.mark.parametrize(("kind", "suggestion", "expected"), [
    ("numeric", "依据 GB 2760，测得值为 5", None),
    ("numeric", "依据 GB 2760。实测值：5", "5"),
    ("numeric", "实测值：5；实测值：6", None),
    ("numeric", "-0.5", "-0.5"),
    ("score", "第1项，得分：0", "0"),
    ("score", "参照标准 2026，评分待确认", None),
])
def test_ai_numeric_adoption_does_not_mistake_standard_number_for_result(kind, suggestion, expected):
    from app.routers.records import accept_ai_suggestion

    user = SimpleNamespace(id=uuid.uuid4(), role="admin")
    record = SimpleNamespace(is_deleted=False, status="draft")
    item = SimpleNamespace(
        ai_suggestion=suggestion,
        template_item=TemplateItem(check_type=kind, result_type=kind),
    )
    rows = Mock()
    rows.scalar_one_or_none.return_value = item
    db = SimpleNamespace(
        get=AsyncMock(return_value=record), execute=AsyncMock(return_value=rows), commit=AsyncMock(),
    )
    call = accept_ai_suggestion(str(uuid.uuid4()), str(uuid.uuid4()), db, user)
    if expected is None:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(call)
        assert exc.value.status_code == 422
        db.commit.assert_not_awaited()
    else:
        response = asyncio.run(call)
        field = "numeric_value" if kind == "numeric" else "score_value"
        assert response["data"][field] == expected
        assert getattr(item, field) == expected


def test_area_item_payload_normalizes_verdict_and_evaluation():
    from app.schemas.audit_project import AuditAreaRecordItemPayload

    assert AuditAreaRecordItemPayload(radio_value="fail").normalized_updates() == {
        "radio_value": "fail", "result": "fail", "evaluation_3level": "3",
    }
    basic = AuditAreaRecordItemPayload(radio_value="pass", evaluation_3level="2").normalized_updates()
    assert basic["result"] == "pass" and basic["evaluation_3level"] == "2"
    na = AuditAreaRecordItemPayload(result="not_applicable").normalized_updates()
    assert na["radio_value"] == "na" and na["evaluation_3level"] is None
    assert AuditAreaRecordItemPayload(score_value=0).normalized_updates()["score_value"] == "0"


def test_area_submit_requires_conclusion_before_any_write():
    from app.routers.audit_projects import _submit_area_record

    record = SimpleNamespace(conclusion="  ", items=[], status="draft")
    project = SimpleNamespace(status="in_progress")
    db = SimpleNamespace(execute=AsyncMock(), get=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_submit_area_record(db, record, project, {}))
    assert exc.value.status_code == 422
    assert "结论" in exc.value.detail
    db.get.assert_not_awaited()


def test_submitted_area_record_rejects_edits_and_allows_idempotent_submit():
    from app.routers.audit_projects import update_area_record
    from app.schemas.audit_project import AuditAreaRecordUpdate

    record = SimpleNamespace(
        id=uuid.uuid4(), status="submitted", recorded_by=uuid.uuid4(),
        co_recorders=[], project_id=uuid.uuid4(),
    )
    project = SimpleNamespace(id=uuid.uuid4(), status="in_progress")
    rows = Mock()
    rows.scalar_one_or_none.return_value = record
    db = SimpleNamespace(execute=AsyncMock(return_value=rows), commit=AsyncMock())
    user = SimpleNamespace(id=record.recorded_by, role="expert")

    with patch("app.routers.audit_projects.ensure_project_access", AsyncMock(return_value=project)):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(update_area_record(
                record.id, AuditAreaRecordUpdate(conclusion="补充"), db, user,
            ))
    assert exc.value.status_code == 409
    db.commit.assert_not_awaited()


@pytest.mark.parametrize("score", [None, 0, 8.5])
def test_report_preserves_zero_and_missing_scores_and_template_snapshot(score):
    from app.models.record import InspectionRecord
    from reportlab.platypus import Table

    record = InspectionRecord(
        id=uuid.uuid4(), total_score=score, template=None, items=[],
        enterprise=None, inspector=None, template_snapshot={"name": "历史模板", "items": []},
    )
    report = report_service.generate_report_data(record)
    assert report["inspection"]["total_score"] == score
    assert report["inspection"]["template_name"] == "历史模板"
    cover = report_service._build_cover_page(record, "TEST-REPORT")
    table = next(element for element in cover if isinstance(element, Table))
    assert ["检查模板", "历史模板"] in table._cellvalues
