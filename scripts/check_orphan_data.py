"""检查软删级联孤儿数据"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from sqlalchemy import select, and_
from app.database import AsyncSessionLocal
from app.models.template import TemplateItem, InspectionTemplate
from app.models.enterprise import (
    EnterpriseQualification,
    EnterpriseProduct,
    Enterprise
)


async def check_orphans():
    """检查各类孤儿数据"""
    async with AsyncSessionLocal() as db:
        print("=" * 60)
        print("软删孤儿数据检查报告")
        print("=" * 60)

        # 1. 检查模板项孤儿（父模板已软删但子项未删）
        query = select(TemplateItem).join(
            InspectionTemplate,
            TemplateItem.template_id == InspectionTemplate.id
        ).where(
            and_(
                InspectionTemplate.is_deleted == True,
                TemplateItem.is_deleted == False
            )
        )
        result = await db.execute(query)
        orphan_items = result.scalars().all()

        print(f"\n1. 模板项孤儿（父模板已删）: {len(orphan_items)} 条")
        if orphan_items:
            for item in orphan_items[:5]:  # 显示前5条
                print(f"   - TemplateItem ID={item.id}, template_id={item.template_id}, title={item.title}")
            if len(orphan_items) > 5:
                print(f"   ... 还有 {len(orphan_items) - 5} 条")

        # 2. 检查企业资质孤儿
        query = select(EnterpriseQualification).join(
            Enterprise,
            EnterpriseQualification.enterprise_id == Enterprise.id
        ).where(
            and_(
                Enterprise.is_deleted == True,
                EnterpriseQualification.is_deleted == False
            )
        )
        result = await db.execute(query)
        orphan_quals = result.scalars().all()

        print(f"\n2. 企业资质孤儿（父企业已删）: {len(orphan_quals)} 条")
        if orphan_quals:
            for q in orphan_quals[:5]:
                print(f"   - Qualification ID={q.id}, enterprise_id={q.enterprise_id}, type={q.qual_type}")
            if len(orphan_quals) > 5:
                print(f"   ... 还有 {len(orphan_quals) - 5} 条")

        # 3. 检查企业产品孤儿（EnterpriseProduct 没有 SoftDeleteMixin，直接检查关联）
        query = select(EnterpriseProduct).join(
            Enterprise,
            EnterpriseProduct.enterprise_id == Enterprise.id
        ).where(
            Enterprise.is_deleted == True
        )
        result = await db.execute(query)
        orphan_products = result.scalars().all()

        print(f"\n3. 企业产品孤儿（父企业已删）: {len(orphan_products)} 条")
        if orphan_products:
            for p in orphan_products[:5]:
                print(f"   - Product ID={p.id}, enterprise_id={p.enterprise_id}, name={p.name}")
            if len(orphan_products) > 5:
                print(f"   ... 还有 {len(orphan_products) - 5} 条")

        # 汇总
        total = len(orphan_items) + len(orphan_quals) + len(orphan_products)

        print("\n" + "=" * 60)
        print(f"总计孤儿数据: {total} 条")
        print("=" * 60)

        return {
            'template_items': orphan_items,
            'qualifications': orphan_quals,
            'products': orphan_products,
            'total': total
        }


if __name__ == "__main__":
    result = asyncio.run(check_orphans())
