import asyncio
import sys
sys.path.insert(0, '.')

from app.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import uuid

async def add_template_items():
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        # 获取模板ID
        result = await conn.execute(text("""
            SELECT id FROM inspection_templates 
            WHERE code = 'TEST-FOOD-002'
        """))
        template = result.fetchone()
        
        if not template:
            print("模板 TEST-FOOD-002 不存在")
            return
        
        template_id = str(template[0])
        print(f"找到模板: {template_id}")
        
        # 获取"一、人员管理"分类的ID
        result = await conn.execute(text("""
            SELECT id FROM template_items 
            WHERE template_id = :template_id AND title = '一、人员管理'
        """), {"template_id": template_id})
        category = result.fetchone()
        
        if not category:
            print("未找到'一、人员管理'分类")
            return
        
        category_id = str(category[0])
        print(f"找到分类: {category_id}")
        
        # 检查是否已有子项
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM template_items 
            WHERE parent_id = :category_id
        """), {"category_id": category_id})
        count = result.scalar()
        
        if count > 0:
            print(f"该分类已有 {count} 个子项")
            return
        
        # 添加检查项
        items = [
            {
                "title": "健康证持有情况",
                "description": "检查从业人员是否持有有效的健康证明",
                "check_method": "现场查验健康证原件，核对人员名单",
                "legal_basis": "《食品安全法》第45条",
                "result_type": "pass_fail",
                "risk_level": "high",
                "sort_order": 1
            },
            {
                "title": "个人卫生状况",
                "description": "检查从业人员个人卫生是否符合要求",
                "check_method": "现场观察从业人员着装、手部卫生等",
                "legal_basis": "《食品安全法》第33条",
                "result_type": "pass_fail",
                "risk_level": "medium",
                "sort_order": 2
            },
            {
                "title": "培训记录",
                "description": "检查从业人员是否接受过食品安全培训",
                "check_method": "查看培训记录和证书",
                "legal_basis": "《食品安全法》第44条",
                "result_type": "pass_fail",
                "risk_level": "medium",
                "sort_order": 3
            }
        ]
        
        for item in items:
            await conn.execute(text("""
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, 
                    check_method, legal_basis, result_type, risk_level, 
                    sort_order, is_required, is_category
                ) VALUES (
                    gen_random_uuid(), :template_id, :parent_id, :title, :description,
                    :check_method, :legal_basis, :result_type, :risk_level,
                    :sort_order, true, false
                )
            """), {
                "template_id": template_id,
                "parent_id": category_id,
                "title": item["title"],
                "description": item["description"],
                "check_method": item["check_method"],
                "legal_basis": item["legal_basis"],
                "result_type": item["result_type"],
                "risk_level": item["risk_level"],
                "sort_order": item["sort_order"]
            })
            print(f"添加检查项: {item['title']}")
        
        # 添加第二个分类
        category2_id = str(uuid.uuid4())
        await conn.execute(text("""
            INSERT INTO template_items (
                id, template_id, title, description, 
                check_method, legal_basis, result_type, risk_level, 
                sort_order, is_required, is_category
            ) VALUES (
                :id, :template_id, '二、环境卫生', '环境卫生相关检查项目',
                '现场查看环境卫生状况', '《食品安全法》第33条', 'pass_fail', 'medium',
                2, true, true
            )
        """), {
            "id": category2_id,
            "template_id": template_id
        })
        print("添加分类: 二、环境卫生")
        
        # 添加环境卫生检查项
        env_items = [
            {
                "title": "场所清洁",
                "description": "检查经营场所是否保持清洁",
                "check_method": "现场查看地面、墙壁、天花板等",
                "legal_basis": "《食品安全法》第33条",
                "result_type": "pass_fail",
                "risk_level": "medium",
                "sort_order": 1
            },
            {
                "title": "防虫防鼠设施",
                "description": "检查是否配备有效的防虫防鼠设施",
                "check_method": "查看防虫防鼠设施配置情况",
                "legal_basis": "《食品安全法》第33条",
                "result_type": "pass_fail",
                "risk_level": "high",
                "sort_order": 2
            }
        ]
        
        for item in env_items:
            await conn.execute(text("""
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, 
                    check_method, legal_basis, result_type, risk_level, 
                    sort_order, is_required, is_category
                ) VALUES (
                    gen_random_uuid(), :template_id, :parent_id, :title, :description,
                    :check_method, :legal_basis, :result_type, :risk_level,
                    :sort_order, true, false
                )
            """), {
                "template_id": template_id,
                "parent_id": category2_id,
                "title": item["title"],
                "description": item["description"],
                "check_method": item["check_method"],
                "legal_basis": item["legal_basis"],
                "result_type": item["result_type"],
                "risk_level": item["risk_level"],
                "sort_order": item["sort_order"]
            })
            print(f"添加检查项: {item['title']}")
        
        print("完成！共添加 2 个分类和 5 个检查项")

if __name__ == '__main__':
    asyncio.run(add_template_items())
