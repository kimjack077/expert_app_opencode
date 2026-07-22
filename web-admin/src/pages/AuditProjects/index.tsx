import { useState, useEffect } from 'react'
import { Card, Table, Button, Space, Tag, message, Modal, Dropdown } from 'antd'
import { PlusOutlined, EyeOutlined, EditOutlined, DeleteOutlined, MoreOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { auditProjectApi } from '@/services/auditProjectApi'
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

const auditTypeMap: Record<string, { text: string; color: string }> = {
  initial: { text: '初审', color: 'blue' },
  surveillance: { text: '监督', color: 'green' },
  recertification: { text: '再认证', color: 'orange' },
  expansion: { text: '扩项', color: 'purple' },
}

const statusMap: Record<string, { text: string; color: string }> = {
  planning: { text: '策划中', color: 'default' },
  in_progress: { text: '进行中', color: 'processing' },
  completed: { text: '已完成', color: 'success' },
  cancelled: { text: '已取消', color: 'error' },
}

export default function AuditProjects() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [projects, setProjects] = useState<AuditProject[]>([])
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 })

  useEffect(() => {
    fetchProjects()
  }, [pagination.current, pagination.pageSize])

  const fetchProjects = async () => {
    setLoading(true)
    try {
      const response = await auditProjectApi.list({
        skip: (pagination.current - 1) * pagination.pageSize,
        limit: pagination.pageSize,
      })
      setProjects(response.data || [])
      setPagination((prev) => ({ ...prev, total: response.data?.length || 0 }))
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取审核项目列表失败')
    } finally {
      setLoading(false)
    }
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
      render: (type: string) => {
        const config = auditTypeMap[type] || { text: type, color: 'default' }
        return <Tag color={config.color}>{config.text}</Tag>
      },
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
      title: '审核人天',
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
      render: (status: string) => {
        const config = statusMap[status] || { text: status, color: 'default' }
        return <Tag color={config.color} style={{ whiteSpace: 'nowrap' }}>{config.text}</Tag>
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
