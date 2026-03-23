import { useState, useEffect } from 'react'
import { Table, Tag, Button, Space, message, Modal, Form, DatePicker, Select } from 'antd'
import { EyeOutlined, PlusOutlined, EditOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { auditRecordApi, auditPlanApi } from '@/services/auditProjectApi'
import { templateApi } from '@/services/api'

interface Props {
  projectId: string
}

export default function RecordsList({ projectId }: Props) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState<any[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [planItems, setPlanItems] = useState<any[]>([])
  const [templates, setTemplates] = useState<any[]>([])
  const [form] = Form.useForm()

  useEffect(() => {
    fetchRecords()
    fetchPlanItems()
    fetchTemplates()
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

  const fetchPlanItems = async () => {
    try {
      const response = await auditPlanApi.list(projectId)
      setPlanItems(response.data || [])
    } catch (error: any) {
      console.error('获取审核计划失败:', error)
    }
  }

  const fetchTemplates = async () => {
    try {
      const response = await templateApi.getTemplates({ limit: 100 })
      setTemplates(response.data?.items || response.data || [])
    } catch (error: any) {
      console.error('获取模板失败:', error)
    }
  }

  const handleCreateRecord = () => {
    navigate(`/audit-projects/${projectId}/records/new`)
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

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateRecord}>
          创建审核记录
        </Button>
      </div>
      <Table columns={columns} dataSource={records} rowKey="id" loading={loading} />
    </>
  )
}
