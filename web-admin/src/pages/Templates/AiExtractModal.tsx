import { useState, useEffect, useRef } from 'react';
import { Modal, Upload, Button, Space, Table, Checkbox, Tag, Alert, Spin, Input, message, Form, Drawer, Select, Steps, Progress } from 'antd';
import {
    RobotOutlined,
    UploadOutlined,
    CheckOutlined,
    EditFilled,
    KeyOutlined,
    CloseOutlined,
    SettingOutlined,
    ThunderboltOutlined,
    FileTextOutlined,
    ApartmentOutlined,
    SafetyCertificateOutlined,
    SyncOutlined
} from '@ant-design/icons';
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
    const [currentStep, setCurrentStep] = useState<number>(0);
    const [statusMessage, setStatusMessage] = useState('');
    const [extractedCount, setExtractedCount] = useState<number>(0);
    const [currentTitle, setCurrentTitle] = useState<string>('');
    const [recentTitles, setRecentTitles] = useState<string[]>([]);
    const [items, setItems] = useState<any[]>([]);
    const [selectedIds, setSelectedIds] = useState<string[]>([]);
    const [elapsed, setElapsed] = useState<number>(0);
    const [errorMsg, setErrorMsg] = useState<string>('');
    const [reasoningText, setReasoningText] = useState<string>('');
    const [contentText, setContentText] = useState<string>('');
    const [reasoningDone, setReasoningDone] = useState<boolean>(false);
    const reasoningBoxRef = useRef<HTMLDivElement>(null);

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
            setCurrentStep(0);
            setExtractedCount(0);
            setCurrentTitle('');
            setRecentTitles([]);
            setExtractLoading(false);
            setDrawerVisible(false);
            setElapsed(0);
            setErrorMsg('');
            setReasoningText('');
            setContentText('');
            setReasoningDone(false);
        }
    }, [open]);

    // 解析中计时器（每秒更新已耗时）
    useEffect(() => {
        if (!extractLoading) return;
        const timer = setInterval(() => setElapsed(prev => prev + 1), 1000);
        return () => clearInterval(timer);
    }, [extractLoading]);

    // 思考/输出过程自动滚动到底部
    useEffect(() => {
        const el = reasoningBoxRef.current;
        if (el) el.scrollTop = el.scrollHeight;
    }, [reasoningText, contentText]);

    // 处理流式提取
    const handleExtract = async (file: File) => {
        setExtractLoading(true);
        setItems([]);
        setSelectedIds([]);
        setCurrentStep(0);
        setExtractedCount(0);
        setCurrentTitle('');
        setRecentTitles([]);
        setElapsed(0);
        setErrorMsg('');
        setReasoningText('');
        setContentText('');
        setReasoningDone(false);
        setStatusMessage(`正在读取 ${file.name}...`);

        try {
            const generator = aiExtractApi.extractItemsStream(file, (msg) => {
                setStatusMessage(msg);
            });

            let finalItems: any[] = [];
            for await (const chunk of generator) {
                if (chunk.type === 'status') {
                    if (chunk.message) {
                        setStatusMessage(chunk.message);
                    }
                    if (chunk.reasoning_delta) {
                        setReasoningText(prev => prev + chunk.reasoning_delta);
                    }
                    if (chunk.reasoning_done) {
                        setReasoningDone(true);
                    }
                    if (chunk.content_delta) {
                        setContentText(prev => prev + chunk.content_delta);
                    }
                    if (chunk.step !== undefined) {
                        setCurrentStep(chunk.step - 1);
                    } else if (chunk.stage === 'parsing_doc') {
                        setCurrentStep(0);
                    } else if (chunk.stage === 'sending' || chunk.stage === 'ai_parsing' || chunk.stage === 'extracting') {
                        setCurrentStep(1);
                    } else if (chunk.stage === 'processing' || chunk.stage === 'validating') {
                        setCurrentStep(2);
                    }

                    if (chunk.item_count) {
                        setExtractedCount(chunk.item_count);
                    }
                    if (chunk.current_title) {
                        setCurrentTitle(chunk.current_title);
                        setRecentTitles(prev => {
                            const updated = [chunk.current_title, ...prev.filter(t => t !== chunk.current_title)];
                            return updated.slice(0, 5);
                        });
                    }
                } else if (chunk.type === 'done') {
                    setCurrentStep(2);
                    finalItems = (chunk.items || []).map((it: any, idx: number) => ({
                        ...it,
                        temp_id: `temp_${Date.now()}_${idx}`,
                    }));
                    setItems(finalItems);
                    setSelectedIds(finalItems.map(it => it.temp_id));
                    setStatusMessage(`解析完成，共提取 ${finalItems.length} 个项目`);
                    setExtractedCount(finalItems.length);
                    message.success(`成功提取 ${finalItems.length} 个检查项目！`);
                } else if (chunk.type === 'error') {
                    message.error(`解析出错: ${chunk.content}`);
                    setStatusMessage(`解析出错: ${chunk.content}`);
                    setErrorMsg(chunk.content || 'AI 解析失败');
                }
            }
        } catch (error: any) {
            console.error('Extract error:', error);
            const msg = error?.name === 'AbortError'
                ? '解析超时（已超过 15 分钟），请稍后重试'
                : (error.message || 'AI解析失败，请重试');
            message.error(msg);
            setStatusMessage('解析失败');
            setErrorMsg(msg);
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

    const categoriesCount = items.filter(it => it.is_category).length;
    const checkItemsCount = items.filter(it => !it.is_category).length;
    const highRiskCount = items.filter(it => it.risk_level === 'high').length;

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
            width: 90,
            render: (isCategory: boolean, record: any) => (
                <Space size={4}>
                    <Tag color={isCategory ? 'cyan' : 'blue'} style={{ borderRadius: 4, margin: 0 }}>
                        {isCategory ? '分类目录' : '检查项'}
                    </Tag>
                    {record.risk_level === 'high' && (
                        <Tag color="red" style={{ borderRadius: 4, margin: 0 }}>重点</Tag>
                    )}
                </Space>
            ),
        },
        {
            title: '检查项 / 分类标题与标准',
            render: (_: any, record: any) => (
                <div>
                    <div style={{
                        fontWeight: record.is_category ? 600 : 500,
                        color: record.is_category ? '#0369A1' : '#1e293b',
                        fontSize: record.is_category ? 15 : 14,
                    }}>
                        {record.is_category && <SettingOutlined style={{ marginRight: 6, color: '#0369A1' }} />}
                        {record.title}
                    </div>
                    {record.parent_title && (
                        <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
                            <ApartmentOutlined style={{ marginRight: 4 }} />所属分类: <span style={{ color: '#0369A1' }}>{record.parent_title}</span>
                        </div>
                    )}
                    {!record.is_category && getCriteriaPreview(record)}
                </div>
            ),
        },
        {
            title: '检查方法 & 依据',
            width: 280,
            render: (_: any, record: any) => {
                if (record.is_category) return <span style={{ color: '#94a3b8' }}>—</span>;
                return (
                    <div style={{ fontSize: 13, color: '#475569' }}>
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
            width: 130,
            render: (type: string, record: any) => {
                if (record.is_category) return <span style={{ color: '#94a3b8' }}>—</span>;
                const typeLabel = CHECK_TYPES.find(c => c.value === type)?.label || '其他';
                return (
                    <Tag color={type === 'radio' ? 'success' : 'processing'} style={{ borderRadius: 4 }}>
                        {typeLabel}
                    </Tag>
                );
            },
        },
        {
            title: '操作',
            width: 80,
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
                    <RobotOutlined style={{ color: '#0369A1', fontSize: 22 }} />
                    <span style={{ fontSize: 18, fontWeight: 600 }}>AI 文档全要素解析与辅助录入</span>
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
            styles={{ body: { padding: '24px', minHeight: '560px', display: 'flex', flexDirection: 'column' } }}
        >
            <div style={{ marginBottom: 20 }}>
                <Alert
                    message="大模型智能文档全要素解析专家"
                    description="支持上传 PDF、Word、Excel（各类检查记录表、标准清单）。系统将基于 DeepSeek 大模型深度提取检查项目、层级结构、风险等级、判定标准及法规依据。"
                    type="info"
                    showIcon
                    style={{ marginBottom: 20, padding: '12px 20px', borderRadius: 10, alignItems: 'center' }}
                    icon={<KeyOutlined style={{ fontSize: 22 }} />}
                />

                {!extractLoading && items.length === 0 && errorMsg && (
                    <Alert
                        message="解析失败"
                        description={errorMsg}
                        type="error"
                        showIcon
                        closable
                        onClose={() => setErrorMsg('')}
                        style={{ marginBottom: 16, borderRadius: 8 }}
                    />
                )}

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
                            border: '2px dashed #93c5fd',
                            borderRadius: 16,
                            background: '#f8fafc',
                            padding: '54px 24px',
                            textAlign: 'center',
                            cursor: 'pointer',
                            transition: 'all 0.3s'
                        }}
                            onMouseEnter={e => {
                                e.currentTarget.style.borderColor = '#0369A1';
                                e.currentTarget.style.background = '#f0f9ff';
                            }}
                            onMouseLeave={e => {
                                e.currentTarget.style.borderColor = '#93c5fd';
                                e.currentTarget.style.background = '#f8fafc';
                            }}
                        >
                            <UploadOutlined style={{ fontSize: 52, color: '#0369A1', marginBottom: 16 }} />
                            <h2 style={{ fontSize: 20, fontWeight: 600, color: '#0f172a', marginBottom: 8 }}>
                                点击或拖拽文件到这里进行解析
                            </h2>
                            <p style={{ color: '#64748b', margin: 0, fontSize: 14 }}>
                                支持格式：PDF、Word（.doc/.docx）、Excel（.xls/.xlsx）、TXT
                            </p>
                        </div>
                    </Upload>
                )}

                {extractLoading && (
                    <div style={{
                        display: 'flex', flexDirection: 'column', alignItems: 'center',
                        justifyContent: 'center', padding: '40px 32px',
                        background: 'linear-gradient(180deg, #f0fdf4 0%, #f8fafc 100%)',
                        borderRadius: 16, border: '1px solid #bbf7d0',
                        boxShadow: '0 8px 24px rgba(34, 197, 94, 0.08)'
                    }}>
                        {/* Steps Indicator */}
                        <div style={{ width: '100%', maxWidth: 700, marginBottom: 32 }}>
                            <Steps
                                current={currentStep}
                                items={[
                                    { title: '本地解析', description: '提取文档文本与表格', icon: <FileTextOutlined /> },
                                    { title: 'AI 智能提取', description: '全要素流式提取', icon: <ThunderboltOutlined /> },
                                    { title: '结构校验', description: '建立层级与准则', icon: <SafetyCertificateOutlined /> },
                                ]}
                            />
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
                            <Spin indicator={<SyncOutlined spin style={{ fontSize: 32, color: '#16a34a' }} />} />
                            <div>
                                <h3 style={{ color: '#0f172a', fontWeight: 600, fontSize: 18, margin: 0 }}>
                                    AI 大模型正在深度解析提取中...
                                </h3>
                                <div style={{ color: '#64748b', fontSize: 13, marginTop: 4 }}>
                                    {statusMessage || '正在处理...'}
                                </div>
                            </div>
                        </div>

                        {/* Live Extracted Items Counter */}
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 12,
                            background: '#ffffff', padding: '10px 24px',
                            borderRadius: 30, border: '1px solid #86efac',
                            boxShadow: '0 2px 10px rgba(0,0,0,0.04)',
                            marginTop: 12,
                        }}>
                            <Tag color="success" style={{ fontSize: 14, padding: '4px 12px', borderRadius: 20, margin: 0, fontWeight: 600 }}>
                                已提取 {extractedCount} 项
                            </Tag>
                            <Tag color="blue" style={{ fontSize: 14, padding: '4px 12px', borderRadius: 20, margin: 0, fontWeight: 600 }}>
                                已耗时 {elapsed >= 60 ? `${Math.floor(elapsed / 60)}分${elapsed % 60}秒` : `${elapsed}秒`}
                            </Tag>
                            {currentTitle && (
                                <div style={{ fontSize: 13, color: '#334155', maxWidth: 450, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    正在解析：<strong style={{ color: '#0369A1' }}>{currentTitle}</strong>
                                </div>
                            )}
                        </div>

                        {/* AI 思考过程 + 输出内容实时面板 */}
                        {(reasoningText || contentText) && (
                            <div style={{ marginTop: 20, width: '100%', maxWidth: 860 }}>
                                <div style={{
                                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                    fontSize: 12, color: '#64748b', marginBottom: 6, fontWeight: 500,
                                }}>
                                    <span>
                                        {!contentText
                                            ? 'AI 思考过程（实时）'
                                            : 'AI 输出内容（结构化 JSON，实时）'}
                                    </span>
                                    <span style={{ color: '#94a3b8' }}>
                                        {reasoningText && `思考 ${reasoningText.length} 字`}
                                        {reasoningText && contentText && ' | '}
                                        {contentText && `输出 ${contentText.length} 字`}
                                    </span>
                                </div>
                                <div
                                    ref={reasoningBoxRef}
                                    style={{
                                        maxHeight: 220, overflowY: 'auto', textAlign: 'left',
                                        background: '#f8fafc', borderRadius: 10,
                                        border: '1px solid #e2e8f0', padding: '12px 16px',
                                    }}
                                >
                                    {reasoningText && (
                                        <div style={{
                                            fontSize: 12, lineHeight: 1.8, color: '#64748b', fontStyle: 'italic',
                                            whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                                        }}>
                                            {reasoningText}
                                        </div>
                                    )}
                                    {contentText && (
                                        <>
                                            <div style={{
                                                color: '#94a3b8', fontSize: 11, margin: '10px 0',
                                                borderTop: '1px dashed #e2e8f0', paddingTop: 10,
                                            }}>
                                                ———— 思考完成，以下为结构化输出 ————
                                            </div>
                                            <div style={{
                                                fontSize: 12, lineHeight: 1.7, color: '#0369A1',
                                                fontFamily: 'Consolas, Monaco, monospace',
                                                whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                                            }}>
                                                {contentText}
                                            </div>
                                        </>
                                    )}
                                    {!reasoningDone && !contentText && (
                                        <span style={{ color: '#16a34a' }}>▍</span>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Recent Extracted List Feed */}
                        {recentTitles.length > 0 && (
                            <div style={{ marginTop: 24, width: '100%', maxWidth: 700 }}>
                                <div style={{ fontSize: 12, color: '#64748b', marginBottom: 8, fontWeight: 500 }}>
                                    实时提取日志流水：
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                    {recentTitles.map((t, i) => (
                                        <div key={i} style={{
                                            fontSize: 12, padding: '6px 14px', borderRadius: 6,
                                            background: i === 0 ? '#dcfce7' : '#f1f5f9',
                                            color: i === 0 ? '#15803d' : '#475569',
                                            display: 'flex', alignItems: 'center', gap: 8,
                                            animation: 'fadeIn 0.3s ease'
                                        }}>
                                            <CheckOutlined style={{ color: '#16a34a' }} />
                                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {!extractLoading && items.length > 0 && (
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                        {/* Summary bar */}
                        <div style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: 16,
                            padding: '14px 20px',
                            background: '#f0fdf4',
                            borderRadius: 10,
                            border: '1px solid #bbf7d0',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
                        }}>
                            <Space size={16}>
                                <Checkbox
                                    checked={selectedIds.length > 0 && selectedIds.length === items.length}
                                    indeterminate={selectedIds.length > 0 && selectedIds.length < items.length}
                                    onChange={(e) => handleSelectAll(e.target.checked)}
                                >
                                    <span style={{ fontWeight: 600 }}>全选所有项目</span>
                                </Checkbox>
                                <Tag color="success" style={{ fontSize: 13, padding: '3px 10px', borderRadius: 6 }}>
                                    已选 {selectedIds.length} / 共 {items.length} 项
                                </Tag>
                                <Tag color="cyan" style={{ fontSize: 13, padding: '3px 10px', borderRadius: 6 }}>
                                    包含 {categoriesCount} 个分类
                                </Tag>
                                <Tag color="blue" style={{ fontSize: 13, padding: '3px 10px', borderRadius: 6 }}>
                                    {checkItemsCount} 个检查项
                                </Tag>
                                {highRiskCount > 0 && (
                                    <Tag color="red" style={{ fontSize: 13, padding: '3px 10px', borderRadius: 6 }}>
                                        {highRiskCount} 个重点项
                                    </Tag>
                                )}
                            </Space>
                            <Button
                                type="primary"
                                ghost
                                icon={<EditFilled />}
                                onClick={() => setRefineModal(true)}
                                style={{ borderRadius: 6, fontWeight: 500 }}
                            >
                                AI 自然语言批量精修
                            </Button>
                        </div>

                        {/* Table */}
                        <Table
                            dataSource={items}
                            rowKey="temp_id"
                            size="middle"
                            pagination={false}
                            columns={tableColumns}
                            scroll={{ y: 380, x: 1000 }}
                            style={{ border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}
                            rowClassName={(record) => record.is_category ? 'category-row' : ''}
                        />

                        {/* Footer */}
                        <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
                            <Button size="large" onClick={() => {
                                setItems([]);
                                setSelectedIds([]);
                            }}>
                                重新上传文档
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
                                    background: 'linear-gradient(90deg, #0369A1 0%, #16a34a 100%)',
                                    border: 'none',
                                    boxShadow: '0 4px 12px rgba(3, 105, 161, 0.25)',
                                    padding: '0 28px'
                                }}
                            >
                                确认导入模板 ({selectedIds.length} 项)
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
                        <span>AI 自然语言批量精修</span>
                    </Space>
                }
                open={refineModal}
                onCancel={() => !refineLoading && setRefineModal(false)}
                onOk={handleRefine}
                confirmLoading={refineLoading}
                okText="执行智能精修"
                okButtonProps={{ style: { background: '#722ed1', borderColor: '#722ed1' } }}
            >
                <Alert
                    message="输入您的修改要求，AI 会自动批量理解并调整当前所有提取项。"
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                />
                <div style={{ marginBottom: 16 }}>
                    <Space wrap size={[8, 8]}>
                        <Tag color="purple" style={{ cursor: 'pointer' }} onClick={() => setRefineInstruction('将重点项的判定标准补充完整')}>
                            补充判定标准
                        </Tag>
                        <Tag color="purple" style={{ cursor: 'pointer' }} onClick={() => setRefineInstruction('规范法规依据格式，统一标注为《食品安全法》具体条文')}>
                            规范法规依据
                        </Tag>
                        <Tag color="purple" style={{ cursor: 'pointer' }} onClick={() => setRefineInstruction('检查分类与子项层级关系，确保全部正确归类')}>
                            整理层级归属
                        </Tag>
                    </Space>
                </div>
                <TextArea
                    rows={4}
                    value={refineInstruction}
                    onChange={(e) => setRefineInstruction(e.target.value)}
                    placeholder="例如：补充所有检查项的现场检查方法 / 把带有*号的标题统一设为高风险..."
                    style={{ borderRadius: 8 }}
                />
            </Modal>

            {/* 详细编辑抽屉 */}
            <Drawer
                title="详细审查/编辑提取项"
                width={520}
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
                        <Checkbox>设为分类目录节点（作为父级层级）</Checkbox>
                    </Form.Item>

                    <Form.Item name="title" label="检查项/分类标题" rules={[{ required: true, message: '请输入标题' }]}>
                        <TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                    </Form.Item>

                    <Form.Item name="parent_title" label="所属上级分类名称（用于挂载树形结构）" style={{ marginBottom: 20 }}>
                        <Input placeholder="输入上级分类的大类标题" />
                    </Form.Item>

                    <Form.Item noStyle shouldUpdate={(prev, current) => prev.is_category !== current.is_category}>
                        {({ getFieldValue }) => {
                            if (getFieldValue('is_category')) return null;

                            return (
                                <div style={{ background: '#f8fafc', padding: 16, borderRadius: 8, border: '1px solid #e2e8f0' }}>
                                    <Form.Item name="check_type" label="判定检查类型">
                                        <Select options={CHECK_TYPES} />
                                    </Form.Item>

                                    <Form.Item noStyle shouldUpdate={(prev, current) => prev.check_type !== current.check_type}>
                                        {({ getFieldValue }) => {
                                            if (getFieldValue('check_type') !== 'radio') return null;
                                            return (
                                                <div style={{ marginBottom: 12, borderLeft: '3px solid #0369A1', paddingLeft: 12 }}>
                                                    <Form.Item name="pass_criteria" label="合格判定规则说明" style={{ marginBottom: 10 }}>
                                                        <TextArea rows={2} placeholder="若符合该项，依据什么判定..." />
                                                    </Form.Item>
                                                    <Form.Item name="fail_criteria" label="不合格判定规则说明" style={{ marginBottom: 10 }}>
                                                        <TextArea rows={2} placeholder="何种情形即判定不合格..." />
                                                    </Form.Item>
                                                </div>
                                            );
                                        }}
                                    </Form.Item>

                                    <Form.Item name="risk_level" label="项目风险等级">
                                        <Select options={RISK_LEVELS} />
                                    </Form.Item>

                                    <Form.Item name="check_method" label="检查方法详细说明">
                                        <TextArea rows={2} />
                                    </Form.Item>

                                    <Form.Item name="legal_basis" label="法律法规依据">
                                        <Input placeholder="如《食品安全法》第五十条" />
                                    </Form.Item>

                                    <Form.Item name="standard_ref" label="技术标准依据">
                                        <Input placeholder="如 GB 14881-2013" />
                                    </Form.Item>

                                    <Form.Item name="description" label="补充要求与说明">
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
          background-color: #f0fdf4 !important;
          font-weight: 600;
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
        </Modal>
    );
}
