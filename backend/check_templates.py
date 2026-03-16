import asyncio
import sys
sys.path.insert(0, '.')

from app.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def check_templates():
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT id, name, category, version 
            FROM inspection_templates 
            ORDER BY created_at
        """))
        templates = result.fetchall()
        
        print('\n' + '=' * 80)
        print('模板列表')
        print('=' * 80)
        
        for t in templates:
            template_id, name, category, version = t
            print(f'\n模板: {name} ({category}) v{version}')
            
            # 检查模板项数量
            items_result = await conn.execute(text("""
                SELECT COUNT(*) 
                FROM template_items 
                WHERE template_id = :tid
            """), {"tid": str(template_id)})
            total_items = items_result.scalar()
            print(f'  总检查项: {total_items}')
            
            # 检查非分类检查项数量
            real_items_result = await conn.execute(text("""
                SELECT COUNT(*) 
                FROM template_items 
                WHERE template_id = :tid AND is_category = false
            """), {"tid": str(template_id)})
            real_items = real_items_result.scalar()
            print(f'  实际检查项(非分类): {real_items}')
            
            # 显示前几个检查项
            sample_result = await conn.execute(text("""
                SELECT title, is_category, sort_order 
                FROM template_items 
                WHERE template_id = :tid 
                ORDER BY sort_order 
                LIMIT 5
            """), {"tid": str(template_id)})
            samples = sample_result.fetchall()
            if samples:
                print('  前5个检查项:')
                for s in samples:
                    item_type = '分类' if s[1] else '检查项'
                    print(f'    {s[2]}. {s[0]} ({item_type})')
    
    await engine.dispose()
    print('\n' + '=' * 80 + '\n')

if __name__ == '__main__':
    asyncio.run(check_templates())
