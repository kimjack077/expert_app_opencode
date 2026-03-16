"""
清空所有检查记录数据
用于在修改数据库和程序前清理历史数据，避免数据不一致问题
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def clear_inspection_records():
    """清空所有检查记录相关数据"""
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        print('\n' + '=' * 80)
        print('开始清空检查记录数据...')
        print('=' * 80)
        
        # 1. 先清空检查记录项表（依赖表）
        print('\n[1/4] 清空检查记录项表 (inspection_record_items)...')
        result = await conn.execute(text("""
            DELETE FROM inspection_record_items
        """))
        count_items = result.rowcount
        print(f'  ✓ 已删除 {count_items} 条检查记录项')
        
        # 2. 清空检查记录表
        print('\n[2/4] 清空检查记录表 (inspection_records)...')
        result = await conn.execute(text("""
            DELETE FROM inspection_records
        """))
        count_records = result.rowcount
        print(f'  ✓ 已删除 {count_records} 条检查记录')
        
        # 3. 清空模板检查项表
        print('\n[3/4] 清空模板检查项表 (template_items)...')
        result = await conn.execute(text("""
            DELETE FROM template_items
        """))
        count_template_items = result.rowcount
        print(f'  ✓ 已删除 {count_template_items} 条模板检查项')
        
        # 4. 清空检查模板表
        print('\n[4/4] 清空检查模板表 (inspection_templates)...')
        result = await conn.execute(text("""
            DELETE FROM inspection_templates
        """))
        count_templates = result.rowcount
        print(f'  ✓ 已删除 {count_templates} 个检查模板')
        
        print('\n' + '=' * 80)
        print('✓ 清空完成！')
        print('=' * 80)
        print(f'\n统计信息:')
        print(f'  - 检查记录项：{count_items} 条')
        print(f'  - 检查记录：{count_records} 条')
        print(f'  - 模板检查项：{count_template_items} 条')
        print(f'  - 检查模板：{count_templates} 个')
        print(f'\n总计清理数据：{count_items + count_records + count_template_items + count_templates} 条')
        print('\n' + '=' * 80)
    
    await engine.dispose()
    return {
        'inspection_record_items': count_items,
        'inspection_records': count_records,
        'template_items': count_template_items,
        'inspection_templates': count_templates,
        'total': count_items + count_records + count_template_items + count_templates
    }


async def clear_only_records():
    """仅清空检查记录（保留模板）"""
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        print('\n' + '=' * 80)
        print('开始清空检查记录（保留模板）...')
        print('=' * 80)
        
        # 1. 先清空检查记录项表（依赖表）
        print('\n[1/2] 清空检查记录项表 (inspection_record_items)...')
        result = await conn.execute(text("""
            DELETE FROM inspection_record_items
        """))
        count_items = result.rowcount
        print(f'  ✓ 已删除 {count_items} 条检查记录项')
        
        # 2. 清空检查记录表
        print('\n[2/2] 清空检查记录表 (inspection_records)...')
        result = await conn.execute(text("""
            DELETE FROM inspection_records
        """))
        count_records = result.rowcount
        print(f'  ✓ 已删除 {count_records} 条检查记录')
        
        print('\n' + '=' * 80)
        print('✓ 清空完成！模板数据已保留')
        print('=' * 80)
        print(f'\n统计信息:')
        print(f'  - 检查记录项：{count_items} 条')
        print(f'  - 检查记录：{count_records} 条')
        print(f'\n总计清理：{count_items + count_records} 条')
        print('\n' + '=' * 80)
    
    await engine.dispose()
    return {
        'inspection_record_items': count_items,
        'inspection_records': count_records,
        'total': count_items + count_records
    }


async def clear_only_records_auto():
    """仅清空检查记录（保留模板），无需确认"""
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        print('\n' + '=' * 80)
        print('开始清空检查记录（保留模板）...')
        print('=' * 80)
        
        # 1. 先清空检查记录项表（依赖表）
        print('\n[1/2] 清空检查记录项表 (inspection_record_items)...')
        result = await conn.execute(text("""
            DELETE FROM inspection_record_items
        """))
        count_items = result.rowcount
        print(f'  ✓ 已删除 {count_items} 条检查记录项')
        
        # 2. 清空检查记录表
        print('\n[2/2] 清空检查记录表 (inspection_records)...')
        result = await conn.execute(text("""
            DELETE FROM inspection_records
        """))
        count_records = result.rowcount
        print(f'  ✓ 已删除 {count_records} 条检查记录')
        
        print('\n' + '=' * 80)
        print('✓ 清空完成！模板数据已保留')
        print('=' * 80)
        print(f'\n统计信息:')
        print(f'  - 检查记录项：{count_items} 条')
        print(f'  - 检查记录：{count_records} 条')
        print(f'\n总计清理：{count_items + count_records} 条')
        print('\n' + '=' * 80)
    
    await engine.dispose()
    return {
        'inspection_record_items': count_items,
        'inspection_records': count_records,
        'total': count_items + count_records
    }


async def main():
    """主函数"""
    print('\n' + '🔴' * 40)
    print('⚠️  警告：此操作将永久删除数据库中的检查记录！')
    print('🔴' * 40)
    print('\n请选择清理范围:')
    print('  1. 仅清空检查记录（保留模板）')
    print('  2. 清空所有数据（包括模板）')
    print('  3. 快速清空检查记录（无需确认）')
    print('  0. 取消操作')
    
    choice = input('\n请输入选项 (0/1/2/3): ').strip()
    
    if choice == '0':
        print('\n✓ 已取消操作')
        return
    
    elif choice == '1':
        print('\n确认：仅清空检查记录，保留模板数据')
        confirm = input('确认执行？(y/n): ').strip().lower()
        if confirm == 'y':
            await clear_only_records()
        else:
            print('\n✓ 已取消操作')
    
    elif choice == '2':
        print('\n确认：清空所有数据（包括模板）')
        confirm = input('确认执行？(y/n): ').strip().lower()
        if confirm == 'y':
            await clear_inspection_records()
        else:
            print('\n✓ 已取消操作')
    
    elif choice == '3':
        print('\n快速清空：仅清空检查记录，保留模板数据（无需确认）')
        await clear_only_records_auto()
    
    else:
        print('\n❌ 无效的选项')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n\n✓ 操作已中断')
    except Exception as e:
        print(f'\n❌ 发生错误：{e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
