import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.config import settings
import bcrypt

async def update_passwords():
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(settings.DATABASE_URL)
    
    admin_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    expert_hash = bcrypt.hashpw('expert123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    async with engine.begin() as conn:
        await conn.execute(text("""
            UPDATE users SET hashed_password = :hash WHERE username = 'admin'
        """), {"hash": admin_hash})
        print("Admin password updated")
        
        await conn.execute(text("""
            UPDATE users SET hashed_password = :hash WHERE username = 'expert'
        """), {"hash": expert_hash})
        print("Expert password updated")
    
    await engine.dispose()
    print("Passwords updated!")

if __name__ == '__main__':
    asyncio.run(update_passwords())
