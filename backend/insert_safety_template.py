import asyncio
import asyncpg
from datetime import datetime
import json

async def insert_safety_template():
    conn = await asyncpg.connect(
        host='117.72.77.52',
        port=5432,
        user='db_admin',
        password='1234567890@sdtj',
        database='db_expert_opencode'
    )
    
    try:
        # 开始事务
        async with conn.transaction():
            # 1. 插入模板主表
            await conn.execute('''
                INSERT INTO inspection_templates (
                    id, name, code, description, category, version, is_published, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9
                )
            ''', 
                '550e8400-e29b-41d4-a716-446655440001',
                '安全生产检查模板',
                'SAFETY-PROD-001',
                '用于企业生产现场安全检查和作业与应急管理检查的专业模板，涵盖设备安全、电气安全、作业人员防护、消防应急等关键检查项目',
                '安全生产',
                '1.0',
                True,
                datetime.now(),
                datetime.now()
            )
            print("✅ 模板主表插入成功")
            
            # 2. 插入分类节点
            # 2.1 生产现场安全检查
            await conn.execute('''
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, is_category, 
                    sort_order, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ''',
                '550e8400-e29b-41d4-a716-446655440010',
                '550e8400-e29b-41d4-a716-446655440001',
                None,
                '一、生产现场安全检查',
                '检查生产现场设备运行状态、电气安全等关键环节',
                True,
                1,
                datetime.now(),
                datetime.now()
            )
            print("✅ 分类节点1插入成功")
            
            # 2.2 作业与应急管理检查
            await conn.execute('''
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, is_category, 
                    sort_order, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ''',
                '550e8400-e29b-41d4-a716-446655440020',
                '550e8400-e29b-41d4-a716-446655440001',
                None,
                '二、作业与应急管理检查',
                '检查作业人员防护佩戴、消防应急设施完好性等关键环节',
                True,
                2,
                datetime.now(),
                datetime.now()
            )
            print("✅ 分类节点2插入成功")
            
            # 3. 插入具体检查项目
            # 3.1 设备安全运行状态
            await conn.execute('''
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, 
                    result_type, is_required, risk_level, 
                    check_method, legal_basis, sort_order, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ''',
                '550e8400-e29b-41d4-a716-446655440011',
                '550e8400-e29b-41d4-a716-446655440001',
                '550e8400-e29b-41d4-a716-446655440010',
                '设备安全运行状态',
                '检查生产设备完好性、安全防护装置有效性',
                'pass_fail',
                True,
                'high',
                '目视检查、功能测试',
                '《安全生产法》第三十六条：生产经营单位必须对安全设备进行经常性维护、保养，并定期检测，保证正常运转',
                1,
                datetime.now(),
                datetime.now()
            )
            print("✅ 检查项目1插入成功")
            
            # 3.2 电气安全规范
            await conn.execute('''
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, 
                    result_type, is_required, risk_level, 
                    check_method, legal_basis, sort_order, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ''',
                '550e8400-e29b-41d4-a716-446655440012',
                '550e8400-e29b-41d4-a716-446655440001',
                '550e8400-e29b-41d4-a716-446655440010',
                '电气安全规范',
                '检查线路、配电箱、接地等用电安全情况',
                'pass_fail',
                True,
                'medium',
                '目视巡检、漏电测试',
                '《安全生产法》第三十八条：生产经营单位应当对电气设备采取可靠的安全措施，防止触电事故',
                2,
                datetime.now(),
                datetime.now()
            )
            print("✅ 检查项目2插入成功")
            
            # 3.3 作业人员防护佩戴
            await conn.execute('''
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, 
                    result_type, is_required, risk_level, 
                    check_method, legal_basis, sort_order, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ''',
                '550e8400-e29b-41d4-a716-446655440021',
                '550e8400-e29b-41d4-a716-446655440001',
                '550e8400-e29b-41d4-a716-446655440020',
                '作业人员防护佩戴',
                '检查员工劳保用品佩戴合规性',
                'pass_fail',
                True,
                'medium',
                '现场抽查、拍照记录',
                '《安全生产法》第五十七条：从业人员在作业过程中，应当严格落实岗位安全责任，正确佩戴和使用劳动防护用品',
                1,
                datetime.now(),
                datetime.now()
            )
            print("✅ 检查项目3插入成功")
            
            # 3.4 消防应急设施完好
            await conn.execute('''
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, 
                    result_type, is_required, risk_level, 
                    check_method, legal_basis, sort_order, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ''',
                '550e8400-e29b-41d4-a716-446655440022',
                '550e8400-e29b-41d4-a716-446655440001',
                '550e8400-e29b-41d4-a716-446655440020',
                '消防应急设施完好',
                '检查灭火器、消防通道、应急照明等状态',
                'pass_fail',
                True,
                'high',
                '压力表核查、实测通道',
                '《消防法》第十六条：机关、团体、企业、事业等单位应当对建筑消防设施每年至少进行一次全面检测，确保完好有效',
                2,
                datetime.now(),
                datetime.now()
            )
            print("✅ 检查项目4插入成功")
        
        # 查询验证
        rows = await conn.fetch('''
            SELECT 
                t.name as template_name,
                t.category,
                ti.title,
                ti.is_category,
                ti.risk_level,
                ti.check_type,
                ti.description
            FROM inspection_templates t
            LEFT JOIN template_items ti ON t.id = ti.template_id
            WHERE t.id = $1
            ORDER BY ti.sort_order
        ''', '550e8400-e29b-41d4-a716-446655440001')
        
        print("\n📊 插入结果验证：")
        print("-" * 80)
        for row in rows:
            print(f"模板: {row['template_name']}")
            print(f"  分类: {row['category']}")
            print(f"  项目: {row['title']}")
            print(f"  是否分类: {row['is_category']}")
            print(f"  风险等级: {row['risk_level']}")
            print(f"  检查类型: {row['check_type']}")
            print(f"  描述: {row['description']}")
            print("-" * 80)
        
        print("\n✨ 安全生产检查模板插入成功！")
        
    except Exception as e:
        print(f"❌ 插入失败: {e}")
        raise
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(insert_safety_template())
