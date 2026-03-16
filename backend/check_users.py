"""检查数据库用户"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def check_users():
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        print('\n' + '=' * 80)
        print('用户列表')
        print('=' * 80)
        
        result = await conn.execute(text("""
            SELECT id, username, email, role, is_active, created_at 
            FROM users 
            ORDER BY created_at
        """))
        users = result.fetchall()
        
        if not users:
            print('\n⚠️  数据库中没有用户！')
        else:
            print(f'\n共找到 {len(users)} 个用户:\n')
            for u in users:
                user_id, username, email, role, is_active, created_at = u
                status = "✓ 激活" if is_active else "✗ 禁用"
                print(f"  [{status}] {username}")
                print(f"    - 邮箱：{email}")
                print(f"    - 角色：{role}")
                print(f"    - ID: {user_id}")
                print()
        
        print('=' * 80)
    
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(check_users())
