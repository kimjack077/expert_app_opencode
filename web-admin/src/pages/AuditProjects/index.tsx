import { useState, useEffect } from 'react'
import {
  Card, Table, Button, Space, Tag, message, Modal, Dropdown, Input, Select, Tooltip,
} from 'antd'
import {
  PlusOutlined, EyeOutlined, EditOutlined, DeleteOutlined, MoreOutlined, SearchOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { auditProjectApi } from '@/services/auditProjectApi'
import { auditTypeLabel, projectStatusMeta } from '@/utils/display'
import type { ColumnsType } from 'antd/es/table'

interface AuditProject {
  id: string
  project_no: string
  title: string
  enterprise_id: string
  audit_type: string
  certification_systems: string[]
  status: string
  scheduled_start: string
  scheduled_end: string
  audit_days: number
  created_at: string
}

const AUDIT_TYPE_OPTIONS = [
  { value: 'initial', label: '初审' },
  { value: 'surveillance', label: '监督' },
  { value: 'recertification', label: '再认证' },
  { value: 'expansion', label: '扩项' },
]

const STATUS_OPTIONS = [
  { value: 'planning', label: '策划中' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'cancelled', label: '已取消' },
]

const EMPTY_FILTERS = {
  status: undefined as string | undefined,
  audit_type: undefined as string | undefined,
  keyword: '',
}

export default function AuditProjects() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [projects, setProjects] = useState<AuditProject[]>([])
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 })
  // 筛选条件与「已提交」的筛选分开：输入框改的是 draft，点查询才生效，
  // 避免每敲一个字都打一次接口。
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS })
  const [draftFilters, setDraftFilters] = useState({ ...EMPTY_FILTERS })

  useEffect(() => {
    fetchProjects()
  }, [pagination.current, pagination.pageSize, filters])

  const fetchProjects = async () => {
    setLoading(true)
    try {
      const response = await auditProjectApi.list({
        skip: (pagination.current - 1) * pagination.pageSize,
        limit: pagination.pageSize,
        ...(filters.status ? { status: filters.status } : {}),
        ...(filters.audit_type ? { audit_type: filters.audit_type } : {}),
        ...(filters.keyword.trim() ? { keyword: filters.keyword.trim() } : {}),
      })
      // 后端已返回 { items, total }；total 是过滤后的真实总数，分页器不再用当页条数凑
      const data = response.data || {}
      setProjects(Array.isArray(data) ? data : data.items || [])
      setPagination((prev) => ({
        ...prev,
        total: Array.isArray(data) ? data.length : data.total || 0,
      }))
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取审核项目列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    setPagination((prev) => ({ ...prev, current: 1 }))
    setFilters({ ...draftFilters })
  }

  const handleReset = () => {
    setDraftFilters({ ...EMPTY_FILTERS })
    setFilters({ ...EMPTY_FILTERS })
    setPagination((prev) => ({ ...prev, current: 1 }))
  }

  const handleDelete = (id: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个审核项目吗？此操作不可恢复。',
      okText: '确定',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        try {
          await auditProjectApi.delete(id)
          message.success('删除成功')
          fetchProjects()
        } catch (error: any) {
          message.error(error.response?.data?.message || '删除失败')
        }
      },
    })
  }

  const columns: ColumnsType<AuditProject> = [
    {
      title: '项目编号',
      dataIndex: 'project_no',
      key: 'project_no',
      width: 180,
    },
    {
      title: '项目名称',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '审核类型',
      dataIndex: 'audit_type',
      key: 'audit_type',
      width: 100,
      render: (type: string) => (
        <Tag color={type === 'initial' ? 'blue' : type === 'surveillance' ? 'green' : type === 'recertification' ? 'orange' : 'purple'}>
          {auditTypeLabel(type)}
        </Tag>
      ),
    },
    {
      title: '认证体系',
      dataIndex: 'certification_systems',
      key: 'certification_systems',
      width: 180,
      render: (systems: string[]) => (
        <Space size={4} style={{ whiteSpace: 'nowrap' }}>
          {systems?.map((sys) => (
            <Tag key={sys} style={{ whiteSpace: 'nowrap' }}>{sys}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '审核工作量（人天）',
      dataIndex: 'audit_days',
      key: 'audit_days',
      width: 100,
      render: (days: number) => `${days || 0} 天`,
    },
    {
      title: '计划时间',
      key: 'schedule',
      width: 200,
      render: (_, record) => {
        if (!record.scheduled_start) return '-'
        const start = new Date(record.scheduled_start).toLocaleDateString()
        const end = record.scheduled_end ? new Date(record.scheduled_end).toLocaleDateString() : ''
        return `${start} ~ ${end}`
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      // 悬停显示该状态的含义，避免用户看不懂「策划中 / 进行中」到底代表什么
      render: (status: string) => {
        const meta = projectStatusMeta(status)
        return (
          <Tooltip title={meta.desc}>
            <Tag color={meta.color} style={{ whiteSpace: 'nowrap', cursor: 'help' }}>
              {meta.text}
            </Tag>
          </Tooltip>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/audit-projects/${record.id}`)}
          >
            查看
          </Button>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'edit',
                  label: '编辑',
                  icon: <EditOutlined />,
                  onClick: () => navigate(`/audit-projects/${record.id}/edit`),
                },
                {
                  key: 'delete',
                  label: '删除',
                  icon: <DeleteOutlined />,
                  danger: true,
                  onClick: () => handleDelete(record.id),
                },
              ],
            }}
          >
            <Button type="link" size="small" icon={<MoreOutlined />} />
          </Dropdown>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title="审核项目管理"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/audit-projects/create')}
          >
            创建审核项目
          </Button>
        }
      >
        {/* 查询条件：状态 / 审核类型 / 编号或名称关键字 */}
        <Space wrap style={{ marginBottom: 16 }}>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="项目编号 / 项目名称"
            style={{ width: 220 }}
            value={draftFilters.keyword}
            onChange={(e) => setDraftFilters((prev) => ({ ...prev, keyword: e.target.value }))}
            onPressEnter={handleSearch}
          />
          <Select
            placeholder="项目状态"
            allowClear
            style={{ width: 140 }}
            value={draftFilters.status}
            onChange={(value) => setDraftFilters((prev) => ({ ...prev, status: value }))}
            options={STATUS_OPTIONS}
          />
          <Select
            placeholder="审核类型"
            allowClear
            style={{ width: 140 }}
            value={draftFilters.audit_type}
            onChange={(value) => setDraftFilters((prev) => ({ ...prev, audit_type: value }))}
            options={AUDIT_TYPE_OPTIONS}
          />
          <Button type="primary" onClick={handleSearch}>
            查询
          </Button>
          <Button onClick={handleReset}>重置</Button>
        </Space>

        <Table
          columns={columns}
          dataSource={projects}
          rowKey="id"
          loading={loading}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
          }}
          onChange={(newPagination) => {
            setPagination({
              current: newPagination.current || 1,
              pageSize: newPagination.pageSize || 10,
              total: pagination.total,
            })
          }}
          scroll={{ x: 1200 }}
        />
      </Card>
    </div>
  )
}
