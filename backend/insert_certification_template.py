import asyncio
import asyncpg
from datetime import datetime

async def insert_certification_template():
    conn = await asyncpg.connect(
        host='62.234.0.182',
        port=5432,
        user='db_admin',
        password='1234567890@sdtj',
        database='db_expert_opencode'
    )
    
    try:
        async with conn.transaction():
            await conn.execute('''
                INSERT INTO inspection_templates (
                    id, name, code, description, category, version, is_published, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ''', 
                '550e8400-e29b-41d4-a716-446655440002',
                '认证审查检查模板',
                'CERT-AUDIT-001',
                '用于企业认证审查的专业模板，涵盖体系文件合规性、过程实施与记录追溯等关键检查项目',
                '认证审查',
                '1.0',
                True,
                datetime.now(),
                datetime.now()
            )
            print("✅ 模板主表插入成功")
            
            await conn.execute('''
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, is_category, 
                    sort_order, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ''',
                '550e8400-e29b-41d4-a716-446655440030',
                '550e8400-e29b-41d4-a716-446655440002',
                None,
                '一、体系文件与合规性审查',
                '核查质量管理/体系文件完整性及法律法规符合性',
                True,
                1,
                datetime.now(),
                datetime.now()
            )
            print("✅ 分类节点1插入成功")
            
            await conn.execute('''
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, is_category, 
                    sort_order, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ''',
                '550e8400-e29b-41d4-a716-446655440040',
                '550e8400-e29b-41d4-a716-446655440002',
                None,
                '二、过程实施与记录追溯审查',
                '核查关键过程执行一致性及记录可追溯性',
                True,
                2,
                datetime.now(),
                datetime.now()
            )
            print("✅ 分类节点2插入成功")
            
            await conn.execute('''
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, 
                    result_type, is_required, risk_level, 
                    check_method, legal_basis, sort_order, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ''',
                '550e8400-e29b-41d4-a716-446655440031',
                '550e8400-e29b-41d4-a716-446655440002',
                '550e8400-e29b-41d4-a716-446655440030',
                '体系文件完整性',
                '核查质量管理/体系文件是否覆盖认证要求，版本是否有效',
                'pass_fail',
                True,
                'high',
                '查阅文件清单、版本追溯、抽样核对',
                '《ISO 9001》4.4：质量管理体系应形成文件并保持更新；《认证认可条例》第十五条',
                1,
                datetime.now(),
                datetime.now()
            )
            print("✅ 检查项目1插入成功")
            
            await conn.execute('''
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, 
                    result_type, is_required, risk_level, 
                    check_method, legal_basis, sort_order, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ''',
                '550e8400-e29b-41d4-a716-446655440032',
                '550e8400-e29b-41d4-a716-446655440002',
                '550e8400-e29b-41d4-a716-446655440030',
                '法律法规符合性',
                '检查体系文件是否符合适用法律法规、行业标准要求',
                'pass_fail',
                True,
                'medium',
                '条款比对、合规性评估、专家评审',
                '《标准化法》第二十五条；对应认证领域专项规则（如食品/医疗/机械类认证规范）',
                2,
                datetime.now(),
                datetime.now()
            )
            print("✅ 检查项目2插入成功")
            
            await conn.execute('''
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, 
                    result_type, is_required, risk_level, 
                    check_method, legal_basis, sort_order, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ''',
                '550e8400-e29b-41d4-a716-446655440041',
                '550e8400-e29b-41d4-a716-446655440002',
                '550e8400-e29b-41d4-a716-446655440040',
                '关键过程执行一致性',
                '核查生产/服务关键过程是否按体系文件要求执行',
                'pass_fail',
                True,
                'high',
                '现场观察、作业记录抽查、流程追溯',
                '《ISO 9001》8.5：生产和服务提供应在受控条件下进行；认证规则中"过程一致性"条款',
                1,
                datetime.now(),
                datetime.now()
            )
            print("✅ 检查项目3插入成功")
            
            await conn.execute('''
                INSERT INTO template_items (
                    id, template_id, parent_id, title, description, 
                    result_type, is_required, risk_level, 
                    check_method, legal_basis, sort_order, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ''',
                '550e8400-e29b-41d4-a716-446655440042',
                '550e8400-e29b-41d4-a716-446655440002',
                '550e8400-e29b-41d4-a716-446655440040',
                '记录可追溯性',
                '检查记录是否完整、可追溯，满足认证追溯要求',
                'pass_fail',
                True,
                'medium',
                '记录抽样、批次追溯、数据完整性核验',
                '《产品质量法》第二十七条；《认证认可条例》第二十一条：认证机构应当对认证过程进行完整记录',
                2,
                datetime.now(),
                datetime.now()
            )
            print("✅ 检查项目4插入成功")
        
        rows = await conn.fetch('''
            SELECT 
                t.name as template_name,
                t.category,
                ti.title,
                ti.is_category,
                ti.risk_level,
                ti.result_type,
                ti.description
            FROM inspection_templates t
            LEFT JOIN template_items ti ON t.id = ti.template_id
            WHERE t.id = $1
            ORDER BY ti.sort_order
        ''', '550e8400-e29b-41d4-a716-446655440002')
        
        print("\n📊 插入结果验证：")
        print("-" * 80)
        for row in rows:
            print(f"模板: {row['template_name']}")
            print(f"  分类: {row['category']}")
            print(f"  项目: {row['title']}")
            print(f"  是否分类: {row['is_category']}")
            print(f"  风险等级: {row['risk_level']}")
            print(f"  检查类型: {row['result_type']}")
            print(f"  描述: {row['description']}")
            print("-" * 80)
        
        print("\n✨ 认证审查检查模板插入成功！")
        
    except Exception as e:
        print(f"❌ 插入失败: {e}")
        raise
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(insert_certification_template())
