"""
检查数据库中的数据
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import select, text
from app.database import AsyncSessionLocal as async_session_maker
from app.models.audit_project import AuditProject, AuditPlanItem
from app.models.enterprise import Enterprise
from app.models.task import InspectionTask


async def check_data():
    """检查相关数据"""
    async with async_session_maker() as db:
        print("=" * 60)
        print("检查数据库数据")
        print("=" * 60)

        # 1. 检查所有企业
        print("\n1. 企业列表:")
        result = await db.execute(select(Enterprise))
        enterprises = result.scalars().all()
        for e in enterprises:
            print(f"   ID: {e.id}")
            print(f"   名称: {e.name}")
            print(f"   地址: {e.address}")
            print("-" * 40)

        # 2. 检查所有审核项目
        print("\n2. 审核项目列表:")
        result = await db.execute(select(AuditProject))
        projects = result.scalars().all()
        for p in projects:
            print(f"   ID: {p.id}")
            print(f"   标题: {p.title}")
            print(f"   企业ID: {p.enterprise_id}")
            print("-" * 40)

        # 3. 检查所有审核计划项
        print("\n3. 审核计划项列表:")
        result = await db.execute(select(AuditPlanItem))
        plan_items = result.scalars().all()
        for pi in plan_items:
            print(f"   ID: {pi.id}")
            print(f"   项目ID: {pi.project_id}")
            print(f"   区域名称: {pi.area_name}")
            print(f"   关联任务ID: {pi.inspection_task_id}")
            print("-" * 40)

        # 4. 检查所有检查任务
        print("\n4. 检查任务列表:")
        result = await db.execute(select(InspectionTask))
        tasks = result.scalars().all()
        for t in tasks:
            print(f"   ID: {t.id}")
            print(f"   编号: {t.task_no}")
            print(f"   标题: {t.title}")
            print(f"   target_name: {t.target_name}")
            print(f"   target_address: {t.target_address}")
            print("-" * 40)

        # 5. 检查关联关系
        print("\n5. 审核计划项与检查任务关联:")
        result = await db.execute(
            select(AuditPlanItem, InspectionTask)
            .join(InspectionTask, AuditPlanItem.inspection_task_id == InspectionTask.id)
        )
        items = result.all()
        for plan_item, inspection_task in items:
            project = await db.get(AuditProject, plan_item.project_id)
            enterprise = None
            if project:
                enterprise = await db.get(Enterprise, project.enterprise_id)

            print(f"   计划项ID: {plan_item.id}")
            print(f"   区域名称: {plan_item.area_name}")
            print(f"   任务ID: {inspection_task.id}")
            print(f"   任务target_name: {inspection_task.target_name}")
            print(f"   任务target_address: {inspection_task.target_address}")
            print(f"   企业名称: {enterprise.name if enterprise else 'N/A'}")
            print(f"   企业地址: {enterprise.address if enterprise else 'N/A'}")
            print("=" * 40)


if __name__ == "__main__":
    asyncio.run(check_data())
