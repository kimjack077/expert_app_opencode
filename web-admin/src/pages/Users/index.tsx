import React, { useState, useEffect, useRef } from 'react';
import { Card, Table, Button, Space, Modal, Form, Input, Select, Switch, message, Tag, Divider, Typography } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import { userApi } from '@/services/api';

const { Option } = Select;
const { Text } = Typography;

const auditorLevelMap: Record<string, string> = {
    basic: '初级审核员',
    intermediate: '中级审核员',
    senior: '高级审核员',
};

const Users: React.FC = () => {
    const [data, setData] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [modalVisible, setModalVisible] = useState(false);
    const [form] = Form.useForm();
    const [editingId, setEditingId] = useState<string | null>(null);
    const [searchText, setSearchText] = useState('');
    const [roleFilter, setRoleFilter] = useState<string | undefined>(undefined);
    const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
    const requestSeq = useRef(0);
    const [listPage, setListPage] = useState(1);
    const [listPageSize, setListPageSize] = useState(10);

    const fetchData = async () => {
        const seq = ++requestSeq.current;
        setLoading(true);
        try {
            const items: any[] = [];
            const limit = 100;
            for (let skip = 0; ; skip += limit) {
                const res: any = await userApi.getUsers({
                    skip,
                    limit,
                    search: searchText.trim() || undefined,
                    role: roleFilter,
                    is_active: statusFilter ? statusFilter === 'active' : undefined,
                });
                if (seq !== requestSeq.current) return;
                const batch = res.data || [];
                items.push(...batch);
                if (batch.length < limit) break;
            }
            setData(items);
        } catch (error) {
            if (seq !== requestSeq.current) return;
            setData([]);
            message.error('获取用户列表失败');
        } finally {
            if (seq === requestSeq.current) setLoading(false);
        }
    };

    useEffect(() => {
        setListPage(1);
        const timer = setTimeout(fetchData, 300);
        return () => {
            clearTimeout(timer);
            requestSeq.current++;
        };
    }, [searchText, roleFilter, statusFilter]);

    const handleAdd = () => {
        setEditingId(null);
        form.resetFields();
        setModalVisible(true);
    };

    const handleEdit = (record: any) => {
        setEditingId(record.id);
        form.setFieldsValue({
            ...record,
            qualified_systems: record.qualified_systems || [],
            qualified_industry_codes: record.qualified_industry_codes || [],
        });
        setModalVisible(true);
    };

    const handleDelete = (id: string) => {
        Modal.confirm({
            title: '确认删除',
            content: '确定要删除该用户吗？删除后不可恢复。',
            onOk: async () => {
                try {
                    await userApi.deleteUser(id);
                    message.success('删除成功');
                    fetchData();
                } catch (error) {
                    message.error('删除失败');
                }
            },
        });
    };

    const handleSubmit = async () => {
        try {
            const values = await form.validateFields();
            if (editingId) {
                if (!values.password) delete values.password;
                await userApi.updateUser(editingId, values);
                message.success('更新成功');
            } else {
                if (!values.password) {
                    message.error('请输入密码');
                    return;
                }
                await userApi.createUser(values);
                message.success('创建成功');
            }
            setModalVisible(false);
            fetchData();
        } catch (error: any) {
            if (error?.errorFields) return;
            console.error(error);
            message.error(error?.response?.data?.message || error?.response?.data?.detail || '操作失败，请检查输入或重试');
        }
    };

    const columns = [
        {
            title: '用户名',
            dataIndex: 'username',
            key: 'username',
        },
        {
            title: '姓名',
            dataIndex: 'full_name',
            key: 'full_name',
        },
        {
            title: '角色',
            dataIndex: 'role',
            key: 'role',
            render: (role: string) => {
                const roleMeta: Record<string, { label: string; color: string }> = {
                    super_admin: { label: '超级管理员', color: 'magenta' },
                    admin: { label: '管理员', color: 'blue' },
                    manager: { label: '主管', color: 'cyan' },
                    expert: { label: '专家', color: 'green' },
                    auditor: { label: '审核员', color: 'default' },
                };
                const item = roleMeta[role] || { label: role, color: 'default' };
                return <Tag color={item.color}>{item.label}</Tag>;
            },
        },
        {
            title: '注册编号',
            dataIndex: 'auditor_registration_no',
            key: 'auditor_registration_no',
            render: (val: string) => val || '-',
        },
        {
            title: '注册级别',
            dataIndex: 'auditor_level',
            key: 'auditor_level',
            render: (level: string) => level ? <Tag color="blue">{auditorLevelMap[level] || level}</Tag> : '-',
        },
        {
            title: '专业代码',
            dataIndex: 'qualified_industry_codes',
            key: 'qualified_industry_codes',
            render: (codes: string[]) => codes?.length > 0 ? codes.join(', ') : '-',
        },
        {
            title: '联系方式',
            dataIndex: 'phone',
            key: 'phone',
        },
        {
            title: '状态',
            dataIndex: 'is_active',
            key: 'is_active',
            render: (active: boolean) => (
                <Tag color={active ? 'success' : 'default'}>{active ? '启用' : '禁用'}</Tag>
            ),
        },
        {
            title: '操作',
            key: 'action',
            width: 150,
            fixed: 'right' as const,
            render: (_: any, record: any) => (
                <Space size="middle">
                    <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
                        编辑
                    </Button>
                    <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)}>
                        删除
                    </Button>
                </Space>
            ),
        },
    ];

    return (
        <div>
            <Card
                title="用户管理"
                extra={
                    <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
                        新增用户
                    </Button>
                }
            >
                <Space wrap style={{ marginBottom: 16 }}>
                    <Input
                        allowClear
                        prefix={<SearchOutlined />}
                        placeholder="搜索登录名、姓名、手机号或注册号"
                        style={{ width: 260 }}
                        value={searchText}
                        onChange={(e) => setSearchText(e.target.value)}
                    />
                    <Select
                        placeholder="角色筛选"
                        allowClear
                        style={{ width: 140 }}
                        value={roleFilter}
                        onChange={(val) => setRoleFilter(val)}
                        options={[
                            { value: 'super_admin', label: '超级管理员' },
                            { value: 'admin', label: '管理员' },
                            { value: 'expert', label: '专家' },
                            { value: 'auditor', label: '审核员' },
                        ]}
                    />
                    <Select
                        placeholder="状态筛选"
                        allowClear
                        style={{ width: 120 }}
                        value={statusFilter}
                        onChange={(val) => setStatusFilter(val)}
                        options={[
                            { value: 'active', label: '启用' },
                            { value: 'inactive', label: '禁用' },
                        ]}
                    />
                    {(searchText || roleFilter || statusFilter) && (
                        <Button onClick={() => { setSearchText(''); setRoleFilter(undefined); setStatusFilter(undefined); }}>
                            重置
                        </Button>
                    )}
                    <Button icon={<ReloadOutlined />} onClick={() => fetchData()} loading={loading}>
                        刷新
                    </Button>
                </Space>
                <Table
                    columns={columns}
                    dataSource={data}
                    rowKey="id"
                    loading={loading}
                    pagination={{
                        current: listPage,
                        pageSize: listPageSize,
                        onChange: (page, pageSize) => { setListPage(page); setListPageSize(pageSize); },
                        showSizeChanger: true,
                        showTotal: (t) => `共 ${t} 人`,
                    }}
                    scroll={{ x: 1200 }}
                />
            </Card>

            <Modal
                title={editingId ? '编辑用户' : '新增用户'}
                open={modalVisible}
                onOk={handleSubmit}
                onCancel={() => setModalVisible(false)}
                destroyOnHidden
                zIndex={1000}
                maskClosable={false}
                width={700}
            >
                <Form form={form} layout="vertical" initialValues={{ role: 'expert', is_active: true, qualified_systems: [], qualified_industry_codes: [] }}>
                    <Form.Item
                        name="username"
                        label="登录名"
                        rules={[{ required: true, message: '请输入登录用户名' }]}
                    >
                        <Input placeholder="请输入登录名（英文/数字）" />
                    </Form.Item>
                    <Form.Item
                        name="password"
                        label={editingId ? '密码 (留空则不修改)' : '密码'}
                        rules={[{ required: !editingId, message: '请输入密码' }]}
                    >
                        <Input.Password placeholder="请输入密码" />
                    </Form.Item>
                    <Form.Item name="full_name" label="真实姓名">
                        <Input placeholder="请输入真实姓名" />
                    </Form.Item>
                    <Form.Item name="phone" label="联系电话">
                        <Input placeholder="请输入手机号码" />
                    </Form.Item>
                    <Form.Item name="email" label="邮箱">
                        <Input placeholder="请输入电子邮箱" />
                    </Form.Item>
                    <Form.Item name="role" label="角色">
                        <Select 
                            placeholder="请选择角色" 
                            getPopupContainer={(triggerNode) => triggerNode.parentElement || document.body}
                            dropdownStyle={{ zIndex: 9999 }}
                            listHeight={200}
                        >
                            <Option value="super_admin">超级管理员 (Super Admin)</Option>
                            <Option value="admin">管理员 (Admin)</Option>
                            <Option value="expert">专家 (Expert)</Option>
                            <Option value="auditor">审核员 (Auditor)</Option>
                        </Select>
                    </Form.Item>
                    <Form.Item name="is_active" label="状态" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                    </Form.Item>

                    <Divider orientation="left">
                        <Text type="secondary">审核员资质信息</Text>
                    </Divider>

                    <Form.Item name="auditor_registration_no" label="注册编号">
                        <Input placeholder="如：2022-N1QMS-2215455" />
                    </Form.Item>
                    <Form.Item name="auditor_level" label="注册级别">
                        <Select placeholder="请选择注册级别" allowClear>
                            <Option value="basic">初级审核员</Option>
                            <Option value="intermediate">中级审核员</Option>
                            <Option value="senior">高级审核员</Option>
                        </Select>
                    </Form.Item>
                    <Form.Item name="qualified_systems" label="注册体系">
                        <Select mode="multiple" placeholder="请选择注册体系">
                            <Option value="Q">Q - 质量</Option>
                            <Option value="E">E - 环境</Option>
                            <Option value="S">S - 职业健康安全</Option>
                            <Option value="En">En - 能源</Option>
                        </Select>
                    </Form.Item>
                    <Form.Item name="qualified_industry_codes" label="专业代码">
                        <Select mode="tags" placeholder="请输入专业代码，如 10.01、12.01">
                            <Option value="10.01">10.01</Option>
                            <Option value="12.01">12.01</Option>
                            <Option value="15.01">15.01</Option>
                            <Option value="17.01">17.01</Option>
                            <Option value="18.01">18.01</Option>
                        </Select>
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    );
};

export default Users;
