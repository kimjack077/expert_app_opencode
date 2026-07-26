from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.enterprise import (
    Enterprise,
    EnterpriseQualification,
    EnterpriseProduct,
    EnterpriseEquipment,
    EnterprisePersonnel,
    RectificationRecord,
)
from app.models.record import InspectionRecord, InspectionRecordItem
from app.schemas import ApiResponse
from app.schemas.enterprise import (
    EnterpriseCreate,
    EnterpriseUpdate,
    EnterpriseResponse,
    EnterpriseDetail,
    QualificationCreate,
    QualificationUpdate,
    QualificationResponse,
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    RectificationCreate,
    RectificationUpdate,
    RectificationResponse,
)
from app.utils.security import get_current_user, get_current_admin_user
from app.services import AuditService

router = APIRouter()


def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.now(timezone.utc)
    )


@router.get("", response_model=ApiResponse)
async def get_enterprises(
    name: Optional[str] = Query(None),
    credit_code: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Enterprise).where(Enterprise.is_deleted == False)  # noqa: E712

    if name:
        query = query.where(Enterprise.name.ilike(f"%{name}%"))
    if credit_code:
        query = query.where(Enterprise.credit_code.ilike(f"%{credit_code}%"))
    if district:
        query = query.where(Enterprise.district == district)
    if risk_level:
        query = query.where(Enterprise.risk_level == risk_level)
    if status:
        query = query.where(Enterprise.status == status)

    query = query.order_by(Enterprise.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    enterprises = result.scalars().all()

    total_query = select(func.count(Enterprise.id)).where(Enterprise.is_deleted == False)  # noqa: E712
    if name:
        total_query = total_query.where(Enterprise.name.ilike(f"%{name}%"))
    if credit_code:
        total_query = total_query.where(Enterprise.credit_code.ilike(f"%{credit_code}%"))
    if district:
        total_query = total_query.where(Enterprise.district == district)
    if risk_level:
        total_query = total_query.where(Enterprise.risk_level == risk_level)
    if status:
        total_query = total_query.where(Enterprise.status == status)

    total = (await db.execute(total_query)).scalar()

    return make_response(
        data={
            "items": [EnterpriseResponse.model_validate(e).model_dump() for e in enterprises],
            "total": total,
        }
    )


@router.post("", response_model=ApiResponse)
async def create_enterprise(
    enterprise_data: EnterpriseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    enterprise = Enterprise(**enterprise_data.model_dump())
    db.add(enterprise)
    await db.commit()
    await db.refresh(enterprise)

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "create_enterprise",
        "enterprise",
        str(enterprise.id),
    )

    return make_response(data=EnterpriseResponse.model_validate(enterprise).model_dump())


@router.get("/{enterprise_id}", response_model=ApiResponse)
async def get_enterprise(
    enterprise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Enterprise)
        .options(
            selectinload(Enterprise.qualifications),
            selectinload(Enterprise.products),
        )
        .where(Enterprise.id == enterprise_id)
        .where(Enterprise.is_deleted == False)  # noqa: E712
    )
    enterprise = result.scalar_one_or_none()

    if not enterprise:
        raise HTTPException(status_code=404, detail="Enterprise not found")

    return make_response(data=EnterpriseDetail.model_validate(enterprise).model_dump())


@router.put("/{enterprise_id}", response_model=ApiResponse)
async def update_enterprise(
    enterprise_id: str,
    enterprise_data: EnterpriseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    enterprise = await db.get(Enterprise, enterprise_id)
    if not enterprise or enterprise.is_deleted:
        raise HTTPException(status_code=404, detail="Enterprise not found")

    update_data = enterprise_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(enterprise, key, value)

    await db.commit()
    await db.refresh(enterprise)

    return make_response(data=EnterpriseResponse.model_validate(enterprise).model_dump())


@router.delete("/{enterprise_id}", response_model=ApiResponse)
async def delete_enterprise(
    enterprise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    enterprise = await db.get(Enterprise, enterprise_id)
    if not enterprise or enterprise.is_deleted:
        raise HTTPException(status_code=404, detail="Enterprise not found")

    from app.utils.soft_delete import soft_delete

    await soft_delete(db, enterprise, unique_fields=["credit_code"])
    await db.commit()

    return make_response(message="Enterprise deleted")


@router.get("/{enterprise_id}/qualifications", response_model=ApiResponse)
async def get_qualifications(
    enterprise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(EnterpriseQualification)
        .where(
            EnterpriseQualification.enterprise_id == enterprise_id,
            EnterpriseQualification.is_deleted == False,  # noqa: E712
        )
        .order_by(EnterpriseQualification.valid_until.desc())
    )
    qualifications = result.scalars().all()

    return make_response(
        data=[QualificationResponse.model_validate(q).model_dump() for q in qualifications]
    )


@router.post("/{enterprise_id}/qualifications", response_model=ApiResponse)
async def create_qualification(
    enterprise_id: str,
    qual_data: QualificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    qual_data.enterprise_id = enterprise_id
    qualification = EnterpriseQualification(**qual_data.model_dump())
    db.add(qualification)
    await db.commit()
    await db.refresh(qualification)

    return make_response(data=QualificationResponse.model_validate(qualification).model_dump())


@router.put("/qualifications/{qual_id}", response_model=ApiResponse)
async def update_qualification(
    qual_id: str,
    qual_data: QualificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    qualification = await db.get(EnterpriseQualification, qual_id)
    if not qualification or qualification.is_deleted:
        raise HTTPException(status_code=404, detail="Qualification not found")

    update_data = qual_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(qualification, key, value)

    await db.commit()
    await db.refresh(qualification)

    return make_response(data=QualificationResponse.model_validate(qualification).model_dump())


@router.delete("/qualifications/{qual_id}", response_model=ApiResponse)
async def delete_qualification(
    qual_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """删除企业资质（软删除）"""
    qualification = await db.get(EnterpriseQualification, qual_id)
    if not qualification or qualification.is_deleted:
        raise HTTPException(status_code=404, detail="Qualification not found")

    from app.utils.soft_delete import soft_delete

    await soft_delete(db, qualification)
    await db.commit()

    return make_response(message="Qualification deleted")


@router.get("/{enterprise_id}/products", response_model=ApiResponse)
async def get_products(
    enterprise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(EnterpriseProduct)
        .where(EnterpriseProduct.enterprise_id == enterprise_id)
        .order_by(EnterpriseProduct.created_at.desc())
    )
    products = result.scalars().all()

    return make_response(
        data=[ProductResponse.model_validate(p).model_dump() for p in products]
    )


@router.post("/{enterprise_id}/products", response_model=ApiResponse)
async def create_product(
    enterprise_id: str,
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    product_data.enterprise_id = enterprise_id
    product = EnterpriseProduct(**product_data.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)

    return make_response(data=ProductResponse.model_validate(product).model_dump())


@router.get("/rectifications/", response_model=ApiResponse)
async def get_rectifications(
    enterprise_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(RectificationRecord).options(selectinload(RectificationRecord.enterprise))

    if enterprise_id:
        query = query.where(RectificationRecord.enterprise_id == enterprise_id)
    if status:
        query = query.where(RectificationRecord.status == status)

    query = query.order_by(RectificationRecord.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    rectifications = result.scalars().all()

    return make_response(
        data=[RectificationResponse.model_validate(r).model_dump() for r in rectifications]
    )


@router.post("/rectifications/", response_model=ApiResponse)
async def create_rectification(
    rect_data: RectificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    rectification = RectificationRecord(
        **rect_data.model_dump(),
        created_by=current_user.id,
    )
    db.add(rectification)
    await db.commit()
    await db.refresh(rectification)

    return make_response(data=RectificationResponse.model_validate(rectification).model_dump())


@router.put("/rectifications/{rect_id}", response_model=ApiResponse)
async def update_rectification(
    rect_id: str,
    rect_data: RectificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rectification = await db.get(RectificationRecord, rect_id)
    if not rectification:
        raise HTTPException(status_code=404, detail="Rectification record not found")

    update_data = rect_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rectification, key, value)

    await db.commit()
    await db.refresh(rectification)

    return make_response(data=RectificationResponse.model_validate(rectification).model_dump())


@router.post("/rectifications/{rect_id}/review", response_model=ApiResponse)
async def review_rectification(
    rect_id: str,
    status: str,
    rectification_result: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    rectification = await db.get(RectificationRecord, rect_id)
    if not rectification:
        raise HTTPException(status_code=404, detail="Rectification record not found")

    rectification.status = status
    rectification.reviewer = current_user.id
    rectification.reviewed_at = datetime.now(timezone.utc)
    if rectification_result:
        rectification.rectification_result = rectification_result

    await db.commit()
    await db.refresh(rectification)

    return make_response(data=RectificationResponse.model_validate(rectification).model_dump())


@router.get("/{enterprise_id}/risk-profile", response_model=ApiResponse)
async def get_enterprise_risk_profile(
    enterprise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enterprise = await db.get(Enterprise, enterprise_id)
    if not enterprise or enterprise.is_deleted:
        raise HTTPException(status_code=404, detail="Enterprise not found")

    history_records_result = await db.execute(
        select(InspectionRecord)
        .where(InspectionRecord.enterprise_id == enterprise_id)
        .where(InspectionRecord.status == "submitted")
        .order_by(desc(InspectionRecord.inspection_date))
        .limit(5)
    )
    history_records = history_records_result.scalars().all()

    history_list = []
    for record in history_records:
        fail_count_result = await db.execute(
            select(func.count(InspectionRecordItem.id))
            .where(InspectionRecordItem.record_id == record.id)
            .where(InspectionRecordItem.radio_value == "fail")
        )
        fail_count = fail_count_result.scalar() or 0

        result_text = "合格"
        if record.overall_result == "fail":
            result_text = "不合格"
        elif record.overall_result == "partial_pass":
            result_text = "基本合格"

        history_list.append({
            "date": record.inspection_date.strftime("%Y-%m") if record.inspection_date else "",
            "result": result_text,
            "fail_count": fail_count if fail_count > 0 else None
        })

    focus_points = []

    if history_records:
        latest_record = history_records[0]
        fail_items_result = await db.execute(
            select(InspectionRecordItem)
            .where(InspectionRecordItem.record_id == latest_record.id)
            .where(InspectionRecordItem.radio_value == "fail")
            .limit(3)
        )
        fail_items = fail_items_result.scalars().all()
        for item in fail_items:
            if item.item_title:
                focus_points.append(f"上次\"{item.item_title}\"不合格")

    def map_risk_level(level):
        if not level:
            return "low"
        level_map = {
            "A": "high",
            "B": "medium",
            "C": "low",
            "D": "low",
            "high": "high",
            "medium": "medium",
            "low": "low"
        }
        return level_map.get(level, "low")

    mapped_risk_level = map_risk_level(enterprise.risk_level)

    if mapped_risk_level == "high":
        focus_points.append("企业风险等级为高风险")
    elif mapped_risk_level == "medium":
        focus_points.append("企业风险等级为中风险")

    total_records_result = await db.execute(
        select(func.count(InspectionRecord.id))
        .where(InspectionRecord.enterprise_id == enterprise_id)
        .where(InspectionRecord.status == "submitted")
    )
    total_records = total_records_result.scalar() or 0

    fail_records_result = await db.execute(
        select(func.count(InspectionRecord.id))
        .where(InspectionRecord.enterprise_id == enterprise_id)
        .where(InspectionRecord.status == "submitted")
        .where(InspectionRecord.overall_result == "fail")
    )
    fail_records = fail_records_result.scalar() or 0

    risk_score = 0
    if total_records > 0:
        fail_rate = (fail_records / total_records) * 100
        if mapped_risk_level == "high":
            risk_score = min(100, 60 + fail_rate * 0.4)
        elif mapped_risk_level == "medium":
            risk_score = min(100, 40 + fail_rate * 0.4)
        else:
            risk_score = min(100, 20 + fail_rate * 0.4)

    risk_level = mapped_risk_level
    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 40:
        risk_level = "medium"

    return make_response(data={
        "enterprise_id": str(enterprise_id),
        "enterprise_name": enterprise.name,
        "risk_level": risk_level,
        "risk_score": round(risk_score, 1),
        "history_records": history_list,
        "focus_points": focus_points[:5],
        "total_inspections": total_records,
        "fail_inspections": fail_records
    })
