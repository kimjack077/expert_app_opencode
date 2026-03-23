import { useState, useEffect } from 'react'
import { Card, Table, Tag, Button, Space, message, Input, Select, Badge, Tooltip, Empty, Spin } from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  ClockCircleOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  CalendarOutlined,
  TeamOutlined,
  SafetyCertificateOutlined,
  RightOutlined,
} from '@ant-design/icons'
import { myTasksApi, auditPlanApi } from '@/services/auditProjectApi'
import dayjs from 'dayjs'

interface AuditTask {
  id: string
  project_id: string
  project_no: string
  project_title: string
  enterprise_name: string
  area_name: string
  area_id: string
  group_no: string
  plan_date: string
  time_start: string
  time_end: string
  status: 'pending' | 'in_progress' | 'completed'
  certification_systems: string[]
  template_id?: string
  record_id?: string
}

const statusConfig: Record<string, { text: string; color: string; icon: React.ReactNode }> = {
  pending: { text: '待开始', color: 'default', icon: <ClockCircleOutlined /> },
  in_progress: { text: '进行中', color: 'processing', icon: <PlayCircleOutlined /> },
  completed: { text: '已完成', color: 'success', icon: <CheckCircleOutlined /> },
}

const systemColors: Record<string, string> = {
  'Q': '#3B82F6',
  'E': '#10B981',
  'S': '#F59E0B',
  'En': '#8B5CF6',
}

const systemNames: Record<string, string> = {
  'Q': '质量',
  'E': '环境',
  'S': '职业健康安全',
  'En': '能源',
}

export default function MyAuditTasks() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [tasks, setTasks] = useState<AuditTask[]>([])
  const [searchText, setSearchText] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)

  useEffect(() => {
    fetchTasks()
  }, [])

  const fetchTasks = async () => {
    setLoading(true)
    try {
      const response = await myTasksApi.list()
      setTasks(response.data || [])
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取任务列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleStartTask = async (task: AuditTask) => {
    try {
      // 如果任务还没有开始，更新状态
      if (task.status === 'pending') {
        await auditPlanApi.update(task.id, { status: 'in_progress' })
      }
      // 跳转到审核记录填写页面
      navigate(`/audit-projects/${task.project_id}/records/new?planItemId=${task.id}`)
    } catch (error: any) {
      message.error(error.response?.data?.message || '操作失败')
    }
  }

  const handleContinueTask = (task: AuditTask) => {
    if (task.record_id) {
      // 如果已有记录，跳转到记录详情
      navigate(`/audit-projects/${task.project_id}/records/${task.record_id}`)
    } else {
      // 否则跳转到创建记录页面
      navigate(`/audit-projects/${task.project_id}/records/new?planItemId=${task.id}`)
    }
  }

  // 过滤任务
  const filteredTasks = tasks.filter(task => {
    const matchSearch = !searchText ||
      task.project_title?.toLowerCase().includes(searchText.toLowerCase()) ||
      task.enterprise_name?.toLowerCase().includes(searchText.toLowerCase()) ||
      task.area_name?.toLowerCase().includes(searchText.toLowerCase())
    const matchStatus = !statusFilter || task.status === statusFilter
    return matchSearch && matchStatus
  })

  // 统计数据
  const stats = {
    total: tasks.length,
    pending: tasks.filter(t => t.status === 'pending').length,
    inProgress: tasks.filter(t => t.status === 'in_progress').length,
    completed: tasks.filter(t => t.status === 'completed').length,
  }

  const columns = [
    {
      title: '项目信息',
      key: 'project',
      width: 280,
      render: (_: any, record: AuditTask) => (
        <div>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>
            {record.project_title || record.project_no}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {record.enterprise_name}
          </div>
        </div>
      ),
    },
    {
      title: '审核区域',
      dataIndex: 'area_name',
      key: 'area_name',
      width: 180,
      render: (text: string, record: AuditTask) => (
        <div>
          <div>{text}</div>
          {record.area_id && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              区域编号: {record.area_id}
            </div>
          )}
        </div>
      ),
    },
    {
      title: '工作组',
      dataIndex: 'group_no',
      key: 'group_no',
      width: 80,
      render: (text: string) => (
        <Tag icon={<TeamOutlined />} color="blue">{text || '默认'}</Tag>
      ),
    },
    {
      title: '审核日期',
      key: 'schedule',
      width: 180,
      render: (_: any, record: AuditTask) => (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
            <CalendarOutlined style={{ color: 'var(--primary-color)' }} />
            <span>{record.plan_date}</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {record.time_start} - {record.time_end}
          </div>
        </div>
      ),
    },
    {
      title: '认证体系',
      dataIndex: 'certification_systems',
      key: 'certification_systems',
      width: 160,
      render: (systems: string[]) => (
        <Space size={4} wrap>
          {systems?.map(sys => (
            <Tooltip key={sys} title={systemNames[sys] || sys}>
              <Tag
                style={{
                  background: systemColors[sys] || 'var(--primary-color)',
                  color: 'white',
                  border: 'none',
                  borderRadius: 4,
                }}
              >
                {sys}
              </Tag>
            </Tooltip>
          ))}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const config = statusConfig[status] || { text: status, color: 'default', icon: null }
        return (
          <Tag icon={config.icon} color={config.color}>
            {config.text}
          </Tag>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: AuditTask) => (
        <Space>
          {record.status === 'pending' && (
            <Button
              type="primary"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => handleStartTask(record)}
            >
              开始
            </Button>
          )}
          {record.status === 'in_progress' && (
            <Button
              type="primary"
              size="small"
              ghost
              onClick={() => handleContinueTask(record)}
            >
              继续
            </Button>
          )}
          {record.status === 'completed' && (
            <Button
              type="link"
              size="small"
              onClick={() => navigate(`/audit-projects/${record.project_id}`)}
            >
              查看详情
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <h1 className="page-title">我的审核任务</h1>
          <p style={{ color: 'var(--text-muted)', marginTop: 4 }}>
            查看和管理分配给您的审核任务
          </p>
        </div>
      </div>

      {/* 统计卡片 */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24 }}>
        <Card
          bordered={false}
          style={{ flex: 1, background: 'linear-gradient(135deg, rgba(100, 116, 139, 0.1) 0%, rgba(100, 116, 139, 0.05) 100%)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 48,
              height: 48,
              background: 'var(--primary-color)',
              borderRadius: 12,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <SafetyCertificateOutlined style={{ fontSize: 24, color: 'white' }} />
            </div>
            <div>
              <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--primary-color)' }}>
                {stats.total}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>总任务数</div>
            </div>
          </div>
        </Card>

        <Card
          bordered={false}
          style={{ flex: 1, background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 48,
              height: 48,
              background: '#F59E0B',
              borderRadius: 12,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <ClockCircleOutlined style={{ fontSize: 24, color: 'white' }} />
            </div>
            <div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#F59E0B' }}>
                {stats.pending}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>待开始</div>
            </div>
          </div>
        </Card>

        <Card
          bordered={false}
          style={{ flex: 1, background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 48,
              height: 48,
              background: '#3B82F6',
              borderRadius: 12,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <PlayCircleOutlined style={{ fontSize: 24, color: 'white' }} />
            </div>
            <div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#3B82F6' }}>
                {stats.inProgress}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>进行中</div>
            </div>
          </div>
        </Card>

        <Card
          bordered={false}
          style={{ flex: 1, background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(16, 185, 129, 0.05) 100%)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 48,
              height: 48,
              background: '#10B981',
              borderRadius: 12,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <CheckCircleOutlined style={{ fontSize: 24, color: 'white' }} />
            </div>
            <div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#10B981' }}>
                {stats.completed}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>已完成</div>
            </div>
          </div>
        </Card>
      </div>

      {/* 筛选区 */}
      <Card bordered={false} style={{ marginBottom: 16 }}>
        <Space size="middle">
          <Input.Search
            placeholder="搜索项目名称、企业名称、审核区域..."
            allowClear
            style={{ width: 300 }}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
          <Select
            placeholder="筛选状态"
            allowClear
            style={{ width: 150 }}
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'pending', label: '待开始' },
              { value: 'in_progress', label: '进行中' },
              { value: 'completed', label: '已完成' },
            ]}
          />
        </Space>
      </Card>

      {/* 任务列表 */}
      <Card bordered={false}>
        <Table
          columns={columns}
          dataSource={filteredTasks}
          rowKey="id"
          loading={loading}
          pagination={{
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条记录`,
          }}
          locale={{
            emptyText: (
              <Empty
                description="暂无审核任务"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ),
          }}
        />
      </Card>
    </div>
  )
}