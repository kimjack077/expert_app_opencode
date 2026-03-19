import asyncio
import asyncpg
from datetime import datetime

async def insert_enterprise():
    conn = await asyncpg.connect(
        host='117.72.77.52',
        port=5432,
        user='db_admin',
        password='1234567890@sdtj',
        database='db_expert_opencode'
    )
    
    try:
        async with conn.transaction():
            await conn.execute('''
                INSERT INTO enterprises (
                    id, name, credit_code, org_code, address, legal_person,
                    contact_person, contact_phone, enterprise_type, economic_type,
                    risk_level, status, district, street, employee_count,
                    annual_output, longitude, latitude, remarks, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
                )
            ''',
                '550e8400-e29b-41d4-a716-446655440100',
                '山东华泰安全科技有限公司',
                '91370100MA3CF5XK8Y',
                'MA3CF5XK-8',
                '山东省济南市高新区齐鲁软件园A座1201室',
                '张明华',
                '李晓红',
                '0531-88812345',
                '生产',
                '私营',
                'B',
                'active',
                '高新区',
                '舜华路街道',
                150,
                8500.00,
                '117.1256',
                '36.6512',
                '专业从事安全生产技术服务、安全评价、安全培训的高新技术企业',
                datetime.now(),
                datetime.now()
            )
            print("✅ 企业信息插入成功")
        
        result = await conn.fetchrow('''
            SELECT * FROM enterprises WHERE id = $1
        ''', '550e8400-e29b-41d4-a716-446655440100')
        
        print("\n📊 插入结果验证：")
        print("-" * 80)
        print(f"企业名称: {result['name']}")
        print(f"统一社会信用代码: {result['credit_code']}")
        print(f"法定代表人: {result['legal_person']}")
        print(f"联系电话: {result['contact_phone']}")
        print(f"企业地址: {result['address']}")
        print(f"所属区域: {result['district']}")
        print(f"风险等级: {result['risk_level']}")
        print(f"状态: {result['status']}")
        print(f"员工人数: {result['employee_count']}")
        print(f"年产值: {result['annual_output']} 万元")
        print(f"备注: {result['remarks']}")
        print("-" * 80)
        
        print("\n✨ 企业信息插入成功！")
        
    except Exception as e:
        print(f"❌ 插入失败: {e}")
        raise
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(insert_enterprise())
