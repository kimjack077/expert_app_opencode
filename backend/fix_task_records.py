"""修复检查任务缺少检查项记录的问题"""
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.task import InspectionTask, TaskItemRecord
from app.models.template import TemplateItem


async def fix_missing_records():
    async with AsyncSessionLocal() as db:
        tasks_result = await db.execute(
            select(InspectionTask).where(InspectionTask.template_id.isnot(None))
        )
        tasks = tasks_result.scalars().all()
        
        fixed_count = 0
        for task in tasks:
            records_result = await db.execute(
                select(TaskItemRecord).where(TaskItemRecord.task_id == task.id)
            )
            existing_records = records_result.scalars().all()
            
            if len(existing_records) == 0:
                print(f"修复任务: {task.task_no} - {task.title}")
                
                items_result = await db.execute(
                    select(TemplateItem)
                    .where(TemplateItem.template_id == task.template_id)
                    .order_by(TemplateItem.sort_order)
                )
                items = items_result.scalars().all()
                
                for item in items:
                    record = TaskItemRecord(
                        task_id=task.id,
                        template_item_id=item.id,
                    )
                    db.add(record)
                
                fixed_count += 1
        
        await db.commit()
        print(f"\n修复完成！共修复 {fixed_count} 个任务")


if __name__ == "__main__":
    asyncio.run(fix_missing_records())
