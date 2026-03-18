import { useState, useEffect } from 'react'
import { Table, Tag, Button, Space, message, Modal, Form, Input, Select, DatePicker } from 'antd'
import { PlusOutlined, RobotOutlined } from '@ant-design/icons'
import { nonconformityApi, auditAIApi } from '@/services/auditProjectApi'
import dayjs from 'dayjs'

interface Props {
  projectId: string
}

export default function NonconformitiesList({ projectId }: Props) {
  const [loading, setLoading] = useState(false)
  const [nonconformities, setNonconformities] = useState<any[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    fetchNonconformities()
  }, [projectId])

  const fetchNonconformities = async () => {
    setLoading(true)
    try {
      const response = await nonconformityApi.list(projectId)
      setNonconformities(response.data || [])
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取不符合项失败')
    } finally {
      setLoading(false)
    }
  }

  const handleAISuggest = async () => {
    const evidence = form.getFieldValue('evidence')
    const clauseNo = form.getFieldValue('clause_no')
    const certificationSystem = form.getFieldValue('certification_system')

    if (!evidence || !clauseNo || !certificationSystem) {
      message.warning('请先填写证据、条款号和认证体系')
      return
    }

    setAiLoading(true)
    try {
      const response = await auditAIApi.suggestNC(projectId, {
        evidence,
        clause_no: clauseNo,
        certification_system: certificationSystem,
      })
      const suggestion = response.data
      
      form.setFieldsValue({
        description: suggestion.description,
        severity: suggestion.severity,
        corrective_action_required: suggestion.corrective_action_required,
      })
      
      message.success('AI 建议已应用')
    } catch (error: any) {
      message.error(error.response?.data?.message || 'AI 建议失败')
    } finally {
      setAiLoading(false)
    }
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      await nonconformityApi.create(projectId, values)
      message.success('不符合项创建成功')
      setModalVisible(false)
      form.resetFields()
      fetchNonconformities()
    } catch (error: any) {
      message.error(error.response?.data?.message || '创建失败')
    }
  }

  const columns = [
    { title: '编号', dataIndex: 'nc_no', key: 'nc_no', width: 150 },
    { 
      title: '严重程度', 
      dataIndex: 'severity', 
      key: 'severity', 
      width: 100,
      render: (severity: string) => {
        const colorMap: Record<string, string> = {
          major: 'error',
          minor: 'warning',
          observation: 'default',
        }
        return <Tag color={colorMap[severity]}>{severity}</Tag>
      }
    },
    { title: '条款号', dataIndex: 'clause_no', key: 'clause_no', width: 100 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status', 
      width: 100,
      render: (status: string) => <Tag>{status}</Tag>
    },
  ]

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
          创建不符合项
        </Button>
      </div>
      <Table columns={columns} dataSource={nonconformities} rowKey="id" loading={loading} />

      <Modal
        title="创建不符合项"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          form.resetFields()
        }}
        onOk={handleSubmit}
        width={800}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="认证体系"
            name="certification_system"
            rules={[{ required: true, message: '请选择认证体系' }]}
          >
            <Select placeholder="选择认证体系">
              <Select.Option value="ISO 9001">ISO 9001</Select.Option>
              <Select.Option value="ISO 14001">ISO 14001</Select.Option>
              <Select.Option value="ISO 45001">ISO 45001</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="条款号"
            name="clause_no"
            rules={[{ required: true, message: '请输入条款号' }]}
          >
            <Input placeholder="例如：7.1.2" />
          </Form.Item>

          <Form.Item
            label="审核证据"
            name="evidence"
            rules={[{ required: true, message: '请输入审核证据' }]}
          >
            <Input.TextArea rows={4} placeholder="描述审核发现的证据" />
          </Form.Item>

          <Form.Item>
            <Button
              type="dashed"
              icon={<RobotOutlined />}
              onClick={handleAISuggest}
              loading={aiLoading}
              block
            >
              AI 智能建议不符合项
            </Button>
          </Form.Item>

          <Form.Item
            label="不符合项描述"
            name="description"
            rules={[{ required: true, message: '请输入不符合项描述' }]}
          >
            <Input.TextArea rows={4} placeholder="客观、具体、可验证的描述" />
          </Form.Item>

          <Form.Item
            label="严重程度"
            name="severity"
            rules={[{ required: true, message: '请选择严重程度' }]}
          >
            <Select placeholder="选择严重程度">
              <Select.Option value="major">严重不符合</Select.Option>
              <Select.Option value="minor">一般不符合</Select.Option>
              <Select.Option value="observation">观察项</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="整改要求"
            name="corrective_action_required"
            rules={[{ required: true, message: '请输入整改要求' }]}
          >
            <Input.TextArea rows={3} placeholder="描述需要采取的整改措施" />
          </Form.Item>

          <Form.Item label="整改期限" name="due_date">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
