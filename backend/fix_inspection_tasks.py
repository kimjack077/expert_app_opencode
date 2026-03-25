"""
修复检查任务数据脚本
将检查任务的 target_name 和 target_address 修正为企业名称和地址
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal as async_session_maker
from app.models.audit_project import AuditProject, AuditPlanItem
from app.models.enterprise import Enterprise
from app.models.task import InspectionTask


async def fix_inspection_tasks():
    """修复所有与审核计划关联的检查任务"""
    async with async_session_maker() as db:
        # 查询所有有关联检查任务的审核计划项
        result = await db.execute(
            select(AuditPlanItem, InspectionTask)
            .join(InspectionTask, AuditPlanItem.inspection_task_id == InspectionTask.id)
            .where(AuditPlanItem.inspection_task_id.isnot(None))
        )
        items = result.all()

        print(f"找到 {len(items)} 个需要修复的检查任务")

        fixed_count = 0
        for plan_item, inspection_task in items:
            # 获取项目信息
            project = await db.get(AuditProject, plan_item.project_id)
            if not project:
                print(f"  跳过: 审核计划项 {plan_item.id} 关联的项目不存在")
                continue

            # 获取企业信息
            enterprise = await db.get(Enterprise, project.enterprise_id)

            # 记录旧值
            old_target_name = inspection_task.target_name
            old_target_address = inspection_task.target_address

            # 修正 target_name 和 target_address
            if enterprise:
                inspection_task.target_name = enterprise.name
                inspection_task.target_address = enterprise.address
            else:
                inspection_task.target_name = project.title
                inspection_task.target_address = None

            # 同时修正标题
            inspection_task.title = f"{project.title} - {plan_item.area_name} - {plan_item.plan_date}"

            # 检查是否有变化
            if old_target_name != inspection_task.target_name or old_target_address != inspection_task.target_address:
                print(f"  修复任务 {inspection_task.id}:")
                print(f"    target_name: '{old_target_name}' -> '{inspection_task.target_name}'")
                print(f"    target_address: '{old_target_address}' -> '{inspection_task.target_address}'")
                fixed_count += 1

        if fixed_count > 0:
            await db.commit()
            print(f"\n成功修复 {fixed_count} 个检查任务")
        else:
            print("\n所有检查任务数据正确，无需修复")


async def check_all_tasks():
    """检查所有检查任务的数据状态"""
    async with async_session_maker() as db:
        # 查询所有检查任务
        result = await db.execute(select(InspectionTask))
        tasks = result.scalars().all()

        print(f"总共有 {len(tasks)} 个检查任务")

        # 分类统计
        from_audit_plan = 0
        manual_create = 0

        for task in tasks:
            # 检查是否来自审核计划
            result = await db.execute(
                select(AuditPlanItem).where(AuditPlanItem.inspection_task_id == task.id)
            )
            plan_item = result.scalar_one_or_none()

            if plan_item:
                from_audit_plan += 1
            else:
                manual_create += 1

        print(f"  - 来自审核计划: {from_audit_plan}")
        print(f"  - 手动创建: {manual_create}")


if __name__ == "__main__":
    print("=" * 60)
    print("检查任务数据修复工具")
    print("=" * 60)

    print("\n1. 检查所有检查任务状态...")
    asyncio.run(check_all_tasks())

    print("\n2. 修复来自审核计划的检查任务...")
    asyncio.run(fix_inspection_tasks())

    print("\n" + "=" * 60)
    print("修复完成")
    print("=" * 60)
