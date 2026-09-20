"""
Enhanced AI Features Router

This router provides endpoints for:
- RAG knowledge base search
- Template recommendation
- Photo analysis
- Regulation linking
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import json

from app.database import get_db
from app.models.user import User
from app.models.knowledge import KnowledgeDocument
from app.models.template import TemplateItem
from app.models.media import MediaFile
from app.schemas import ApiResponse
from app.utils.security import get_current_user
from app.services.rag_service import rag_service
from app.services.template_recommendation_service import template_recommendation_service
from app.services.multimodal_service import multimodal_service
from app.utils.response import make_response

router = APIRouter()


# ============== Request Models ==============

class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    doc_type: Optional[str] = None


class CreateEmbeddingRequest(BaseModel):
    document_id: str


class LinkRegulationRequest(BaseModel):
    template_item_id: str
    top_k: int = 3
    min_similarity: float = 0.5


class TemplateRecommendRequest(BaseModel):
    enterprise_id: str
    top_k: int = 3
    use_ai: bool = True


class RecommendationFeedbackRequest(BaseModel):
    enterprise_id: str
    template_id: str
    was_accepted: bool
    was_effective: Optional[bool] = None


class PhotoAnalysisRequest(BaseModel):
    media_file_id: str
    analysis_type: str = "compliance"
    task_item_id: Optional[str] = None
    check_item_title: Optional[str] = None


# ============== RAG Endpoints ==============

@router.post("/knowledge/search", response_model=ApiResponse)
async def search_knowledge(
    request: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search knowledge base using semantic similarity."""
    results = await rag_service.search_knowledge(
        query=request.query,
        db=db,
        top_k=request.top_k,
        doc_type=request.doc_type,
    )

    return make_response(data={
        "query": request.query,
        "results": results,
        "total": len(results),
    })


@router.post("/knowledge/embeddings", response_model=ApiResponse)
async def create_document_embeddings(
    request: CreateEmbeddingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create embeddings for a knowledge document."""
    # Check if user has permission (admin or super_admin)
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Permission denied")

    result = await rag_service.create_embeddings_for_document(
        document_id=request.document_id,
        db=db,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return make_response(data=result)


@router.post("/regulations/link", response_model=ApiResponse)
async def link_check_item_regulations(
    request: LinkRegulationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Automatically link a check item to relevant regulations."""
    # Check if template item exists
    item = await db.get(TemplateItem, request.template_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Template item not found")

    linked = await rag_service.link_check_item_to_regulations(
        template_item_id=request.template_item_id,
        db=db,
        top_k=request.top_k,
        min_similarity=request.min_similarity,
    )

    return make_response(data={
        "template_item_id": request.template_item_id,
        "linked_count": len(linked),
        "linked_regulations": linked,
    })


@router.get("/regulations/{template_item_id}", response_model=ApiResponse)
async def get_item_regulations(
    template_item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all linked regulations for a template item."""
    regulations = await rag_service.get_relevant_regulations_for_item(
        template_item_id=template_item_id,
        db=db,
    )

    return make_response(data={
        "template_item_id": template_item_id,
        "regulations": regulations,
    })


@router.post("/knowledge/context", response_model=ApiResponse)
async def generate_regulation_context(
    request: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate regulation context string for LLM prompts."""
    context = await rag_service.generate_regulation_context(
        query=request.query,
        db=db,
        max_chunks=request.top_k,
    )

    return make_response(data={
        "query": request.query,
        "context": context,
    })


# ============== Template Recommendation Endpoints ==============

@router.post("/templates/recommend", response_model=ApiResponse)
async def recommend_templates(
    request: TemplateRecommendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recommend inspection templates for an enterprise."""
    recommendations = await template_recommendation_service.recommend_templates(
        enterprise_id=request.enterprise_id,
        db=db,
        top_k=request.top_k,
        use_ai=request.use_ai,
    )

    return make_response(data={
        "enterprise_id": request.enterprise_id,
        "recommendations": recommendations,
    })


@router.post("/templates/feedback", response_model=ApiResponse)
async def record_recommendation_feedback(
    request: RecommendationFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record feedback on template recommendation."""
    await template_recommendation_service.record_recommendation_feedback(
        enterprise_id=request.enterprise_id,
        template_id=request.template_id,
        was_accepted=request.was_accepted,
        was_effective=request.was_effective,
        user_id=str(current_user.id),
        db=db,
    )

    return make_response(message="Feedback recorded successfully")


@router.get("/templates/popular", response_model=ApiResponse)
async def get_popular_templates(
    industry_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get most frequently used templates."""
    templates = await template_recommendation_service.get_popular_templates(
        db=db,
        industry_id=industry_id,
        limit=limit,
    )

    return make_response(data={
        "templates": templates,
    })


@router.get("/templates/{template_id}/effectiveness", response_model=ApiResponse)
async def get_template_effectiveness(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get effectiveness metrics for a template."""
    metrics = await template_recommendation_service.get_template_effectiveness(
        template_id=template_id,
        db=db,
    )

    return make_response(data=metrics)


# ============== Photo Analysis Endpoints ==============

@router.post("/photo/analyze", response_model=ApiResponse)
async def analyze_photo(
    request: PhotoAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analyze a photo for compliance issues."""
    # Check if media file exists
    media_file = await db.get(MediaFile, request.media_file_id)
    if not media_file:
        raise HTTPException(status_code=404, detail="Media file not found")

    result = await multimodal_service.analyze_photo(
        media_file_id=request.media_file_id,
        db=db,
        analysis_type=request.analysis_type,
        task_item_id=request.task_item_id,
        check_item_title=request.check_item_title,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return make_response(data=result)


@router.post("/photo/analyze/stream")
async def analyze_photo_stream(
    request: PhotoAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream photo analysis results."""

    async def generate():
        async for chunk in multimodal_service.analyze_photo_stream(
            media_file_id=request.media_file_id,
            db=db,
            analysis_type=request.analysis_type,
            check_item_title=request.check_item_title,
        ):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


@router.get("/photo/{media_file_id}/analysis", response_model=ApiResponse)
async def get_photo_analysis(
    media_file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get existing analysis for a photo."""
    analysis = await multimodal_service.get_photo_analysis(
        media_file_id=media_file_id,
        db=db,
    )

    if not analysis:
        return make_response(data={"analysis": None})

    return make_response(data={"analysis": analysis})


@router.post("/photo/batch-analyze", response_model=ApiResponse)
async def batch_analyze_photos(
    media_file_ids: List[str],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analyze multiple photos in batch."""
    results = await multimodal_service.batch_analyze_photos(
        media_file_ids=media_file_ids,
        db=db,
    )

    return make_response(data={
        "total": len(results),
        "results": results,
    })