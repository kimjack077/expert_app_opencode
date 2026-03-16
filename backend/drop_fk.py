"""
drop_fk_constraint.py
"""
import asyncio
from sqlalchemy import text
from app.database import engine

async def run():
    async with engine.begin() as conn:
        # Try to drop the foreign key constraint on inspection_record_items.template_item_id
        # PostgreSQL constraint name is usually table_name_column_name_fkey
        constraint_query = text("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'inspection_record_items' 
              AND constraint_type = 'FOREIGN KEY'
              AND constraint_name LIKE '%template_item_id%';
        """)
        result = await conn.execute(constraint_query)
        constraints = result.scalars().all()
        for const in constraints:
            print(f"Dropping constraint {const}")
            await conn.execute(text(f"ALTER TABLE inspection_record_items DROP CONSTRAINT {const};"))
            
        print("Done dropping FK constraints.")
        
        # We also need to reverse the 'SET NULL' fix from templates.py !
        # But wait, we can't restore the UUID if it's already NULL. We'll just rely on our title fallback in build_tree.

if __name__ == "__main__":
    asyncio.run(run())
