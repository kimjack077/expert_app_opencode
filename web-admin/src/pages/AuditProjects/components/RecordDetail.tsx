import { useState, useEffect } from 'react'
import { Card, Form, Input, Button, Space, message, Modal, Spin, Descriptions, Tag, Drawer } from 'antd'
import { RobotOutlined, SaveOutlined } from '@ant-design/icons'
import { auditRecordApi, auditAIApi } from '@/services/auditProjectApi'

interface Props {
  recordId: string
  projectId: string
  onClose: () => void
  onRefresh: () => void
}

export default function RecordDetail({ recordId, projectId, onClose, onRefresh }: Props) {
  const [loading, setLoading] = useState(false)
  const [record, setRecord] = useState<any>(null)
  const [form] = Form.useForm()
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResult, setAiResult] = useState<any>(null)
  const [aiModalVisible, setAiModalVisible] = useState(false)

  useEffect(() => {
    if (recordId) {
      fetchRecord()
    }
  }, [recordId])

  const fetchRecord = async () => {
    setLoading(true)
    try {
      const response = await auditRecordApi.get(recordId)
      setRecord(response.data)
      form.setFieldsValue(response.data)
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取记录失败')
    } finally {
      setLoading(false)
    }
  }

  const handleAIEvaluate = async () => {
    const conclusion = form.getFieldValue('conclusion')
    
    if (!conclusion || conclusion.length < 10) {
      message.warning('请先填写审核结论（至少10个字符）')
      return
    }

    const clauseNo = record?.items?.find((item: any) => item?.clause_no_snapshot)?.clause_no_snapshot
      || record?.plan_item?.clauses?.[0]
    if (!clauseNo) {
      message.warning('当前区域记录未关联审核条款，无法进行 AI 证据评估')
      return
    }

    setAiModalVisible(true)
    setAiLoading(true)
    setAiResult(null)

    try {
      const response = await auditAIApi.evaluateEvidence(projectId, {
        evidence: conclusion,
        clause_no: clauseNo,
        certification_system: record?.certification_systems?.[0] || 'ISO 9001',
      })
      
      setAiResult(response.data)
    } catch (error: any) {
      message.error(error.response?.data?.message || 'AI 评估失败')
      setAiModalVisible(false)
    } finally {
      setAiLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      await auditRecordApi.update(recordId, values)
      message.success('记录已保存')
      onRefresh()
    } catch (error: any) {
      message.error(error.response?.data?.message || '保存失败')
    }
  }

  if (loading) {
    return <Spin />
  }

  if (!record) {
    return <div>记录不存在</div>
  }

  return (
    <Drawer
      title="审核记录详情"
      placement="right"
      onClose={onClose}
      width={800}
      open={true}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Card title="基本信息" size="small">
          <Descriptions column={2} size="small">
            <Descriptions.Item label="记录编号">{record.record_no}</Descriptions.Item>
            <Descriptions.Item label="审核日期">{record.audit_date}</Descriptions.Item>
            <Descriptions.Item label="审核时间">
              {record.audit_time_start} - {record.audit_time_end}
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag>{record.status}</Tag>
            </Descriptions.Item>
          </Descriptions>
        </Card>

        <Card title="审核结论" size="small">
          <Form form={form} layout="vertical">
            <Form.Item
              label="审核结论"
              name="conclusion"
              rules={[
                { required: true, message: '请输入审核结论' },
                { min: 10, message: '审核结论至少10个字符' }
              ]}
            >
              <Input.TextArea rows={4} placeholder="描述审核发现的主要情况" />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  onClick={handleSave}
                >
                  保存
                </Button>
                <Button
                  type="dashed"
                  icon={<RobotOutlined />}
                  onClick={handleAIEvaluate}
                  loading={aiLoading}
                >
                  AI 智能评估
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      </Space>

      <Modal
        title="AI 证据评估结果"
        open={aiModalVisible}
        onCancel={() => setAiModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setAiModalVisible(false)}>
            关闭
          </Button>,
        ]}
        width={600}
      >
        {aiLoading ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16 }}>AI 正在评估中...</div>
          </div>
        ) : aiResult ? (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Card title="证据充分性" size="small">
              <Tag color={aiResult.is_sufficient ? 'green' : 'red'}>
                {aiResult.is_sufficient ? '充分' : '不充分'}
              </Tag>
            </Card>
            <Card title="建议评级" size="small">
              <Tag color="blue">
                {aiResult.suggested_evaluation === '1' ? '符合' : 
                 aiResult.suggested_evaluation === '2' ? '基本符合' : '不符合'}
              </Tag>
            </Card>
            <Card title="评估理由" size="small">
              {aiResult.reasoning}
            </Card>
            {aiResult.additional_evidence_needed && (
              <Card title="建议补充证据" size="small">
                {aiResult.additional_evidence_needed}
              </Card>
            )}
          </Space>
        ) : null}
      </Modal>
    </Drawer>
  )
}
