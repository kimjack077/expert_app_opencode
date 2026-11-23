import { useState, useEffect } from 'react'
import { Card, Table, Button, Modal, Form, Input, Select, DatePicker, message, Space, Tag, Popconfirm, Typography } from 'antd'
import { PlusOutlined, EyeOutlined, PlayCircleOutlined, ReloadOutlined, DeleteOutlined, SearchOutlined, EditOutlined, StopOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { taskApi, templateApi, userApi } from '@/services/api'
import { formatTaskDisplay } from '@/utils/display'
import dayjs from 'dayjs'
import { useAuthStore } from '@/stores/auth'
import { isAdminRole } from '@/utils/roles'

const { TextArea } = Input

export default function Tasks() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [tasks, setTasks] = useState<any[]>([])
  const [templates, setTemplates] = useState<any[]>([])
  const [users, setUsers] = useState<any[]>([])
  const user = useAuthStore(state => state.user)
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [editingTask, setEditingTask] = useState<any>(null)
  const [form] = Form.useForm()
  // 初值取 URL 的 ?status=：工作台「待办/进行中」卡片是带参数跳进来的，
  // 不解析的话列表不过滤，卡片数字与列表条数就会对不上。
  const [statusFilter, setStatusFilter] = useState<string | null>(
    searchParams.get('status')
  )
  const [keyword, setKeyword] = useState('')
  // 服务端搜索关键词（输入防抖后生效），搜索时重置回第一页
  const [searchKeyword, setSearchKeyword] = useState('')
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 })
  const [total, setTotal] = useState(0)

  /** 切换状态筛选，并把条件同步回 URL，便于分享/刷新保持筛选 */
  const handleStatusChange = (value?: string | null) => {
    const next = value || null
    setStatusFilter(next)
    setPagination((prev) => ({ ...prev, current: 1 }))
    const params = new URLSearchParams(searchParams)
    if (next) params.set('status', next)
    else params.delete('status')
    setSearchParams(params, { replace: true })
  }

  // 下拉数据与列表互不依赖，只在进入页面时拉取一次
  useEffect(() => {
    void Promise.all([fetchTemplates(), fetchUsers()])
  }, [])

  // 关键词防抖后走服务端 search 参数（后端按标题/任务号/检查对象模糊匹配）
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearchKeyword(keyword.trim())
      setPagination((prev) => (prev.current === 1 ? prev : { ...prev, current: 1 }))
    }, 400)
    return () => window.clearTimeout(timer)
  }, [keyword])

  useEffect(() => {
    void fetchTasks()
  }, [statusFilter, searchKeyword, pagination.current, pagination.pageSize])

  const fetchUsers = async () => {
    if (!isAdminRole(user?.role)) return
    try {
      const res: any = await userApi.getUserOptions()
      const userList = res.data || res || []
      setUsers(Array.isArray(userList) ? userList : [])
    } catch (error) {
      console.error('Failed to fetch users:', error)
      message.error('人员列表加载失败，请刷新重试')
    }
  }

  const fetchTasks = async () => {
    setLoading(true)
    try {
      // 服务端分页：page/pageSize → skip/limit，total 用后端返回值
      const params: any = {
        skip: (pagination.current - 1) * pagination.pageSize,
        limit: pagination.pageSize,
      }
      if (statusFilter) params.status = statusFilter
      if (searchKeyword) params.search = searchKeyword
      const res: any = await taskApi.getTasks(params)
      setTasks(res.data?.items || [])
      setTotal(Number(res.data?.total ?? 0))
    } catch (error) {
      console.error('Failed to fetch tasks:', error)
      message.error('任务列表加载失败，请刷新重试')
    } finally {
      setLoading(false)
    }
  }

  const fetchTemplates = async () => {
    try {
      const res: any = await templateApi.getTemplates({ is_published: true, limit: 100 })
      setTemplates(res.data || [])
    } catch (error) {
      console.error('Failed to fetch templates:', error)
      message.error('检查模板加载失败，请刷新重试')
    }
  }

  const errorText = (error: any, fallback: string) => {
    const detail = error?.response?.data?.message || error?.response?.data?.detail
    return typeof detail === 'string' ? detail : fallback
  }

  const openCreate = () => {
    setEditingTask(null)
    form.resetFields()
    setModalVisible(true)
  }

  const openEdit = (record: any) => {
    setEditingTask(record)
    form.resetFields()
    form.setFieldsValue({
      title: record.title,
      template_id: record.template_id,
      assigned_to: record.assigned_to,
      target_name: record.target_name,
      target_address: record.target_address,
      target_contact: record.target_contact,
      target_phone: record.target_phone,
      scheduled_at: record.scheduled_at ? dayjs(record.scheduled_at) : undefined,
      remarks: record.remarks,
    })
    setModalVisible(true)
  }

  const handleCreate = async (values: any) => {
    try {
      const data = {
        ...values,
        scheduled_at: values.scheduled_at?.toISOString(),
      }
      if (editingTask) {
        // 已开始的任务不允许换模板，避免已填报记录与新模板错位
        if (editingTask.status !== 'pending') delete data.template_id
        await taskApi.updateTask(editingTask.id, data)
        message.success('任务已更新')
      } else {
        await taskApi.createTask(data)
        message.success('任务创建成功')
      }
      setModalVisible(false)
      setEditingTask(null)
      form.resetFields()
      fetchTasks()
    } catch (error: any) {
      message.error(errorText(error, editingTask ? '更新失败' : '创建失败'))
    }
  }

  const handleCancelTask = async (id: string) => {
    try {
      await taskApi.cancelTask(id)
      message.success('任务已取消')
      fetchTasks()
    } catch (error) {
      message.error(errorText(error, '取消失败'))
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await taskApi.deleteTask(id)
      message.success('任务已删除')
      fetchTasks()
    } catch (error) {
      message.error(errorText(error, '删除失败'))
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
            {/* 标题做成链接，点击直接进任务详情，与「查看」按钮等效 */}
            <Typography.Link
              strong
              onClick={() => navigate(`/tasks/${record.id}`)}
              style={{ color: 'var(--text-main)' }}
            >
              {d.primary}
            </Typography.Link>
            {d.secondary && (
              <div style={{ marginTop: 2 }}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {d.secondary}
                </Typography.Text>
              </div>
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
      // 此前列表看不到任务派给了谁，必须点进编辑才知道（远程实测发现）
      title: '检查员',
      dataIndex: 'assigned_to',
      key: 'assigned_to',
      width: 110,
      ellipsis: true,
      render: (v: string, record: any) => {
        if (!v) return <Typography.Text type="secondary">未分配</Typography.Text>
        if (user?.id && v === user.id) return '我'
        const u = users.find((x) => x.id === v)
        return u ? u.full_name || u.username : record.assignee_name || '—'
      },
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
      width: 170,
      // 计划时间已过仍未完成的任务标红提示，避免逾期任务混在列表里不被发现
      render: (date: string, record: any) => {
        if (!date) return '-'
        const overdue = ['pending', 'in_progress'].includes(record.status) && dayjs(date).isBefore(dayjs(), 'day')
        return (
          <span style={{ color: overdue ? '#EF4444' : undefined }}>
            {dayjs(date).format('YYYY-MM-DD HH:mm')}
            {overdue && <Tag color="error" style={{ marginLeft: 6 }}>已逾期</Tag>}
          </span>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 340,
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
              onClick={() => navigate(`/tasks/${record.id}`)}
            >
              查看检查结果
            </Button>
          )}
          {record.status !== 'completed' && (
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => navigate(`/tasks/${record.id}`)}
            >
              查看
            </Button>
          )}
          {isAdminRole(user?.role) && ['pending', 'in_progress'].includes(record.status) && (
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
              编辑
            </Button>
          )}
          {['pending', 'in_progress'].includes(record.status) && (
            <Popconfirm
              title="取消任务"
              description={
                record.status === 'in_progress'
                  ? '任务已在进行中，取消后不可再填报，确定取消？'
                  : '确定取消该任务吗？'
              }
              onConfirm={() => handleCancelTask(record.id)}
              okText="确认取消"
              cancelText="再想想"
            >
              <Button type="link" size="small" icon={<StopOutlined />}>
                取消
              </Button>
            </Popconfirm>
          )}
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
            style={{ width: 160 }}
            value={statusFilter}
            onChange={(value) => handleStatusChange(value)}
            options={[
              { value: 'todo', label: '待处理 (全部待办)' },
              { value: 'in_progress', label: '进行中' },
              { value: 'pending', label: '待开始' },
              { value: 'completed', label: '已完成' },
              { value: 'cancelled', label: '已取消' },
            ]}
          />
          <Button icon={<ReloadOutlined />} onClick={() => fetchTasks()} loading={loading}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
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
          scroll={{ x: 1100 }}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
          }}
        />
      </Card>

      <Modal
        title={editingTask ? `编辑任务：${editingTask.task_no || ''}` : '新建检查任务'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          setEditingTask(null)
        }}
        onOk={() => form.submit()}
        okText={editingTask ? '保存' : '创建'}
        cancelText="取消"
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="title" label="任务标题" rules={[{ required: true, message: '请输入任务标题' }]}>
            <Input placeholder="例如：XX 公司季度日常检查" />
          </Form.Item>
          <Form.Item name="template_id" label="检查模板" rules={[{ required: true, message: '请选择检查模板' }]}>
            <Select
              showSearch
              optionFilterProp="label"
              disabled={!!editingTask && editingTask.status !== 'pending'}
              placeholder="选择检查模板"
              options={templates.map((t) => ({ value: t.id, label: t.name }))}
            />
          </Form.Item>
          <Form.Item name="assigned_to" label="分配给">
            <Select
              placeholder="选择检查人员"
              allowClear
              showSearch
              optionFilterProp="label"
              options={users.map((u) => ({ value: u.id, label: u.full_name || u.username }))}
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
            {/* 计划时间精确到分钟，不显示秒列 */}
            <DatePicker showTime format="YYYY-MM-DD HH:mm" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="remarks" label="备注">
            <TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
