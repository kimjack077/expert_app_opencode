import asyncio
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from docx import Document

from app.routers.project_agent import _session_quality
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
    artifacts = [
        SimpleNamespace(artifact_type="area_record", version=1),
        SimpleNamespace(artifact_type="area_record", version=2),
        SimpleNamespace(artifact_type="audit_report", version=1),
    ]

    latest = ProjectArtifactService._latest_artifacts(artifacts)

    assert {(item.artifact_type, item.version) for item in latest} == {
        ("area_record", 2),
        ("audit_report", 1),
    }
