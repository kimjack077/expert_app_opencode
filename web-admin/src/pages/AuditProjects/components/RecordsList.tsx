import { useState, useEffect } from 'react'
import { Table, Tag, Button, Space, message } from 'antd'
import { EyeOutlined } from '@ant-design/icons'
import { auditRecordApi } from '@/services/auditProjectApi'
import RecordDetail from './RecordDetail'

interface Props {
  projectId: string
}

export default function RecordsList({ projectId }: Props) {
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState<any[]>([])
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null)

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

  const handleViewRecord = (recordId: string) => {
    setSelectedRecordId(recordId)
  }

  const columns = [
    { title: '记录编号', dataIndex: 'record_no', key: 'record_no', width: 180 },
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
        return <Tag color={colorMap[status]}>{status}</Tag>
      }
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: any) => (
        <Space>
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

  return (
    <>
      <Table columns={columns} dataSource={records} rowKey="id" loading={loading} />
      
      {selectedRecordId && (
        <RecordDetail
          recordId={selectedRecordId}
          projectId={projectId}
          onClose={() => setSelectedRecordId(null)}
          onRefresh={fetchRecords}
        />
      )}
    </>
  )
}
