import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.config import settings
from datetime import datetime
import uuid

async def create_test_tasks():
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT id FROM users WHERE username = 'expert'"))
        expert = result.scalar_one_or_none()
        
        result = await conn.execute(text("SELECT id FROM inspection_templates WHERE code = 'TPL-FOOD-RESTAURANT-001'"))
        template = result.scalar_one_or_none()
        
        if not expert or not template:
            print(f"Expert: {expert}, Template: {template}")
            return
        
        tasks = [
            ("2026年第一批餐饮单位食品安全检查 — 顺发川菜馆", "顺发川菜馆", "XX市XX区解放路188号", "王老板", "138-0000-1001"),
            ("2026年第一批餐饮单位食品安全检查 — 好味轩快餐", "好味轩快餐", "XX市XX区人民路66号", "张经理", "138-0000-2002"),
            ("2026年第一批餐饮单位食品安全检查 — 学府路小吃店", "学府路小吃店", "XX市XX区学府路88号", "李老板", "138-0000-3003"),
        ]
        
        scheduled = datetime(2026, 2, 23, 9, 0, 0)
        
        for i, (title, target, addr, contact, phone) in enumerate(tasks):
            task_id = str(uuid.uuid4())
            await conn.execute(text("""
                INSERT INTO inspection_tasks (id, task_no, title, template_id, assigned_to, assigned_by, target_name, target_address, target_contact, target_phone, scheduled_at, status)
                VALUES (:id, :task_no, :title, :tid, :expert, :admin, :target, :addr, :contact, :phone, :scheduled, 'pending')
            """), {
                "id": task_id,
                "task_no": f"TASK-2026-0223-00{i+1}",
                "title": title,
                "tid": template,
                "expert": expert,
                "admin": "ab5acfd5-51bb-4ea4-ad8a-1574d07e4233",
                "target": target,
                "addr": addr,
                "contact": contact,
                "phone": phone,
                "scheduled": scheduled
            })
            print(f"Created task: {title}")
        
    await engine.dispose()
    print("Tasks created!")

if __name__ == '__main__':
    asyncio.run(create_test_tasks())
