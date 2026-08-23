import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import InspectionGuideline, KnowledgeDocument
from app.models.user import User
from app.schemas import ApiResponse
from app.services import AuditService
from app.services.rag_service import rag_service
from app.utils.document_parser import document_parser
from app.utils.security import get_current_admin_user, get_current_user

router = APIRouter()

# Markdown 文件存储目录
KNOWLEDGE_MD_DIR = Path("uploads") / "knowledge_md"
KNOWLEDGE_MD_DIR.mkdir(parents=True, exist_ok=True)


def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.now(timezone.utc)
    )


@router.get("/documents", response_model=ApiResponse)
async def get_documents(
    doc_type: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(KnowledgeDocument).where(KnowledgeDocument.is_deleted == False)  # noqa: E712

    if doc_type:
        query = query.where(KnowledgeDocument.doc_type == doc_type)
    if keyword:
        query = query.where(
            KnowledgeDocument.title.ilike(f"%{keyword}%") |
            KnowledgeDocument.content.ilike(f"%{keyword}%") |
            KnowledgeDocument.keywords.ilike(f"%{keyword}%")
        )
    if status:
        query = query.where(KnowledgeDocument.status == status)

    query = query.order_by(KnowledgeDocument.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    documents = result.scalars().all()

    return make_response(
        data=[{
            "id": str(d.id),
            "title": d.title,
            "doc_type": d.doc_type,
            "doc_no": d.doc_no,
            "summary": d.summary,
            "issue_authority": d.issue_authority,
            "issue_date": d.issue_date.isoformat() if d.issue_date else None,
            "effective_date": d.effective_date.isoformat() if d.effective_date else None,
            "status": d.status,
        } for d in documents]
    )


class DocumentCreate(BaseModel):
    title: str
    doc_type: str
    content: Optional[str] = None
    doc_no: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[str] = None
    issue_authority: Optional[str] = None
    issue_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    status: str = "effective"


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    doc_type: Optional[str] = None
    content: Optional[str] = None
    doc_no: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[str] = None
    issue_authority: Optional[str] = None
    issue_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    status: Optional[str] = None


@router.post("/documents", response_model=ApiResponse)
async def create_document(
    data: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    document = KnowledgeDocument(
        title=data.title,
        doc_type=data.doc_type,
        content=data.content,
        doc_no=data.doc_no,
        summary=data.summary,
        keywords=data.keywords,
        issue_authority=data.issue_authority,
        issue_date=data.issue_date,
        effective_date=data.effective_date,
        expiry_date=data.expiry_date,
        file_url=data.file_url,
        file_name=data.file_name,
        status=data.status,
        created_by=current_user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "create_document",
        "knowledge_document",
        str(document.id),
    )

    indexing = await rag_service.create_embeddings_for_document(str(document.id), db)

    return make_response(data={
        "id": str(document.id),
        "title": document.title,
        "indexing": indexing,
    })


@router.post("/documents/parse", response_model=ApiResponse)
async def parse_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_admin_user),
):
    """
    第一阶段：上传文件并解析为 Markdown。
    不写数据库，仅返回解析后的 Markdown 内容供前端预览/编辑。
    """
    md_content, metadata = await document_parser.parse_document(file)

    parser_errors = ("[PDF解析", "[Word解析", "[Excel解析")
    if not md_content.strip() or md_content.lstrip().startswith(parser_errors):
        raise HTTPException(status_code=400, detail=md_content or "未能从文件中提取文字")

    return make_response(data={
        "markdown": md_content,
        "filename": metadata.get("filename"),
        "size": metadata.get("size"),
        "char_count": metadata.get("char_count"),
    })


@router.post("/documents/index")
async def index_document(
    doc_id: Optional[str] = Form(None),
    doc_type: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    doc_no: Optional[str] = Form(None),
    keywords: Optional[str] = Form(None),
    status: str = Form("effective"),
    filename: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    第二阶段：接收用户确认后的 Markdown 内容，建立数据库记录并流式推送向量索引进度 (SSE)。
    """
    async def _sse_generator():
        # 1. 保存 Markdown 到磁盘
        md_filename = None
        if filename:
            safe_name = Path(filename).stem
            md_filename = f"{safe_name}.md"
            md_path = KNOWLEDGE_MD_DIR / md_filename
            md_path.write_text(content, encoding="utf-8")

        # 2. 写入数据库
        document = KnowledgeDocument(
            title=title,
            doc_type=doc_type,
            content=content,
            doc_no=doc_no,
            keywords=keywords,
            status=status,
            file_name=filename,
            markdown_path=str(KNOWLEDGE_MD_DIR / md_filename) if md_filename else None,
            created_by=current_user.id,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)

        doc_id_str = str(document.id)

        yield f"data: {json.dumps({'stage': 'saved', 'doc_id': doc_id_str, 'message': '文档已保存'}, ensure_ascii=False)}\n\n"

        # 3. 审计日志
        await AuditService.log_action(
            db,
            str(current_user.id),
            current_user.username,
            "upload_document",
            "knowledge_document",
            doc_id_str,
        )

        # 4. 流式建立向量索引
        async for event in rag_service.create_embeddings_streaming(doc_id_str, db):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/documents/upload", response_model=ApiResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    title: Optional[str] = Form(None),
    doc_no: Optional[str] = Form(None),
    keywords: Optional[str] = Form(None),
    status: str = Form("effective"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """上传知识库文件，抽取正文（Markdown）并立即生成 RAG 向量索引。"""
    md_content, metadata = await document_parser.parse_document(file)
    parser_errors = ("[PDF解析", "[Word解析", "[Excel解析")
    if not md_content.strip() or md_content.lstrip().startswith(parser_errors):
        raise HTTPException(status_code=400, detail=md_content or "未能从文件中提取文字")

    # 保存 Markdown 文件到磁盘
    md_filename = None
    if metadata.get("filename"):
        safe_name = Path(metadata["filename"]).stem
        md_filename = f"{safe_name}.md"
        md_path = KNOWLEDGE_MD_DIR / md_filename
        md_path.write_text(md_content, encoding="utf-8")

    document = KnowledgeDocument(
        title=title or metadata.get("filename") or "未命名知识文档",
        doc_type=doc_type,
        content=md_content,
        doc_no=doc_no,
        keywords=keywords,
        status=status,
        file_name=metadata.get("filename"),
        markdown_path=str(KNOWLEDGE_MD_DIR / md_filename) if md_filename else None,
        created_by=current_user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    indexing = await rag_service.create_embeddings_for_document(str(document.id), db)
    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "upload_document",
        "knowledge_document",
        str(document.id),
        detail={
            "filename": metadata.get("filename"),
            "file_size": metadata.get("size"),
            "embeddings_created": indexing.get("embeddings_created", 0),
        },
    )

    return make_response(data={
        "id": str(document.id),
        "title": document.title,
        "file_name": document.file_name,
        "markdown_path": document.markdown_path,
        "content_length": len(md_content),
        "indexing": indexing,
    })


@router.get("/documents/{doc_id}", response_model=ApiResponse)
async def get_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = await db.get(KnowledgeDocument, doc_id)
    if not document or document.is_deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    return make_response(data={
        "id": str(document.id),
        "title": document.title,
        "doc_type": document.doc_type,
        "doc_no": document.doc_no,
        "content": document.content,
        "summary": document.summary,
        "keywords": document.keywords,
        "issue_authority": document.issue_authority,
        "issue_date": document.issue_date.isoformat() if document.issue_date else None,
        "effective_date": document.effective_date.isoformat() if document.effective_date else None,
        "expiry_date": document.expiry_date.isoformat() if document.expiry_date else None,
        "status": document.status,
        "file_url": document.file_url,
        "file_name": document.file_name,
        "markdown_path": document.markdown_path,
    })


@router.put("/documents/{doc_id}", response_model=ApiResponse)
async def update_document(
    doc_id: str,
    data: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    document = await db.get(KnowledgeDocument, doc_id)
    if not document or document.is_deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(document, field, value)

    await db.commit()
    await db.refresh(document)

    indexing = None
    if "content" in update_data:
        indexing = await rag_service.create_embeddings_for_document(str(document.id), db)

    return make_response(data={
        "id": str(document.id),
        "title": document.title,
        "indexing": indexing,
    })


@router.delete("/documents/{doc_id}", response_model=ApiResponse)
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    document = await db.get(KnowledgeDocument, doc_id)
    if not document or document.is_deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    from sqlalchemy import delete as sa_delete

    from app.models.rag import KnowledgeEmbedding
    from app.utils.soft_delete import soft_delete

    # Remove RAG index so deleted knowledge cannot be retrieved
    await db.execute(
        sa_delete(KnowledgeEmbedding).where(KnowledgeEmbedding.document_id == document.id)
    )
    await soft_delete(db, document)
    await db.commit()

    return make_response(message="Document deleted")


@router.get("/guidelines", response_model=ApiResponse)
async def get_guidelines(
    product_category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(InspectionGuideline)

    if product_category:
        query = query.where(InspectionGuideline.product_category.ilike(f"%{product_category}%"))
    if is_active is not None:
        query = query.where(InspectionGuideline.is_active == is_active)

    query = query.order_by(InspectionGuideline.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    guidelines = result.scalars().all()

    return make_response(
        data=[{
            "id": str(g.id),
            "name": g.name,
            "code": g.code,
            "product_category": g.product_category,
            "content": g.content,
            "legal_basis": g.legal_basis,
            "version": g.version,
            "is_active": g.is_active,
            "effective_date": g.effective_date.isoformat() if g.effective_date else None,
        } for g in guidelines]
    )


class GuidelineCreate(BaseModel):
    name: str
    product_category: str
    content: str
    code: Optional[str] = None
    legal_basis: Optional[str] = None
    version: str = "1.0"
    effective_date: Optional[datetime] = None


@router.post("/guidelines", response_model=ApiResponse)
async def create_guideline(
    data: GuidelineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    guideline = InspectionGuideline(
        name=data.name,
        code=data.code,
        product_category=data.product_category,
        content=data.content,
        legal_basis=data.legal_basis,
        version=data.version,
        effective_date=data.effective_date,
        created_by=current_user.id,
    )
    db.add(guideline)
    await db.commit()
    await db.refresh(guideline)

    return make_response(data={"id": str(guideline.id), "name": guideline.name})
