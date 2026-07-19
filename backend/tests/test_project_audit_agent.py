import asyncio
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from docx import Document

from app.routers import project_agent
from app.routers.project_agent import _run_artifact_generation, _session_quality
from app.services.agent_service import agent_service
from app.services.project_artifact_service import ProjectArtifactService
from app.services.project_knowledge_service import project_knowledge_service
from app.services.rag_service import rag_service


def test_combined_search_keeps_project_and_global_scopes_separate():
    project_id = uuid4()
    db = AsyncMock()

    with (
        patch.object(
            project_knowledge_service,
            "search",
            AsyncMock(
                return_value=[
                    {
                        "chunk_id": "project-1",
                        "project_id": str(project_id),
                        "source_scope": "project",
                        "content": "本项目程序文件",
                    }
                ]
            ),
        ) as project_search,
        patch.object(
            rag_service,
            "search_knowledge",
            AsyncMock(
                return_value=[
                    {
                        "chunk_id": "global-1",
                        "document_title": "GB/T 19001",
                        "content": "全局法规条款",
                    }
                ]
            ),
        ) as global_search,
    ):
        results = asyncio.run(
            project_knowledge_service.search_combined(
                db, project_id, "文件控制", top_k=4
            )
        )

    assert {item["source_scope"] for item in results} == {
        "project",
        "global_regulation",
    }
    assert results[0]["project_id"] == str(project_id)
    assert results[1]["project_id"] is None
    project_search.assert_awaited_once_with(db, project_id, "文件控制", 2)
    global_search.assert_awaited()


def test_web_agent_evidence_proposal_targets_formal_project_session():
    project_id = uuid4()
    session_id = uuid4()
    plan_item_id = uuid4()
    area_record_id = uuid4()
    session = SimpleNamespace(
        id=session_id,
        project_id=project_id,
        status="active",
        context_snapshot={
            "plan_item_id": str(plan_item_id),
            "area_record_id": str(area_record_id),
        },
    )
    execute_result = Mock()
    execute_result.scalar_one_or_none.return_value = session
    db = AsyncMock()
    db.execute.return_value = execute_result

    result = asyncio.run(
        agent_service._tool_propose_audit_evidence(
            {"content": "查见受控文件清单已更新", "evidence_type": "text"},
            {
                "project_id": str(project_id),
                "audit_session_id": str(session_id),
            },
            db,
        )
    )

    assert result["type"] == "action_proposal"
    assert result["action"] == "submit_audit_evidence"
    assert result["data"]["project_id"] == str(project_id)
    assert result["data"]["plan_item_id"] == str(plan_item_id)
    assert result["data"]["area_record_id"] == str(area_record_id)
    assert result["data"]["confirm_endpoint"] == (
        f"/api/audit-projects/{project_id}/sessions/{session_id}/evidence"
    )


def test_session_quality_blocks_pending_safe_and_abnormal_drafts():
    session = SimpleNamespace(
        drafts=[
            SimpleNamespace(
                id=uuid4(),
                status="draft",
                primary_clause_no="7.5",
                evaluation="1",
                quality={"level": "sufficient", "risk_level": "medium"},
            ),
            SimpleNamespace(
                id=uuid4(),
                status="draft",
                primary_clause_no="8.7",
                evaluation="3",
                quality={"level": "sufficient", "risk_level": "high"},
            ),
        ]
    )

    result = asyncio.run(_session_quality(session))

    assert result["passed"] is False
    assert result["blocking_count"] == 2
    assert {item["code"] for item in result["blockers"]} == {
        "DRAFT_PENDING",
        "NC_UNCONFIRMED",
    }


def test_area_record_word_contains_confirmed_clause_and_evidence():
    project = SimpleNamespace(title="测试审核项目", project_no="P-001")
    record = SimpleNamespace(
        area_name="生产部",
        audit_date="2026-07-15",
        status="submitted",
        conclusion="体系运行有效",
        items=[
            SimpleNamespace(
                clause_no_snapshot="7.5",
                certification_system="Q",
                evaluation_3level="1",
                audit_evidence="查见文件清单版本为 V3",
                audit_findings="",
                ai_basis="GB/T 19001-2016 7.5",
            )
        ],
    )

    content = ProjectArtifactService._area_record_docx(project, record)
    document = Document(io.BytesIO(content))
    text = "\n".join(
        [paragraph.text for paragraph in document.paragraphs]
        + [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    )

    assert "7.5" in text
    assert "查见文件清单版本为 V3" in text
    assert "GB/T 19001-2016 7.5" in text


def test_package_uses_only_the_latest_artifact_version_per_type():
    # 同类型不同文件名（多区域记录）都应保留；同名只保留最高版本
    artifacts = [
        SimpleNamespace(artifact_type="area_record", version=1, filename="区域A.docx", id="1"),
        SimpleNamespace(artifact_type="area_record", version=2, filename="区域B.docx", id="2"),
        SimpleNamespace(artifact_type="area_record", version=3, filename="区域A.docx", id="3"),
        SimpleNamespace(artifact_type="audit_report", version=1, filename="报告.docx", id="4"),
    ]

    latest = ProjectArtifactService._latest_artifacts(artifacts)

    assert {(item.filename, item.version) for item in latest} == {
        ("区域A.docx", 3),
        ("区域B.docx", 2),
        ("报告.docx", 1),
    }


def test_user_facing_deliverables_are_word_not_json():
    project = SimpleNamespace(title="测试项目", project_no="AUDIT-1", status="completed", audit_type="initial", certification_systems=["Q"])
    snapshot = {
        "project": {"title": "测试项目", "project_no": "AUDIT-1", "status": "completed", "audit_type": "initial", "certification_systems": ["Q"]},
        "plan_items": [{"area": "推磨车间", "status": "completed", "clauses": ["5.1", "7.1"]}],
        "area_records": [],
        "nonconformities": [],
        "documents": [],
        "drafts": [],
    }
    quality = {
        "passed": True,
        "completeness_score": 100,
        "consistency_score": 100,
        "checked_at": "2026-07-19T00:00:00+00:00",
        "completeness": {
            "organization_materials": True,
            "audit_plan": True,
            "area_records": True,
            "ai_drafts": True,
            "nonconformities": True,
            "document_index": True,
        },
        "blockers": [],
        "warnings": [],
        "consistency": {"plan_count": 1, "record_count": 0, "confirmed_draft_count": 0, "nonconformity_count": 0},
    }

    for builder in (
        lambda: ProjectArtifactService._project_summary_docx(project, snapshot),
        lambda: ProjectArtifactService._audit_plan_docx(project, snapshot),
        lambda: ProjectArtifactService._quality_check_docx(project, quality, snapshot),
        lambda: ProjectArtifactService._package_file_list_docx(project, quality, [{"path": "a.docx", "size": 10, "sha256": "abc"}]),
    ):
        content = builder()
        assert content[:2] == b"PK"  # docx is a zip container
        document = Document(io.BytesIO(content))
        text = "\n".join(p.text for p in document.paragraphs)
        assert "测试项目" in text or "AUDIT-1" in text or "资料包" in text or "完整性" in text


def test_package_generation_runs_as_a_retryable_background_job():
    job_id = uuid4()
    project_id = uuid4()
    package_id = uuid4()
    job = SimpleNamespace(
        id=job_id,
        artifact_type="generation_job",
        project_id=project_id,
        created_by=uuid4(),
        artifact_metadata={"artifact_types": ["package"]},
        status="pending",
        progress=0,
        error_message=None,
    )
    db = AsyncMock()
    db.get.return_value = job

    class SessionContext:
        async def __aenter__(self):
            return db

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    with (
        patch.object(project_agent, "AsyncSessionLocal", return_value=SessionContext()),
        patch.object(
            project_agent.project_artifact_service,
            "quality_check",
            AsyncMock(return_value={"passed": True}),
        ),
        patch.object(
            project_agent.project_artifact_service,
            "generate_package",
            AsyncMock(return_value=SimpleNamespace(id=package_id)),
        ) as generate_package,
        patch.object(
            project_agent.project_artifact_service,
            "generate",
            AsyncMock(),
        ) as generate,
    ):
        asyncio.run(_run_artifact_generation(job_id))

    generate_package.assert_awaited_once_with(db, project_id, job.created_by)
    generate.assert_not_awaited()
    assert job.status == "completed"
    assert job.progress == 100
    assert job.artifact_metadata["artifact_ids"] == [str(package_id)]
