import asyncio
import asyncpg

async def delete_template():
    conn = await asyncpg.connect(
        host='62.234.0.182',
        port=5432,
        user='db_admin',
        password='1234567890@sdtj',
        database='db_expert_opencode'
    )
    
    try:
        # 删除模板（会级联删除所有 items）
        await conn.execute(
            "DELETE FROM inspection_templates WHERE id = $1",
            '550e8400-e29b-41d4-a716-446655440001'
        )
        print("✅ 已删除旧的模板数据")
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(delete_template())
