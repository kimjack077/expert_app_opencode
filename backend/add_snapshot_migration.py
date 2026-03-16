"""
add_template_snapshot_and_denormalized_fields

在 inspection_records 增加 template_snapshot 字段，
在 inspection_record_items 增加冗余字段（用于历史快照回显）。

手动执行：
    psql -h <HOST> -U <USER> -d <DB> -f this_file.sql
或在后端初始化时执行（见 init_db.py）。
"""

ADD_COLUMNS_SQL = """
-- Step1: inspection_records 新增快照字段
ALTER TABLE inspection_records
  ADD COLUMN IF NOT EXISTS template_snapshot JSONB;

-- Step2: inspection_record_items 新增冗余字段
ALTER TABLE inspection_record_items
  ADD COLUMN IF NOT EXISTS item_title        VARCHAR(500),
  ADD COLUMN IF NOT EXISTS item_description  TEXT,
  ADD COLUMN IF NOT EXISTS item_check_method TEXT,
  ADD COLUMN IF NOT EXISTS item_legal_basis  TEXT,
  ADD COLUMN IF NOT EXISTS item_standard_ref TEXT,
  ADD COLUMN IF NOT EXISTS item_risk_level   VARCHAR(20),
  ADD COLUMN IF NOT EXISTS item_check_type   VARCHAR(50),
  ADD COLUMN IF NOT EXISTS item_result_options JSONB,
  ADD COLUMN IF NOT EXISTS item_min_value    NUMERIC,
  ADD COLUMN IF NOT EXISTS item_max_value    NUMERIC,
  ADD COLUMN IF NOT EXISTS item_unit         VARCHAR(50);
"""

if __name__ == "__main__":
    import asyncio
    from app.database import engine

    async def run():
        async with engine.begin() as conn:
            for stmt in ADD_COLUMNS_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    await conn.execute(__import__("sqlalchemy").text(stmt + ";"))
        print("[Migration] template_snapshot columns added successfully.")

    asyncio.run(run())
