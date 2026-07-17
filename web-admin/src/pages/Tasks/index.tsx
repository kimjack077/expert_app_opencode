import { useState, useEffect, useMemo } from 'react'
import { Card, Table, Button, Modal, Form, Input, Select, DatePicker, message, Space, Tag, Popconfirm, Typography } from 'antd'
import { PlusOutlined, EyeOutlined, PlayCircleOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { taskApi, templateApi, userApi } from '@/services/api'
import { formatTaskDisplay } from '@/utils/display'
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
  const [keyword, setKeyword] = useState('')

  useEffect(() => {
    fetchTasks()
    fetchTemplates()
    fetchUsers()
  }, [statusFilter])

  const filteredTasks = useMemo(() => {
    const q = keyword.trim().toLowerCase()
    if (!q) return tasks
    return tasks.filter((t) => {
      const display = formatTaskDisplay(t)
      return (
        String(t.title || '').toLowerCase().includes(q) ||
        String(t.target_name || '').toLowerCase().includes(q) ||
        String(t.task_no || '').toLowerCase().includes(q) ||
        String(display.primary || '').toLowerCase().includes(q) ||
        String(display.secondary || '').toLowerCase().includes(q)
      )
    })
  }, [tasks, keyword])

  const fetchUsers = async () => {
    try {
      const res: any = await userApi.getUsers()
      const userList = res.data || res || []
      setUsers(Array.isArray(userList) ? userList : [])
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

  const handleDelete = async (id: string) => {
    try {
      await taskApi.deleteTask(id)
      message.success('任务已删除')
      fetchTasks()
    } catch (error) {
      message.error('删除失败')
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
    {
      title: '任务',
      key: 'display',
      render: (_: any, record: any) => {
        const d = formatTaskDisplay(record)
        return (
          <div>
            <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{d.primary}</div>
            {d.secondary && (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {d.secondary}
              </Typography.Text>
            )}
            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{record.task_no}</div>
          </div>
        )
      },
    },
    {
      title: '企业/对象',
      dataIndex: 'target_name',
      key: 'target_name',
      width: 160,
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '计划时间',
      dataIndex: 'scheduled_at',
      key: 'scheduled_at',
      width: 150,
      render: (date: string) => (date ? dayjs(date).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 280,
      fixed: 'right' as const,
      render: (_: any, record: any) => (
        <Space wrap>
          {record.status === 'pending' && (
            <Button
              type="primary"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => navigate(`/inspection/${record.id}`)}
            >
              开始检查
            </Button>
          )}
          {record.status === 'in_progress' && (
            <Button
              type="primary"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => navigate(`/inspection/${record.id}`)}
            >
              继续检查
            </Button>
          )}
          {record.status === 'completed' && (
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => navigate(`/inspection/${record.id}`)}
            >
              查看检查
            </Button>
          )}
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/tasks/${record.id}`)}
          >
            详情
          </Button>
          <Popconfirm
            title="确认删除"
            description="确定要删除这个任务吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确认"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 className="page-title">日常检查任务</h1>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            用于模板化日常检查。正式认证审核请使用「审核项目 / 我的审核任务」。
          </Typography.Text>
        </div>
        <Space wrap>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="搜索企业、区域、任务号"
            style={{ width: 220 }}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
          <Select
            placeholder="状态"
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
          dataSource={filteredTasks}
          columns={columns}
          rowKey="id"
          loading={loading}
          scroll={{ x: 900 }}
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
