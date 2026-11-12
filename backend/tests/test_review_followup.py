"""复核回归：全部使用内存对象或 mock 会话，不连接业务数据库。"""

import asyncio
from datetime import date
from decimal import Decimal
from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.record import InspectionRecordItem
from app.models.template import TemplateItem
from app.routers import audit_projects, records, tasks, users
from app.schemas.audit_project import AuditAreaRecordItemPayload, AuditAreaRecordRequest, AuditAreaRecordUpdate
from app.schemas import InspectionRecordItemCorrection, InspectionRecordItemCreate
from app.utils.item_completion import is_item_assessed
from app.utils.scoring import calculate_total_score
from app.utils.template_order import move_template_item

pytestmark = pytest.mark.unit


def rows(values):
    result = Mock()
    result.all.return_value = values
    result.scalars.return_value.all.return_value = values
    return result


@pytest.mark.parametrize(("items", "expected"), [
    ([], None),
    ([{"item_check_type": "score", "score_value": "0", "item_score_weight": 2}], Decimal(0)),
    ([{"item_check_type": "score", "score_value": "2.5", "item_score_weight": "0.2"}], Decimal("0.5")),
    ([{"item_check_type": "score", "score_value": "8", "item_score_weight": 0}], Decimal(0)),
    ([{"item_check_type": "score", "score_value": None}], None),
    ([{"item_check_type": "score", "score_value": "nan"}], None),
    ([{"item_check_type": "radio", "radio_value": "pass", "item_score_weight": 0, "item_default_score": 10}], Decimal(0)),
    ([{"item_check_type": "radio", "radio_value": "na", "item_default_score": 0}], Decimal(0)),
    ([{"item_check_type": "numeric", "numeric_value": 10, "item_score_weight": 1}], None),
])
def test_server_scoring_preserves_zero_and_uses_snapshots(items, expected):
    assert calculate_total_score([Obj(**item) for item in items]) == expected


@pytest.mark.parametrize(("kind", "values", "expected"), [
    ("checkbox", {"multi_value": ["A"]}, True),
    ("multi_check", {"multi_value": []}, False),
    ("photo", {"photos": ["/uploads/a.jpg"]}, True),
    ("score", {"score_value": 0}, True),
    ("text", {"text_value": "  "}, False),
    ("numeric", {"radio_value": "na"}, True),
    ("audit_3level", {"radio_value": "pass"}, True),
])
def test_completion_handles_real_types(kind, values, expected):
    assert is_item_assessed({"check_type": kind}, values) is expected


def test_reorder_moves_up_and_down_without_duplicate_positions():
    items = [Obj(id=uuid4(), parent_id=None, sort_order=i) for i in range(4)]
    a, b, c, d = items
    move_template_item(items, a.id, None, 3)
    assert sorted(items, key=lambda node: node.sort_order) == [b, c, d, a]
    move_template_item(items, a.id, None, 1)
    assert sorted(items, key=lambda node: node.sort_order) == [b, a, c, d]
    assert sorted(node.sort_order for node in items) == [0, 1, 2, 3]


def test_reorder_reparents_and_compacts_both_groups():
    parent = Obj(id=uuid4(), parent_id=None, sort_order=0)
    a, b = [Obj(id=uuid4(), parent_id=None, sort_order=i + 1) for i in range(2)]
    child = Obj(id=uuid4(), parent_id=parent.id, sort_order=0)
    items = [parent, a, b, child]
    move_template_item(items, a.id, parent.id, 0)
    assert a.parent_id == parent.id and a.sort_order == 0 and child.sort_order == 1
    assert parent.sort_order == 0 and b.sort_order == 1
    with pytest.raises(ValueError, match="子节点"):
        move_template_item(items, parent.id, child.id, 0)


def test_statistics_counts_more_than_one_page_and_share_visible_scope():
    user = Obj(id=uuid4(), role="expert")
    db = Obj(execute=AsyncMock(side_effect=[
        rows([("pass", 120), ("partial_pass", 11), ("fail", 2), (None, 7)]),
        rows([(date(2026, 11, 12), 131)]),
    ]))
    response = asyncio.run(records.get_record_statistics(db, user))["data"]
    assert response["total"] == 140
    assert response["results"] == {"pass": 120, "partial_pass": 11, "fail": 2, "pending": 7}
    assert response["recent_activity"] == [{"date": "2026-11-12", "records": 131}]
    for call in db.execute.await_args_list:
        query = str(call.args[0])
        assert "inspection_records.is_deleted = false" in query
        assert "inspection_records.inspector_id =" in query
        assert "LIMIT" not in query
    assert "timezone" in str(db.execute.await_args_list[1].args[0])


def area_context():
    template_id = uuid4()
    item = TemplateItem(
        id=uuid4(), template_id=template_id, title="多选项", is_deleted=False,
        check_type="multi_check", result_type="multi_check", is_required=True,
        result_options={"options": [{"value": "A", "label": "甲"}]},
    )
    user = Obj(id=uuid4(), role="expert")
    record = Obj(
        id=uuid4(), project_id=uuid4(), recorded_by=user.id, co_recorders=[],
        template_id=template_id, plan_item_id=None, area_id=None, items=[],
        status="draft", conclusion=None,
    )
    result = Mock()
    result.scalar_one_or_none.return_value = record
    result.all.return_value = []
    def add(obj):
        obj.id = uuid4()
    db = Obj(
        execute=AsyncMock(return_value=result), get=AsyncMock(return_value=item),
        add=Mock(side_effect=add), flush=AsyncMock(), commit=AsyncMock(), refresh=AsyncMock(),
    )
    return db, user, record, item


def test_area_save_and_submit_have_one_commit_with_new_items_visible_to_validation():
    db, user, record, item = area_context()
    events = []
    async def submit(session, saved, project, updates):
        assert saved.items[0].multi_value == ["A"]
        session.commit.assert_not_awaited()
        events.append("submit")
        saved.status = "submitted"
    async def commit():
        events.append("commit")
    db.commit.side_effect = commit
    with patch.object(audit_projects, "ensure_project_access", AsyncMock(return_value=Obj())), patch.object(audit_projects, "_submit_area_record", AsyncMock(side_effect=submit)):
        asyncio.run(audit_projects.update_area_record(record.id, AuditAreaRecordUpdate(
            conclusion="审核结论", status="submitted", items=[{"template_item_id": item.id, "multi_value": ["A"]}],
        ), db, user))
    assert events == ["submit", "commit"]
    db.commit.assert_awaited_once()


def test_area_rejected_submission_never_commits_partial_details():
    db, user, record, item = area_context()
    with patch.object(audit_projects, "ensure_project_access", AsyncMock(return_value=Obj())), pytest.raises(HTTPException) as exc:
        asyncio.run(audit_projects.update_area_record(record.id, AuditAreaRecordUpdate(
            status="submitted", items=[{"template_item_id": item.id, "multi_value": ["A"]}],
        ), db, user))
    assert exc.value.status_code == 422
    db.commit.assert_not_awaited()


@pytest.mark.parametrize("invalid", ["foreign_template", "undefined_option"])
def test_area_save_rejects_foreign_template_and_unknown_option(invalid):
    db, user, record, item = area_context()
    if invalid == "foreign_template":
        item.template_id = uuid4()
    entry = AuditAreaRecordItemPayload(template_item_id=item.id, multi_value=["UNKNOWN"] if invalid == "undefined_option" else ["A"])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(audit_projects._save_area_record_items(db, record, [entry]))
    assert exc.value.status_code == 422
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


def test_attachment_placeholder_is_created_but_not_considered_assessed():
    db, user, record, item = area_context()
    saved = asyncio.run(audit_projects._save_area_record_items(db, record, [
        AuditAreaRecordItemPayload(template_item_id=item.id, ensure_exists=True),
    ]))
    assert saved == 1 and len(record.items) == 1
    assert not is_item_assessed(item, record.items[0])
    db.commit.assert_not_awaited()


def test_new_area_record_accepts_atomic_payload_and_no_early_commit():
    db, user, _, item = area_context()
    payload = AuditAreaRecordRequest(template_id=item.template_id, conclusion="通过", status="submitted", items=[{"template_item_id": item.id, "multi_value": ["A"]}])
    async def submit(session, record, project, updates):
        assert len(record.items) == 1 and record.items[0].multi_value == ["A"]
        session.commit.assert_not_awaited()
    with patch.object(audit_projects, "ensure_project_access", AsyncMock(return_value=Obj())), patch.object(audit_projects, "_submit_area_record", AsyncMock(side_effect=submit)):
        asyncio.run(audit_projects.create_area_record(uuid4(), payload, db, user))
    db.commit.assert_awaited_once()


def test_user_directory_requires_admin_or_managed_project():
    db = Obj(execute=AsyncMock())
    user = Obj(id=uuid4(), role="expert")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(users.get_user_options(db=db, current_user=user))
    assert exc.value.status_code == 403
    db.execute.assert_not_awaited()


def test_readonly_auditor_cannot_write_even_if_original_inspector():
    user = Obj(id=uuid4(), role="auditor")
    with pytest.raises(HTTPException) as exc:
        records._ensure_record_access(Obj(inspector_id=user.id), user, write=True)
    assert exc.value.status_code == 403


def test_admin_correction_recalculates_total_using_original_scoring_snapshot():
    user = Obj(id=uuid4(), username="admin", role="admin")
    record = Obj(id=uuid4(), is_deleted=False, status="submitted", template_id=uuid4(),
                 template_snapshot={"is_quantified": True}, total_score=Decimal(20))
    item = InspectionRecordItem(id=uuid4(), record_id=record.id, template_item_id=None,
                                item_check_type="score", item_score_weight=2, score_value=10)
    found = Mock()
    found.scalar_one_or_none.return_value = item
    db = Obj(get=AsyncMock(return_value=record), execute=AsyncMock(side_effect=[found, rows([item])]),
             flush=AsyncMock(), commit=AsyncMock(), refresh=AsyncMock())
    with patch.object(records.AuditService, "log_action", AsyncMock()):
        asyncio.run(records.correct_submitted_record_item(str(record.id), str(item.id),
            InspectionRecordItemCorrection(reason="修正评分", score_value=0), db, user))
    assert record.total_score == Decimal(0)
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()


def test_record_item_creation_preserves_scoring_metadata_and_rejects_foreign_template():
    db, user, _, template = area_context()
    template.check_type = template.result_type = "score"
    template.score_weight = Decimal("0.5")
    record = Obj(id=uuid4(), is_deleted=False, status="draft", inspector_id=user.id, template_id=template.template_id)
    found = Mock()
    found.scalar_one_or_none.return_value = None
    db.execute.return_value = found
    db.get.side_effect = [record, template]
    with patch.object(records, "load_parent_ids", AsyncMock(return_value=set())):
        asyncio.run(records.create_or_update_record_item(str(record.id),
            InspectionRecordItemCreate(template_item_id=template.id, score_value="0"), db, user))
    saved = db.add.call_args.args[0]
    assert saved.item_check_type == "score" and saved.item_score_weight == Decimal("0.5")
    db.commit.assert_awaited_once()
    template.template_id = uuid4()
    db.get.side_effect = [record, template]
    db.commit.reset_mock()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(records.create_or_update_record_item(str(record.id),
            InspectionRecordItemCreate(template_item_id=template.id, check_type="text", text_value="绕过"), db, user))
    assert exc.value.status_code == 422
    db.commit.assert_not_awaited()
