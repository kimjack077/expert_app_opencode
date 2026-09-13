"""Project-scoped formal audit Agent, knowledge and artifact APIs."""

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer, selectinload

from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.models.audit_project import AuditArea, AuditAreaRecord, AuditPlanItem, AuditProject, Nonconformity
from app.models.enterprise import Enterprise
from app.models.evidence_agent import AiAuditSession, AiDraftRecord, EvidenceItem, EvidenceSubmission
from app.models.industry import Industry
from app.models.media import MediaFile
from app.models.project_artifact import ProjectArtifact
from app.models.project_knowledge import ProjectDocument, ProjectKnowledgeChunk
from app.models.record import InspectionRecordItem
from app.models.task import InspectionTask
from app.models.template import TemplateItem
from app.models.user import User
from app.routers.auth import get_current_user
from app.utils.category import is_category_node, load_parent_ids
from app.schemas.project_agent import (
    ArtifactGenerateRequest,
    AuditSessionCreateRequest,
    DraftConfirmRequest,
    EvidenceSubmitRequest,
    ManualRecordCreateRequest,
)
from app.services.agent_feedback_service import agent_feedback_service
from app.services.agent_memory_service import agent_memory_service
from app.services.evidence_agent_service import EvidenceCandidate, evidence_agent_service
from app.services.multimodal_service import multimodal_service
from app.services.project_access_service import PRIVILEGED_ROLES, ensure_project_access
from app.services.project_artifact_service import project_artifact_service
from app.services.project_knowledge_service import project_knowledge_service
from app.utils.file_handler import enforce_magic_bytes, save_upload_file
from app.utils.response import make_response
from app.utils.storage_path import resolve_storage_path, storage_key
from app.services.project_document_parser import SUPPORTED_PROJECT_EXTENSIONS


router = APIRouter(prefix="/api/audit-projects", tags=["project-agent"])


def response(data: Any = None, message: str = "success") -> dict[str, Any]:
    return make_response(data=data, message=message)


async def _document_project_context(
    db: AsyncSession,
    project_id: UUID,
) -> tuple[str | None, list[str]]:
    """Return the authoritative enterprise and industry hints for isolation."""

    project = await db.get(AuditProject, project_id)
    if not project:
        return None, []
    enterprise = (
        await db.get(Enterprise, project.enterprise_id)
        if project.enterprise_id
        else None
    )
    industry = (
        await db.get(Industry, enterprise.industry_id)
        if enterprise and enterprise.industry_id
        else None
    )
    keywords = [
        project.title,
        str(project.audit_scope or ""),
        enterprise.name if enterprise else None,
        industry.name if industry else None,
        industry.description if industry else None,
    ]
    return (
        enterprise.name if enterprise else None,
        [str(value) for value in keywords if value],
    )


def document_dict(item: ProjectDocument, chunk_count: int | None = None) -> dict[str, Any]:
    if chunk_count is None and "chunks" in item.__dict__:
        chunk_count = len(item.chunks)
    return {
        "id": str(item.id),
        "project_id": str(item.project_id),
        "title": item.title,
        "file_name": item.original_filename,
        "filename": item.original_filename,
        "category": item.document_type,
        "status": item.status,
        "parse_status": item.status,
        "file_size": item.file_size,
        "size": item.file_size,
        "metadata": item.document_metadata or {},
        "parse_error": item.parse_error,
        "parsed_at": item.parsed_at,
        "created_at": item.created_at,
        "chunk_count": chunk_count,
    }


def draft_dict(item: AiDraftRecord) -> dict[str, Any]:
    quality = item.quality or {}
    return {"id": str(item.id), "session_id": str(item.session_id), "submission_id": str(item.submission_id) if item.submission_id else None, "area_record_id": str(item.area_record_id) if item.area_record_id else None, "plan_item_id": str(item.plan_item_id) if item.plan_item_id else None, "clause_refs": item.clause_refs or [], "primary_clause_no": item.primary_clause_no, "certification_system": item.certification_system, "evaluation": item.evaluation, "finding_text": item.finding_text, "record_payload": item.record_payload or {}, "quality": quality, "reasoning": item.reasoning, "confidence": float(item.confidence or 0), "citations": item.citations or [], "status": item.status, "model_status": quality.get("model_status") or "ok", "confirmed_record_item_id": str(item.confirmed_record_item_id) if item.confirmed_record_item_id else None, "created_at": item.created_at}


def _manual_records_from_session(session: AiAuditSession) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for submission in getattr(session, "submissions", []) or []:
        snapshot = getattr(submission, "source_snapshot", None) or {}
        manual_record = snapshot.get("manual_record")
        if not isinstance(manual_record, dict):
            continue
        value = {**manual_record}
        value.setdefault("submission_id", str(submission.id))
        records.append(value)
    return records


async def _sync_inspection_task_status(
    db: AsyncSession,
    plan_item: AuditPlanItem | None,
    status: str,
    at: datetime | None = None,
) -> InspectionTask | None:
    """Keep the legacy task projection aligned with the formal plan item."""

    if not plan_item or not plan_item.inspection_task_id:
        return None
    task = await db.get(InspectionTask, plan_item.inspection_task_id)
    if not task:
        return None
    changed_at = at or datetime.now(timezone.utc)
    task.status = status
    if status == "in_progress":
        task.started_at = task.started_at or changed_at
        task.completed_at = None
    elif status == "completed":
        task.started_at = task.started_at or changed_at
        task.completed_at = changed_at
    return task


def _draft_clause_key(draft: AiDraftRecord) -> str:
    """Stable identity for one audit clause within a session (template item preferred)."""
    payload = draft.record_payload or {}
    template_item_id = str(payload.get("template_item_id") or "").strip()
    if template_item_id:
        return f"ti:{template_item_id}"
    clause = str(draft.primary_clause_no or "").strip()
    return f"cl:{clause}" if clause else f"id:{draft.id}"


def _candidate_clause_key(candidate: EvidenceCandidate) -> str:
    template_item_id = str(candidate.template_item_id or "").strip()
    if template_item_id:
        return f"ti:{template_item_id}"
    clause = str(candidate.clause_no or "").strip()
    return f"cl:{clause}" if clause else f"cand:{id(candidate)}"


def _draft_keep_score(draft: AiDraftRecord) -> tuple:
    """Prefer non-fallback, higher confidence, then newer when de-duplicating."""
    quality = draft.quality or {}
    is_fallback = 1 if quality.get("model_status") == "fallback" else 0
    confidence = float(draft.confidence or 0)
    created = draft.created_at.timestamp() if draft.created_at else 0.0
    return (-is_fallback, confidence, created)


def _supersede_draft(draft: AiDraftRecord, reason: str) -> None:
    draft.status = "superseded"
    draft.rejected_reason = reason


def _dedupe_session_pending_drafts(session: AiAuditSession) -> int:
    """Collapse historical duplicate pending drafts for the same clause.

    Returns number of drafts marked superseded. Callers must commit if > 0.
    """
    drafts = list(session.drafts or [])
    pending = [d for d in drafts if d.status == "draft"]
    confirmed_keys = {_draft_clause_key(d) for d in drafts if d.status == "confirmed"}
    superseded = 0

    # Pending drafts for already-confirmed clauses are obsolete
    for draft in pending:
        key = _draft_clause_key(draft)
        if key in confirmed_keys:
            _supersede_draft(draft, "该条款已确认采纳，清除重复待确认草稿")
            superseded += 1

    pending = [d for d in drafts if d.status == "draft"]
    by_key: dict[str, list[AiDraftRecord]] = {}
    for draft in pending:
        by_key.setdefault(_draft_clause_key(draft), []).append(draft)

    for key, items in by_key.items():
        if len(items) <= 1:
            continue
        ranked = sorted(items, key=_draft_keep_score, reverse=True)
        for old in ranked[1:]:
            _supersede_draft(old, "同条款存在重复待确认草稿，已保留更优/更新的一条")
            superseded += 1
    return superseded


def session_dict(item: AiAuditSession, include_children: bool = False) -> dict[str, Any]:
    context = item.context_snapshot or {}
    value = {"id": str(item.id), "project_id": str(item.project_id), "conversation_id": str(item.conversation_id) if item.conversation_id else None, "title": item.title, "status": item.status, "context_snapshot": context, "model_provider": item.model_provider, "model_name": item.model_name, "created_by": str(item.created_by), "started_at": item.started_at, "completed_at": item.completed_at, "created_at": item.created_at, "updated_at": item.updated_at, "manual_record_count": int(context.get("manual_record_count") or 0)}
    if include_children:
        # Only surface active review items; superseded/rejected stay in DB for audit trail
        visible_drafts = [d for d in item.drafts if d.status in {"draft", "confirmed"}]
        manual_records = _manual_records_from_session(item)
        value["drafts"] = [draft_dict(draft) for draft in visible_drafts]
        value["submissions"] = [{"id": str(submission.id), "status": submission.status, "description": submission.description, "source_files": submission.source_files or [], "submitted_at": submission.submitted_at} for submission in item.submissions]
        confirmed = sum(1 for draft in visible_drafts if draft.status == "confirmed")
        pending = sum(1 for draft in visible_drafts if draft.status == "draft")
        manual_count = len(manual_records)
        active_total = confirmed + manual_count + pending
        if item.status == "completed":
            progress = 100
        elif active_total == 0:
            progress = 0
        else:
            progress = round((confirmed + manual_count) * 100 / max(active_total, 1))
        value["progress"] = progress
        # 仅统计待确认中的 fallback，避免历史回退草稿继续吓人
        fallback_count = sum(
            1 for draft in visible_drafts
            if draft.status == "draft" and (draft.quality or {}).get("model_status") == "fallback"
        )
        value["model_status"] = "fallback" if fallback_count else "ok"
        value["fallback_draft_count"] = fallback_count
        if fallback_count:
            value["model_status_message"] = f"有 {fallback_count} 条草稿因 AI 模型异常为保守回退结果，需人工复核"
        value["pending_clause_count"] = pending
        value["confirmed_clause_count"] = confirmed
        value["manual_records"] = manual_records
        value["manual_record_count"] = manual_count
        value["confirmed_record_count"] = confirmed + manual_count
    return value


def artifact_dict(item: ProjectArtifact) -> dict[str, Any]:
    available = (
        item.status == "ready" and resolve_storage_path(item.path) is not None
    )
    return {"id": str(item.id), "project_id": str(item.project_id), "type": item.artifact_type, "artifact_type": item.artifact_type, "name": item.filename, "file_name": item.filename, "status": item.status, "progress": item.progress, "error_message": item.error_message, "metadata": item.artifact_metadata or {}, "version": item.version, "file_size": item.file_size, "size": item.file_size, "mime_type": item.mime_type, "available": available, "generated_at": item.created_at, "created_at": item.created_at, "updated_at": item.updated_at}


async def _run_artifact_generation(job_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(ProjectArtifact, job_id)
        if not job or job.artifact_type != "generation_job":
            return
        try:
            job.status = "generating"
            job.progress = 1
            job.error_message = None
            await db.commit()

            metadata = job.artifact_metadata or {}
            artifact_types = list(metadata.get("artifact_types") or [])
            quality = await project_artifact_service.quality_check(db, job.project_id)
            if not quality["passed"]:
                raise ValueError("完整性和一致性检查未通过")

            artifact_ids: list[str] = []
            total = max(1, len(artifact_types))
            for index, artifact_type in enumerate(artifact_types, start=1):
                if artifact_type == "package":
                    generated = [
                        await project_artifact_service.generate_package(
                            db,
                            job.project_id,
                            job.created_by,
                        )
                    ]
                else:
                    generated = await project_artifact_service.generate(
                        db,
                        job.project_id,
                        [artifact_type],
                        job.created_by,
                        UUID(metadata["area_record_id"])
                        if metadata.get("area_record_id")
                        else None,
                    )
                artifact_ids.extend(str(item.id) for item in generated)
                job = await db.get(ProjectArtifact, job_id)
                job.progress = round(index / total * 100)
                job.artifact_metadata = {
                    **metadata,
                    "artifact_ids": artifact_ids,
                }
                await db.commit()

            job = await db.get(ProjectArtifact, job_id)
            job.status = "completed"
            job.progress = 100
            await db.commit()
        except Exception as exc:
            await db.rollback()
            job = await db.get(ProjectArtifact, job_id)
            if job:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
                await db.commit()


@router.get("/{project_id}/documents")
async def list_documents(project_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List project materials for UI — lightweight, no chunk bodies/embeddings."""
    await ensure_project_access(db, project_id, current_user)

    # Do NOT selectinload chunks: each chunk stores full text + embedding JSON.
    # Loading them makes this endpoint multi-second even for a handful of docs.
    # Also defer extracted_text (can be 100KB+ per file) — list UI never shows it.
    result = await db.execute(
        select(ProjectDocument)
        .where(
            ProjectDocument.project_id == project_id,
            ProjectDocument.is_deleted == False,  # noqa: E712
        )
        .options(defer(ProjectDocument.extracted_text))
        .order_by(ProjectDocument.created_at.desc())
    )
    documents = list(result.scalars().all())
    if not documents:
        return response([])

    count_result = await db.execute(
        select(
            ProjectKnowledgeChunk.document_id,
            func.count(ProjectKnowledgeChunk.id),
        )
        .where(
            ProjectKnowledgeChunk.project_id == project_id,
            ProjectKnowledgeChunk.document_id.in_([doc.id for doc in documents]),
        )
        .group_by(ProjectKnowledgeChunk.document_id)
    )
    chunk_counts = {row[0]: int(row[1]) for row in count_result.all()}

    return response([
        document_dict(item, chunk_count=chunk_counts.get(item.id, 0))
        for item in documents
    ])


@router.post("/{project_id}/documents")
async def upload_document(
    project_id: UUID,
    file: UploadFile = File(...),
    category: str = Form("auto"),
    force_index: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await ensure_project_access(db, project_id, current_user)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(content) > settings.PROJECT_DOCUMENT_MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件超过允许大小")
    filename = Path(file.filename or "project-document").name
    # 落盘前校验扩展名与真实文件头。原先直接写盘、把类型判断留给解析器，
    # 等于任何类型的文件都能先进 uploads/ 目录。
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_PROJECT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的项目资料格式: {extension or '未知'}",
        )
    enforce_magic_bytes(content, extension)
    directory = Path(settings.UPLOAD_DIR) / "audit_projects" / str(project_id) / "documents"
    directory.mkdir(parents=True, exist_ok=True)
    stored_name = f"{hashlib.sha256(content).hexdigest()[:16]}_{filename}"
    stored_path = directory / stored_name
    stored_path.write_bytes(content)
    document = ProjectDocument(project_id=project_id, title=Path(filename).stem, document_type=category or "auto", original_filename=filename, stored_path=storage_key(stored_path), mime_type=file.content_type, file_size=len(content), checksum_sha256=hashlib.sha256(content).hexdigest(), status="uploaded", created_by=current_user.id)
    db.add(document); await db.commit(); await db.refresh(document)
    try:
        enterprise_name, industry_keywords = await _document_project_context(
            db, project_id
        )
        stats = await project_knowledge_service.index_document(
            db,
            document,
            content,
            expected_enterprise_name=enterprise_name,
            expected_industry_keywords=industry_keywords,
            force_index=force_index,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"资料已保存但解析失败: {exc}") from exc
    await db.refresh(document)
    msg = "初审提示：文档可能与当前项目特征存在差异，已暂停自动索引" if stats.get("requires_confirmation") else "项目资料已上传并索引"
    return response({**document_dict(document), **stats}, msg)


@router.delete("/{project_id}/documents/{document_id}")
async def delete_document(project_id: UUID, document_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除项目资料（软删除，保留文件以备审计）"""
    from app.utils.soft_delete import soft_delete

    await ensure_project_access(db, project_id, current_user, require_manage=True)
    document = await db.get(ProjectDocument, document_id)
    if not document or document.project_id != project_id or document.is_deleted:
        raise HTTPException(status_code=404, detail="项目资料不存在")
    await soft_delete(db, document)
    await db.commit()
    # 保留物理文件以便审计追溯，不再 unlink
    return response({"id": str(document_id)}, "项目资料已删除")


@router.post("/{project_id}/documents/{document_id}/reindex")
async def reindex_document(project_id: UUID, document_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user)
    document = await db.get(ProjectDocument, document_id)
    if not document or document.project_id != project_id or document.is_deleted: raise HTTPException(status_code=404, detail="项目资料不存在")
    path = resolve_storage_path(document.stored_path)
    if not path: raise HTTPException(status_code=404, detail="原始文件不存在")
    enterprise_name, industry_keywords = await _document_project_context(
        db, project_id
    )
    return response(
        await project_knowledge_service.index_document(
            db,
            document,
            path.read_bytes(),
            expected_enterprise_name=enterprise_name,
            expected_industry_keywords=industry_keywords,
            force_index=True,
        ),
        "索引已重建",
    )


@router.post("/{project_id}/documents/{document_id}/confirm_index")
async def confirm_document_index(
    project_id: UUID,
    document_id: UUID,
    payload: dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await ensure_project_access(db, project_id, current_user)
    document = await db.get(ProjectDocument, document_id)
    if not document or document.project_id != project_id or document.is_deleted:
        raise HTTPException(status_code=404, detail="项目资料不存在")
    action = payload.get("action", "index")
    if action == "archive_only":
        document.document_metadata = {
            **(document.document_metadata or {}),
            "quarantined": True,
            "searchable": False,
            "pending_confirmation": False,
            "archive_only": True,
        }
        await db.execute(
            delete(ProjectKnowledgeChunk).where(
                ProjectKnowledgeChunk.document_id == document.id
            )
        )
        await db.commit()
        return response(
            {
                "document_id": str(document.id),
                "chunk_count": 0,
                "status": document.status,
                "archive_only": True,
                "quarantined": True,
            },
            "已设置为仅归档资料",
        )

    # 强制建立索引
    path = resolve_storage_path(document.stored_path)
    if not path:
        raise HTTPException(status_code=404, detail="原始文件不存在")
    enterprise_name, industry_keywords = await _document_project_context(
        db, project_id
    )
    stats = await project_knowledge_service.index_document(
        db,
        document,
        path.read_bytes(),
        expected_enterprise_name=enterprise_name,
        expected_industry_keywords=industry_keywords,
        force_index=True,
    )
    return response(stats, "已确认并完成知识向量索引")


@router.post("/{project_id}/knowledge/search")
async def search_project_knowledge(project_id: UUID, payload: dict[str, Any] = Body(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user)
    query = str(payload.get("query") or "").strip()
    if not query: raise HTTPException(status_code=422, detail="请输入检索内容")
    top_k = max(1, min(20, int(payload.get("top_k") or payload.get("limit") or 5)))
    return response(
        await project_knowledge_service.search_combined(
            db, project_id, query, top_k
        )
    )


@router.get("/{project_id}/sessions")
async def list_sessions(project_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user)
    result = await db.execute(select(AiAuditSession).where(AiAuditSession.project_id == project_id).order_by(AiAuditSession.updated_at.desc()))
    return response([session_dict(item) for item in result.scalars().all()])


@router.post("/{project_id}/sessions")
async def create_session(project_id: UUID, payload: AuditSessionCreateRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user)
    context: dict[str, Any] = {"focus": payload.focus}
    area_record_id = payload.area_record_id
    reaudit = bool(payload.reaudit)
    plan_item: AuditPlanItem | None = None
    if payload.plan_item_id:
        plan_item = await db.get(AuditPlanItem, payload.plan_item_id)
        if not plan_item or plan_item.project_id != project_id: raise HTTPException(status_code=404, detail="审核计划项不存在")
        # 已完成任务发起重新审核：计划项回到进行中
        if reaudit or plan_item.status == "completed":
            reaudit = True
            plan_item.status = "in_progress"
            context["reaudit"] = True
            context["reaudit_from_status"] = "completed"
        context.update({"plan_item_id": str(plan_item.id), "area_name": plan_item.area_name, "template_id": str(plan_item.template_id) if plan_item.template_id else None, "clauses": plan_item.clauses or [], "certification_systems": plan_item.certification_systems or []})
        if not area_record_id:
            # 修复 MultipleResultsFound：一个 plan_item 可能对应多条 area_record，取最新的 draft 记录
            existing = (await db.execute(select(AuditAreaRecord).where(AuditAreaRecord.project_id == project_id, AuditAreaRecord.plan_item_id == plan_item.id).order_by(AuditAreaRecord.created_at.desc()).limit(1))).scalars().first()
            if existing and not reaudit:
                area_record_id = existing.id
            elif existing and reaudit and existing.status not in {"submitted", "completed"}:
                # 仍有未提交区域记录，复用
                area_record_id = existing.id
                if existing.status == "draft":
                    pass
                else:
                    existing.status = "in_progress"
            else:
                area = (await db.execute(select(AuditArea).where(AuditArea.project_id == project_id, AuditArea.area_name == plan_item.area_name))).scalar_one_or_none()
                if not area:
                    area = AuditArea(
                        project_id=project_id,
                        area_name=plan_item.area_name,
                        area_type=plan_item.area_type,
                        responsible_team_member_ids=plan_item.assigned_member_ids or [],
                        audit_clauses=plan_item.clauses or [],
                        status="in_progress",
                    )
                    db.add(area)
                    await db.flush()
                else:
                    area.status = "in_progress"
                # 重新审核时新建一轮区域记录，保留历史 submitted 记录
                record_suffix = datetime.now(timezone.utc).strftime("%H%M%S") if reaudit else str(plan_item.id)[:8]
                area_record = AuditAreaRecord(
                    project_id=project_id,
                    area_id=area.id,
                    plan_item_id=plan_item.id,
                    record_no=f"AR-{record_suffix}",
                    template_id=plan_item.template_id,
                    certification_systems=plan_item.certification_systems or [],
                    recorded_by=current_user.id,
                    audit_date=plan_item.plan_date,
                    audit_time_start=plan_item.time_start,
                    audit_time_end=plan_item.time_end,
                    status="draft",
                )
                db.add(area_record)
                await db.flush()
                area_record_id = area_record.id
                if not reaudit:
                    plan_item.status = "in_progress"
        elif plan_item.status in {"pending", "completed"}:
            plan_item.status = "in_progress"
    if area_record_id:
        area_record = await db.get(AuditAreaRecord, area_record_id)
        if not area_record or area_record.project_id != project_id:
            raise HTTPException(status_code=404, detail="审核区域记录不存在")
        if payload.plan_item_id and area_record.plan_item_id != payload.plan_item_id:
            raise HTTPException(status_code=409, detail="区域记录与审核计划项不匹配")
        if reaudit and area_record.status in {"submitted", "completed"}:
            area_record.status = "in_progress"
        context["area_record_id"] = str(area_record_id)
        if not plan_item and area_record.plan_item_id:
            plan_item = await db.get(AuditPlanItem, area_record.plan_item_id)
            if plan_item:
                context.update({
                    "plan_item_id": str(plan_item.id),
                    "area_name": plan_item.area_name,
                    "template_id": str(plan_item.template_id) if plan_item.template_id else None,
                    "clauses": plan_item.clauses or [],
                    "certification_systems": plan_item.certification_systems or [],
                })
    await _sync_inspection_task_status(db, plan_item, "in_progress")
    title = payload.title or "AI 现场审核"
    if reaudit and title and "重新" not in title:
        title = f"{title}（重新审核）"
    session = AiAuditSession(project_id=project_id, title=title, status="active", context_snapshot=context, model_provider=settings.LLM_PROVIDER, model_name=settings.LLM_MODEL, prompt_version="project-agent-v2", created_by=current_user.id)
    db.add(session); await db.commit(); await db.refresh(session)
    return response(session_dict(session), "重新审核会话已创建" if reaudit else "审核会话已创建")


async def _load_session(db: AsyncSession, project_id: UUID, session_id: UUID, children: bool = False) -> AiAuditSession:
    stmt = select(AiAuditSession).where(AiAuditSession.id == session_id, AiAuditSession.project_id == project_id)
    if children: stmt = stmt.options(selectinload(AiAuditSession.drafts), selectinload(AiAuditSession.submissions))
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item: raise HTTPException(status_code=404, detail="审核会话不存在")
    return item


def _ensure_can_confirm_session(session: AiAuditSession, user: User) -> None:
    """确认 AI 草稿 = 生成有法律效力的正式记录，需限定执行人。

    项目成员之间不应互相确认对方的 AI 草稿（审核职责分离）。
    平台管理角色保留兜底权限。
    """
    if user.role in PRIVILEGED_ROLES:
        return
    if session.created_by and str(session.created_by) == str(user.id):
        return
    raise HTTPException(status_code=403, detail="只能确认本人发起的审核会话草稿")


@router.get("/{project_id}/sessions/{session_id}")
async def get_session(project_id: UUID, session_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user)
    item = await _load_session(db, project_id, session_id, True)
    # 历史多次生成会堆积同条款草稿；打开会话时自动折叠
    if _dedupe_session_pending_drafts(item):
        await db.commit()
        item = await _load_session(db, project_id, session_id, True)
    value = session_dict(item, True)
    quality = await _session_quality(item, db)
    value["quality_check"] = quality
    if quality.get("template_total_items", 0) > 0:
        total_items = quality["template_total_items"]
        covered_items = quality.get("template_covered_items", 0)
        value["progress"] = 100 if item.status == "completed" else round((covered_items / total_items) * 100)
    return response(value)


@router.post("/{project_id}/sessions/{session_id}/media")
async def upload_session_media(
    project_id: UUID,
    session_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await ensure_project_access(db, project_id, current_user)
    await _load_session(db, project_id, session_id)
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="现场证据仅支持图片文件")

    stored_name, file_path, file_size = await save_upload_file(
        file, f"audit_projects/{project_id}/sessions/{session_id}"
    )
    media = MediaFile(
        project_id=project_id,
        audit_session_id=session_id,
        file_type="image",
        original_name=file.filename,
        stored_name=stored_name,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type,
        uploaded_by=current_user.id,
    )
    db.add(media)
    await db.commit()
    await db.refresh(media)
    return response(
        {
            "id": str(media.id),
            "project_id": str(project_id),
            "session_id": str(session_id),
            "file_name": media.original_name,
            "file_path": media.file_path,
            "mime_type": media.mime_type,
            "file_size": media.file_size,
        },
        "现场证据照片已上传",
    )


async def _candidates(db: AsyncSession, project_id: UUID, session: AiAuditSession, ids: list[UUID]) -> list[EvidenceCandidate]:
    """构建多条款候选。

    优先使用 clause_no / standard_ref；若模板未填条款号，则用检查项标题兜底，
    避免「有模板但生成 0 条草稿」的空结果。
    """
    context = session.context_snapshot or {}
    stmt = select(TemplateItem).where(
        TemplateItem.is_category.is_not(True),
        TemplateItem.is_deleted == False,  # noqa: E712
    )
    if ids:
        stmt = stmt.where(TemplateItem.id.in_(ids))
    elif context.get("template_id"):
        stmt = stmt.where(TemplateItem.template_id == UUID(context["template_id"]))
    else:
        return [
            EvidenceCandidate(
                None,
                None,
                str(clause),
                str(clause),
                certification_system=(context.get("certification_systems") or [None])[0],
            )
            for clause in context.get("clauses", [])
        ]
    # 分类目录（存在有效子节点的父节点）不参与条款候选，统一走 app/utils/category
    parent_ids = await load_parent_ids(db)
    items = [
        i
        for i in (await db.execute(stmt.order_by(TemplateItem.sort_order))).scalars().all()
        if not is_category_node(i, parent_ids)
    ]
    candidates: list[EvidenceCandidate] = []
    for item in items:
        clause_no = (item.clause_no or "").strip()
        standard_ref = (item.standard_ref or "").strip()
        title = (item.title or "").strip()

        # 优先提取具体条款号（例如标题 "*1.3 卫生间..." 提取 "1.3"）
        if not clause_no and title:
            m = re.match(r"^[\*\s]*(\d+(?:\.\d+)*)", title)
            if m:
                clause_no = m.group(1)

        if clause_no:
            clause_key = f"{standard_ref} {clause_no}".strip() if standard_ref else clause_no
        elif standard_ref and title:
            clause_key = f"{standard_ref} {title[:20]}".strip()
        elif title:
            clause_key = title[:30]
        else:
            clause_key = str(item.id)

        if not clause_key:
            continue
        systems = item.applicable_systems or [None]
        candidates.append(
            EvidenceCandidate(
                str(item.id),
                str(item.id),
                clause_key,
                item.title or clause_key,
                item.description or "",
                item.check_method or "",
                item.evidence_hint or "",
                item.risk_level or "medium",
                bool(item.attachment_required),
                systems[0] if systems else None,
            )
        )
    return candidates


@router.post("/{project_id}/sessions/{session_id}/evidence")
async def submit_evidence(project_id: UUID, session_id: UUID, payload: EvidenceSubmitRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user); session = await _load_session(db, project_id, session_id)
    context = session.context_snapshot or {}; area_record_id = UUID(context["area_record_id"]) if context.get("area_record_id") else None; plan_item_id = UUID(context["plan_item_id"]) if context.get("plan_item_id") else None
    if not area_record_id or not plan_item_id:
        raise HTTPException(
            status_code=409,
            detail="正式审核证据必须关联审核计划项和区域记录",
        )
    media_rows = []
    if payload.media_file_ids:
        media_rows = (await db.execute(select(MediaFile).where(
            MediaFile.id.in_(payload.media_file_ids),
            MediaFile.uploaded_by == current_user.id,
            MediaFile.project_id == project_id,
            MediaFile.audit_session_id == session.id,
        ))).scalars().all()
        if len(media_rows) != len(set(payload.media_file_ids)):
            raise HTTPException(status_code=400, detail="包含不属于当前项目会话的证据文件")
    submission = EvidenceSubmission(project_id=project_id, session_id=session.id, area_record_id=area_record_id, plan_item_id=plan_item_id, submitted_by=current_user.id, input_type=payload.evidence_type, description=payload.content, source_files=[{"id": str(item.id), "name": item.original_name, "path": item.file_path, "mime_type": item.mime_type} for item in media_rows], source_snapshot={"input": payload.source_metadata}, status="processing")
    db.add(submission); await db.flush()
    evidence_item = EvidenceItem(project_id=project_id, submission_id=submission.id, sequence_no=0, evidence_type="text", content=payload.content, item_metadata=payload.source_metadata)
    db.add(evidence_item); await db.flush()
    for index, media in enumerate(media_rows, start=1): db.add(EvidenceItem(project_id=project_id, submission_id=submission.id, sequence_no=index, evidence_type="photo", content=media.original_name or "现场照片", file_path=media.file_path, filename=media.original_name, mime_type=media.mime_type, item_metadata={"media_file_id": str(media.id)}))
    candidates = evidence_agent_service.rank_candidates(payload.content, await _candidates(db, project_id, session, payload.candidate_item_ids))
    citations = await project_knowledge_service.search_combined(
        db, project_id, payload.content, 8
    )
    if not candidates:
        raise HTTPException(
            status_code=422,
            detail="当前审核计划未绑定可用检查项（或模板无检查项），无法生成多条款 AI 记录。请在计划中绑定带检查项的模板。",
        )

    # 多模态融合（#7）：先用视觉模型分析随证据一起提交的现场照片，
    # 把识别出的问题作为客观证据的一部分喂进多条款判定，而不是仅存为附件。
    photo_findings: list[dict[str, Any]] = []
    for media in media_rows:
        if not (media.mime_type or "").startswith("image/"):
            continue
        try:
            pa = await multimodal_service.analyze_photo(
                str(media.id), db, analysis_type="compliance"
            )
            if isinstance(pa, dict) and not pa.get("error"):
                photo_findings.append({
                    "media_file_id": str(media.id),
                    "filename": media.original_name,
                    "description": pa.get("description", ""),
                    "issues": pa.get("issues", []),
                })
        except Exception as exc:  # 照片分析失败不阻断文字判定
            print(f"[Evidence] photo analysis skipped for {media.id}: {exc}")

    # 反馈回流（#1）：取该体系近期被拒绝的判定作为负面 few-shot
    systems = {c.certification_system for c in candidates if getattr(c, "certification_system", None)}
    feedback_hints = await agent_feedback_service.few_shot_examples(
        db, certification_system=next(iter(systems), None), limit=3
    )

    results = await evidence_agent_service.analyze(
        payload.content,
        candidates,
        citations,
        db=db,
        user_id=str(current_user.id),
        photo_findings=photo_findings or None,
        feedback_hints=feedback_hints or None,
    )

    # Load existing drafts so re-generation supersedes same-clause history instead of stacking
    existing_drafts = (
        await db.execute(
            select(AiDraftRecord).where(AiDraftRecord.session_id == session.id)
        )
    ).scalars().all()
    confirmed_keys = {_draft_clause_key(d) for d in existing_drafts if d.status == "confirmed"}
    pending_by_key: dict[str, list[AiDraftRecord]] = {}
    for old in existing_drafts:
        if old.status == "draft":
            pending_by_key.setdefault(_draft_clause_key(old), []).append(old)

    drafts: list[AiDraftRecord] = []
    skipped_confirmed = 0
    new_keys: set[str] = set()
    for result in results:
        candidate = result["candidate"]
        clause_key = _candidate_clause_key(candidate)
        if clause_key in confirmed_keys:
            skipped_confirmed += 1
            continue
        evaluation = result["evaluation_3level"]
        draft = AiDraftRecord(
            project_id=project_id,
            session_id=session.id,
            submission_id=submission.id,
            area_record_id=area_record_id,
            plan_item_id=plan_item_id,
            evidence_item_ids=[evidence_item.id],
            clause_refs=[{
                "clause_no": candidate.clause_no,
                "title": candidate.title,
                "certification_system": candidate.certification_system,
                "rank": len(drafts) + 1,
            }],
            primary_clause_no=candidate.clause_no,
            certification_system=candidate.certification_system,
            evaluation=evaluation,
            finding_text=result["audit_findings"] or payload.content,
            record_payload={
                "template_item_id": candidate.template_item_id,
                "item_title": candidate.title,
                "audit_evidence": payload.content,
                "evaluation_3level": evaluation,
                "audit_findings": result["audit_findings"],
                "rectification_suggestion": result["rectification_suggestion"],
                "risk_level": candidate.risk_level,
                "attachment_required": candidate.attachment_required,
                "attachment_count": len(media_rows),
                "photo_paths": [media.file_path for media in media_rows],
            },
            quality={
                "level": result["evidence_quality"],
                "risk_level": candidate.risk_level,
                "attachment_required": candidate.attachment_required,
                "attachment_missing": candidate.attachment_required and not media_rows,
                "model_status": result.get("model_status") or "ok",
            },
            reasoning=result["reasoning"] or "需要人工确认",
            confidence=result["confidence"],
            citations=result["citations"],
            source_snapshot={
                "evidence": payload.content,
                "citations": result["citations"],
                "model_status": result.get("model_status") or "ok",
            },
            status="draft",
            model_provider=settings.LLM_PROVIDER,
            model_name=settings.LLM_MODEL,
            # 溯源：版本号与 call log id 均由分析服务随结果返回，
            # 不再在这里硬编码字面量（硬编码会与真实提示词脱节）。
            prompt_version=result.get("_prompt_version")
            or evidence_agent_service.prompt_fingerprint(),
            llm_call_log_id=result.get("_llm_call_log_id"),
        )
        db.add(draft)
        drafts.append(draft)
        new_keys.add(clause_key)

    superseded_count = 0
    for key in new_keys:
        for old in pending_by_key.get(key, []):
            _supersede_draft(old, "已被新一轮 AI 分析结果替代")
            superseded_count += 1

    submission.status = "completed"
    submission.processed_at = datetime.now(timezone.utc)
    await db.commit()

    fallback_count = sum(1 for r in drafts if (r.quality or {}).get("model_status") == "fallback")
    message = f"已生成 {len(drafts)} 条待确认记录"
    if superseded_count:
        message += f"（已替换 {superseded_count} 条同条款旧草稿）"
    if skipped_confirmed:
        message += f"（跳过 {skipped_confirmed} 条已确认条款）"
    if fallback_count:
        message += f"（其中 {fallback_count} 条因模型异常为保守回退结果，需人工复核）"
    return response(
        {
            "submission_id": str(submission.id),
            "drafts": [draft_dict(item) for item in drafts],
            "fallback_count": fallback_count,
            "superseded_count": superseded_count,
            "skipped_confirmed": skipped_confirmed,
        },
        message,
    )


@router.post("/{project_id}/sessions/{session_id}/records/manual")
async def create_manual_record(
    project_id: UUID,
    session_id: UUID,
    payload: ManualRecordCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist a human-authored record without invoking the LLM."""

    await ensure_project_access(db, project_id, current_user)
    session = await _load_session(db, project_id, session_id)
    if session.status == "completed":
        raise HTTPException(status_code=409, detail="审核会话已提交，不能新增手工记录")

    context = session.context_snapshot or {}
    area_record_id = UUID(context["area_record_id"]) if context.get("area_record_id") else None
    plan_item_id = UUID(context["plan_item_id"]) if context.get("plan_item_id") else None
    if not area_record_id or not plan_item_id:
        raise HTTPException(status_code=409, detail="手工审核记录必须关联审核计划项和区域记录")

    area_record = await db.get(AuditAreaRecord, area_record_id)
    plan_item = await db.get(AuditPlanItem, plan_item_id)
    if not area_record or area_record.project_id != project_id:
        raise HTTPException(status_code=409, detail="审核区域记录不存在或不属于当前项目")
    if not plan_item or plan_item.project_id != project_id or area_record.plan_item_id != plan_item.id:
        raise HTTPException(status_code=409, detail="审核计划项与区域记录不匹配")

    template_item = None
    if payload.template_item_id:
        template_item = await db.get(TemplateItem, payload.template_item_id)
        if not template_item or template_item.is_deleted:
            raise HTTPException(status_code=404, detail="检查模板项目不存在")
        if plan_item.template_id and template_item.template_id != plan_item.template_id:
            raise HTTPException(status_code=400, detail="检查模板项目不属于当前审核计划模板")

    media_rows: list[MediaFile] = []
    if payload.media_file_ids:
        media_rows = (
            await db.execute(
                select(MediaFile).where(
                    MediaFile.id.in_(payload.media_file_ids),
                    MediaFile.uploaded_by == current_user.id,
                    MediaFile.project_id == project_id,
                    MediaFile.audit_session_id == session.id,
                    MediaFile.is_deleted == False,  # noqa: E712
                )
            )
        ).scalars().all()
        if len(media_rows) != len(set(payload.media_file_ids)):
            raise HTTPException(status_code=400, detail="包含不属于当前项目会话的证据文件")

    clauses = payload.resolve_clause_nos()
    clause_text = " / ".join(clauses)
    photo_paths = [media.file_path for media in media_rows]
    now = datetime.now(timezone.utc)
    submission = EvidenceSubmission(
        project_id=project_id,
        session_id=session.id,
        area_record_id=area_record_id,
        plan_item_id=plan_item_id,
        submitted_by=current_user.id,
        input_type="mixed" if media_rows else "text",
        title=payload.item_title,
        description=payload.audit_evidence,
        source_files=[
            {
                "id": str(media.id),
                "name": media.original_name,
                "path": media.file_path,
                "mime_type": media.mime_type,
            }
            for media in media_rows
        ],
        source_snapshot={},
        status="completed",
        processed_at=now,
    )
    db.add(submission)
    await db.flush()

    evidence_item = EvidenceItem(
        project_id=project_id,
        submission_id=submission.id,
        sequence_no=0,
        evidence_type="text",
        content=payload.audit_evidence,
        item_metadata={
            "manual_record": True,
            "item_title": payload.item_title,
            "clause_nos": clauses,
            "certification_system": payload.certification_system,
            "evaluation_3level": payload.evaluation_3level,
        },
    )
    db.add(evidence_item)
    for index, media in enumerate(media_rows, start=1):
        db.add(
            EvidenceItem(
                project_id=project_id,
                submission_id=submission.id,
                sequence_no=index,
                evidence_type="photo",
                content=media.original_name or "现场照片",
                file_path=media.file_path,
                filename=media.original_name,
                mime_type=media.mime_type,
                item_metadata={"media_file_id": str(media.id), "manual_record": True},
            )
        )

    record_item = InspectionRecordItem(
        audit_area_record_id=area_record_id,
        template_item_id=template_item.id if template_item else None,
        result="fail" if payload.evaluation_3level == "3" else "pass",
        result_text=payload.audit_findings or payload.audit_evidence,
        problem_description=payload.audit_findings,
        rectification_suggestion=payload.rectification_suggestion,
        audit_evidence=payload.audit_evidence,
        evaluation_3level=payload.evaluation_3level,
        audit_findings=payload.audit_findings,
        certification_system=payload.certification_system,
        clause_no_snapshot=clause_text,
        ai_generated=False,
        photos=photo_paths,
        item_title=payload.item_title,
        item_description=template_item.description if template_item else None,
        item_check_method=template_item.check_method if template_item else None,
        item_legal_basis=template_item.legal_basis if template_item else None,
        item_standard_ref=template_item.standard_ref if template_item else None,
        item_risk_level=template_item.risk_level if template_item else None,
        item_check_type="audit_3level",
        item_result_options=template_item.result_options if template_item else None,
        item_allow_attachment=template_item.allow_attachment if template_item else bool(media_rows),
        item_attachment_required=template_item.attachment_required if template_item else False,
        item_use_ai=False,
    )
    db.add(record_item)
    await db.flush()

    nc = None
    if payload.evaluation_3level == "3":
        nc = Nonconformity(
            project_id=project_id,
            plan_item_id=plan_item_id,
            area_record_id=area_record_id,
            record_item_id=record_item.id,
            nc_no=f"MAN-{str(record_item.id)[:8].upper()}",
            severity="minor",
            certification_system=payload.certification_system,
            clause_no=clause_text,
            description=payload.audit_findings or payload.audit_evidence,
            evidence=payload.audit_evidence,
            corrective_action_required=payload.rectification_suggestion or "请分析原因并完成整改",
            status="draft",
            created_by=current_user.id,
        )
        db.add(nc)
        await db.flush()

    manual_record = {
        "id": str(record_item.id),
        "session_id": str(session.id),
        "submission_id": str(submission.id),
        "area_record_id": str(area_record_id),
        "plan_item_id": str(plan_item_id),
        "item_title": payload.item_title,
        "clause_nos": clauses,
        "clause_no": clause_text,
        "certification_system": payload.certification_system,
        "evaluation_3level": payload.evaluation_3level,
        "audit_evidence": payload.audit_evidence,
        "audit_findings": payload.audit_findings,
        "rectification_suggestion": payload.rectification_suggestion,
        "template_item_id": str(template_item.id) if template_item else None,
        "media_file_ids": [str(media.id) for media in media_rows],
        "photos": photo_paths,
        "ai_generated": False,
        "nc_id": str(nc.id) if nc else None,
        "created_at": now.isoformat(),
    }
    submission.source_snapshot = {"manual_record": manual_record}
    session.context_snapshot = {
        **context,
        "manual_record_count": int(context.get("manual_record_count") or 0) + 1,
    }
    if area_record.status == "draft":
        area_record.status = "in_progress"
    plan_item.status = "in_progress"
    await _sync_inspection_task_status(db, plan_item, "in_progress", now)
    await db.commit()
    return response(manual_record, "手工审核记录已保存")


async def _session_quality(session: AiAuditSession, db: AsyncSession | None = None) -> dict[str, Any]:
    blockers = []
    warnings = []
    confirmed_ai_count = sum(1 for draft in (session.drafts or []) if draft.status == "confirmed")
    manual_record_count = len(_manual_records_from_session(session))
    if confirmed_ai_count + manual_record_count == 0:
        blockers.append({"code": "NO_CONFIRMED_RECORDS", "message": "尚未形成已确认 AI 记录或手工审核记录"})
    for draft in (session.drafts or []):
        if draft.status != "draft":
            continue
        risk = str((draft.quality or {}).get("risk_level", "")).lower()
        missing = bool((draft.quality or {}).get("attachment_missing"))
        insufficient = (draft.quality or {}).get("level") == "insufficient"
        if risk in {"high", "a", "高风险"} and insufficient:
            blockers.append({"code": "HIGH_RISK_EVIDENCE", "draft_id": str(draft.id), "message": f"高风险条款 {draft.primary_clause_no} 证据不足"})
        elif missing:
            blockers.append({"code": "ATTACHMENT_REQUIRED", "draft_id": str(draft.id), "message": f"条款 {draft.primary_clause_no} 缺少必传附件"})
        elif str(draft.evaluation) == "3":
            blockers.append({"code": "NC_UNCONFIRMED", "draft_id": str(draft.id), "message": f"不符合条款 {draft.primary_clause_no} 尚未确认"})
        else:
            blockers.append({"code": "DRAFT_PENDING", "draft_id": str(draft.id), "message": f"条款 {draft.primary_clause_no} 尚未确认"})

    # 检查模板检查项完整覆盖率
    template_id = (getattr(session, "context_snapshot", None) or {}).get("template_id")
    total_items_count = 0
    covered_items_count = 0
    uncovered_items = []

    if db and template_id:
        try:
            stmt = select(TemplateItem).where(
                TemplateItem.template_id == UUID(template_id),
                TemplateItem.is_category.is_not(True),
                TemplateItem.is_deleted == False
            ).order_by(TemplateItem.sort_order)
            _parent_ids = await load_parent_ids(db, template_id=UUID(template_id))
            template_items = [
                i
                for i in (await db.execute(stmt)).scalars().all()
                if not is_category_node(i, _parent_ids)
            ]
            total_items_count = len(template_items)

            # 收集所有已确认记录覆盖的 template_item_id
            confirmed_ti_ids = set()
            for draft in (getattr(session, "drafts", []) or []):
                if getattr(draft, "status", None) == "confirmed":
                    ti_id = (getattr(draft, "record_payload", {}) or {}).get("template_item_id")
                    if ti_id:
                        confirmed_ti_ids.add(str(ti_id))
            for sub in (getattr(session, "submissions", []) or []):
                man = (getattr(sub, "source_snapshot", {}) or {}).get("manual_record") or {}
                ti_id = man.get("template_item_id")
                if ti_id:
                    confirmed_ti_ids.add(str(ti_id))

            for ti in template_items:
                if str(ti.id) in confirmed_ti_ids:
                    covered_items_count += 1
                else:
                    uncovered_items.append({
                        "id": str(ti.id),
                        "title": ti.title or "检查项",
                        "is_required": bool(ti.is_required),
                    })

            if total_items_count > 0 and uncovered_items:
                uncovered_names = [it["title"][:20] for it in uncovered_items[:3]]
                more_suffix = f" 等 {len(uncovered_items)} 项" if len(uncovered_items) > 3 else ""
                blockers.append({
                    "code": "ITEMS_INCOMPLETE",
                    "message": f"模板包含 {total_items_count} 项检查，尚有 {len(uncovered_items)} 项未完成审核（未完成：{', '.join(uncovered_names)}{more_suffix}）",
                    "total_items": total_items_count,
                    "covered_items": covered_items_count,
                    "uncovered_items": uncovered_items,
                })
        except Exception as exc:
            print(f"[_session_quality] query template items error: {exc}")
    elif total_items_count == 0 and (confirmed_ai_count + manual_record_count) > 0:
        covered_items_count = confirmed_ai_count + manual_record_count

    return {
        "passed": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "blocking_count": len(blockers),
        "warning_count": len(warnings),
        "confirmed_ai_count": confirmed_ai_count,
        "manual_record_count": manual_record_count,
        "confirmed_record_count": confirmed_ai_count + manual_record_count,
        "template_total_items": total_items_count,
        "template_covered_items": covered_items_count,
        "uncovered_items": uncovered_items,
    }


async def perform_draft_confirmation(
    db: AsyncSession,
    project_id: UUID,
    session_id: UUID,
    payload: DraftConfirmRequest,
    current_user: User,
) -> dict[str, Any]:
    """确认/驳回 AI 草稿的核心能力函数。

    路由与 Agent 动作注册表共用同一份实现，避免同一业务规则出现两份。
    """
    await ensure_project_access(db, project_id, current_user)
    session = await _load_session(db, project_id, session_id, True)

    # 审核职责：确认 AI 草稿会生成有法律效力的正式记录与不符合项，
    # 只允许该会话的发起人本人、项目负责人或平台管理角色执行。
    _ensure_can_confirm_session(session, current_user)

    # 用于把确认的不符合项写入企业级长期记忆（#5）
    _project = await db.get(AuditProject, project_id)
    _project_enterprise_id = _project.enterprise_id if _project else None

    # P1-6 修复：兼容 draft_id 单数误用情况
    resolved_ids = payload.resolve_draft_ids()
    selected = [draft for draft in session.drafts if draft.status == "draft" and (draft.id in resolved_ids or payload.safe_only)]

    # 幂等闸：对候选草稿加行锁并强制刷新状态后再判定。
    # 否则重复点击 / 客户端重试会并发通过 status=="draft" 检查，
    # 生成重复的 InspectionRecordItem 与重复的 Nonconformity。
    if selected:
        locked = (
            await db.execute(
                select(AiDraftRecord)
                .where(AiDraftRecord.id.in_([d.id for d in selected]))
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalars().all()
        still_pending = {d.id for d in locked if d.status == "draft"}
        selected = [d for d in selected if d.id in still_pending]
    if payload.safe_only: selected = [draft for draft in selected if str(draft.evaluation) != "3" and float(draft.confidence or 0) >= .7 and (draft.quality or {}).get("level") == "sufficient" and not (draft.quality or {}).get("attachment_missing") and (draft.quality or {}).get("model_status") != "fallback"]
    overrides = {item.draft_id: item for item in payload.overrides}; confirmed=[]
    for draft in selected:
        if payload.action == "reject": draft.status="rejected"; draft.confirmed_by=current_user.id; draft.confirmed_at=datetime.now(timezone.utc); continue
        override=overrides.get(draft.id); record_payload={**(draft.record_payload or {})}
        # 反馈信号（#1）：审核员对本条草稿做了实质改动则标记 was_edited，
        # 用于区分"AI 直接对 / 半对（被改）"，喂给采纳率统计与提示词回流。
        edited = False
        if override:
            for key in ("evaluation_3level", "audit_evidence", "audit_findings", "rectification_suggestion"):
                value=getattr(override, key)
                if value is not None and value != record_payload.get(key):
                    edited = True
                record_payload[key]=value if value is not None else record_payload.get(key)
        draft.was_edited = edited
        item = InspectionRecordItem(audit_area_record_id=draft.area_record_id, template_item_id=UUID(record_payload["template_item_id"]) if record_payload.get("template_item_id") else None, result="fail" if record_payload.get("evaluation_3level") == "3" else "pass", result_text=record_payload.get("audit_findings") or record_payload.get("audit_evidence"), problem_description=record_payload.get("audit_findings"), rectification_suggestion=record_payload.get("rectification_suggestion"), audit_evidence=record_payload.get("audit_evidence"), evaluation_3level=record_payload.get("evaluation_3level") or draft.evaluation, audit_findings=record_payload.get("audit_findings"), certification_system=draft.certification_system, clause_no_snapshot=draft.primary_clause_no, ai_generated=True, ai_suggestion=draft.reasoning, ai_basis="; ".join(str(c.get("document_title") or c.get("file_name") or "项目资料") for c in draft.citations or []), photos=record_payload.get("photo_paths") or [], item_title=(draft.clause_refs or [{}])[0].get("title"), item_risk_level=record_payload.get("risk_level"), item_check_type="audit_3level", item_attachment_required=record_payload.get("attachment_required"), item_use_ai=True)
        db.add(item); await db.flush(); draft.status="confirmed"; draft.confirmed_by=current_user.id; draft.confirmed_at=datetime.now(timezone.utc); draft.confirmed_record_item_id=item.id; confirmed.append(draft)
        if str(item.evaluation_3level) == "3":
            nc = Nonconformity(project_id=project_id, plan_item_id=draft.plan_item_id, area_record_id=draft.area_record_id, record_item_id=item.id, nc_no=f"AI-{str(draft.id).replace('-', '')[:12].upper()}", severity="minor", certification_system=draft.certification_system, clause_no=draft.primary_clause_no, description=item.audit_findings or item.audit_evidence or "AI 识别的不符合项", evidence=item.audit_evidence, corrective_action_required=item.rectification_suggestion or "请分析原因并完成整改", status="draft", created_by=current_user.id, source_draft_id=draft.id)
            db.add(nc)
            # 长期记忆（#5）：确认的不符合项沉淀为企业级记忆，下次审核该企业时带入简报
            if _project_enterprise_id:
                await agent_memory_service.remember_enterprise(
                    db,
                    enterprise_id=_project_enterprise_id,
                    user_id=current_user.id,
                    content=f"条款 {draft.primary_clause_no or '?'}（{draft.certification_system or ''}）曾判不符合：{(item.audit_findings or item.audit_evidence or '')[:120]}",
                )
    await db.commit()
    return {
        "confirmed": [str(item.id) for item in confirmed],
        "count": len(confirmed),
        "requested_ids": [str(i) for i in resolved_ids],
    }


@router.post("/{project_id}/sessions/{session_id}/drafts/confirm")
async def confirm_drafts(
    project_id: UUID,
    session_id: UUID,
    payload: DraftConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await perform_draft_confirmation(
        db, project_id, session_id, payload, current_user
    )
    return response(result, "AI 草稿已处理")


@router.post("/{project_id}/sessions/{session_id}/quality-check")
async def session_quality(project_id: UUID, session_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user); return response(await _session_quality(await _load_session(db, project_id, session_id, True), db))


@router.post("/{project_id}/sessions/{session_id}/submit")
async def submit_session(project_id: UUID, session_id: UUID, payload: dict[str, Any] = Body(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user); session=await _load_session(db, project_id, session_id, True); check=await _session_quality(session, db)
    if session.status == "completed":
        return response(session_dict(session, True), "审核记录已提交")
    if check["blockers"]: raise HTTPException(status_code=409, detail={"message":"存在阻断项，不能提交","quality_check":check})
    conclusion=str(payload.get("conclusion") or "").strip()
    if not conclusion: raise HTTPException(status_code=422, detail="请填写最终审核结论")
    try:
        completed_at = datetime.now(timezone.utc)
        context={**(session.context_snapshot or {}),"conclusion":conclusion}; session.context_snapshot=context; session.status="completed"; session.completed_at=completed_at
        # P0-7 修复：添加 None 检查，避免 area_record_id 不存在时 record=None 导致 500
        if context.get("area_record_id"):
            record=await db.get(AuditAreaRecord, UUID(context["area_record_id"]))
            if record:
                record.conclusion=conclusion; record.status="submitted"
            else:
                # 区域记录已删除，仅记录日志不阻断提交
                print(f"[submit_session] area_record {context['area_record_id']} not found, skipping")
        if context.get("plan_item_id"):
            plan=await db.get(AuditPlanItem, UUID(context["plan_item_id"]))
            if plan:
                plan.status="completed"
                await _sync_inspection_task_status(db, plan, "completed", completed_at)
            else:
                print(f"[submit_session] plan_item {context['plan_item_id']} not found, skipping")
        # 先 commit 让数据持久化，避免序列化关系时触发 lazy load 绿let 错误
        await db.commit()
        # 重新加载 session 以获取最新状态（包含 drafts/submissions 关系）
        session = await _load_session(db, project_id, session_id, True)
        result = session_dict(session, True)
        return response(result, "审核记录已提交")
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        # 重新加载 session 以避免会话状态污染
        session = await _load_session(db, project_id, session_id, True)
        raise HTTPException(status_code=500, detail=f"提交审核记录失败：{type(exc).__name__}: {str(exc)[:200]}")


@router.post("/{project_id}/nonconformities/{nc_id}/confirm")
async def confirm_nc(project_id: UUID, nc_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user, require_manage=True); nc=await db.get(Nonconformity,nc_id)
    if not nc or nc.project_id != project_id: raise HTTPException(status_code=404, detail="不符合项不存在")
    nc.status="open"; nc.confirmed_by=current_user.id; nc.confirmed_at=datetime.now(timezone.utc); await db.commit(); return response({"id":str(nc.id),"status":nc.status},"不符合项草稿已确认")


@router.post("/{project_id}/quality-check")
async def project_quality(project_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user); return response(await project_artifact_service.quality_check(db, project_id))


@router.get("/{project_id}/artifacts")
async def list_artifacts(project_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user); items=(await db.execute(select(ProjectArtifact).where(ProjectArtifact.project_id==project_id, ProjectArtifact.is_deleted == False, ProjectArtifact.status != "missing").order_by(ProjectArtifact.created_at.desc()))).scalars().all(); return response([artifact_dict(item) for item in items])


@router.post("/{project_id}/artifacts/generate")
async def generate_artifacts(project_id: UUID, payload: ArtifactGenerateRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user, require_manage=True)
    quality = await project_artifact_service.quality_check(db, project_id)
    deliverable_types = set(payload.artifact_types) - {"manifest"}
    if deliverable_types and not quality["passed"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "完整性和一致性检查未通过，不能生成正式审核成果",
                "quality_check": quality,
            },
        )
    version_result = await db.execute(
        select(func.max(ProjectArtifact.version)).where(
            ProjectArtifact.project_id == project_id,
            ProjectArtifact.artifact_type == "generation_job",
        )
    )
    version = (version_result.scalar_one_or_none() or 0) + 1
    job = ProjectArtifact(
        project_id=project_id,
        artifact_type="generation_job",
        path="",
        filename=f"成果生成任务 V{version}",
        mime_type="application/x-efis-generation-job",
        file_size=0,
        version=version,
        artifact_metadata={
            "artifact_types": payload.artifact_types,
            "area_record_id": str(payload.area_record_id)
            if payload.area_record_id
            else None,
            "force": payload.force,
        },
        status="pending",
        progress=0,
        created_by=current_user.id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    background_tasks.add_task(_run_artifact_generation, job.id)
    return response(artifact_dict(job), "审核成果生成任务已创建")


@router.post("/{project_id}/artifacts/{artifact_id}/retry")
async def retry_artifact_generation(
    project_id: UUID,
    artifact_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await ensure_project_access(db, project_id, current_user, require_manage=True)
    job = await db.get(ProjectArtifact, artifact_id)
    if (
        not job
        or job.project_id != project_id
        or job.artifact_type != "generation_job"
        or job.is_deleted
    ):
        raise HTTPException(status_code=404, detail="成果生成任务不存在")
    if job.status != "failed":
        raise HTTPException(status_code=409, detail="仅失败的成果生成任务可以重试")
    quality = await project_artifact_service.quality_check(db, project_id)
    if not quality["passed"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "完整性和一致性检查未通过，不能重试生成",
                "quality_check": quality,
            },
        )
    job.status = "pending"
    job.progress = 0
    job.error_message = None
    await db.commit()
    background_tasks.add_task(_run_artifact_generation, job.id)
    return response(artifact_dict(job), "成果生成任务已重新提交")


@router.get("/{project_id}/artifacts/{artifact_id}/download")
async def download_artifact(project_id: UUID, artifact_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user); item=await db.get(ProjectArtifact,artifact_id)
    if not item or item.project_id != project_id or item.is_deleted: raise HTTPException(status_code=404,detail="成果文件不存在")
    path = resolve_storage_path(item.path)
    if not path: raise HTTPException(status_code=404,detail="成果文件不存在")
    # P0-5 修复：制品下载必须通过质量门禁（与 /package 接口一致）
    # 仅 generation_job 元数据任务文件不强制门禁（用户不会直接下载此类文件）
    if item.artifact_type != "generation_job":
        quality = await project_artifact_service.quality_check(db, project_id)
        if not quality["passed"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "完整性和一致性检查未通过，不能下载正式审核成果",
                    "quality_check": quality,
                },
            )
    return FileResponse(path,media_type=item.mime_type,filename=item.filename)


@router.get("/{project_id}/package")
async def download_package(project_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user, require_manage=True)
    quality = await project_artifact_service.quality_check(db, project_id)
    if not quality["passed"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "完整性和一致性检查未通过，不能生成完整资料包",
                "quality_check": quality,
            },
        )
    items = (
        await db.execute(
            select(ProjectArtifact)
            .where(
                ProjectArtifact.project_id == project_id,
                ProjectArtifact.artifact_type == "package",
                ProjectArtifact.status == "ready",
                ProjectArtifact.is_deleted == False,  # noqa: E712
            )
            .order_by(ProjectArtifact.version.desc())
        )
    ).scalars().all()
    item = None
    path = None
    for candidate in items:
        candidate_path = resolve_storage_path(candidate.path)
        if candidate_path:
            item = candidate
            path = candidate_path
            break
    if not item or not path:
        raise HTTPException(
            status_code=404,
            detail="完整资料包尚未生成，请先创建资料包生成任务",
        )
    return FileResponse(
        path, media_type="application/zip", filename=item.filename
    )
