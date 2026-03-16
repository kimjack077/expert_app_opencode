import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.config import settings
from app.models import Base

async def reset_db():
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
        print("UUID extension created")
    
    tables = [
        "audit_logs", "llm_call_logs", "media_files", "check_records",
        "inspection_tasks", "template_items", "inspection_templates",
        "check_items", "standard_categories", "users", "organizations"
    ]
    
    async with engine.begin() as conn:
        for table in tables:
            try:
                await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                print(f"Dropped table: {table}")
            except Exception as e:
                print(f"Error dropping {table}: {e}")
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("All tables created")
    
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(reset_db())
