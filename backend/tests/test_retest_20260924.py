"""Read-only regressions for the September 24 retest findings."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enterprise import EnterpriseProduct
from app.routers.enterprises import update_product
from app.routers.industries import get_industries
from app.schemas.audit_project import AuditReportCreate, AuditReportUpdate
from app.schemas.enterprise import ProductUpdate
from app.schemas.record import InspectionRecordItemCorrection
from app.services.report_service import report_service


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("field,value,stored", [
    ("numeric_value", 10, "10"),
    ("numeric_value", 10.5, "10.5"),
    ("score_value", 45.5, "45.5"),
])
def test_correction_accepts_numeric_input_as_stored_text(field, value, stored):
    correction = InspectionRecordItemCorrection(reason="复核结果", **{field: value})
    assert getattr(correction, field) == stored


def test_correction_rejects_boolean_as_number():
    with pytest.raises(ValidationError):
        InspectionRecordItemCorrection(reason="复核结果", score_value=True)


def test_audit_report_rejects_unknown_summary_instead_of_silently_dropping_it():
    with pytest.raises(ValidationError):
        AuditReportCreate(report_type="QES", summary="无法落库的内容")
    with pytest.raises(ValidationError):
        AuditReportUpdate(summary="无法落库的内容")


class _IndustryDb:
    def __init__(self):
        self.query = None

    async def execute(self, query):
        self.query = query
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))


def test_industry_pagination_is_applied_only_when_requested():
    db = _IndustryDb()
    asyncio.run(get_industries(skip=0, limit=None, db=db, current_user=object()))
    assert "LIMIT" not in str(db.query)

    asyncio.run(get_industries(skip=2, limit=3, db=db, current_user=object()))
    sql = str(db.query)
    assert "LIMIT" in sql and "OFFSET" in sql


def test_report_uses_placeholder_when_legacy_snapshot_has_no_template_name():
    record = SimpleNamespace(
        id=uuid4(), template=None, template_snapshot={}, items=[], enterprise=None,
        enterprise_name=None, enterprise_address=None, contact_person=None,
        contact_phone=None, inspection_date=None, inspector=None,
        overall_result=None, total_score=None, remarks=None, judgment_note=None,
    )
    report = report_service.generate_report_data(record)
    assert report["inspection"]["template_name"] == "-"
    assert report["inspection"]["template_version"] == "-"


class _ProductDb:
    def __init__(self, enterprise_id, product):
        self.enterprise_id = enterprise_id
        self.product = product
        self.query = None
        self.committed = False

    async def get(self, _model, enterprise_id):
        assert enterprise_id == self.enterprise_id
        return SimpleNamespace(is_deleted=False)

    async def execute(self, query):
        self.query = query
        return SimpleNamespace(scalar_one_or_none=lambda: self.product)

    async def commit(self):
        self.committed = True

    async def refresh(self, _product):
        pass


def test_product_update_is_scoped_to_enterprise():
    enterprise_id = uuid4()
    product_id = uuid4()
    now = datetime.now(timezone.utc)
    product = EnterpriseProduct(
        id=product_id, enterprise_id=enterprise_id, name="旧产品",
        created_at=now, updated_at=now,
    )
    db = _ProductDb(str(enterprise_id), product)

    asyncio.run(update_product(
        enterprise_id=str(enterprise_id), product_id=str(product_id),
        product_data=ProductUpdate(name="新产品"), db=db, current_user=object(),
    ))

    assert db.committed and product.name == "新产品"
    where_sql = str(db.query.whereclause)
    assert "enterprise_products.id" in where_sql
    assert "enterprise_products.enterprise_id" in where_sql
