import { useState, useEffect } from 'react';
import { Modal, Upload, Button, Space, Table, Checkbox, Tag, Alert, Spin, Input, message, Form, Drawer, Select } from 'antd';
import { RobotOutlined, UploadOutlined, CheckOutlined, EditFilled, KeyOutlined, CloseOutlined, SettingOutlined } from '@ant-design/icons';
import { aiExtractApi } from '@/services/api';

const { TextArea } = Input;

// 风险等级选项
const RISK_LEVELS = [
    { label: '低风险', value: 'low' },
    { label: '中风险', value: 'medium' },
    { label: '高风险', value: 'high' },
];

// 检查类型选项
const CHECK_TYPES = [
    { label: '单选判定 (合格/不合格)', value: 'radio' },
    { label: '数值测量', value: 'numeric' },
    { label: '文字描述', value: 'text' },
    { label: '打分评价', value: 'score' },
    { label: '多选', value: 'multi_check' },
];

interface AiExtractModalProps {
    open: boolean;
    onCancel: () => void;
    templateId: string;
    onSuccess: () => void;
}

export default function AiExtractModal({ open, onCancel, templateId, onSuccess }: AiExtractModalProps) {
    const [extractLoading, setExtractLoading] = useState(false);
    const [statusMessage, setStatusMessage] = useState('');
    const [items, setItems] = useState<any[]>([]);
    const [selectedIds, setSelectedIds] = useState<string[]>([]);

    const [applyLoading, setApplyLoading] = useState(false);

    const [refineModal, setRefineModal] = useState(false);
    const [refineInstruction, setRefineInstruction] = useState('');
    const [refineLoading, setRefineLoading] = useState(false);

    // 抽屉状态（用于单条编辑/查看详情）
    const [drawerVisible, setDrawerVisible] = useState(false);
    const [editingItem, setEditingItem] = useState<any>(null);
    const [form] = Form.useForm();

    // 重置状态
    useEffect(() => {
        if (!open) {
            setItems([]);
            setSelectedIds([]);
            setStatusMessage('');
            setExtractLoading(false);
            setDrawerVisible(false);
        }
    }, [open]);

    // 处理流式提取
    const handleExtract = async (file: File) => {
        setExtractLoading(true);
        setItems([]);
        setSelectedIds([]);
        setStatusMessage('准备解析文档...');

        try {
            const generator = aiExtractApi.extractItemsStream(file, (msg) => {
                setStatusMessage(msg);
            });

            let finalItems: any[] = [];
            for await (const chunk of generator) {
                if (chunk.type === 'thinking') {
                    // 正在思考输出文本，可以忽略或者显示特效
                } else if (chunk.type === 'status') {
                    setStatusMessage(chunk.message);
                } else if (chunk.type === 'done') {
                    finalItems = chunk.items.map((it: any, idx: number) => ({
                        ...it,
                        temp_id: `temp_${Date.now()}_${idx}`,
                    }));
                    setItems(finalItems);
                    setSelectedIds(finalItems.map(it => it.temp_id));
                    setStatusMessage('解析完成');
                    message.success(`成功提取 ${finalItems.length} 个项目`);
                } else if (chunk.type === 'error') {
                    message.error(`解析出错: ${chunk.content}`);
                    setStatusMessage(`解析出错: ${chunk.content}`);
                }
            }
        } catch (error: any) {
            console.error('Extract error:', error);
            message.error(error.message || 'AI解析失败，请重试');
            setStatusMessage('解析失败');
        } finally {
            setExtractLoading(false);
        }
    };

    // 确认应用结果
    const handleApply = async () => {
        if (selectedIds.length === 0) {
            message.warning('请选择要添加的检查项');
            return;
        }

        setApplyLoading(true);
        try {
            const selectedItems = items.filter(it => selectedIds.includes(it.temp_id));
            const res: any = await aiExtractApi.applyItems(templateId, selectedItems);
            if (res.code === 200) {
                message.success(`成功添加 ${res.data?.created_count || 0} 个检查项`);
                if (res.data?.errors?.length > 0) {
                    message.warning(`有 ${res.data.errors.length} 项添加失败，请查看控制台`);
                    console.warn('Apply errors:', res.data.errors);
                }
                onSuccess();
            } else {
                message.error(res.message || '添加失败');
            }
        } catch (error: any) {
            message.error(error?.response?.data?.message || '添加失败');
        } finally {
            setApplyLoading(false);
        }
    };

    // AI 优化
    const handleRefine = async () => {
        if (!refineInstruction.trim()) {
            message.warning('请输入优化指令');
            return;
        }

        setRefineLoading(true);
        try {
            const currentItems = items.map(({ temp_id, ...rest }) => rest);
            const res: any = await aiExtractApi.refineItems(currentItems, refineInstruction);
            if (res.code === 200 && res.data?.items) {
                const refinedItems = res.data.items.map((it: any, idx: number) => ({
                    ...it,
                    temp_id: `temp_${Date.now()}_refine_${idx}`,
                }));
                setItems(refinedItems);
                setSelectedIds(refinedItems.map((it: any) => it.temp_id));
                setRefineModal(false);
                setRefineInstruction('');
                message.success('优化完成');
            } else {
                message.error(res.message || '优化失败');
            }
        } catch (error: any) {
            message.error(error?.response?.data?.message || '优化失败');
        } finally {
            setRefineLoading(false);
        }
    };

    const handleSelectAll = (checked: boolean) => {
        if (checked) {
            setSelectedIds(items.map(i => i.temp_id));
        } else {
            setSelectedIds([]);
        }
    };

    // 打开编辑抽屉
    const openEditDrawer = (record: any) => {
        setEditingItem(record);

        // 提取 radio 类型的 criteria 回显到表单
        let passCriteria = '';
        let failCriteria = '';
        if (record.check_type === 'radio' && record.result_options?.options) {
            const passOpt = record.result_options.options.find((o: any) => o.value === 'pass');
            const failOpt = record.result_options.options.find((o: any) => o.value === 'fail');
            if (passOpt) passCriteria = passOpt.criteria || '';
            if (failOpt) failCriteria = failOpt.criteria || '';
        }

        form.setFieldsValue({
            ...record,
            pass_criteria: passCriteria,
            fail_criteria: failCriteria,
        });
        setDrawerVisible(true);
    };

    const saveDrawerEdit = async () => {
        try {
            const values = await form.validateFields();

            // 处理回填 result_options criteria
            const newItem = { ...editingItem, ...values };

            if (newItem.check_type === 'radio') {
                newItem.result_options = {
                    options: [
                        { value: 'pass', label: '合格', criteria: values.pass_criteria || '' },
                        { value: 'fail', label: '不合格', criteria: values.fail_criteria || '' },
                        { value: 'na', label: '不适用' },
                    ]
                };
            }

            delete newItem.pass_criteria;
            delete newItem.fail_criteria;

            const newItems = items.map(it => it.temp_id === newItem.temp_id ? newItem : it);
            setItems(newItems);
            setDrawerVisible(false);
            message.success('已应用本地修改');
        } catch (e) {
            // Validate failed
        }
    };

    // 获得合格/不合格判定标准文本以供显示
    const getCriteriaPreview = (record: any) => {
        if (record.check_type === 'radio' && record.result_options?.options) {
            const passOpt = record.result_options.options.find((o: any) => o.value === 'pass');
            const failOpt = record.result_options.options.find((o: any) => o.value === 'fail');

            if (passOpt?.criteria || failOpt?.criteria) {
                return (
                    <div style={{ fontSize: 12, marginTop: 4 }}>
                        {passOpt?.criteria && <div style={{ color: '#52c41a' }}><CheckOutlined /> 合格: {passOpt.criteria}</div>}
                        {failOpt?.criteria && <div style={{ color: '#ff4d4f' }}><CloseOutlined /> 不合格: {failOpt.criteria}</div>}
                    </div>
                );
            }
        }
        return null;
    };

    const tableColumns = [
        {
            title: '',
            width: 50,
            render: (_: any, record: any) => (
                <Checkbox
                    checked={selectedIds.includes(record.temp_id)}
                    onChange={(e) => {
                        if (e.target.checked) setSelectedIds([...selectedIds, record.temp_id]);
                        else setSelectedIds(selectedIds.filter(id => id !== record.temp_id));
                    }}
                />
            ),
        },
        {
            title: '类型',
            dataIndex: 'is_category',
            width: 80,
            render: (isCategory: boolean) => (
                <Tag color={isCategory ? 'cyan' : 'blue'} style={{ borderRadius: 4 }}>
                    {isCategory ? '分类' : '检查项'}
                </Tag>
            ),
        },
        {
            title: '标题与标准',
            width: 350,
            render: (_: any, record: any) => (
                <div>
                    <div style={{ fontWeight: 500, color: record.is_category ? '#0369A1' : 'inherit' }}>
                        {record.is_category && <SettingOutlined style={{ marginRight: 4 }} />}
                        {record.title}
                    </div>
                    {record.parent_title && (
                        <div style={{ fontSize: 12, color: '#8c8c8c' }}>父级: {record.parent_title}</div>
                    )}
                    {!record.is_category && getCriteriaPreview(record)}
                </div>
            ),
        },
        {
            title: '检查方法 & 依据',
            width: 250,
            render: (_: any, record: any) => {
                if (record.is_category) return '-';
                return (
                    <div style={{ fontSize: 13, color: '#595959' }}>
                        {record.check_method && <div><strong>方法:</strong> {record.check_method}</div>}
                        {record.legal_basis && <div><strong>法规:</strong> {record.legal_basis}</div>}
                        {record.standard_ref && <div><strong>标准:</strong> {record.standard_ref}</div>}
                    </div>
                );
            }
        },
        {
            title: '判定类型',
            dataIndex: 'check_type',
            width: 120,
            render: (type: string, record: any) => {
                if (record.is_category) return '-';
                const typeLabel = CHECK_TYPES.find(c => c.value === type)?.label || '其他';
                return (
                    <Tag color={type === 'radio' ? 'success' : 'processing'}>
                        {typeLabel}
                    </Tag>
                );
            },
        },
        {
            title: '操作',
            width: 100,
            fixed: 'right' as any,
            render: (_: any, record: any) => (
                <Button type="link" size="small" onClick={() => openEditDrawer(record)}>
                    精调
                </Button>
            ),
        },
    ];

    return (
        <Modal
            title={
                <Space>
                    <RobotOutlined style={{ color: '#0369A1', fontSize: 20 }} />
                    <span style={{ fontSize: 18 }}>AI 文档解析辅助录入</span>
                </Space>
            }
            open={open}
            onCancel={() => {
                if (!extractLoading && !applyLoading) {
                    onCancel();
                }
            }}
            width={1200}
            footer={null}
            maskClosable={false}
            style={{ top: 20 }}
            styles={{ body: { padding: '24px', minHeight: '600px', display: 'flex', flexDirection: 'column' } }}
        >
            <div style={{ marginBottom: 24 }}>
                <Alert
                    message="智能化文档解析专家"
                    description="支持上传 PDF、Word、Excel（尤其是各类检查记录表）。我们将利用大模型自动提取结构化的检查项目、判断依据、法规标准以及合格/不合格的判定准则。"
                    type="info"
                    showIcon
                    style={{ marginBottom: 24, padding: '16px 24px', borderRadius: 12, alignItems: 'center' }}
                    icon={<KeyOutlined style={{ fontSize: 24 }} />}
                />

                {!extractLoading && items.length === 0 && (
                    <Upload
                        accept=".pdf,.doc,.docx,.xls,.xlsx,.txt"
                        showUploadList={false}
                        beforeUpload={(file) => {
                            handleExtract(file);
                            return false;
                        }}
                    >
                        <div style={{
                            border: '2px dashed #d9d9d9',
                            borderRadius: 16,
                            background: '#fafafa',
                            padding: '48px',
                            textAlign: 'center',
                            cursor: 'pointer',
                            transition: 'all 0.3s'
                        }}
                            onMouseEnter={e => e.currentTarget.style.borderColor = '#0369A1'}
                            onMouseLeave={e => e.currentTarget.style.borderColor = '#d9d9d9'}
                        >
                            <UploadOutlined style={{ fontSize: 48, color: '#0369A1', marginBottom: 16 }} />
                            <h2 style={{ fontSize: 20, fontWeight: 500, color: '#1a1a2e' }}>点击或拖拽文件到这里进行解析</h2>
                            <p style={{ color: '#8c8c8c', margin: 0 }}>单次支持一份文档，支持常见的管理表格和标准文本</p>
                        </div>
                    </Upload>
                )}

                {extractLoading && (
                    <div style={{
                        display: 'flex', flexDirection: 'column', alignItems: 'center',
                        justifyContent: 'center', padding: '64px 0',
                        background: '#f8f9ff', borderRadius: 16, border: '1px solid #d6e4ff'
                    }}>
                        <Spin size="large" style={{ marginBottom: 24 }} tip="解析中..." />
                        <h3 style={{ color: '#0369A1', fontWeight: 500 }}>正在深度分析文档并抽取实体</h3>
                        <div style={{
                            marginTop: 12, color: '#595959', fontSize: 14,
                            background: '#e6f4ff', padding: '6px 16px', borderRadius: 20
                        }}>
                            实时追踪: <span style={{ fontWeight: 'bold' }}>{statusMessage}</span>
                        </div>
                    </div>
                )}

                {!extractLoading && items.length > 0 && (
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                        {/* 工具栏 */}
                        <div style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: 16,
                            padding: '12px 20px',
                            background: '#f6ffed',
                            borderRadius: 8,
                            border: '1px solid #b7eb8f',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
                        }}>
                            <Space>
                                <Checkbox
                                    checked={selectedIds.length > 0 && selectedIds.length === items.length}
                                    indeterminate={selectedIds.length > 0 && selectedIds.length < items.length}
                                    onChange={(e) => handleSelectAll(e.target.checked)}
                                >
                                    <span style={{ fontWeight: 500 }}>全选所有检查项</span>
                                </Checkbox>
                                <Tag color="success" style={{ fontSize: 14, padding: '2px 8px', borderRadius: 6 }}>
                                    已选 {selectedIds.length} / 共 {items.length} 提取项
                                </Tag>
                            </Space>
                            <Button
                                type="primary"
                                ghost
                                icon={<EditFilled />}
                                onClick={() => setRefineModal(true)}
                                style={{ borderRadius: 6, fontWeight: 500 }}
                            >
                                唤起大模型批量修正指令
                            </Button>
                        </div>

                        {/* Table */}
                        <Table
                            dataSource={items}
                            rowKey="temp_id"
                            size="small"
                            pagination={false}
                            columns={tableColumns}
                            scroll={{ y: 400, x: 1000 }}
                            style={{ border: '1px solid #f0f0f0', borderRadius: 8, overflow: 'hidden' }}
                            rowClassName={(record) => record.is_category ? 'category-row' : ''}
                        />

                        {/* Footer */}
                        <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
                            <Button size="large" onClick={() => {
                                setItems([]);
                                setSelectedIds([]);
                            }}>
                                重新上传
                            </Button>
                            <Button
                                type="primary"
                                size="large"
                                icon={<CheckOutlined />}
                                loading={applyLoading}
                                onClick={handleApply}
                                disabled={selectedIds.length === 0}
                                style={{
                                    borderRadius: 8,
                                    fontWeight: 600,
                                    background: 'linear-gradient(90deg, #0369A1 0%, #22C55E 100%)',
                                    border: 'none',
                                    boxShadow: '0 4px 12px rgba(24, 144, 255, 0.3)'
                                }}
                            >
                                一键入库 ({selectedIds.length}项)
                            </Button>
                        </div>
                    </div>
                )}
            </div>

            {/* AI 修正 Modal */}
            <Modal
                title={
                    <Space>
                        <RobotOutlined style={{ color: '#722ed1' }} />
                        <span>AI 自然语言批量修正</span>
                    </Space>
                }
                open={refineModal}
                onCancel={() => !refineLoading && setRefineModal(false)}
                onOk={handleRefine}
                confirmLoading={refineLoading}
                okText="一键智能修正"
                okButtonProps={{ style: { background: '#722ed1', borderColor: '#722ed1' } }}
            >
                <Alert
                    message="输入你的修改意图，AI会自动理解并修正表格中所有提取项。"
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                />
                <div style={{ marginBottom: 16 }}>
                    <Space wrap size={[8, 8]}>
                        <Tag color="purple" style={{ cursor: 'pointer' }} onClick={() => setRefineInstruction('提取项太细碎，请将同一表格行内的测试合并为单项')}>
                            合并细碎检查项目
                        </Tag>
                        <Tag color="purple" style={{ cursor: 'pointer' }} onClick={() => setRefineInstruction('确保所有的合格判定和不合格判定被提取到 criteria 字段')}>
                            深度提炼判定标准
                        </Tag>
                        <Tag color="purple" style={{ cursor: 'pointer' }} onClick={() => setRefineInstruction('规范每个项目的法规依据格式，只保留法律名称和条文号')}>
                            规范化法规格式
                        </Tag>
                    </Space>
                </div>
                <TextArea
                    rows={5}
                    value={refineInstruction}
                    onChange={(e) => setRefineInstruction(e.target.value)}
                    placeholder="例如：把所有的“判定类型”改为“文字描述” / 把检查方法里重复的前缀去掉..."
                    style={{ borderRadius: 8 }}
                />
            </Modal>

            {/* 详细编辑抽屉 */}
            <Drawer
                title="详细审查/编辑提取项"
                width={500}
                onClose={() => setDrawerVisible(false)}
                open={drawerVisible}
                extra={
                    <Space>
                        <Button onClick={() => setDrawerVisible(false)}>取消</Button>
                        <Button type="primary" onClick={saveDrawerEdit}>保存修改</Button>
                    </Space>
                }
            >
                <Form form={form} layout="vertical">
                    <Form.Item name="is_category" valuePropName="checked" style={{ marginBottom: 16 }}>
                        <Checkbox>设为分类标题节点(作为层级父节点)</Checkbox>
                    </Form.Item>

                    <Form.Item name="title" label="检查项/分类标题" rules={[{ required: true }]}>
                        <TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                    </Form.Item>

                    <Form.Item name="parent_title" label="上级分类名称(用于自动挂载树形结构)" style={{ marginBottom: 24 }}>
                        <Input placeholder="输入一字不差的父节点标题" />
                    </Form.Item>

                    <Form.Item noStyle shouldUpdate={(prev, current) => prev.is_category !== current.is_category}>
                        {({ getFieldValue }) => {
                            if (getFieldValue('is_category')) return null;

                            return (
                                <div style={{ background: '#fafafa', padding: 16, borderRadius: 8, border: '1px solid #f0f0f0' }}>
                                    <Form.Item name="check_type" label="判定检查类型">
                                        <Select options={CHECK_TYPES} />
                                    </Form.Item>

                                    <Form.Item noStyle shouldUpdate={(prev, current) => prev.check_type !== current.check_type}>
                                        {({ getFieldValue }) => {
                                            if (getFieldValue('check_type') !== 'radio') return null;
                                            return (
                                                <div style={{ marginTop: -12, marginBottom: 12, borderLeft: '3px solid #0369A1', paddingLeft: 12 }}>
                                                    <Form.Item name="pass_criteria" label="合格/符合标准判定详细规则" style={{ marginBottom: 12 }}>
                                                        <TextArea rows={2} placeholder="若符合该项，依据什么判定..." />
                                                    </Form.Item>
                                                    <Form.Item name="fail_criteria" label="不合格/违规详细规则判定" style={{ marginBottom: 12 }}>
                                                        <TextArea rows={2} placeholder="有何种情形即判定不合格..." />
                                                    </Form.Item>
                                                </div>
                                            )
                                        }}
                                    </Form.Item>

                                    <Form.Item name="risk_level" label="项目风险等级">
                                        <Select options={RISK_LEVELS} />
                                    </Form.Item>

                                    <Form.Item name="check_method" label="检查方法详细描述">
                                        <TextArea rows={2} />
                                    </Form.Item>

                                    <Form.Item name="legal_basis" label="执法法律依据">
                                        <Input />
                                    </Form.Item>

                                    <Form.Item name="standard_ref" label="技术标准依据">
                                        <Input />
                                    </Form.Item>

                                    <Form.Item name="description" label="项目补充说明(可选)">
                                        <TextArea rows={2} />
                                    </Form.Item>
                                </div>
                            );
                        }}
                    </Form.Item>
                </Form>
            </Drawer>

            <style>{`
        .category-row {
          background-color: #f0f5ff !important;
        }
      `}</style>
        </Modal>
    );
}
