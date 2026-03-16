"""检查重复用户名"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def check_duplicates():
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        print('\n' + '=' * 80)
        print('检查重复用户名')
        print('=' * 80)
        
        result = await conn.execute(text("""
            SELECT username, COUNT(*) as count
            FROM users
            GROUP BY username
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        
        if duplicates:
            print('\n⚠️  发现重复用户名:')
            for dup in duplicates:
                print(f'  - {dup[0]}: {dup[1]} 次')
        else:
            print('\n✓ 没有重复用户名')
        
        # 检查所有用户
        result = await conn.execute(text("""
            SELECT id, username, email, role, is_active 
            FROM users 
            ORDER BY username, created_at
        """))
        users = result.fetchall()
        
        print(f'\n所有用户 (共{len(users)}个):')
        for u in users:
            status = "✓" if u[4] else "✗"
            print(f'  [{status}] {u[1]} ({u[3]}) - {u[0]}')
        
        print('\n' + '=' * 80)
    
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(check_duplicates())
