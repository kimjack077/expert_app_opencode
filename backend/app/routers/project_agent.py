"""Project-scoped formal audit Agent, knowledge and artifact APIs."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.models.audit_project import AuditArea, AuditAreaRecord, AuditPlanItem, Nonconformity
from app.models.evidence_agent import AiAuditSession, AiDraftRecord, EvidenceItem, EvidenceSubmission
from app.models.media import MediaFile
from app.models.project_artifact import ProjectArtifact
from app.models.project_knowledge import ProjectDocument
from app.models.record import InspectionRecordItem
from app.models.template import TemplateItem
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.project_agent import ArtifactGenerateRequest, AuditSessionCreateRequest, DraftConfirmRequest, EvidenceSubmitRequest
from app.services.evidence_agent_service import EvidenceCandidate, evidence_agent_service
from app.services.project_access_service import ensure_project_access
from app.services.project_artifact_service import project_artifact_service
from app.services.project_knowledge_service import project_knowledge_service
from app.utils.file_handler import save_upload_file


router = APIRouter(prefix="/api/audit-projects", tags=["project-agent"])


def response(data: Any = None, message: str = "success") -> dict[str, Any]:
    return {
        "code": 200,
        "message": message,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def document_dict(item: ProjectDocument) -> dict[str, Any]:
    return {"id": str(item.id), "project_id": str(item.project_id), "title": item.title, "file_name": item.original_filename, "filename": item.original_filename, "category": item.document_type, "status": item.status, "parse_status": item.status, "file_size": item.file_size, "size": item.file_size, "metadata": item.document_metadata or {}, "parse_error": item.parse_error, "parsed_at": item.parsed_at, "created_at": item.created_at, "chunk_count": len(item.chunks) if "chunks" in item.__dict__ else None}


def draft_dict(item: AiDraftRecord) -> dict[str, Any]:
    return {"id": str(item.id), "session_id": str(item.session_id), "submission_id": str(item.submission_id) if item.submission_id else None, "area_record_id": str(item.area_record_id) if item.area_record_id else None, "plan_item_id": str(item.plan_item_id) if item.plan_item_id else None, "clause_refs": item.clause_refs or [], "primary_clause_no": item.primary_clause_no, "certification_system": item.certification_system, "evaluation": item.evaluation, "finding_text": item.finding_text, "record_payload": item.record_payload or {}, "quality": item.quality or {}, "reasoning": item.reasoning, "confidence": float(item.confidence or 0), "citations": item.citations or [], "status": item.status, "confirmed_record_item_id": str(item.confirmed_record_item_id) if item.confirmed_record_item_id else None, "created_at": item.created_at}


def session_dict(item: AiAuditSession, include_children: bool = False) -> dict[str, Any]:
    value = {"id": str(item.id), "project_id": str(item.project_id), "conversation_id": str(item.conversation_id) if item.conversation_id else None, "title": item.title, "status": item.status, "context_snapshot": item.context_snapshot or {}, "model_provider": item.model_provider, "model_name": item.model_name, "created_by": str(item.created_by), "started_at": item.started_at, "completed_at": item.completed_at, "created_at": item.created_at, "updated_at": item.updated_at}
    if include_children:
        value["drafts"] = [draft_dict(draft) for draft in item.drafts]
        value["submissions"] = [{"id": str(submission.id), "status": submission.status, "description": submission.description, "source_files": submission.source_files or [], "submitted_at": submission.submitted_at} for submission in item.submissions]
        confirmed = sum(1 for draft in item.drafts if draft.status == "confirmed")
        value["progress"] = min(100, 10 + confirmed * 15)
    return value


def artifact_dict(item: ProjectArtifact) -> dict[str, Any]:
    return {"id": str(item.id), "project_id": str(item.project_id), "type": item.artifact_type, "artifact_type": item.artifact_type, "name": item.filename, "file_name": item.filename, "status": item.status, "progress": item.progress, "error_message": item.error_message, "metadata": item.artifact_metadata or {}, "version": item.version, "file_size": item.file_size, "size": item.file_size, "mime_type": item.mime_type, "generated_at": item.created_at, "created_at": item.created_at, "updated_at": item.updated_at}


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
    await ensure_project_access(db, project_id, current_user)
    result = await db.execute(select(ProjectDocument).where(ProjectDocument.project_id == project_id).options(selectinload(ProjectDocument.chunks)).order_by(ProjectDocument.created_at.desc()))
    return response([document_dict(item) for item in result.scalars().unique().all()])


@router.post("/{project_id}/documents")
async def upload_document(project_id: UUID, file: UploadFile = File(...), category: str = Form("auto"), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件超过允许大小")
    filename = Path(file.filename or "project-document").name
    directory = Path(settings.UPLOAD_DIR) / "audit_projects" / str(project_id) / "documents"
    directory.mkdir(parents=True, exist_ok=True)
    stored_name = f"{hashlib.sha256(content).hexdigest()[:16]}_{filename}"
    stored_path = directory / stored_name
    stored_path.write_bytes(content)
    document = ProjectDocument(project_id=project_id, title=Path(filename).stem, document_type=category or "auto", original_filename=filename, stored_path=str(stored_path.resolve()), mime_type=file.content_type, file_size=len(content), checksum_sha256=hashlib.sha256(content).hexdigest(), status="uploaded", created_by=current_user.id)
    db.add(document); await db.commit(); await db.refresh(document)
    try:
        stats = await project_knowledge_service.index_document(db, document, content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"资料已保存但解析失败: {exc}") from exc
    await db.refresh(document)
    return response({**document_dict(document), **stats}, "项目资料已上传并索引")


@router.delete("/{project_id}/documents/{document_id}")
async def delete_document(project_id: UUID, document_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user, require_manage=True)
    document = await db.get(ProjectDocument, document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=404, detail="项目资料不存在")
    path = Path(document.stored_path); await db.delete(document); await db.commit()
    if path.is_file(): path.unlink(missing_ok=True)
    return response({"id": str(document_id)}, "项目资料已删除")


@router.post("/{project_id}/documents/{document_id}/reindex")
async def reindex_document(project_id: UUID, document_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user)
    document = await db.get(ProjectDocument, document_id)
    if not document or document.project_id != project_id: raise HTTPException(status_code=404, detail="项目资料不存在")
    path = Path(document.stored_path)
    if not path.is_file(): raise HTTPException(status_code=404, detail="原始文件不存在")
    return response(await project_knowledge_service.index_document(db, document, path.read_bytes()), "索引已重建")


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
    if payload.plan_item_id:
        plan_item = await db.get(AuditPlanItem, payload.plan_item_id)
        if not plan_item or plan_item.project_id != project_id: raise HTTPException(status_code=404, detail="审核计划项不存在")
        context.update({"plan_item_id": str(plan_item.id), "area_name": plan_item.area_name, "template_id": str(plan_item.template_id) if plan_item.template_id else None, "clauses": plan_item.clauses or [], "certification_systems": plan_item.certification_systems or []})
        if not area_record_id:
            existing = (await db.execute(select(AuditAreaRecord).where(AuditAreaRecord.project_id == project_id, AuditAreaRecord.plan_item_id == plan_item.id))).scalar_one_or_none()
            if existing: area_record_id = existing.id
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
                elif area.status == "pending":
                    area.status = "in_progress"
                area_record = AuditAreaRecord(project_id=project_id, area_id=area.id, plan_item_id=plan_item.id, record_no=f"AR-{str(plan_item.id)[:8]}", template_id=plan_item.template_id, certification_systems=plan_item.certification_systems or [], recorded_by=current_user.id, audit_date=plan_item.plan_date, audit_time_start=plan_item.time_start, audit_time_end=plan_item.time_end, status="draft")
                db.add(area_record); await db.flush(); area_record_id = area_record.id
                plan_item.status = "in_progress"
    if area_record_id:
        area_record = await db.get(AuditAreaRecord, area_record_id)
        if not area_record or area_record.project_id != project_id:
            raise HTTPException(status_code=404, detail="审核区域记录不存在")
        if payload.plan_item_id and area_record.plan_item_id != payload.plan_item_id:
            raise HTTPException(status_code=409, detail="区域记录与审核计划项不匹配")
        context["area_record_id"] = str(area_record_id)
    session = AiAuditSession(project_id=project_id, title=payload.title or "AI 现场审核", status="active", context_snapshot=context, model_provider=settings.LLM_PROVIDER, model_name=settings.LLM_MODEL, prompt_version="project-agent-v2", created_by=current_user.id)
    db.add(session); await db.commit(); await db.refresh(session)
    return response(session_dict(session), "审核会话已创建")


async def _load_session(db: AsyncSession, project_id: UUID, session_id: UUID, children: bool = False) -> AiAuditSession:
    stmt = select(AiAuditSession).where(AiAuditSession.id == session_id, AiAuditSession.project_id == project_id)
    if children: stmt = stmt.options(selectinload(AiAuditSession.drafts), selectinload(AiAuditSession.submissions))
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item: raise HTTPException(status_code=404, detail="审核会话不存在")
    return item


@router.get("/{project_id}/sessions/{session_id}")
async def get_session(project_id: UUID, session_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user)
    item = await _load_session(db, project_id, session_id, True)
    value = session_dict(item, True); value["quality_check"] = await _session_quality(item)
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
    context = session.context_snapshot or {}; stmt = select(TemplateItem).where(TemplateItem.is_category.is_(False))
    if ids: stmt = stmt.where(TemplateItem.id.in_(ids))
    elif context.get("template_id"): stmt = stmt.where(TemplateItem.template_id == UUID(context["template_id"]))
    else: return [EvidenceCandidate(None, None, str(clause), str(clause), certification_system=(context.get("certification_systems") or [None])[0]) for clause in context.get("clauses", [])]
    items = (await db.execute(stmt.order_by(TemplateItem.sort_order))).scalars().all()
    return [EvidenceCandidate(str(item.id), str(item.id), item.clause_no or item.standard_ref or str(item.id), item.title, item.description or "", item.check_method or "", item.evidence_hint or "", item.risk_level or "medium", bool(item.attachment_required), (item.applicable_systems or [None])[0]) for item in items if item.clause_no or item.standard_ref]


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
    results = await evidence_agent_service.analyze(payload.content, candidates, citations)
    drafts = []
    for result in results:
        candidate = result["candidate"]; evaluation = result["evaluation_3level"]
        draft = AiDraftRecord(project_id=project_id, session_id=session.id, submission_id=submission.id, area_record_id=area_record_id, plan_item_id=plan_item_id, evidence_item_ids=[evidence_item.id], clause_refs=[{"clause_no": candidate.clause_no, "title": candidate.title, "certification_system": candidate.certification_system, "rank": len(drafts) + 1}], primary_clause_no=candidate.clause_no, certification_system=candidate.certification_system, evaluation=evaluation, finding_text=result["audit_findings"] or payload.content, record_payload={"template_item_id": candidate.template_item_id, "audit_evidence": payload.content, "evaluation_3level": evaluation, "audit_findings": result["audit_findings"], "rectification_suggestion": result["rectification_suggestion"], "risk_level": candidate.risk_level, "attachment_required": candidate.attachment_required, "attachment_count": len(media_rows), "photo_paths": [media.file_path for media in media_rows]}, quality={"level": result["evidence_quality"], "risk_level": candidate.risk_level, "attachment_required": candidate.attachment_required, "attachment_missing": candidate.attachment_required and not media_rows}, reasoning=result["reasoning"] or "需要人工确认", confidence=result["confidence"], citations=result["citations"], source_snapshot={"evidence": payload.content, "citations": result["citations"]}, status="draft", model_provider=settings.LLM_PROVIDER, model_name=settings.LLM_MODEL, prompt_version="evidence-multiclause-v2")
        db.add(draft); drafts.append(draft)
    submission.status = "completed"; submission.processed_at = func.now(); await db.commit()
    return response({"submission_id": str(submission.id), "drafts": [draft_dict(item) for item in drafts]}, f"已生成 {len(drafts)} 条待确认记录")


async def _session_quality(session: AiAuditSession) -> dict[str, Any]:
    blockers=[]; warnings=[]
    for draft in session.drafts:
        if draft.status != "draft": continue
        risk = str((draft.quality or {}).get("risk_level", "")).lower(); missing = bool((draft.quality or {}).get("attachment_missing")); insufficient = (draft.quality or {}).get("level") == "insufficient"
        if risk in {"high", "a", "高风险"} and insufficient: blockers.append({"code": "HIGH_RISK_EVIDENCE", "draft_id": str(draft.id), "message": f"高风险条款 {draft.primary_clause_no} 证据不足"})
        elif missing: blockers.append({"code": "ATTACHMENT_REQUIRED", "draft_id": str(draft.id), "message": f"条款 {draft.primary_clause_no} 缺少必传附件"})
        elif str(draft.evaluation) == "3": blockers.append({"code": "NC_UNCONFIRMED", "draft_id": str(draft.id), "message": f"不符合条款 {draft.primary_clause_no} 尚未确认"})
        else: blockers.append({"code": "DRAFT_PENDING", "draft_id": str(draft.id), "message": f"条款 {draft.primary_clause_no} 尚未确认"})
    return {"passed": not blockers, "blockers": blockers, "warnings": warnings, "blocking_count": len(blockers), "warning_count": len(warnings)}


@router.post("/{project_id}/sessions/{session_id}/drafts/confirm")
async def confirm_drafts(project_id: UUID, session_id: UUID, payload: DraftConfirmRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user); session = await _load_session(db, project_id, session_id, True)
    selected = [draft for draft in session.drafts if draft.status == "draft" and (draft.id in payload.draft_ids or payload.safe_only)]
    if payload.safe_only: selected = [draft for draft in selected if str(draft.evaluation) != "3" and float(draft.confidence or 0) >= .7 and (draft.quality or {}).get("level") == "sufficient" and not (draft.quality or {}).get("attachment_missing")]
    overrides = {item.draft_id: item for item in payload.overrides}; confirmed=[]
    for draft in selected:
        if payload.action == "reject": draft.status="rejected"; draft.confirmed_by=current_user.id; draft.confirmed_at=func.now(); continue
        override=overrides.get(draft.id); record_payload={**(draft.record_payload or {})}
        if override:
            for key in ("evaluation_3level", "audit_evidence", "audit_findings", "rectification_suggestion"):
                value=getattr(override, key); record_payload[key]=value if value is not None else record_payload.get(key)
        item = InspectionRecordItem(audit_area_record_id=draft.area_record_id, template_item_id=UUID(record_payload["template_item_id"]) if record_payload.get("template_item_id") else None, result="fail" if record_payload.get("evaluation_3level") == "3" else "pass", result_text=record_payload.get("audit_findings") or record_payload.get("audit_evidence"), problem_description=record_payload.get("audit_findings"), rectification_suggestion=record_payload.get("rectification_suggestion"), audit_evidence=record_payload.get("audit_evidence"), evaluation_3level=record_payload.get("evaluation_3level") or draft.evaluation, audit_findings=record_payload.get("audit_findings"), certification_system=draft.certification_system, clause_no_snapshot=draft.primary_clause_no, ai_generated=True, ai_suggestion=draft.reasoning, ai_basis="; ".join(str(c.get("document_title") or c.get("file_name") or "项目资料") for c in draft.citations or []), photos=record_payload.get("photo_paths") or [], item_title=(draft.clause_refs or [{}])[0].get("title"), item_risk_level=record_payload.get("risk_level"), item_check_type="audit_3level", item_attachment_required=record_payload.get("attachment_required"), item_use_ai=True)
        db.add(item); await db.flush(); draft.status="confirmed"; draft.confirmed_by=current_user.id; draft.confirmed_at=func.now(); draft.confirmed_record_item_id=item.id; confirmed.append(draft)
        if str(item.evaluation_3level) == "3":
            nc = Nonconformity(project_id=project_id, plan_item_id=draft.plan_item_id, area_record_id=draft.area_record_id, record_item_id=item.id, nc_no=f"AI-{str(draft.id)[:8].upper()}", severity="minor", certification_system=draft.certification_system, clause_no=draft.primary_clause_no, description=item.audit_findings or item.audit_evidence or "AI 识别的不符合项", evidence=item.audit_evidence, corrective_action_required=item.rectification_suggestion or "请分析原因并完成整改", status="draft", created_by=current_user.id, source_draft_id=draft.id)
            db.add(nc)
    await db.commit(); return response({"confirmed": [str(item.id) for item in confirmed], "count": len(confirmed)}, "AI 草稿已处理")


@router.post("/{project_id}/sessions/{session_id}/quality-check")
async def session_quality(project_id: UUID, session_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user); return response(await _session_quality(await _load_session(db, project_id, session_id, True)))


@router.post("/{project_id}/sessions/{session_id}/submit")
async def submit_session(project_id: UUID, session_id: UUID, payload: dict[str, Any] = Body(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user); session=await _load_session(db, project_id, session_id, True); check=await _session_quality(session)
    if session.status == "completed":
        return response(session_dict(session, True), "审核记录已提交")
    if check["blockers"]: raise HTTPException(status_code=409, detail={"message":"存在阻断项，不能提交","quality_check":check})
    conclusion=str(payload.get("conclusion") or "").strip()
    if not conclusion: raise HTTPException(status_code=422, detail="请填写最终审核结论")
    context={**(session.context_snapshot or {}),"conclusion":conclusion}; session.context_snapshot=context; session.status="completed"; session.completed_at=func.now()
    if context.get("area_record_id"):
        record=await db.get(AuditAreaRecord, UUID(context["area_record_id"])); record.conclusion=conclusion; record.status="submitted"
    if context.get("plan_item_id"):
        plan=await db.get(AuditPlanItem, UUID(context["plan_item_id"])); plan.status="completed"
    result = session_dict(session, True)
    await db.commit()
    return response(result, "审核记录已提交")


@router.post("/{project_id}/nonconformities/{nc_id}/confirm")
async def confirm_nc(project_id: UUID, nc_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user, require_manage=True); nc=await db.get(Nonconformity,nc_id)
    if not nc or nc.project_id != project_id: raise HTTPException(status_code=404, detail="不符合项不存在")
    nc.status="open"; nc.confirmed_by=current_user.id; nc.confirmed_at=func.now(); await db.commit(); return response({"id":str(nc.id),"status":nc.status},"不符合项草稿已确认")


@router.post("/{project_id}/quality-check")
async def project_quality(project_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user); return response(await project_artifact_service.quality_check(db, project_id))


@router.get("/{project_id}/artifacts")
async def list_artifacts(project_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await ensure_project_access(db, project_id, current_user); items=(await db.execute(select(ProjectArtifact).where(ProjectArtifact.project_id==project_id).order_by(ProjectArtifact.created_at.desc()))).scalars().all(); return response([artifact_dict(item) for item in items])


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
    if not item or item.project_id != project_id or not Path(item.path).is_file(): raise HTTPException(status_code=404,detail="成果文件不存在")
    return FileResponse(item.path,media_type=item.mime_type,filename=item.filename)


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
    item = (
        await db.execute(
            select(ProjectArtifact)
            .where(
                ProjectArtifact.project_id == project_id,
                ProjectArtifact.artifact_type == "package",
                ProjectArtifact.status == "ready",
            )
            .order_by(ProjectArtifact.version.desc())
        )
    ).scalars().first()
    if not item or not Path(item.path).is_file():
        raise HTTPException(
            status_code=404,
            detail="完整资料包尚未生成，请先创建资料包生成任务",
        )
    return FileResponse(
        item.path, media_type="application/zip", filename=item.filename
    )
