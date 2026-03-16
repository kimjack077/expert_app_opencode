from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from ..database import get_db
from ..models import Industry
from ..schemas.industry import IndustryCreate, IndustryUpdate, IndustryResponse, IndustryTreeResponse
from ..schemas.common import ApiResponse
from app.utils.security import get_current_user

router = APIRouter()

def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.utcnow()
    )

@router.get("/tree", response_model=ApiResponse)
async def get_industry_tree(
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    query = select(Industry)
    if is_active is not None:
        query = query.where(Industry.is_active == is_active)
    query = query.order_by(Industry.sort_order.asc())
    
    result = await db.execute(query)
    all_industries = result.scalars().all()
    
    # Build tree - manually construct dict to avoid lazy loading issues
    industry_dict = {}
    for ind in all_industries:
        industry_dict[ind.id] = {
            "id": ind.id,
            "name": ind.name,
            "code": ind.code,
            "description": ind.description,
            "parent_id": ind.parent_id,
            "sort_order": ind.sort_order,
            "icon": ind.icon,
            "is_active": ind.is_active,
            "created_at": ind.created_at,
            "updated_at": ind.updated_at,
            "children": []
        }
        
    tree = []
    for ind in all_industries:
        if ind.parent_id and ind.parent_id in industry_dict:
            industry_dict[ind.parent_id]["children"].append(industry_dict[ind.id])
        else:
            tree.append(industry_dict[ind.id])
            
    # Sort children
    def sort_children(nodes):
        nodes.sort(key=lambda x: x["sort_order"])
        for node in nodes:
            sort_children(node["children"])
            
    sort_children(tree)
    return make_response(data=tree)

@router.get("/", response_model=ApiResponse)
async def get_industries(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    result = await db.execute(select(Industry).order_by(Industry.sort_order.asc()))
    industries = result.scalars().all()
    return make_response(data=[IndustryResponse.model_validate(i).model_dump() for i in industries])

@router.get("/{industry_id}", response_model=ApiResponse)
async def get_industry(
    industry_id: UUID, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    ind = await db.get(Industry, industry_id)
    if not ind:
        raise HTTPException(status_code=404, detail="行业分类不存在")
    return make_response(data=IndustryResponse.model_validate(ind).model_dump())

@router.post("/", response_model=ApiResponse)
async def create_industry(
    data: IndustryCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if data.code:
        result = await db.execute(select(Industry).where(Industry.code == data.code))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="分类编码已存在")
            
    ind = Industry(**data.model_dump())
    db.add(ind)
    await db.commit()
    await db.refresh(ind)
    return make_response(data=IndustryResponse.model_validate(ind).model_dump())

@router.put("/{industry_id}", response_model=ApiResponse)
async def update_industry(
    industry_id: UUID, 
    data: IndustryUpdate, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    ind = await db.get(Industry, industry_id)
    if not ind:
        raise HTTPException(status_code=404, detail="行业分类不存在")
        
    update_data = data.model_dump(exclude_unset=True)
    if 'code' in update_data and update_data['code']:
        result = await db.execute(select(Industry).where(Industry.code == update_data['code'], Industry.id != industry_id))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="分类编码已存在")
            
    for key, value in update_data.items():
        setattr(ind, key, value)
        
    await db.commit()
    await db.refresh(ind)
    return make_response(data=IndustryResponse.model_validate(ind).model_dump())

@router.delete("/{industry_id}", response_model=ApiResponse)
async def delete_industry(
    industry_id: UUID, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    ind = await db.get(Industry, industry_id)
    if not ind:
        raise HTTPException(status_code=404, detail="行业分类不存在")
        
    await db.delete(ind)
    await db.commit()
    return make_response(message="删除成功")
