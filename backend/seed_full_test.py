import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.config import settings
import uuid
import json

async def seed_full_test_data():
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT id FROM users WHERE username = 'admin'"))
        admin = result.scalar_one_or_none()
        
        if not admin:
            print("Admin user not found")
            return
        
        cat_ids = {}
        
        categories = [
            ("A. 食品安全管理制度", "FOOD-SAFETY-MGMT", 1),
            ("A.1 证照与档案管理", "FOOD-SAFETY-MGMT-001", 2),
            ("A.2 人员管理", "FOOD-SAFETY-MGMT-002", 2),
            ("B. 场所与环境", "ENVIRONMENT", 1),
            ("B.1 加工场所卫生", "ENVIRONMENT-001", 2),
            ("B.2 设施设备维护", "ENVIRONMENT-002", 2),
            ("C. 食品原料管理", "FOOD-MATERIAL", 1),
            ("C.1 采购索证索票", "FOOD-MATERIAL-001", 2),
            ("C.2 原料贮存", "FOOD-MATERIAL-002", 2),
            ("D. 加工操作过程", "PROCESSING", 1),
            ("D.1 粗加工", "PROCESSING-001", 2),
            ("D.2 烹饪操作", "PROCESSING-002", 2),
            ("D.3 餐饮具清洗消毒", "PROCESSING-003", 2),
            ("E. 食品添加剂使用", "ADDITIVES", 1),
            ("E.1 合规使用管理", "ADDITIVES-001", 2),
        ]
        
        for name, code, level in categories:
            cat_id = str(uuid.uuid4())
            cat_ids[code] = cat_id
            parent_code = code.rsplit('-', 1)[0] if level == 2 else None
            parent_id = cat_ids.get(parent_code) if parent_code else None
            
            await conn.execute(text("""
                INSERT INTO standard_categories (id, name, code, level, parent_id, sort_order, description)
                VALUES (:id, :name, :code, :level, :parent_id, :sort, :desc)
            """), {
                "id": cat_id,
                "name": name,
                "code": code,
                "level": level,
                "parent_id": parent_id,
                "sort": len(cat_ids),
                "desc": f"检查分类: {name}"
            })
        print(f"Created {len(categories)} categories")
        
        check_items = [
            (cat_ids["FOOD-SAFETY-MGMT-001"], "食品经营许可证是否在有效期内且悬挂于显眼位置", "检查食品经营许可证的有效期、许可范围与实际经营范围是否一致", "现场查看证件原件或复印件，核查有效期截止日期", "《食品安全法》第三十五条", "yes_no", "high"),
            (cat_ids["FOOD-SAFETY-MGMT-001"], "营业执照是否在有效期内且与实际经营者一致", "营业执照注册信息与实际经营者、经营地址是否一致", "查看营业执照原件，核对信息", "《公司法》", "yes_no", "high"),
            (cat_ids["FOOD-SAFETY-MGMT-001"], "食品安全管理档案是否完整", "核查各类台账记录是否完整", "查阅进货台账、消毒记录", "《食品安全法》第五十条", "yes_no", "medium"),
            (cat_ids["FOOD-SAFETY-MGMT-002"], "所有从业人员是否持有效健康证上岗", "检查从业人员健康证明", "核验健康证有效期", "《食品安全法》第四十五条", "yes_no", "high"),
            (cat_ids["FOOD-SAFETY-MGMT-002"], "从业人员操作时是否规范着装", "检查着装规范", "现场观察", "餐饮操作规范", "yes_no", "medium"),
            (cat_ids["ENVIRONMENT-001"], "加工场所地面、墙面、天花板是否整洁无破损", "检查加工区域卫生", "目视检查", "餐饮操作规范4.1", "yes_no", "medium"),
            (cat_ids["ENVIRONMENT-001"], "食品加工区域是否存在非食品物品混放", "检查是否有非食品物品", "检查存储区域", "《食品安全法》第五十四条", "yes_no", "high"),
            (cat_ids["ENVIRONMENT-001"], "生熟食品是否有效分区、分架存放", "检查生熟分开存放", "检查冰箱分层", "餐饮操作规范6.2", "yes_no", "high"),
            (cat_ids["FOOD-MATERIAL-001"], "肉类原料是否有检验检疫合格证明", "检查肉类检疫证明", "抽查进货记录", "《食品安全法》第五十条", "yes_no", "high"),
            (cat_ids["FOOD-MATERIAL-001"], "蔬菜类原料是否建立进货台账并如实记录", "检查蔬菜台账", "查阅台账", "《食品安全法》第五十条", "yes_no", "medium"),
            (cat_ids["PROCESSING-002"], "烹饪加热食品是否达到食品安全要求温度", "测量食物中心温度", "使用温度计测量", "餐饮操作规范7.2", "score", "high"),
            (cat_ids["PROCESSING-002"], "高风险食品是否在专间制作", "检查凉菜制作区域", "查看专间", "餐饮操作规范7.4", "yes_no", "high"),
            (cat_ids["PROCESSING-002"], "食品留样是否按规定执行", "检查留样情况", "检查留样冰箱", "餐饮操作规范第10条", "yes_no", "medium"),
            (cat_ids["PROCESSING-003"], "餐饮具清洗消毒流程是否符合规范", "检查洗碗流程", "现场观察", "餐饮操作规范8.1", "yes_no", "medium"),
            (cat_ids["PROCESSING-003"], "消毒液浓度是否符合要求", "检测消毒液浓度", "用试纸检测", "GB 31654-2021", "score", "high"),
            (cat_ids["PROCESSING-003"], "餐饮具是否存放于密闭清洁柜内", "检查保洁柜", "检查存放情况", "餐饮操作规范8.3", "yes_no", "medium"),
            (cat_ids["ADDITIVES-001"], "食品添加剂是否有专柜存放并有使用记录台账", "检查添加剂管理", "检查专柜和台账", "《食品安全法》第四十条", "yes_no", "high"),
            (cat_ids["ADDITIVES-001"], "使用的食品添加剂品种和用量是否符合GB 2760规定", "检查添加剂合规性", "核查品种和用量", "GB 2760", "yes_no", "high"),
        ]
        
        item_ids = []
        for cat_id, title, desc, method, legal, rtype, risk in check_items:
            item_id = str(uuid.uuid4())
            item_ids.append(item_id)
            await conn.execute(text("""
                INSERT INTO check_items (id, category_id, title, description, check_method, legal_basis, result_type, risk_level, is_required)
                VALUES (:id, :cat_id, :title, :desc, :method, :legal, :rtype, :risk, true)
            """), {
                "id": item_id,
                "cat_id": cat_id,
                "title": title,
                "desc": desc,
                "method": method,
                "legal": legal,
                "rtype": rtype,
                "risk": risk
            })
        print(f"Created {len(check_items)} check items")
        
        template_id = str(uuid.uuid4())
        await conn.execute(text("""
            INSERT INTO inspection_templates (id, name, code, description, category, version, is_published, created_by)
            VALUES (:id, '餐饮单位食品安全日常监督检查（标准版）', 'TPL-FOOD-RESTAURANT-001', '适用于普通餐饮服务单位的日常食品安全监督检查', '食品安全', '1.0', true, :admin_id)
        """), {"id": template_id, "admin_id": admin})
        print("Created template")
        
        for i, item_id in enumerate(item_ids):
            await conn.execute(text("""
                INSERT INTO template_items (id, template_id, check_item_id, sort_order, is_required)
                VALUES (gen_random_uuid(), :tid, :item_id, :sort, true)
            """), {"tid": template_id, "item_id": item_id, "sort": i+1})
        print(f"Added {len(item_ids)} items to template")
        
    await engine.dispose()
    print("Full test data seeded!")

if __name__ == '__main__':
    asyncio.run(seed_full_test_data())
