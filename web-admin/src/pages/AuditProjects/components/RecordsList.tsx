import { useState, useEffect } from 'react'
import { Table, Tag, Button, Space, message, Empty } from 'antd'
import { EyeOutlined, EditOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { auditRecordApi } from '@/services/auditProjectApi'

interface Props {
  projectId: string
}

export default function RecordsList({ projectId }: Props) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState<any[]>([])

  useEffect(() => {
    fetchRecords()
  }, [projectId])

  const fetchRecords = async () => {
    setLoading(true)
    try {
      const response = await auditRecordApi.list(projectId)
      setRecords(response.data || [])
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取审核记录失败')
    } finally {
      setLoading(false)
    }
  }

  const handleEditRecord = (recordId: string) => {
    navigate(`/audit-projects/${projectId}/records/${recordId}`)
  }

  const handleViewRecord = (recordId: string) => {
    navigate(`/audit-projects/${projectId}/records/${recordId}`)
  }

  const columns = [
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
            onClick={() => handleEditRecord(record.id)}
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

  if (records.length === 0 && !loading) {
    return (
      <Empty
        description="暂无审核记录"
        style={{ padding: '40px 0' }}
      >
        <span style={{ color: '#999', fontSize: 13 }}>
          审核记录由审核员在现场检查时自动生成，无需手动创建
        </span>
      </Empty>
    )
  }

  return (
    <Table columns={columns} dataSource={records} rowKey="id" loading={loading} />
  )
}
