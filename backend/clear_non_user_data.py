"""
清空除用户相关表以外的所有数据
保留：users, organizations
清空：templates, records, tasks, enterprises, knowledge, media, audit_logs等
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings

async def clear_non_user_data():
    engine = create_async_engine(settings.DATABASE_URL)
    
    # 按照外键依赖顺序排列的表（先清空子表）
    tables_to_clear = [
        # 审计和日志表
        "llm_call_logs",
        "audit_logs",
        
        # 媒体文件表
        "media_files",
        
        # 任务相关表
        "task_item_records",
        "inspection_tasks",
        
        # 检查记录相关表
        "inspection_record_items",
        "inspection_records",
        
        # 企业相关表
        "rectification_records",
        "enterprise_products",
        "enterprise_qualifications",
        "enterprises",
        
        # 知识库相关表
        "inspection_guidelines",
        "knowledge_documents",
        "knowledge_categories",
        
        # 模板相关表
        "template_items",
        "inspection_templates",
    ]
    
    async with engine.begin() as conn:
        for table in tables_to_clear:
            try:
                result = await conn.execute(text(f"DELETE FROM {table}"))
                print(f"已清空表: {table}")
            except Exception as e:
                print(f"清空表 {table} 时出错: {e}")
    
    # 验证用户数据是否保留
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM users"))
        user_count = result.scalar()
        print(f"\n用户表保留记录数: {user_count}")
        
        result = await conn.execute(text("SELECT COUNT(*) FROM organizations"))
        org_count = result.scalar()
        print(f"组织表保留记录数: {org_count}")
    
    await engine.dispose()
    print("\n✅ 非用户数据清空完成！")

if __name__ == '__main__':
    asyncio.run(clear_non_user_data())
