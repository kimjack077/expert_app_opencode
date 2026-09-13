import json
from datetime import datetime, timezone
from typing import Optional, List, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.template import InspectionTemplate, TemplateItem
from app.schemas import ApiResponse
from app.utils.security import get_current_admin_user
from app.utils.category import normalize_as_category
from app.utils.document_parser import document_parser
from app.services.ai_extract_service import ai_extract_service
from app.services import AuditService

router = APIRouter()


def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.now(timezone.utc)
    )


class RefineRequest(BaseModel):
    items: List[dict]
    instruction: str


@router.post("/extract", response_model=ApiResponse)
async def extract_items_from_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    try:
        file_content = await file.read()
        
        result = {"success": False, "items": [], "error": "Unknown error"}
        async for chunk in ai_extract_service.extract_items_from_file(file_content, file.filename or "document"):
            if chunk.get("type") == "done":
                result = {"success": True, "items": chunk.get("items", []), "raw_response": chunk.get("raw_response")}
            elif chunk.get("type") == "error":
                result = {"success": False, "items": [], "error": chunk.get("content")}

        if not result.get("success"):
            return make_response(
                code=500,
                message=f"AI解析失败: {result.get('error', '未知错误')}",
                data={"items": []}
            )

        await AuditService.log_action(
            db,
            str(current_user.id),
            current_user.username,
            "ai_extract_items",
            "template",
            None,
            detail={
                "filename": file.filename,
                "file_size": len(file_content),
                "items_count": len(result.get("items", [])),
            }
        )

        return make_response(
            data={
                "items": result.get("items", []),
                "metadata": {"filename": file.filename, "size": len(file_content)},
                "raw_response": result.get("raw_response"),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        return make_response(
            code=500,
            message=f"处理失败: {str(e)}",
            data={"items": []}
        )


@router.post("/extract/stream")
async def extract_items_stream(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    async def generate():
        try:
            file_content = await file.read()
            
            async for chunk in ai_extract_service.extract_items_from_file(file_content, file.filename or "document"):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/preview", response_model=ApiResponse)
async def preview_extracted_items(
    items: List[dict],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    validated_items = []
    for idx, item in enumerate(items):
        validated_item = {
            "temp_id": f"temp_{idx}",
            "title": item.get("title", ""),
            "description": item.get("description"),
            "check_method": item.get("check_method"),
            "legal_basis": item.get("legal_basis"),
            "standard_ref": item.get("standard_ref"),
            "check_type": item.get("check_type", "radio"),
            "result_options": item.get("result_options"),
            "min_value": item.get("min_value"),
            "max_value": item.get("max_value"),
            "unit": item.get("unit"),
            "max_score": item.get("max_score"),
            "pass_score": item.get("pass_score"),
            "risk_level": item.get("risk_level", "medium"),
            "is_category": item.get("is_category", False),
            "parent_title": item.get("parent_title"),
            "sort_order": item.get("sort_order", idx),
            "validation_errors": [],
        }

        if not validated_item["title"]:
            validated_item["validation_errors"].append("标题不能为空")

        if validated_item["check_type"] == "numeric":
            if validated_item["min_value"] is None or validated_item["max_value"] is None:
                validated_item["validation_errors"].append("数值类型需要设置最小值和最大值")

        validated_items.append(validated_item)

    return make_response(data={"items": validated_items})


@router.post("/apply/{template_id}", response_model=ApiResponse)
async def apply_extracted_items(
    template_id: str,
    items: List[dict],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    template = await db.get(InspectionTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    title_to_id = {}
    existing_items_query = select(TemplateItem).where(
        TemplateItem.template_id == template_id
    )
    result = await db.execute(existing_items_query)
    existing_items = result.scalars().all()
    
    for item in existing_items:
        title_to_id[item.title] = str(item.id)

    created_items = []
    errors = []
    new_objects: List[TemplateItem] = []

    # 先处理分类节点，再处理检查项（保证parent_id能正确关联）
    sorted_items = sorted(items, key=lambda x: (
        0 if x.get("is_category") else 1,
        x.get("sort_order", 0)
    ))

    for item_data in sorted_items:
        try:
            parent_id = None
            parent_title = item_data.get("parent_title")
            if parent_title and parent_title in title_to_id:
                parent_id = UUID(title_to_id[parent_title])

            # 处理 result_options（保留合格/不合格判定标准）
            result_options = item_data.get("result_options")
            
            # 根据 check_type 确定 result_type（兼容旧字段）
            check_type = item_data.get("check_type", "radio")
            if check_type == "radio":
                result_type = "pass_fail"
            elif check_type == "numeric":
                result_type = "numeric"
            elif check_type == "text":
                result_type = "text"
            else:
                result_type = "pass_fail"

            new_item = TemplateItem(
                template_id=template_id,
                parent_id=parent_id,
                title=item_data.get("title", ""),
                description=item_data.get("description"),
                check_method=item_data.get("check_method"),
                legal_basis=item_data.get("legal_basis"),
                standard_ref=item_data.get("standard_ref"),
                check_type=check_type,
                result_type=result_type,
                result_options=result_options,
                min_value=item_data.get("min_value"),
                max_value=item_data.get("max_value"),
                unit=item_data.get("unit"),
                max_score=item_data.get("max_score"),
                pass_score=item_data.get("pass_score"),
                risk_level=item_data.get("risk_level", "medium"),
                is_category=item_data.get("is_category", False),
                sort_order=item_data.get("sort_order", 0),
                is_required=True,
                created_by=current_user.id,
            )
            db.add(new_item)
            await db.flush()
            new_objects.append(new_item)
            
            title_to_id[new_item.title] = str(new_item.id)
            created_items.append({
                "id": str(new_item.id),
                "title": new_item.title,
                "is_category": new_item.is_category,
            })

        except Exception as e:
            errors.append({
                "title": item_data.get("title", "未知项目"),
                "error": str(e),
            })

    # 统一规范化（与 templates.py 同一规则）：只要某节点下挂了子项，
    # 就强制升级为分类目录并清空检查项属性。
    # LLM 抽取结果不受控，这一步是防止"有子项但未标分类"的脏数据入库的最后一道闸。
    parent_ids = {obj.parent_id for obj in new_objects if obj.parent_id is not None}
    if parent_ids:
        for obj in new_objects:
            if obj.id in parent_ids:
                normalize_as_category(obj)
        # 本次新增的子项若挂到了历史条目下，该历史条目同样需要升级
        hist_res = await db.execute(
            select(TemplateItem).where(TemplateItem.id.in_(parent_ids))
        )
        for obj in hist_res.scalars().all():
            normalize_as_category(obj)

    await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "ai_apply_items",
        "inspection_template",
        template_id,
        detail={
            "items_created": len(created_items),
            "errors": len(errors),
        }
    )

    return make_response(
        data={
            "created_count": len(created_items),
            "created_items": created_items,
            "errors": errors,
        }
    )


@router.post("/refine", response_model=ApiResponse)
async def refine_extracted_items(
    request: RefineRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """AI优化检查项列表（使用JSON body）"""
    result = await ai_extract_service.refine_items(
        items=request.items,
        instruction=request.instruction,
    )

    if result.get("success"):
        return make_response(data={"items": result.get("items", [])})
    else:
        return make_response(
            code=500,
            message=f"优化失败: {result.get('error', '未知错误')}",
            data={"items": request.items}
        )


@router.post("/refine/stream")
async def refine_extracted_items_stream(
    request: RefineRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """AI 优化检查项列表（SSE 流式：推送思考过程与结构化输出）"""
    async def generate():
        try:
            async for chunk in ai_extract_service.refine_items_stream(
                items=request.items,
                instruction=request.instruction,
            ):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
