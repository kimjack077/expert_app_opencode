import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.record import InspectionRecord
from app.routers.tasks import complete_task, start_task, update_task
from app.schemas.task import InspectionTaskUpdate
from app.services.formal_audit_sync_service import (
    can_access_linked_task,
    legacy_result_to_evaluation,
    overall_from_remarks,
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
    # 完成任务必须带最终判定结论（测试问题 7 的新校验）
    task.remarks = "最终判定:合格 | 判定说明:route test"
    plan = SimpleNamespace(id=uuid4(), project_id=uuid4())
    project = SimpleNamespace(status="planning", is_deleted=False, actual_end=None)
    records_result = Mock()
    records_result.scalars.return_value.all.return_value = []
    count_result = Mock()
    count_result.scalar.return_value = 0
    db = SimpleNamespace(
        get=AsyncMock(side_effect=[task, project]),
        execute=AsyncMock(side_effect=[records_result, count_result]),
        flush=AsyncMock(),
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
    # 统一响应体走 app.utils.response.make_response，返回 dict（HTTP 层 JSON 不变）
    assert result["code"] == 200


def test_post_complete_without_final_judgment_is_rejected():
    user = SimpleNamespace(id=uuid4(), role="admin", username="admin")
    task = make_task(user.id)
    task.remarks = "普通备注，没有最终判定标记"
    records_result = Mock()
    records_result.scalars.return_value.all.return_value = []
    db = SimpleNamespace(
        get=AsyncMock(return_value=task),
        execute=AsyncMock(return_value=records_result),
        commit=AsyncMock(),
    )

    import pytest as _pytest

    with _pytest.raises(Exception) as exc_info:
        asyncio.run(complete_task(str(task.id), db=db, current_user=user))
    assert "最终判定" in str(exc_info.value.detail)
    db.commit.assert_not_awaited()


def test_put_completed_route_cannot_bypass_formal_sync():
    user = SimpleNamespace(id=uuid4(), role="expert", username="expert")
    task = make_task(user.id)
    # 完成任务必须带最终判定结论（测试问题 7 的新校验）
    task.remarks = "最终判定:合格 | 判定说明:route test"
    plan = SimpleNamespace(id=uuid4(), project_id=uuid4(), status="in_progress")
    project = SimpleNamespace(status="planning", is_deleted=False, actual_end=None)
    records_result = Mock()
    records_result.scalars.return_value.all.return_value = []
    count_result = Mock()
    count_result.scalar.return_value = 0
    db = SimpleNamespace(
        get=AsyncMock(side_effect=[task, project]),
        execute=AsyncMock(side_effect=[records_result, count_result]),
        flush=AsyncMock(),
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
    # 统一响应体走 app.utils.response.make_response，返回 dict（HTTP 层 JSON 不变）
    assert result["code"] == 200


def test_put_completed_without_final_judgment_is_rejected():
    user = SimpleNamespace(id=uuid4(), role="expert", username="expert")
    task = make_task(user.id)
    task.remarks = None
    records_result = Mock()
    records_result.scalars.return_value.all.return_value = []
    db = SimpleNamespace(
        get=AsyncMock(return_value=task),
        execute=AsyncMock(return_value=records_result),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    import pytest as _pytest

    with _pytest.raises(Exception) as exc_info:
        asyncio.run(
            update_task(
                str(task.id),
                InspectionTaskUpdate(status="completed"),
                db=db,
                current_user=user,
            )
        )
    assert "最终判定" in str(exc_info.value.detail)
    db.commit.assert_not_awaited()


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
        # 空/None（未填写）必须返回 None → 同步层落为 not_applicable，
        # 绝不能映射成 "2"（基本符合）：否则漏填项会被算进合格档，
        # 正式审核记录的合规率被虚增。旧用例期望 ("None", "2") 是错的。
        ("", None),
        (None, None),
        ("  ", None),
    ],
)
def test_legacy_result_mapping_covers_all_client_values(legacy_result, expected):
    assert legacy_result_to_evaluation(legacy_result) == expected


@pytest.mark.parametrize(("remarks", "expected"), [
    ("最终判定:合格 | 说明：无不合格项", "pass"),
    ("最终判定： 基本合格 | 说明：部分不合格", "partial_pass"),
    ("最终判定: 不合格 | 说明：多数项目合格", "fail"),
    ("最终判定:PASS | 不合格项已整改", "pass"),
    ("最终判定:partial_pass", "partial_pass"),
    ("最终判定:fail", "fail"),
    ("最终判定:不符合", "fail"),
    ("最终判定:符合", "pass"),
])
def test_final_judgment_does_not_read_keywords_from_explanation(remarks, expected):
    assert overall_from_remarks(remarks) == expected


@pytest.fixture(autouse=True)
def forbid_real_database_connections():
    with (
        patch("sqlalchemy.ext.asyncio.AsyncEngine.connect", side_effect=AssertionError("禁止连接数据库")),
        patch("sqlalchemy.ext.asyncio.AsyncEngine.begin", side_effect=AssertionError("禁止连接数据库")),
    ):
        yield


def rows_result(rows):
    result = Mock()
    result.scalars.return_value.all.return_value = rows
    result.scalars.return_value.unique.return_value.all.return_value = rows
    result.scalars.return_value.first.return_value = rows[0] if rows else None
    result.scalar_one_or_none.return_value = rows[0] if rows else None
    return result


def make_template_item(**overrides):
    fields = dict(
        id=uuid4(), template_id=None, title="必填检查项", is_required=True,
        is_deleted=False, is_category=False, parent_id=None,
        check_type="radio", result_type="pass_fail",
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def make_source(item, **overrides):
    fields = dict(
        id=uuid4(), template_item_id=item.id, template_item=item,
        result=None, result_value=None, result_text=None, inspector_note=None,
        llm_suggestion=None, llm_basis=None, media_files=[],
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


@pytest.mark.parametrize("remarks", [None, "", "历史不合格结论", "合格", "最终判定:待确认"])
def test_unrecognized_final_judgment_is_unknown(remarks):
    assert overall_from_remarks(remarks) is None


@pytest.mark.parametrize("role", ["admin", "super_admin", "expert", "auditor"])
@pytest.mark.parametrize("method", ["POST", "PUT"])
def test_cancelled_task_cannot_complete(role, method):
    user = SimpleNamespace(id=uuid4(), role=role, username=role)
    task = make_task(user.id, status="cancelled")
    task.remarks = "最终判定:合格"
    db = SimpleNamespace(get=AsyncMock(return_value=task), commit=AsyncMock())
    with (
        patch("app.routers.tasks.can_access_linked_task", AsyncMock(return_value=True)),
        patch("app.routers.tasks.sync_task_to_formal_record", AsyncMock()) as sync,
        pytest.raises(HTTPException) as exc,
    ):
        if method == "POST":
            asyncio.run(complete_task(str(task.id), db=db, current_user=user))
        else:
            asyncio.run(update_task(
                str(task.id), InspectionTaskUpdate(status="completed"), db=db, current_user=user,
            ))
    assert exc.value.status_code == 409
    assert "已取消" in exc.value.detail
    assert task.status == "cancelled"
    sync.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.parametrize("role", ["admin", "expert"])
@pytest.mark.parametrize("method", ["POST", "PUT"])
@pytest.mark.parametrize("record_state", ["absent", "empty", "whitespace"])
def test_completion_rejects_missing_required_items_before_mutation(role, method, record_state):
    user = SimpleNamespace(id=uuid4(), role=role, username=role)
    task = make_task(user.id)
    task.template_id = uuid4()
    if method == "POST":
        task.remarks = "最终判定:合格"
    original_remarks = task.remarks
    item = make_template_item(template_id=task.template_id)
    records = [] if record_state == "absent" else [make_source(
        item, result_text="  " if record_state == "whitespace" else None,
    )]
    db = SimpleNamespace(
        get=AsyncMock(return_value=task),
        execute=AsyncMock(side_effect=[rows_result(records), rows_result([item])]),
        flush=AsyncMock(), commit=AsyncMock(),
    )
    with (
        patch("app.routers.tasks.can_access_linked_task", AsyncMock(return_value=True)),
        patch("app.routers.tasks.load_parent_ids", AsyncMock(return_value=set())),
        patch("app.routers.tasks.sync_task_to_formal_record", AsyncMock()) as sync,
        patch("app.routers.tasks._sync_project_status_after_plan_item", AsyncMock()) as summary,
        pytest.raises(HTTPException) as exc,
    ):
        if method == "POST":
            asyncio.run(complete_task(str(task.id), db=db, current_user=user))
        else:
            asyncio.run(update_task(
                str(task.id), InspectionTaskUpdate(status="completed", remarks="最终判定:合格"),
                db=db, current_user=user,
            ))
    assert exc.value.status_code == 409
    assert "未填报的必填检查项" in exc.value.detail
    assert item.title in exc.value.detail
    assert task.status == "in_progress"
    assert task.completed_at is None
    assert task.remarks == original_remarks
    sync.assert_not_awaited()
    summary.assert_not_awaited()
    db.flush.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.parametrize("method", ["POST", "PUT"])
@pytest.mark.parametrize("value", [0, "0"])
def test_completion_accepts_zero_and_excludes_categories_deleted_optional_items(method, value):
    user = SimpleNamespace(id=uuid4(), role="admin", username="admin")
    task = make_task(user.id)
    task.template_id = uuid4()
    task.remarks = "最终判定:合格"
    parent = make_template_item(template_id=task.template_id)
    item = make_template_item(
        template_id=task.template_id, parent_id=parent.id, result_type="numeric",
    )
    items = [
        parent, item,
        make_template_item(template_id=task.template_id, is_category=True),
        make_template_item(template_id=task.template_id, is_deleted=True),
        make_template_item(template_id=task.template_id, is_required=False),
    ]
    records = [make_source(item, result_value=value), make_source(parent)]
    results = [rows_result(records), rows_result(items)]
    if method == "PUT":
        count = Mock()
        count.scalar.return_value = len(records)
        results.extend([rows_result([]), count])
    db = SimpleNamespace(
        get=AsyncMock(return_value=task), execute=AsyncMock(side_effect=results),
        flush=AsyncMock(), commit=AsyncMock(), refresh=AsyncMock(),
    )
    with (
        patch("app.routers.tasks.load_parent_ids", AsyncMock(return_value={parent.id})),
        patch("app.routers.tasks.get_linked_plan_item", AsyncMock(return_value=None)),
        patch("app.routers.tasks.AuditService.log_action", AsyncMock()),
    ):
        if method == "POST":
            result = asyncio.run(complete_task(str(task.id), db=db, current_user=user))
        else:
            result = asyncio.run(update_task(
                str(task.id), InspectionTaskUpdate(status="completed"), db=db, current_user=user,
            ))
    assert result["code"] == 200
    assert task.status == "completed"
    db.commit.assert_awaited_once()


def make_formal_sync_context(remarks, *, existing=True, value=None):
    user = SimpleNamespace(id=uuid4(), role="admin", username="admin")
    task = make_task(user.id)
    task.remarks = remarks
    plan = SimpleNamespace(
        id=uuid4(), project_id=uuid4(), status="in_progress", template_id=None,
        certification_systems=[], area_name="测试区域",
    )
    project = SimpleNamespace(
        status="planning", is_deleted=False, actual_end=None, enterprise_id=None, title="测试项目",
    )
    template = make_template_item(result_type="numeric" if value is not None else "pass_fail")
    source = make_source(template, result="pass" if value is None else None, result_value=value)
    formal = SimpleNamespace(id=uuid4(), template_item_id=template.id)
    area = SimpleNamespace(id=uuid4(), status="in_progress")
    area_record = SimpleNamespace(id=uuid4(), items=[formal], status="in_progress")
    inspection = SimpleNamespace(
        id=uuid4(), status="submitted", overall_result="fail",
        remarks=f"[task:{task.id}] 历史备注", judgment_note="历史判定说明",
    ) if existing else None
    results = [
        rows_result([source]), Mock(), rows_result([area]), rows_result([area_record]),
        rows_result([inspection] if inspection else []),
    ]
    events = []
    flushed = {}

    async def execute(stmt):
        if str(stmt).startswith("SELECT count("):
            events.append("summary")
            assert flushed == {"task": "completed", "plan": "completed"}
            count = Mock()
            count.scalar.return_value = 0
            return count
        return results.pop(0)

    async def flush():
        events.append("flush")
        flushed.update(task=task.status, plan=plan.status)

    async def commit():
        events.append("commit")

    def add(obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()

    db = SimpleNamespace(
        get=AsyncMock(side_effect=lambda model, ident: task if ident == str(task.id) else project),
        execute=AsyncMock(side_effect=execute), flush=AsyncMock(side_effect=flush),
        commit=AsyncMock(side_effect=commit), refresh=AsyncMock(), add=Mock(side_effect=add),
    )
    return SimpleNamespace(
        user=user, task=task, plan=plan, project=project, source=source, formal=formal,
        area_record=area_record, inspection=inspection, results=results, events=events, db=db,
    )


@pytest.mark.parametrize("method", ["POST", "PUT"])
@pytest.mark.parametrize("role", ["admin", "expert"])
def test_completion_flushes_before_formal_sync_and_project_summary(method, role):
    ctx = make_formal_sync_context("最终判定:合格 | 判定说明:全部通过")
    ctx.user.role = role
    ctx.results.insert(0, rows_result([ctx.source]))

    async def sync(db, task, plan, user_id):
        assert ctx.events[-1] == "flush"
        ctx.events.append("sync")
        return await sync_task_to_formal_record(db, task, plan, user_id)

    with (
        patch("app.routers.tasks.can_access_linked_task", AsyncMock(return_value=True)),
        patch("app.routers.tasks.get_linked_plan_item", AsyncMock(return_value=ctx.plan)),
        patch("app.routers.tasks.sync_task_to_formal_record", AsyncMock(side_effect=sync)),
        patch("app.routers.tasks.AuditService.log_action", AsyncMock()),
    ):
        if method == "POST":
            result = asyncio.run(complete_task(str(ctx.task.id), db=ctx.db, current_user=ctx.user))
        else:
            result = asyncio.run(update_task(
                str(ctx.task.id), InspectionTaskUpdate(status="completed"),
                db=ctx.db, current_user=ctx.user,
            ))
    assert result["code"] == 200
    assert ctx.events == ["flush", "sync", "flush", "summary", "commit"]
    assert ctx.task.status == ctx.plan.status == ctx.project.status == "completed"
    assert ctx.project.actual_end is not None
    assert ctx.inspection.overall_result == "pass"
    assert ctx.results == []


@pytest.mark.parametrize(("remarks", "expected"), [
    ("最终判定:基本合格 | 判定说明:管理员复核", "partial_pass"),
    ("历史不合格，补充判定依据", "fail"),
    ("最终判定:待确认 | 补充说明", "fail"),
    (None, "fail"),
])
def test_completed_admin_remarks_edit_refreshes_formal_record(remarks, expected):
    ctx = make_formal_sync_context("旧备注")
    ctx.task.status = "completed"
    ctx.task.completed_at = datetime.now(timezone.utc)
    completed_at = ctx.task.completed_at
    with patch("app.routers.tasks.get_linked_plan_item", AsyncMock(return_value=ctx.plan)):
        response = asyncio.run(update_task(
            str(ctx.task.id), InspectionTaskUpdate(remarks=remarks),
            db=ctx.db, current_user=ctx.user,
        ))
    assert response["code"] == 200
    assert ctx.inspection.overall_result == expected
    assert f"[task:{ctx.task.id}]" in ctx.inspection.remarks
    assert ctx.inspection.remarks.endswith(remarks or "|")
    assert "历史备注" not in ctx.inspection.remarks
    assert ctx.inspection.judgment_note == remarks
    assert ctx.task.completed_at == completed_at
    assert ctx.formal.record_id == ctx.inspection.id
    assert ctx.area_record.status == "submitted"
    assert ctx.results == []
    ctx.db.commit.assert_awaited_once()


@pytest.mark.parametrize("remarks", [None, "历史不合格", "最终判定:待确认"])
def test_new_formal_inspection_requires_explicit_final_judgment(remarks):
    ctx = make_formal_sync_context(remarks, existing=False)
    with pytest.raises(ValueError, match="最终判定结论"):
        asyncio.run(sync_task_to_formal_record(ctx.db, ctx.task, ctx.plan, ctx.user.id))
    assert not any(isinstance(call.args[0], InspectionRecord) for call in ctx.db.add.call_args_list)
    assert ctx.task.status == ctx.plan.status == "in_progress"
    ctx.db.commit.assert_not_awaited()


@pytest.mark.parametrize("value", [None, 0, "0"])
def test_new_formal_inspection_keeps_final_judgment_and_zero_values(value):
    ctx = make_formal_sync_context("最终判定:不合格 | 判定说明:人工复核", existing=False, value=value)
    asyncio.run(sync_task_to_formal_record(ctx.db, ctx.task, ctx.plan, ctx.user.id))
    records = [call.args[0] for call in ctx.db.add.call_args_list if isinstance(call.args[0], InspectionRecord)]
    assert len(records) == 1
    assert records[0].overall_result == "fail"
    assert records[0].judgment_note == ctx.task.remarks
    assert f"[task:{ctx.task.id}]" in records[0].remarks
    assert ctx.formal.result_value == value
    assert ctx.formal.record_id == records[0].id
    assert ctx.task.status == ctx.plan.status == "completed"


def test_start_task_still_updates_plan_and_project_status():
    user = SimpleNamespace(id=uuid4(), role="expert", username="expert")
    task = make_task(user.id, status="pending")
    plan = SimpleNamespace(project_id=uuid4(), status="pending")
    project = SimpleNamespace(status="planning")
    db = SimpleNamespace(
        get=AsyncMock(side_effect=[task, project]), execute=AsyncMock(return_value=rows_result([plan])),
        commit=AsyncMock(),
    )
    with (
        patch("app.routers.tasks.can_access_linked_task", AsyncMock(return_value=True)),
        patch("app.routers.tasks.AuditService.log_action", AsyncMock()),
        patch("app.routers.tasks.sync_task_to_formal_record", AsyncMock()) as sync,
    ):
        result = asyncio.run(start_task(str(task.id), db=db, current_user=user))
    assert result["code"] == 200
    assert task.status == plan.status == project.status == "in_progress"
    sync.assert_not_awaited()
    db.commit.assert_awaited_once()
