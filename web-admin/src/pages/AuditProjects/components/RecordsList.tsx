import { useState, useEffect } from 'react'
import { Table, Tag, Button, Space, message, Empty, Tabs } from 'antd'
import { EyeOutlined, EditOutlined, FileTextOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { auditRecordApi, auditPlanApi } from '@/services/auditProjectApi'
import dayjs from 'dayjs'
import type { TabsProps } from 'antd'

interface Props {
  projectId: string
}

export default function RecordsList({ projectId }: Props) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState<any[]>([])
  const [planItems, setPlanItems] = useState<any[]>([])

  useEffect(() => {
    fetchData()
  }, [projectId])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [recordsRes, planItemsRes] = await Promise.all([
        auditRecordApi.list(projectId),
        auditPlanApi.list(projectId),
      ])
      setRecords(recordsRes.data || [])
      // Filter plan items that have inspection tasks (completed or not)
      const itemsWithTasks = (planItemsRes.data || []).filter(
        (item: any) => item.inspection_task_id
      )
      setPlanItems(itemsWithTasks)
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取审核记录失败')
    } finally {
      setLoading(false)
    }
  }

  const handleViewTask = (taskId: string) => {
    navigate(`/inspection/${taskId}`)
  }

  const handleViewRecord = (recordId: string) => {
    navigate(`/audit-projects/${projectId}/records/${recordId}`)
  }

  const inspectionTaskColumns = [
    { title: '区域名称', dataIndex: 'area_name', key: 'area_name', width: 150 },
    {
      title: '审核日期',
      dataIndex: 'plan_date',
      key: 'plan_date',
      width: 120,
      render: (date: string) => date ? dayjs(date).format('YYYY-MM-DD') : '-',
    },
    { title: '工作组', dataIndex: 'group_no', key: 'group_no', width: 80 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          pending: 'default',
          in_progress: 'processing',
          completed: 'success',
        }
        const textMap: Record<string, string> = {
          pending: '待开始',
          in_progress: '进行中',
          completed: '已完成',
        }
        return <Tag color={colorMap[status]}>{textMap[status] || status}</Tag>
      }
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: any) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={record.status === 'completed' ? <EyeOutlined /> : <EditOutlined />}
            onClick={() => handleViewTask(record.inspection_task_id)}
          >
            {record.status === 'completed' ? '查看检查' : '执行检查'}
          </Button>
          {record.status === 'completed' && (
            <Tag color="success" icon={<CheckCircleOutlined />}>已提交</Tag>
          )}
        </Space>
      ),
    },
  ]

  const auditRecordColumns = [
    { title: '记录编号', dataIndex: 'record_no', key: 'record_no', width: 180 },
    { title: '审核区域', dataIndex: 'area_name', key: 'area_name', width: 150 },
    { title: '审核日期', dataIndex: 'audit_date', key: 'audit_date', width: 120 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          draft: 'default',
          submitted: 'processing',
          reviewed: 'success',
        }
        const textMap: Record<string, string> = {
          draft: '草稿',
          submitted: '已提交',
          reviewed: '已审核',
        }
        return <Tag color={colorMap[status]}>{textMap[status] || status}</Tag>
      }
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: any) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleViewRecord(record.id)}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewRecord(record.id)}
          >
            查看
          </Button>
        </Space>
      ),
    },
  ]

  const hasAnyRecords = records.length > 0 || planItems.length > 0

  if (!hasAnyRecords && !loading) {
    return (
      <Empty
        description="暂无审核记录"
        style={{ padding: '40px 0' }}
      >
        <span style={{ color: '#999', fontSize: 13 }}>
          请先在"审核计划"中添加计划项，然后执行检查任务
        </span>
      </Empty>
    )
  }

  const tabItems: TabsProps['items'] = [
    {
      key: 'inspection_tasks',
      label: (
        <span>
          <FileTextOutlined style={{ marginRight: 8 }} />
          检查任务记录
        </span>
      ),
      children: (
        <Table
          columns={inspectionTaskColumns}
          dataSource={planItems}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{ emptyText: '暂无检查任务' }}
        />
      ),
    },
  ]

  // Only show AuditAreaRecords tab if there are any
  if (records.length > 0) {
    tabItems.push({
      key: 'audit_records',
      label: '正式审核记录',
      children: (
        <Table
          columns={auditRecordColumns}
          dataSource={records}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
      ),
    })
  }

  return <Tabs items={tabItems} />
}
