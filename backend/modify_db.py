import asyncio
from sqlalchemy import text
from app.database import engine

async def update_tables():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE inspection_templates ADD COLUMN is_quantified BOOLEAN DEFAULT FALSE;"))
        except Exception as e:
            print(e)
            
        columns = [
            "ALTER TABLE template_items ADD COLUMN score_weight NUMERIC;",
            "ALTER TABLE template_items ADD COLUMN default_score NUMERIC;",
            "ALTER TABLE template_items ADD COLUMN allow_attachment BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE template_items ADD COLUMN attachment_required BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE template_items ADD COLUMN ai_prompt_template TEXT;",
            "ALTER TABLE inspection_records ADD COLUMN total_score NUMERIC;"
        ]
        snapshot_cols = [
            "ALTER TABLE inspection_record_items ADD COLUMN item_score_weight NUMERIC;",
            "ALTER TABLE inspection_record_items ADD COLUMN item_default_score NUMERIC;",
            "ALTER TABLE inspection_record_items ADD COLUMN item_allow_attachment BOOLEAN;",
            "ALTER TABLE inspection_record_items ADD COLUMN item_attachment_required BOOLEAN;",
            "ALTER TABLE inspection_record_items ADD COLUMN item_ai_prompt_template TEXT;",
        ]
        
        for col in columns + snapshot_cols:
            try:
                await conn.execute(text(col))
            except Exception as e:
                print(e)

if __name__ == "__main__":
    asyncio.run(update_tables())
