import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.audit_project import AuditAreaRecord, AuditPlanItem, Nonconformity
from app.models.evidence_agent import EvidenceItem, EvidenceSubmission
from app.models.record import InspectionRecordItem
from app.routers.audit_projects import (
    _task_progress_fields,
    _validate_nonconformity_transition,
)
from app.routers.project_agent import (
    _session_quality,
    _sync_inspection_task_status,
    create_manual_record,
    session_dict,
)
from app.schemas.project_agent import ManualRecordCreateRequest


def _session(**overrides):
    values = {
        "id": uuid4(),
        "project_id": uuid4(),
        "conversation_id": None,
        "title": "生产区域审核",
        "status": "active",
        "context_snapshot": {},
        "model_provider": "test",
        "model_name": "test-model",
        "created_by": uuid4(),
        "started_at": None,
        "completed_at": None,
        "created_at": None,
        "updated_at": None,
        "drafts": [],
        "submissions": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_manual_record_request_accepts_clause_alias_and_normalizes_values():
    payload = ManualRecordCreateRequest(
        item_title="  文件控制  ",
        clause_nos=["7.5", "7.5"],
        clause_no="8.1",
        certification_system="Q",
        evaluation_3level="1",
        audit_evidence="  查见受控文件清单 V3  ",
    )

    assert payload.item_title == "文件控制"
    assert payload.audit_evidence == "查见受控文件清单 V3"
    assert payload.resolve_clause_nos() == ["7.5", "8.1"]


def test_manual_record_request_requires_at_least_one_clause():
    with pytest.raises(ValidationError):
        ManualRecordCreateRequest(
            item_title="文件控制",
            certification_system="Q",
            evaluation_3level="1",
            audit_evidence="查见受控文件清单 V3",
        )


def test_session_quality_blocks_empty_session_and_accepts_manual_record():
    empty_result = asyncio.run(_session_quality(_session()))
    assert empty_result["passed"] is False
    assert empty_result["blockers"][0]["code"] == "NO_CONFIRMED_RECORDS"

    submission = SimpleNamespace(
        id=uuid4(),
        source_snapshot={"manual_record": {"id": str(uuid4()), "clause_nos": ["7.5"]}},
    )
    manual_result = asyncio.run(_session_quality(_session(submissions=[submission])))
    assert manual_result["passed"] is True
    assert manual_result["manual_record_count"] == 1
    assert manual_result["confirmed_record_count"] == 1


def test_session_dict_exposes_manual_records_and_combined_count():
    submission = SimpleNamespace(
        id=uuid4(),
        status="completed",
        description="查见受控文件清单 V3",
        source_files=[],
        submitted_at=None,
        source_snapshot={
            "manual_record": {
                "id": str(uuid4()),
                "clause_nos": ["7.5"],
                "ai_generated": False,
            }
        },
    )

    result = session_dict(_session(submissions=[submission]), include_children=True)

    assert result["manual_record_count"] == 1
    assert result["confirmed_record_count"] == 1
    assert result["manual_records"][0]["submission_id"] == str(submission.id)


def test_inspection_task_status_syncs_start_and_completion():
    task_id = uuid4()
    plan_item = SimpleNamespace(inspection_task_id=task_id)
    task = SimpleNamespace(status="pending", started_at=None, completed_at=None)
    db = SimpleNamespace(get=AsyncMock(return_value=task))

    asyncio.run(_sync_inspection_task_status(db, plan_item, "in_progress"))
    started_at = task.started_at
    assert task.status == "in_progress"
    assert started_at is not None
    assert task.completed_at is None

    asyncio.run(_sync_inspection_task_status(db, plan_item, "completed"))
    assert task.status == "completed"
    assert task.started_at == started_at
    assert task.completed_at is not None


def test_task_progress_uses_latest_formal_record_and_unresolved_nc():
    plan_item = SimpleNamespace(clauses=["7.5", "8.1"])
    record = SimpleNamespace(
        status="submitted",
        items=[
            SimpleNamespace(evaluation_3level="1"),
            SimpleNamespace(evaluation_3level="3"),
        ],
    )
    ncs = [
        SimpleNamespace(status="open"),
        SimpleNamespace(status="closed"),
    ]

    result = _task_progress_fields(plan_item, record, ncs)

    assert result == {
        "total_clause_count": 2,
        "confirmed_record_count": 2,
        "completion_rate": 100,
        "exception_count": 1,
        "has_nc": True,
        "record_status": "submitted",
    }


def test_nonconformity_cannot_close_without_rectification_and_verification():
    nc = SimpleNamespace(
        status="open",
        corrective_action=None,
        verification_result=None,
    )

    with pytest.raises(HTTPException) as missing_action:
        _validate_nonconformity_transition(nc, {"status": "closed"})
    assert missing_action.value.status_code == 422

    with pytest.raises(HTTPException) as missing_verification:
        _validate_nonconformity_transition(
            nc,
            {"status": "closed", "corrective_action": "已更新操作规程"},
        )
    assert missing_verification.value.status_code == 422

    _validate_nonconformity_transition(
        nc,
        {
            "status": "closed",
            "corrective_action": "已更新操作规程",
            "verification_result": "抽查记录符合要求",
        },
    )


def test_manual_record_endpoint_persists_formal_objects_and_draft_nc():
    project_id = uuid4()
    session_id = uuid4()
    plan_item_id = uuid4()
    area_record_id = uuid4()
    user_id = uuid4()
    session = _session(
        id=session_id,
        project_id=project_id,
        context_snapshot={
            "plan_item_id": str(plan_item_id),
            "area_record_id": str(area_record_id),
        },
    )
    area_record = SimpleNamespace(
        id=area_record_id,
        project_id=project_id,
        plan_item_id=plan_item_id,
        status="draft",
    )
    plan_item = SimpleNamespace(
        id=plan_item_id,
        project_id=project_id,
        template_id=None,
        inspection_task_id=None,
        status="pending",
    )

    added = []
    db = SimpleNamespace()
    db.add = Mock(side_effect=added.append)

    async def flush():
        for item in added:
            if getattr(item, "id", None) is None:
                item.id = uuid4()

    async def get(model, item_id):
        if model is AuditAreaRecord and item_id == area_record_id:
            return area_record
        if model is AuditPlanItem and item_id == plan_item_id:
            return plan_item
        return None

    db.flush = AsyncMock(side_effect=flush)
    db.get = AsyncMock(side_effect=get)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    payload = ManualRecordCreateRequest(
        item_title="应急准备和响应",
        clause_nos=["8.2"],
        certification_system="E",
        evaluation_3level="3",
        audit_evidence="现场未见年度应急演练记录",
        audit_findings="应急演练未按计划实施",
        rectification_suggestion="补充演练并评价效果",
    )

    with (
        patch(
            "app.routers.project_agent.ensure_project_access",
            AsyncMock(),
        ),
        patch(
            "app.routers.project_agent._load_session",
            AsyncMock(return_value=session),
        ),
    ):
        result = asyncio.run(
            create_manual_record(
                project_id,
                session_id,
                payload,
                db,
                SimpleNamespace(id=user_id),
            )
        )

    assert result["data"]["ai_generated"] is False
    assert result["data"]["evaluation_3level"] == "3"
    assert result["data"]["nc_id"] is not None
    assert any(isinstance(item, EvidenceSubmission) for item in added)
    assert any(isinstance(item, EvidenceItem) for item in added)
    record_item = next(item for item in added if isinstance(item, InspectionRecordItem))
    assert record_item.ai_generated is False
    assert record_item.clause_no_snapshot == "8.2"
    nc = next(item for item in added if isinstance(item, Nonconformity))
    assert nc.status == "draft"
    assert nc.record_item_id == record_item.id
    assert session.context_snapshot["manual_record_count"] == 1
    assert area_record.status == "in_progress"
    assert plan_item.status == "in_progress"
    db.commit.assert_awaited_once()
