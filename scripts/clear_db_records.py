import sys
import asyncio
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import text
from app.database import async_session_maker

async def clear_data():
    async with async_session_maker() as session:
        await session.execute(text("TRUNCATE TABLE inspection_record_items CASCADE;"))
        await session.execute(text("TRUNCATE TABLE inspection_records CASCADE;"))
        await session.execute(text("TRUNCATE TABLE template_items CASCADE;"))
        await session.execute(text("TRUNCATE TABLE inspection_templates CASCADE;"))
        await session.commit()
        print("All data cleared successfully.")

if __name__ == "__main__":
    asyncio.run(clear_data())
