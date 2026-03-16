import { useState, useEffect } from 'react'
import { Card, Table, Button, Modal, Form, Input, Select, DatePicker, message, Space, Tag } from 'antd'
import { PlusOutlined, EyeOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { taskApi, templateApi, authApi } from '@/services/api'
import dayjs from 'dayjs'

const { TextArea } = Input

export default function Tasks() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<any[]>([])
  const [templates, setTemplates] = useState<any[]>([])
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [form] = Form.useForm()
  const [statusFilter, setStatusFilter] = useState<string | null>(null)

  useEffect(() => {
    fetchTasks()
    fetchTemplates()
    fetchUsers()
  }, [statusFilter])

  const fetchUsers = async () => {
    try {
      // 获取专家用户列表用于分配任务
      const res: any = await authApi.getMe()
      // 暂时使用当前用户，后续可以添加获取用户列表的API
      setUsers([
        { id: res.data?.id, username: res.data?.username, real_name: res.data?.real_name || res.data?.username }
      ])
    } catch (error) {
      console.error('Failed to fetch users:', error)
    }
  }

  const fetchTasks = async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (statusFilter) params.status = statusFilter
      const res: any = await taskApi.getTasks(params)
      setTasks(res.data?.items || res.data || [])
    } catch (error) {
      console.error('Failed to fetch tasks:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchTemplates = async () => {
    try {
      const res: any = await templateApi.getTemplates({ is_published: true })
      setTemplates(res.data || [])
    } catch (error) {
      console.error('Failed to fetch templates:', error)
    }
  }

  const handleCreate = async (values: any) => {
    try {
      const data = {
        ...values,
        scheduled_at: values.scheduled_at?.toISOString(),
      }
      await taskApi.createTask(data)
      message.success('任务创建成功')
      setModalVisible(false)
      form.resetFields()
      fetchTasks()
    } catch (error) {
      message.error('创建失败')
    }
  }

  const handleStart = async (id: string) => {
    try {
      await taskApi.startTask(id)
      message.success('任务已开始')
      fetchTasks()
    } catch (error) {
      message.error('操作失败')
    }
  }

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      pending: { color: 'default', text: '待开始' },
      in_progress: { color: 'processing', text: '进行中' },
      completed: { color: 'success', text: '已完成' },
      cancelled: { color: 'error', text: '已取消' },
    }
    const item = statusMap[status] || { color: 'default', text: status }
    return <Tag color={item.color}>{item.text}</Tag>
  }

  const columns = [
    { title: '任务编号', dataIndex: 'task_no', key: 'task_no', width: 180 },
    { title: '任务标题', dataIndex: 'title', key: 'title' },
    { title: '被检查对象', dataIndex: 'target_name', key: 'target_name' },
    { title: '检查地址', dataIndex: 'target_address', key: 'target_address', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '计划时间',
      dataIndex: 'scheduled_at',
      key: 'scheduled_at',
      render: (date: string) => (date ? dayjs(date).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: any) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/tasks/${record.id}`)}
          >
            详情
          </Button>
          {record.status === 'pending' && (
            <Button
              type="link"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => navigate(`/inspection/${record.id}`)}
            >
              开始检查
            </Button>
          )}
          {record.status === 'in_progress' && (
            <Button
              type="link"
              size="small"
              onClick={() => navigate(`/inspection/${record.id}`)}
            >
              继续检查
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 className="page-title">检查任务管理</h1>
        <Space>
          <Select
            placeholder="状态筛选"
            allowClear
            style={{ width: 120 }}
            onChange={(value) => setStatusFilter(value)}
            options={[
              { value: 'pending', label: '待开始' },
              { value: 'in_progress', label: '进行中' },
              { value: 'completed', label: '已完成' },
            ]}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
            新建任务
          </Button>
        </Space>
      </div>

      <Card>
        <Table
          dataSource={tasks}
          columns={columns}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1000 }}
        />
      </Card>

      <Modal
        title="新建检查任务"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="title" label="任务标题" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="template_id" label="检查模板" rules={[{ required: true }]}>
            <Select
              placeholder="选择检查模板"
              options={templates.map((t) => ({ value: t.id, label: t.name }))}
            />
          </Form.Item>
          <Form.Item name="assigned_to" label="分配给">
            <Select
              placeholder="选择检查人员"
              allowClear
              options={users.map((u) => ({ value: u.id, label: u.real_name || u.username }))}
            />
          </Form.Item>
          <Form.Item name="target_name" label="被检查对象">
            <Input />
          </Form.Item>
          <Form.Item name="target_address" label="检查地址">
            <Input />
          </Form.Item>
          <Form.Item name="target_contact" label="联系人">
            <Input />
          </Form.Item>
          <Form.Item name="target_phone" label="联系电话">
            <Input />
          </Form.Item>
          <Form.Item name="scheduled_at" label="计划时间">
            <DatePicker showTime style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="remarks" label="备注">
            <TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
