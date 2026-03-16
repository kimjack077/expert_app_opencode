import asyncio
import sys
sys.path.insert(0, '.')

from app.database import engine
from app.models import Base

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print('Database recreated successfully')

if __name__ == '__main__':
    asyncio.run(init_db())
