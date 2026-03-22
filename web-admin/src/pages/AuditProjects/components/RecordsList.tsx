import { useState, useEffect } from 'react'
import { Table, Tag, Button, Space, message, Modal, Form, DatePicker, Select } from 'antd'
import { EyeOutlined, PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { auditRecordApi, auditPlanApi } from '@/services/auditProjectApi'
import { templateApi } from '@/services/api'
import RecordDetail from './RecordDetail'

interface Props {
  projectId: string
}

export default function RecordsList({ projectId }: Props) {
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState<any[]>([])
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null)
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

  const handleViewRecord = (recordId: string) => {
    setSelectedRecordId(recordId)
  }

  const handleCreateRecord = () => {
    form.resetFields()
    setModalVisible(true)
  }

  const handleSubmit = async (values: any) => {
    try {
      const data = {
        ...values,
        audit_date: values.audit_date?.format('YYYY-MM-DD'),
        certification_systems: values.certification_systems || [],
      }
      await auditRecordApi.create(projectId, data)
      message.success('创建审核记录成功')
      setModalVisible(false)
      form.resetFields()
      fetchRecords()
    } catch (error: any) {
      message.error(error.response?.data?.message || '创建审核记录失败')
    }
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
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateRecord}>
          创建审核记录
        </Button>
      </Space>

      <Table columns={columns} dataSource={records} rowKey="id" loading={loading} />
      
      {selectedRecordId && (
        <RecordDetail
          recordId={selectedRecordId}
          projectId={projectId}
          onClose={() => setSelectedRecordId(null)}
          onRefresh={fetchRecords}
        />
      )}

      <Modal
        title="创建审核记录"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="plan_item_id"
            label="关联审核计划项"
          >
            <Select placeholder="选择关联的审核计划项（可选）" allowClear>
              {planItems.map((item) => (
                <Select.Option key={item.id} value={item.id}>
                  {item.plan_date} - {item.area_name} ({item.group_no})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="template_id"
            label="使用模板"
          >
            <Select placeholder="选择检查模板（可选）" allowClear>
              {templates.filter(t => t.status === 'published').map((t) => (
                <Select.Option key={t.id} value={t.id}>
                  {t.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="audit_date"
            label="审核日期"
            rules={[{ required: true, message: '请选择审核日期' }]}
          >
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="certification_systems"
            label="认证体系"
          >
            <Select mode="multiple" placeholder="选择认证体系">
              <Select.Option value="Q">Q - 质量</Select.Option>
              <Select.Option value="E">E - 环境</Select.Option>
              <Select.Option value="S">S - 职业健康安全</Select.Option>
              <Select.Option value="En">En - 能源</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
