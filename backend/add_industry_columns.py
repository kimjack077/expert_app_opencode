import asyncio
from sqlalchemy import text
from app.database import engine, Base
from app.models.industry import Industry

async def init_industry():
    async with engine.begin() as conn:
        # Create industries table if not exists
        await conn.run_sync(Base.metadata.create_all)
        
        # Add industry_id column to users
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN industry_id UUID REFERENCES industries(id) ON DELETE SET NULL;"))
            print("Added industry_id to users.")
        except Exception as e:
            print(f"Skipping users: {e}")
            
        # Add industry_id column to enterprises
        try:
            await conn.execute(text("ALTER TABLE enterprises ADD COLUMN industry_id UUID REFERENCES industries(id) ON DELETE SET NULL;"))
            print("Added industry_id to enterprises.")
        except Exception as e:
            print(f"Skipping enterprises: {e}")
            
        # Add industry_id column to inspection_templates
        try:
            await conn.execute(text("ALTER TABLE inspection_templates ADD COLUMN industry_id UUID REFERENCES industries(id) ON DELETE SET NULL;"))
            print("Added industry_id to inspection_templates.")
        except Exception as e:
            print(f"Skipping inspection_templates: {e}")

if __name__ == "__main__":
    asyncio.run(init_industry())
