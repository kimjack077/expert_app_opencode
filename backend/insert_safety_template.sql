-- 安全生产检查模板插入 SQL
-- 注意：执行前请确保数据库连接正确

-- 1. 插入模板主表
INSERT INTO inspection_templates (
    id, name, code, description, category, version, is_published, created_at, updated_at
) VALUES (
    '550e8400-e29b-41d4-a716-446655440001'::uuid,
    '安全生产检查模板',
    'SAFETY-PROD-001',
    '用于企业生产现场安全检查和作业与应急管理检查的专业模板，涵盖设备安全、电气安全、作业人员防护、消防应急等关键检查项目',
    '安全生产',
    '1.0',
    true,
    NOW(),
    NOW()
);

-- 2. 插入分类节点（一级分类）
-- 2.1 生产现场安全检查
INSERT INTO template_items (
    id, template_id, parent_id, title, description, is_category, 
    sort_order, created_at, updated_at
) VALUES (
    '550e8400-e29b-41d4-a716-446655440010'::uuid,
    '550e8400-e29b-41d4-a716-446655440001'::uuid,
    NULL,
    '一、生产现场安全检查',
    '检查生产现场设备运行状态、电气安全等关键环节',
    true,
    1,
    NOW(),
    NOW()
);

-- 2.2 作业与应急管理检查
INSERT INTO template_items (
    id, template_id, parent_id, title, description, is_category, 
    sort_order, created_at, updated_at
) VALUES (
    '550e8400-e29b-41d4-a716-446655440020'::uuid,
    '550e8400-e29b-41d4-a716-446655440001'::uuid,
    NULL,
    '二、作业与应急管理检查',
    '检查作业人员防护佩戴、消防应急设施完好性等关键环节',
    true,
    2,
    NOW(),
    NOW()
);

-- 3. 插入具体检查项目（二级项目）
-- 3.1 生产现场安全检查 - 设备安全运行状态
INSERT INTO template_items (
    id, template_id, parent_id, title, description, 
    check_type, result_options, is_required, risk_level, 
    check_method, legal_basis, sort_order, created_at, updated_at
) VALUES (
    '550e8400-e29b-41d4-a716-446655440011'::uuid,
    '550e8400-e29b-41d4-a716-446655440001'::uuid,
    '550e8400-e29b-41d4-a716-446655440010'::uuid,
    '设备安全运行状态',
    '检查生产设备完好性、安全防护装置有效性',
    'radio',
    '{"options": [{"value": "pass", "label": "通过"}, {"value": "fail", "label": "不通过"}, {"value": "na", "label": "不适用"}]}'::json,
    true,
    'high',
    '目视检查、功能测试',
    '《安全生产法》第三十六条：生产经营单位必须对安全设备进行经常性维护、保养，并定期检测，保证正常运转',
    1,
    NOW(),
    NOW()
);

-- 3.2 生产现场安全检查 - 电气安全规范
INSERT INTO template_items (
    id, template_id, parent_id, title, description, 
    check_type, result_options, is_required, risk_level, 
    check_method, legal_basis, sort_order, created_at, updated_at
) VALUES (
    '550e8400-e29b-41d4-a716-446655440012'::uuid,
    '550e8400-e29b-41d4-a716-446655440001'::uuid,
    '550e8400-e29b-41d4-a716-446655440010'::uuid,
    '电气安全规范',
    '检查线路、配电箱、接地等用电安全情况',
    'radio',
    '{"options": [{"value": "pass", "label": "通过"}, {"value": "fail", "label": "不通过"}, {"value": "na", "label": "不适用"}]}'::json,
    true,
    'medium',
    '目视巡检、漏电测试',
    '《安全生产法》第三十八条：生产经营单位应当对电气设备采取可靠的安全措施，防止触电事故',
    2,
    NOW(),
    NOW()
);

-- 3.3 作业与应急管理检查 - 作业人员防护佩戴
INSERT INTO template_items (
    id, template_id, parent_id, title, description, 
    check_type, result_options, is_required, risk_level, 
    check_method, legal_basis, sort_order, created_at, updated_at
) VALUES (
    '550e8400-e29b-41d4-a716-446655440021'::uuid,
    '550e8400-e29b-41d4-a716-446655440001'::uuid,
    '550e8400-e29b-41d4-a716-446655440020'::uuid,
    '作业人员防护佩戴',
    '检查员工劳保用品佩戴合规性',
    'radio',
    '{"options": [{"value": "pass", "label": "通过"}, {"value": "fail", "label": "不通过"}, {"value": "na", "label": "不适用"}]}'::json,
    true,
    'medium',
    '现场抽查、拍照记录',
    '《安全生产法》第五十七条：从业人员在作业过程中，应当严格落实岗位安全责任，正确佩戴和使用劳动防护用品',
    1,
    NOW(),
    NOW()
);

-- 3.4 作业与应急管理检查 - 消防应急设施完好
INSERT INTO template_items (
    id, template_id, parent_id, title, description, 
    check_type, result_options, is_required, risk_level, 
    check_method, legal_basis, sort_order, created_at, updated_at
) VALUES (
    '550e8400-e29b-41d4-a716-446655440022'::uuid,
    '550e8400-e29b-41d4-a716-446655440001'::uuid,
    '550e8400-e29b-41d4-a716-446655440020'::uuid,
    '消防应急设施完好',
    '检查灭火器、消防通道、应急照明等状态',
    'radio',
    '{"options": [{"value": "pass", "label": "通过"}, {"value": "fail", "label": "不通过"}, {"value": "na", "label": "不适用"}]}'::json,
    true,
    'high',
    '压力表核查、实测通道',
    '《消防法》第十六条：机关、团体、企业、事业等单位应当对建筑消防设施每年至少进行一次全面检测，确保完好有效',
    2,
    NOW(),
    NOW()
);

-- 查询验证
SELECT 
    t.name as template_name,
    t.category,
    ti.title,
    ti.is_category,
    ti.risk_level,
    ti.check_type,
    ti.description,
    ti.check_method,
    ti.legal_basis
FROM inspection_templates t
LEFT JOIN template_items ti ON t.id = ti.template_id
WHERE t.id = '550e8400-e29b-41d4-a716-446655440001'::uuid
ORDER BY ti.sort_order;
