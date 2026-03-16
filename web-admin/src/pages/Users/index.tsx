import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Space, Modal, Form, Input, Select, Switch, message } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { userApi } from '@/services/api';

const { Option } = Select;

const Users: React.FC = () => {
    const [data, setData] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [modalVisible, setModalVisible] = useState(false);
    const [form] = Form.useForm();
    const [editingId, setEditingId] = useState<string | null>(null);

    const fetchData = async () => {
        setLoading(true);
        try {
            const res: any = await userApi.getUsers();
            setData(res.data || []);
        } catch (error) {
            message.error('获取用户列表失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleAdd = () => {
        setEditingId(null);
        form.resetFields();
        setModalVisible(true);
    };

    const handleEdit = (record: any) => {
        setEditingId(record.id);
        form.setFieldsValue(record);
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
        } catch (error) {
            console.error(error);
            message.error('操作失败，请检查输入或重试');
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
                const roles: Record<string, string> = {
                    admin: '管理员',
                    manager: '主管',
                    expert: '专家',
                };
                return roles[role] || role;
            },
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
            render: (active: boolean) => (active ? '启用' : '禁用'),
        },
        {
            title: '操作',
            key: 'action',
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
                <Table
                    columns={columns}
                    dataSource={data}
                    rowKey="id"
                    loading={loading}
                    pagination={{ defaultPageSize: 10 }}
                />
            </Card>

            <Modal
                title={editingId ? '编辑用户' : '新增用户'}
                open={modalVisible}
                onOk={handleSubmit}
                onCancel={() => setModalVisible(false)}
                destroyOnClose
                zIndex={1000}
                maskClosable={false}
            >
                <Form form={form} layout="vertical" initialValues={{ role: 'expert', is_active: true }}>
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
                            <Option value="admin">管理员 (Admin)</Option>
                            <Option value="manager">主管 (Manager)</Option>
                            <Option value="expert">专家 (Expert)</Option>
                        </Select>
                    </Form.Item>
                    <Form.Item name="is_active" label="状态" valuePropName="checked">
                        <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    );
};

export default Users;
