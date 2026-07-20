import asyncio
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from docx import Document

from app.config import settings
from app.services.project_artifact_service import ProjectArtifactService
from app.services.project_document_parser import ProjectDocumentParser
from app.services.project_knowledge_service import ProjectKnowledgeService


def _document_metadata(category="organization", **extra):
    return {"category": category, "searchable": True, **extra}


def _complete_snapshot():
    return {
        "project": {
            "title": "山东盛发焦化有限公司再认证",
            "project_no": "LYEC-2025-1058",
        },
        "auditors": [],
        "plan_items": [
            {
                "id": "plan-1",
                "status": "completed",
                "clauses": ["7.5", "8.1"],
            }
        ],
        "area_records": [
            {
                "id": "record-1",
                "status": "submitted",
                "area": "煤焦车间",
                "items": [
                    {
                        "id": "item-1",
                        "title": "文件控制",
                        "clause_no": "7.5",
                        "evaluation": "1",
                        "evidence": "抽查受控文件清单，版本有效",
                        "findings": "",
                        "photos": [],
                    },
                    {
                        "id": "item-2",
                        "title": "运行控制",
                        "clause_no": "8.1",
                        "evaluation": "1",
                        "evidence": "现场查看焦炉运行正常",
                        "findings": "",
                        "photos": [],
                    },
                ],
            }
        ],
        "meetings": [
            {
                "id": "opening",
                "type": "opening",
                "sign_in_sheet": {"participants": ["企业代表", "审核组长"]},
            },
            {
                "id": "closing",
                "type": "closing",
                "sign_in_sheet": {"participants": ["企业代表", "审核组长"]},
            },
        ],
        "reports": [{"id": "report-1", "type": "combined"}],
        "nonconformities": [],
        "drafts": [],
        "documents": [
            {
                "id": "org-1",
                "name": "体系认证申请书2025.pdf",
                "status": "ready",
                "type": "organization",
                "metadata": _document_metadata(),
            },
            {
                "id": "manual-1",
                "name": "2025管理手册.doc",
                "status": "ready",
                "type": "manual",
                "metadata": _document_metadata(
                    "manual", archive_only=True, searchable=False
                ),
            },
        ],
    }


@pytest.mark.parametrize("filename", ["现场审核记录.doc", "能源绩效表.xls"])
def test_legacy_office_files_are_archive_only(filename):
    parsed = ProjectDocumentParser().parse(b"legacy-binary", filename)

    assert parsed.text == ""
    assert parsed.metadata["archive_only"] is True
    assert parsed.metadata["searchable"] is False
    assert parsed.metadata["warning"] == "旧格式仅归档，需转换后才能检索"


def test_archive_only_document_is_ready_without_knowledge_chunks():
    service = ProjectKnowledgeService()
    document = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        original_filename="现场审核记录.doc",
        document_type="auto",
        document_metadata={},
        extracted_text=None,
        status="uploaded",
        parse_error=None,
        parsed_at=None,
        is_deleted=False,
    )
    db = AsyncMock()

    result = asyncio.run(service.index_document(db, document, b"legacy-binary"))

    assert result["status"] == "ready"
    assert result["chunk_count"] == 0
    assert result["archive_only"] is True
    assert document.status == "ready"
    assert document.document_metadata["searchable"] is False
    db.add.assert_not_called()
    db.commit.assert_awaited_once()


def test_archive_only_file_keeps_original_archive_section_hint():
    parsed = ProjectDocumentParser().parse(
        b"legacy-binary", "E A1高层领导现场审核记录.doc"
    )

    assert parsed.metadata["archive_section"] == "E"
    assert parsed.metadata["category"] == "record"


def test_consistency_analysis_quarantines_wrong_enterprise_and_industry():
    text = (
        "青岛示例电气有限公司\n"
        "PCBA事业部负责线路板贴片、回流焊、电能表和智能断路器生产。"
    )

    risk = ProjectDocumentParser.analyze_consistency(
        text,
        expected_enterprise_name="山东盛发焦化有限公司",
        expected_industry_keywords=["焦炭", "焦炉", "煤焦油"],
        filename="S-RZ-JL-SH-004c现场审核记录.docx",
    )

    assert risk["risk_level"] == "high"
    assert risk["recommended_quarantine"] is True
    assert {reason["code"] for reason in risk["reasons"]} == {
        "OTHER_ENTERPRISE_NAME",
        "INDUSTRY_MISMATCH",
    }


def test_missing_enterprise_name_alone_is_not_a_consistency_failure():
    risk = ProjectDocumentParser.analyze_consistency(
        "现场审核记录：检查表、审核记录、标准号条款号、评估",
        expected_enterprise_name="山东盛发焦化有限公司",
    )

    assert risk["risk_level"] == "low"
    assert risk["recommended_quarantine"] is False
    assert risk["reasons"] == []


def test_deleted_archive_only_and_quarantined_documents_are_not_searchable():
    service = ProjectKnowledgeService()

    assert service._document_is_searchable(
        SimpleNamespace(is_deleted=False, document_metadata={"searchable": True})
    )
    assert not service._document_is_searchable(
        SimpleNamespace(is_deleted=True, document_metadata={"searchable": True})
    )
    assert not service._document_is_searchable(
        SimpleNamespace(
            is_deleted=False,
            document_metadata={"archive_only": True, "searchable": False},
        )
    )
    assert not service._document_is_searchable(
        SimpleNamespace(
            is_deleted=False,
            document_metadata={
                "consistency": {
                    "risk_level": "high",
                    "recommended_quarantine": True,
                }
            },
        )
    )


def test_project_search_query_filters_soft_deleted_documents():
    db = AsyncMock()
    result = Mock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result

    assert asyncio.run(ProjectKnowledgeService().search(db, uuid4(), "焦炉")) == []

    statement = db.execute.await_args.args[0]
    sql = str(statement).lower()
    assert "project_documents.is_deleted is false" in sql


def test_project_search_drops_quarantined_document_before_embedding():
    db = AsyncMock()
    result = Mock()
    result.scalars.return_value.all.return_value = [
        SimpleNamespace(
            document=SimpleNamespace(
                is_deleted=False,
                document_metadata={"quarantined": True},
            )
        )
    ]
    db.execute.return_value = result

    results = asyncio.run(ProjectKnowledgeService().search(db, uuid4(), "电能表"))

    assert results == []


def test_artifact_document_query_filters_soft_deleted_documents():
    sql = str(ProjectArtifactService._active_documents_statement(uuid4())).lower()

    assert "project_documents.is_deleted is false" in sql


@pytest.mark.parametrize(
    "status", ["draft", "open", "corrected", "pending_verification"]
)
def test_unclosed_nonconformity_statuses_block_formal_artifacts(status):
    snapshot = _complete_snapshot()
    snapshot["nonconformities"] = [{"id": "nc-1", "status": status}]

    quality = ProjectArtifactService.evaluate_snapshot_quality(snapshot)

    assert quality["passed"] is False
    assert quality["archive_checks"]["G_nonconformity_closure"] is False
    assert "UNCLOSED_NONCONFORMITIES" in {
        item["code"] for item in quality["blockers"]
    }


@pytest.mark.parametrize("status", ["verified", "closed"])
def test_verified_or_closed_nonconformities_pass_closure_gate(status):
    snapshot = _complete_snapshot()
    snapshot["nonconformities"] = [{"id": "nc-1", "status": status}]

    quality = ProjectArtifactService.evaluate_snapshot_quality(snapshot)

    assert quality["passed"] is True
    assert quality["archive_ready"] is True
    assert quality["archive_completeness_score"] == 100


def test_submitted_record_requires_a_valid_item_and_reports_clause_coverage():
    snapshot = _complete_snapshot()
    snapshot["area_records"][0]["items"] = []

    empty_quality = ProjectArtifactService.evaluate_snapshot_quality(snapshot)

    assert "EMPTY_SUBMITTED_RECORDS" in {
        item["code"] for item in empty_quality["blockers"]
    }
    assert empty_quality["consistency"]["clause_coverage"] == 0

    snapshot = _complete_snapshot()
    snapshot["area_records"][0]["items"] = snapshot["area_records"][0][
        "items"
    ][:1]
    partial_quality = ProjectArtifactService.evaluate_snapshot_quality(snapshot)

    assert partial_quality["consistency"]["clause_coverage"] == 50
    assert partial_quality["consistency"]["uncovered_clauses"] == ["8.1"]
    assert "PLAN_CLAUSE_GAPS" in {
        item["code"] for item in partial_quality["blockers"]
    }


def test_report_absence_affects_archive_ready_without_creating_a_gate_cycle():
    snapshot = _complete_snapshot()
    snapshot["reports"] = []

    quality = ProjectArtifactService.evaluate_snapshot_quality(snapshot)

    assert quality["passed"] is True
    assert quality["archive_ready"] is False
    assert quality["archive_checks"]["F_audit_report"] is False
    assert quality["archive_completeness_score"] == 88


def test_area_record_word_uses_real_four_column_form_and_source_note():
    project = SimpleNamespace(title="测试审核项目", project_no="P-001")
    record = SimpleNamespace(
        area_name="生产部",
        audit_date="2026-07-15",
        status="submitted",
        conclusion="体系运行有效",
        items=[
            SimpleNamespace(
                item_title="文件控制",
                item_check_method="抽样查阅",
                clause_no_snapshot="7.5",
                certification_system="Q",
                evaluation_3level="1",
                audit_evidence="查见文件清单版本为 V3",
                audit_findings="",
                ai_generated=True,
                ai_basis="GB/T 19001-2016 7.5",
            )
        ],
    )

    document = Document(
        io.BytesIO(ProjectArtifactService._area_record_docx(project, record))
    )
    table = document.tables[-1]

    assert len(table.columns) == 4
    assert [cell.text for cell in table.rows[0].cells] == [
        "检查表",
        "审核记录",
        "标准号/条款号",
        "评估",
    ]
    assert "来源：AI辅助，经人工确认" in table.rows[1].cells[1].text
    assert "AI依据：GB/T 19001-2016 7.5" in table.rows[1].cells[1].text


def test_meeting_word_contains_minutes_and_sign_in():
    project = SimpleNamespace(title="测试审核项目", project_no="P-001")
    meeting = {
        "type": "opening",
        "time": "2026-07-15T08:30:00+08:00",
        "audit_team_members": ["审核员甲"],
        "participants_enterprise": "企业代表乙",
        "key_points": "确认审核目的、范围和准则",
        "minutes": "双方确认计划。",
        "sign_in_sheet": {"人员": ["审核员甲", "企业代表乙"]},
    }

    document = Document(
        io.BytesIO(ProjectArtifactService._meeting_docx(project, meeting))
    )
    text = "\n".join(
        [paragraph.text for paragraph in document.paragraphs]
        + [
            cell.text
            for table in document.tables
            for row in table.rows
            for cell in row.cells
        ]
    )

    assert "首次会议记录" in text
    assert "确认审核目的、范围和准则" in text
    assert "审核员甲" in text


def test_existing_record_photo_is_added_under_e_attachments(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    photo = upload_dir / "records" / "evidence.jpg"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"photo-bytes")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    snapshot = _complete_snapshot()
    snapshot["area_records"][0]["items"][0]["photos"] = [
        "/uploads/records/evidence.jpg"
    ]

    files = ProjectArtifactService._record_photo_files(snapshot)

    assert len(files) == 1
    archive_path, resolved = files[0]
    assert archive_path.startswith("E审核记录汇总（含附件）/附件/煤焦车间/")
    assert resolved == photo.resolve()


@pytest.mark.parametrize(
    ("filename", "category", "expected"),
    [
        ("体系认证申请书2025.pdf", "organization", "A组织信息"),
        ("管理体系审核计划.doc", "audit_plan", "B审核通知"),
        ("2025管理手册.doc", "manual", "C管理手册和程序文件"),
        ("会议签到表.pdf", "meeting", "D审核资料汇总"),
        ("现场审核记录.doc", "record", "E审核记录汇总（含附件）"),
        ("QES管理体系审核报告.pdf", "audit_report", "F审核计划和审核报告"),
        ("不符合项整改汇总.doc", "nonconformity", "G不符合项整改汇总"),
        ("认证项目资料审查和传递记录.doc", "record", "I案卷检查表"),
        ("认证证书.pdf", "other", "Z其它文件"),
    ],
)
def test_document_archive_classification(filename, category, expected):
    document = SimpleNamespace(
        original_filename=filename,
        document_type=category,
        document_metadata={"category": category},
    )

    assert ProjectArtifactService._document_archive_folder(document) == expected
