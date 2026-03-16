import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.config import settings
import uuid

async def add_safety_template():
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        # 1. 创建标准分类 - 安全生产检查
        category_id = str(uuid.uuid4())
        await conn.execute(text("""
            INSERT INTO standard_categories (id, name, code, level, parent_id, created_at)
            VALUES (:id, '安全生产现场检查', 'SAFETY-001', 1, NULL, NOW())
        """), {"id": category_id})
        print(f"Created category: {category_id}")
        
        # 2. 创建检查模板
        template_id = str(uuid.uuid4())
        await conn.execute(text("""
            INSERT INTO inspection_templates (id, name, code, category, version, is_published, description, created_by, created_at, updated_at)
            VALUES (:id, '安全生产现场检查模板（通用）', 'TPL-SAFETY-001', '安全生产', '1.0', true, 
                    '适用于工厂、车间、施工现场、仓库等场景的安全生产现场检查', 
                    (SELECT id FROM users WHERE username = 'admin'), NOW(), NOW())
        """), {"id": template_id})
        print(f"Created template: {template_id}")
        
        # 3. 定义所有检查项
        check_items = [
            # 一、现场基础管理
            ("安全生产责任制是否落实到人", "现场基础管理", "检查安全生产责任制是否明确到具体人员", "查阅资料、现场询问", "《安全生产法》", "一般"),
            ("现场安全警示标识是否齐全、清晰、规范", "现场基础管理", "检查安全警示标识是否符合国家标准", "现场检查", "GB 2894《安全标志及其使用导则》", "一般"),
            ("作业人员是否按规定佩戴劳动防护用品", "现场基础管理", "检查安全帽、安全带、防护鞋、口罩、护目镜等佩戴情况", "现场检查", "《劳动防护用品监督管理规定》", "较大"),
            ("现场是否存在违章指挥、违章作业、违反劳动纪律", "现场基础管理", "检查三违行为", "现场观察", "企业安全管理制度", "重大"),
            ("班前安全交底、安全培训记录是否齐全", "现场基础管理", "检查安全培训记录", "查阅资料", "《安全生产培训管理办法》", "一般"),
            
            # 二、作业环境与通道
            ("安全通道畅通、无堵塞、无占用", "作业环境与通道", "检查安全通道是否被占用", "现场检查", "GB 50016《建筑设计防火规范》", "较大"),
            ("地面整洁，无积水、油污、杂物、易滑物", "作业环境与通道", "检查地面清洁情况", "现场检查", "5S管理标准", "一般"),
            ("物料堆放整齐、稳固，不超高、不占道", "作业环境与通道", "检查物料堆放规范", "现场检查", "《仓储场所消防安全管理通则》", "一般"),
            ("通风、采光、照明符合安全要求", "作业环境与通道", "检查环境条件", "现场检测", "GB 50033《建筑采光设计标准》", "一般"),
            ("消防通道、安全出口标识清晰、畅通", "作业环境与通道", "检查消防通道", "现场检查", "《消防法》", "重大"),
            
            # 三、用电安全
            ("配电箱、开关箱完好、上锁、标识清晰", "用电安全", "检查配电设施", "现场检查", "GB/T 13869《用电安全导则》", "较大"),
            ("电线无破损、无乱拉乱接、无裸露", "用电安全", "检查电线电缆", "现场检查", "《电气安全管理规程》", "较大"),
            ("设备接地、接零保护可靠", "用电安全", "检查接地保护", "现场检测", "GB 50169《电气装置安装工程接地装置施工及验收规范》", "重大"),
            ("无违规使用插线板串联、超负荷用电", "用电安全", "检查用电负荷", "现场检查", "《用电安全导则》", "较大"),
            ("潮湿、易燃易爆区域用电符合防爆要求", "用电安全", "检查防爆电气", "现场检查", "GB 3836《爆炸性环境用电气设备》", "重大"),
            
            # 四、机械设备安全
            ("设备防护装置齐全有效", "机械设备安全", "检查防护罩、护栏、急停按钮等", "现场检查", "GB/T 8196《机械安全 防护装置》", "重大"),
            ("设备定期维护、保养、点检记录完整", "机械设备安全", "检查维保记录", "查阅资料", "设备管理制度", "一般"),
            ("特种设备持证上岗、定期检验", "机械设备安全", "检查起重机、叉车、压力容器等", "查阅证书", "《特种设备安全法》", "重大"),
            ("设备运行无异常声响、过热、漏油漏气", "机械设备安全", "检查设备运行状态", "现场检查", "设备操作规程", "较大"),
            ("危险设备区域有隔离和警示", "机械设备安全", "检查隔离措施", "现场检查", "GB 2894《安全标志及其使用导则》", "较大"),
            
            # 五、消防安全
            ("灭火器、消防栓完好有效", "消防安全", "检查消防器材", "现场检查", "GB 50140《建筑灭火器配置设计规范》", "重大"),
            ("消防器材前无遮挡、便于取用", "消防安全", "检查消防通道", "现场检查", "《消防法》", "较大"),
            ("易燃易爆物品分类存放、远离火源", "消防安全", "检查危化品存储", "现场检查", "GB 15603《常用化学危险品贮存通则》", "重大"),
            ("现场无违规吸烟、违规动火", "消防安全", "检查火源管理", "现场检查", "《消防法》", "较大"),
            ("动火作业审批、监护措施到位", "消防安全", "检查动火作业票", "查阅资料", "《动火作业安全管理规定》", "重大"),
            
            # 六、危险作业管理
            ("高处作业系安全带、设防护、有监护", "危险作业管理", "检查高处作业", "现场检查", "GB 30871《危险化学品企业特殊作业安全规范》", "重大"),
            ("有限空间作业执行审批、通风、检测、监护", "危险作业管理", "检查有限空间作业", "现场检查", "《有限空间作业安全管理规定》", "重大"),
            ("吊装作业规范，指挥人员持证", "危险作业管理", "检查吊装作业", "现场检查", "《起重机械安全规程》", "重大"),
            ("临时用电规范，无违规动火动焊", "危险作业管理", "检查临时用电", "现场检查", "JGJ 46《施工现场临时用电安全技术规范》", "较大"),
            ("危险作业现场无无关人员逗留", "危险作业管理", "检查作业区域隔离", "现场检查", "作业许可管理规定", "一般"),
            
            # 七、职业健康
            ("粉尘、噪声、有毒有害岗位防护措施到位", "职业健康", "检查职业病防护", "现场检测", "《职业病防治法》", "较大"),
            ("职业病危害告知、警示标识齐全", "职业健康", "检查警示标识", "现场检查", "GBZ 158《工作场所职业病危害警示标识》", "一般"),
            ("作业人员按规定佩戴防护用品", "职业健康", "检查个体防护", "现场检查", "《个体防护装备选用规范》", "较大"),
            
            # 八、应急管理
            ("应急疏散路线图清晰", "应急管理", "检查疏散指示", "现场检查", "GB 2894《安全标志及其使用导则》", "较大"),
            ("急救药品、应急器材配备齐全", "应急管理", "检查应急物资", "现场检查", "《生产安全事故应急条例》", "一般"),
            ("现场人员掌握基本应急处置知识", "应急管理", "抽查应急知识", "现场询问", "应急预案", "一般"),
        ]
        
        # 4. 创建检查项和模板项
        sort_order = 0
        for title, category, description, method, legal_basis, risk_level in check_items:
            # 创建检查项
            check_item_id = str(uuid.uuid4())
            await conn.execute(text("""
                INSERT INTO check_items (id, category_id, title, description, check_method, 
                                        legal_basis, standard_ref, result_type, is_required, 
                                        risk_level, sort_order, created_by, created_at, updated_at)
                VALUES (:id, :category_id, :title, :description, :method, :legal_basis, 
                        :standard_ref, 'pass_fail', true, :risk_level, :sort_order,
                        (SELECT id FROM users WHERE username = 'admin'), NOW(), NOW())
            """), {
                "id": check_item_id,
                "category_id": category_id,
                "title": title,
                "description": description,
                "method": method,
                "legal_basis": legal_basis,
                "standard_ref": legal_basis,
                "risk_level": risk_level,
                "sort_order": sort_order
            })
            
            # 创建模板项关联
            template_item_id = str(uuid.uuid4())
            await conn.execute(text("""
                INSERT INTO template_items (id, template_id, check_item_id, sort_order, is_required)
                VALUES (:id, :template_id, :check_item_id, :sort_order, true)
            """), {
                "id": template_item_id,
                "template_id": template_id,
                "check_item_id": check_item_id,
                "sort_order": sort_order
            })
            
            sort_order += 1
            print(f"Created check item {sort_order}: {title[:30]}...")
        
        print(f"\nTotal check items created: {sort_order}")
        print(f"Template ID: {template_id}")
        print("Safety template added successfully!")
    
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(add_safety_template())
