"""归档软删级联孤儿数据"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from sqlalchemy import select, and_, update
from app.database import AsyncSessionLocal
from app.models.template import TemplateItem, InspectionTemplate
from app.models.enterprise import (
    EnterpriseQualification,
    EnterpriseProduct,
    Enterprise
)


async def archive_orphans():
    """归档孤儿数据（软删除）"""
    async with AsyncSessionLocal() as db:
        print("=" * 60)
        print("开始归档软删孤儿数据")
        print("=" * 60)

        deleted_at = datetime.now()
        total_archived = 0

        # 1. 归档模板项孤儿（父模板已软删但子项未删）
        print("\n处理模板项孤儿...")
        query = select(TemplateItem.id).join(
            InspectionTemplate,
            TemplateItem.template_id == InspectionTemplate.id
        ).where(
            and_(
                InspectionTemplate.is_deleted == True,
                TemplateItem.is_deleted == False
            )
        )
        result = await db.execute(query)
        orphan_item_ids = [row[0] for row in result.all()]

        if orphan_item_ids:
            stmt = update(TemplateItem).where(
                TemplateItem.id.in_(orphan_item_ids)
            ).values(
                is_deleted=True,
                deleted_at=deleted_at
            )
            await db.execute(stmt)
            print(f"   ✓ 已归档 {len(orphan_item_ids)} 条模板项")
            total_archived += len(orphan_item_ids)
        else:
            print("   - 无需处理")

        # 2. 归档企业资质孤儿（父企业已删但资质未删）
        print("\n处理企业资质孤儿...")
        query = select(EnterpriseQualification.id).join(
            Enterprise,
            EnterpriseQualification.enterprise_id == Enterprise.id
        ).where(
            and_(
                Enterprise.is_deleted == True,
                EnterpriseQualification.is_deleted == False
            )
        )
        result = await db.execute(query)
        orphan_qual_ids = [row[0] for row in result.all()]

        if orphan_qual_ids:
            stmt = update(EnterpriseQualification).where(
                EnterpriseQualification.id.in_(orphan_qual_ids)
            ).values(
                is_deleted=True,
                deleted_at=deleted_at
            )
            await db.execute(stmt)
            print(f"   ✓ 已归档 {len(orphan_qual_ids)} 条企业资质")
            total_archived += len(orphan_qual_ids)
        else:
            print("   - 无需处理")

        # 3. 删除企业产品孤儿（EnterpriseProduct 无软删，直接物理删除）
        print("\n处理企业产品孤儿...")
        query = select(EnterpriseProduct.id).join(
            Enterprise,
            EnterpriseProduct.enterprise_id == Enterprise.id
        ).where(
            Enterprise.is_deleted == True
        )
        result = await db.execute(query)
        orphan_product_ids = [row[0] for row in result.all()]

        if orphan_product_ids:
            # 先获取要删除的产品详情（用于日志）
            query = select(EnterpriseProduct).where(
                EnterpriseProduct.id.in_(orphan_product_ids)
            )
            result = await db.execute(query)
            products_to_delete = result.scalars().all()

            # 执行物理删除
            for product in products_to_delete:
                await db.delete(product)

            print(f"   ✓ 已删除 {len(orphan_product_ids)} 条企业产品（物理删除）")
            total_archived += len(orphan_product_ids)
        else:
            print("   - 无需处理")

        # 提交事务
        await db.commit()

        print("\n" + "=" * 60)
        print(f"归档完成！共处理 {total_archived} 条孤儿数据")
        print("=" * 60)

        return total_archived


if __name__ == "__main__":
    print("【警告】此脚本将归档所有检测到的孤儿数据")
    print("按 Enter 继续，Ctrl+C 取消...")
    try:
        input()
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(0)

    result = asyncio.run(archive_orphans())
    print(f"\n✓ 归档操作成功完成，共处理 {result} 条数据")
