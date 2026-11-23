import { useState, useEffect } from 'react'
import { Table, Button, Space, Tag, Modal, Form, Select, message } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons'
import { auditTeamApi } from '@/services/auditProjectApi'
import { userApi } from '@/services/api'
import type { ColumnsType } from 'antd/es/table'

interface TeamMember {
  id: string
  member_id: string
  member_name: string
  member_username: string
  role: string
  responsible_systems: string[]
  qualification_codes: string[]
  registration_no: string
  registration_level: string
  status: string
}

interface Props {
  projectId: string
  canManage: boolean
}

const roleMap: Record<string, string> = {
  leader: '组长',
  member: '组员',
  trainee: '被验证审核员',
  observer: '观察员',
  expert: '技术专家',
}

export default function TeamManagement({ projectId, canManage }: Props) {
  const [loading, setLoading] = useState(false)
  const [members, setMembers] = useState<TeamMember[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [editingMember, setEditingMember] = useState<TeamMember | null>(null)
  const [users, setUsers] = useState<any[]>([])
  const [form] = Form.useForm()

  useEffect(() => {
    fetchMembers()
    if (canManage) fetchUsers()
  }, [projectId, canManage])

  const fetchMembers = async () => {
    setLoading(true)
    try {
      const response = await auditTeamApi.list(projectId)
      setMembers(response.data || [])
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取审核组成员失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchUsers = async () => {
    try {
      const response: any = await userApi.getUserOptions({ project_id: projectId })
      setUsers(response.data || [])
    } catch (error) {
      console.error('获取用户列表失败:', error)
    }
  }

  const handleAdd = async (values: any) => {
    try {
      if (editingMember) {
        const { member_id: _ignored, ...rest } = values
        await auditTeamApi.update(editingMember.id, rest)
        message.success('成员信息已更新')
      } else {
        await auditTeamApi.add(projectId, { ...values, project_id: projectId })
        message.success('添加成员成功')
      }
      setModalVisible(false)
      setEditingMember(null)
      form.resetFields()
      fetchMembers()
    } catch (error: any) {
      const detail = error.response?.data?.detail || error.response?.data?.message
      message.error(typeof detail === 'string' ? detail : editingMember ? '更新失败' : '添加成员失败')
    }
  }

  const openAdd = () => {
    setEditingMember(null)
    form.resetFields()
    setModalVisible(true)
  }

  const openEdit = (record: TeamMember) => {
    setEditingMember(record)
    form.resetFields()
    form.setFieldsValue({
      member_id: record.member_id,
      role: record.role,
      responsible_systems: record.responsible_systems || [],
      qualification_codes: record.qualification_codes || [],
    })
    setModalVisible(true)
  }

  const handleRemove = (id: string) => {
    Modal.confirm({
      title: '确认移除',
      content: '确定要移除这个审核组成员吗？',
      okText: '确定',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        try {
          await auditTeamApi.remove(id)
          message.success('移除成功')
          fetchMembers()
        } catch (error: any) {
          message.error(error.response?.data?.message || '移除失败')
        }
      },
    })
  }

  const getMemberName = (memberId: string) => {
    const member = members.find((m) => m.member_id === memberId)
    if (member?.member_name || member?.member_username) {
      return member.member_name || member.member_username
    }
    const user = users.find((u) => u.id === memberId)
    return user ? `${user.full_name || user.username}` : memberId
  }

  const columns: ColumnsType<TeamMember> = [
    {
      title: '成员姓名',
      key: 'member_name',
      width: 200,
      ellipsis: true,
      render: (_, record) => record.member_name || record.member_username || getMemberName(record.member_id),
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 120,
      render: (role: string) => roleMap[role] || role,
    },
    {
      title: '负责体系',
      dataIndex: 'responsible_systems',
      key: 'responsible_systems',
      width: 150,
      render: (systems: string[]) => (
        <Space size={4}>
          {systems?.map((sys) => (
            <Tag key={sys}>{sys}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '专业代码',
      dataIndex: 'qualification_codes',
      key: 'qualification_codes',
      width: 150,
      render: (codes: string[]) => codes?.join(', ') || '-',
    },
    {
      title: '注册编号',
      dataIndex: 'registration_no',
      key: 'registration_no',
      width: 180,
      ellipsis: true,
    },
    {
      title: '注册级别',
      dataIndex: 'registration_level',
      key: 'registration_level',
      width: 120,
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      fixed: 'right',
      render: (_, record) => canManage ? (
        <Space size={0}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Button
            type="link"
            danger
            size="small"
            icon={<DeleteOutlined />}
            onClick={() => handleRemove(record.id)}
          >
            移除
          </Button>
        </Space>
      ) : null,
    },
  ]

  return (
    <>
      {canManage && <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
          添加成员
        </Button>
      </div>}

      <Table
        columns={columns}
        dataSource={members}
        rowKey="id"
        loading={loading}
        pagination={false}
        scroll={{ x: 1000 }}
      />

      <Modal
        title={editingMember ? `编辑成员：${editingMember.member_name || editingMember.member_username || ''}` : '添加审核组成员'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          setEditingMember(null)
          form.resetFields()
        }}
        onOk={() => form.submit()}
        okText={editingMember ? '保存' : '添加'}
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={handleAdd}>
          <Form.Item
            label="选择成员"
            name="member_id"
            rules={[{ required: true, message: '请选择成员' }]}
          >
            <Select
              placeholder="请选择审核员"
              disabled={!!editingMember}
              showSearch
              optionFilterProp="children"
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={[
                ...users.map((u) => ({
                  label: `${u.full_name || u.username} (${u.username})`,
                  value: u.id,
                })),
                // 编辑时当前成员可能不在可选列表中（已入组），补一项用于显示姓名
                ...(editingMember && !users.some((u) => u.id === editingMember.member_id)
                  ? [{ label: editingMember.member_name || editingMember.member_username || '当前成员', value: editingMember.member_id }]
                  : []),
              ]}
            />
          </Form.Item>

          <Form.Item
            label="角色"
            name="role"
            rules={[{ required: true, message: '请选择角色' }]}
            initialValue="member"
          >
            <Select>
              <Select.Option value="leader">组长</Select.Option>
              <Select.Option value="member">组员</Select.Option>
              <Select.Option value="trainee">被验证审核员</Select.Option>
              <Select.Option value="observer">观察员</Select.Option>
              <Select.Option value="expert">技术专家</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="负责体系"
            name="responsible_systems"
            rules={[{ required: true, message: '请选择负责体系' }]}
          >
            <Select mode="multiple" placeholder="请选择负责的认证体系">
              <Select.Option value="Q">Q - 质量</Select.Option>
              <Select.Option value="E">E - 环境</Select.Option>
              <Select.Option value="S">S - 职业健康安全</Select.Option>
              <Select.Option value="En">En - 能源</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item label="专业代码" name="qualification_codes">
            <Select mode="tags" placeholder="请输入专业代码，如 10.01">
              <Select.Option value="10.01">10.01</Select.Option>
              <Select.Option value="12.01">12.01</Select.Option>
              <Select.Option value="15.01">15.01</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
