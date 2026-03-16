import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.config import settings

async def check_records():
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT id, task_id, check_item_id FROM inspection_records"))
        records = result.fetchall()
        print(f"Total inspection_records: {len(records)}")
        for r in records:
            print(f"  {r}")
        
        result = await conn.execute(text("SELECT id, template_id, check_item_id FROM template_items"))
        items = result.fetchall()
        print(f"\nTotal template_items: {len(items)}")
        for i in items:
            print(f"  {i}")
        
        result = await conn.execute(text("SELECT id, template_id FROM inspection_tasks"))
        tasks = result.fetchall()
        print(f"\nTotal tasks: {len(tasks)}")
        for t in tasks:
            print(f"  {t}")
    
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(check_records())
