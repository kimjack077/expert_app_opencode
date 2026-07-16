from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.knowledge import InspectionGuideline, KnowledgeCategory, KnowledgeDocument
from app.models.user import User
from app.schemas import ApiResponse
from app.services import AuditService
from app.services.rag_service import rag_service
from app.utils.document_parser import document_parser
from app.utils.security import get_current_admin_user, get_current_user

router = APIRouter()


def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.utcnow()
    )


@router.get("/categories", response_model=ApiResponse)
async def get_categories(
    category_type: Optional[str] = Query(None),
    parent_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(KnowledgeCategory).where(KnowledgeCategory.is_deleted == False)  # noqa: E712

    if category_type:
        query = query.where(KnowledgeCategory.category_type == category_type)
    if parent_id:
        query = query.where(KnowledgeCategory.parent_id == parent_id)
    else:
        query = query.where(KnowledgeCategory.parent_id == None)

    query = query.order_by(KnowledgeCategory.sort_order)
    result = await db.execute(query)
    categories = result.scalars().all()

    return make_response(
        data=[{
            "id": str(c.id),
            "name": c.name,
            "code": c.code,
            "category_type": c.category_type,
            "sort_order": c.sort_order,
            "description": c.description,
        } for c in categories]
    )


class CategoryCreate(BaseModel):
    name: str
    category_type: str
    code: Optional[str] = None
    parent_id: Optional[str] = None
    sort_order: int = 0
    description: Optional[str] = None


@router.post("/categories", response_model=ApiResponse)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    category = KnowledgeCategory(
        name=data.name,
        code=data.code,
        category_type=data.category_type,
        parent_id=data.parent_id,
        sort_order=data.sort_order,
        description=data.description,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)

    return make_response(data={"id": str(category.id), "name": category.name})


@router.get("/documents", response_model=ApiResponse)
async def get_documents(
    category_id: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(KnowledgeDocument).options(selectinload(KnowledgeDocument.category)).where(KnowledgeDocument.is_deleted == False)  # noqa: E712

    if category_id:
        query = query.where(KnowledgeDocument.category_id == category_id)
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
            "view_count": d.view_count,
            "category": {"id": str(d.category.id), "name": d.category.name} if d.category else None,
        } for d in documents]
    )


class DocumentCreate(BaseModel):
    title: str
    category_id: str
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
    category_id: Optional[str] = None
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
        category_id=data.category_id,
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


@router.post("/documents/upload", response_model=ApiResponse)
async def upload_document(
    file: UploadFile = File(...),
    category_id: str = Form(...),
    doc_type: str = Form(...),
    title: Optional[str] = Form(None),
    doc_no: Optional[str] = Form(None),
    keywords: Optional[str] = Form(None),
    status: str = Form("effective"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """上传知识库文件，抽取正文并立即生成 RAG 向量索引。"""
    content, metadata = await document_parser.parse_document(file)
    parser_errors = ("[PDF解析", "[Word解析", "[Excel解析")
    if not content.strip() or content.lstrip().startswith(parser_errors):
        raise HTTPException(status_code=400, detail=content or "未能从文件中提取文字")

    document = KnowledgeDocument(
        title=title or metadata.get("filename") or "未命名知识文档",
        category_id=category_id,
        doc_type=doc_type,
        content=content,
        doc_no=doc_no,
        keywords=keywords,
        status=status,
        file_name=metadata.get("filename"),
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
        "content_length": len(content),
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

    document.view_count += 1
    await db.commit()

    return make_response(data={
        "id": str(document.id),
        "title": document.title,
        "category_id": str(document.category_id) if document.category_id else None,
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
        "view_count": document.view_count,
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

    from app.utils.soft_delete import soft_delete

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
