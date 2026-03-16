import asyncio
import sys
sys.path.insert(0, '.')

from app.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def list_users():
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT username, email, full_name, role, is_active 
            FROM users 
            ORDER BY created_at
        """))
        users = result.fetchall()
        
        print('\n' + '=' * 100)
        print('所有用户列表')
        print('=' * 100)
        print(f'{"用户名":<15} {"邮箱":<30} {"姓名":<15} {"角色":<20} {"状态":<10}')
        print('-' * 100)
        for user in users:
            username, email, full_name, role, is_active = user
            status = "激活" if is_active else "禁用"
            print(f'{username:<15} {email:<30} {full_name:<15} {role:<20} {status:<10}')
        print('=' * 100)
        print(f'\n总共 {len(users)} 个用户\n')
        print('默认密码说明：')
        print('  - admin 账号: admin123')
        print('  - expert 账号: expert123')
        print('  - 其他账号默认密码通常为: 用户名123 或 password123')
        print()

if __name__ == '__main__':
    asyncio.run(list_users())
