import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.config import settings
import uuid

# Pre-computed bcrypt hashes for "admin123" and "expert123"
ADMIN_PASSWORD_HASH = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"
EXPERT_PASSWORD_HASH = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"

async def seed_data():
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        admin_id = str(uuid.uuid4())
        expert_id = str(uuid.uuid4())
        
        await conn.execute(text("""
            INSERT INTO users (id, username, email, hashed_password, full_name, role, is_active)
            VALUES 
                (:admin_id, 'admin', 'admin@efis.com', :admin_pwd, '系统管理员', 'super_admin', true),
                (:expert_id, 'expert', 'expert@efis.com', :expert_pwd, '张专家', 'expert', true)
        """), {
            "admin_id": admin_id,
            "admin_pwd": ADMIN_PASSWORD_HASH,
            "expert_id": expert_id,
            "expert_pwd": EXPERT_PASSWORD_HASH,
        })
        print("Users created")
        
        cat1_id = str(uuid.uuid4())
        cat2_id = str(uuid.uuid4())
        cat3_id = str(uuid.uuid4())
        
        await conn.execute(text("""
            INSERT INTO standard_categories (id, name, code, level, sort_order, description)
            VALUES 
                (:cat1, '消防安全', 'FIRE', 1, 1, '消防安全检查类别'),
                (:cat2, '电气安全', 'ELEC', 1, 2, '电气安全检查类别'),
                (:cat3, '建筑安全', 'BUILD', 1, 3, '建筑安全检查类别')
        """), {"cat1": cat1_id, "cat2": cat2_id, "cat3": cat3_id})
        print("Categories created")
        
        item1_id = str(uuid.uuid4())
        item2_id = str(uuid.uuid4())
        item3_id = str(uuid.uuid4())
        item4_id = str(uuid.uuid4())
        
        await conn.execute(text("""
            INSERT INTO check_items (id, category_id, title, description, check_method, legal_basis, result_type, risk_level)
            VALUES 
                (:item1, :cat1, '灭火器配置检查', '检查灭火器数量、类型、有效期是否符合要求', '现场查看灭火器配置情况，检查有效期标签', '《消防法》第十六条', 'yes_no', 'high'),
                (:item2, :cat1, '疏散通道检查', '检查疏散通道是否畅通，标识是否清晰', '现场查看疏散通道，测试应急照明', '《消防法》第二十八条', 'yes_no', 'high'),
                (:item3, :cat2, '电气线路检查', '检查电气线路是否老化、裸露，是否存在私拉乱接', '目视检查，使用红外测温仪检测', '《电气安全规程》第3.2条', 'yes_no', 'medium'),
                (:item4, :cat3, '建筑结构安全检查', '检查建筑物是否存在裂缝、变形等安全隐患', '现场查看，必要时进行专业检测', '《建筑法》第六十条', 'yes_no', 'high')
        """), {
            "item1": item1_id, "item2": item2_id, "item3": item3_id, "item4": item4_id,
            "cat1": cat1_id, "cat2": cat2_id, "cat3": cat3_id,
        })
        print("Check items created")
        
        template_id = str(uuid.uuid4())
        
        await conn.execute(text("""
            INSERT INTO inspection_templates (id, name, code, description, category, version, is_published, created_by)
            VALUES (:tid, '综合安全检查模板', 'TPL-001', '用于一般企业综合安全检查', '综合', '1.0', true, :admin_id)
        """), {"tid": template_id, "admin_id": admin_id})
        print("Template created")
        
        await conn.execute(text("""
            INSERT INTO template_items (id, template_id, check_item_id, sort_order, is_required)
            VALUES 
                (gen_random_uuid(), :tid, :item1, 1, true),
                (gen_random_uuid(), :tid, :item2, 2, true),
                (gen_random_uuid(), :tid, :item3, 3, true),
                (gen_random_uuid(), :tid, :item4, 4, true)
        """), {
            "tid": template_id,
            "item1": item1_id, "item2": item2_id, "item3": item3_id, "item4": item4_id,
        })
        print("Template items created")
        
        task_id = str(uuid.uuid4())
        
        await conn.execute(text("""
            INSERT INTO inspection_tasks (id, task_no, title, template_id, assigned_to, assigned_by, target_name, target_address, status)
            VALUES (:tid, 'TASK-20240223-0001', 'XX公司年度安全检查', :template_id, :expert_id, :admin_id, 'XX科技有限公司', '北京市朝阳区XX路XX号', 'pending')
        """), {
            "tid": task_id,
            "template_id": template_id,
            "expert_id": expert_id,
            "admin_id": admin_id,
        })
        print("Task created")
    
    await engine.dispose()
    print("Seed data completed!")

if __name__ == '__main__':
    asyncio.run(seed_data())
