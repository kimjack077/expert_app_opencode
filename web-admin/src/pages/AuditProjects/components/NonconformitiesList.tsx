import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  DatePicker,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'
import { CheckOutlined, EditOutlined, PlusOutlined, RobotOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'

import { nonconformityApi } from '@/services/auditProjectApi'

const { Paragraph, Text } = Typography
const { TextArea } = Input

interface Props {
  projectId: string
}

interface NonconformityItem {
  id: string
  nc_no?: string
  severity?: string
  clause_no?: string
  certification_system?: string
  description?: string
  objective_evidence?: string
  evidence?: string
  analysis_reasoning?: string
  confidence?: number
  status?: string
  source?: string
  ai_generated?: boolean
  corrective_action_required?: string
  due_date?: string
  corrective_action?: string
  correction_date?: string
  verification_result?: string
  verification_photos?: string[]
  created_at?: string
}

const unwrapList = (response: any): NonconformityItem[] => {
  const payload = response?.data ?? response
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.nonconformities)) return payload.nonconformities
  return []
}

const severityConfig: Record<string, { text: string; color: string }> = {
  major: { text: '严重不符合', color: 'error' },
  minor: { text: '一般不符合', color: 'warning' },
  observation: { text: '观察项', color: 'default' },
}

const statusConfig: Record<string, { text: string; color: string }> = {
  draft: { text: 'AI 草稿·待确认', color: 'processing' },
  open: { text: '待整改', color: 'error' },
  pending_rectification: { text: '待整改', color: 'error' },
  pending_verification: { text: '待验证', color: 'warning' },
  corrected: { text: '已整改·待验证', color: 'warning' },
  verified: { text: '已验证·待关闭', color: 'processing' },
  closed: { text: '已关闭', color: 'success' },
  rejected: { text: '已驳回', color: 'default' },
}

export default function NonconformitiesList({ projectId }: Props) {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [confirmingId, setConfirmingId] = useState<string>()
  const [saving, setSaving] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<NonconformityItem>()
  const [nonconformities, setNonconformities] = useState<NonconformityItem[]>([])

  const fetchNonconformities = async () => {
    setLoading(true)
    try {
      const response = await nonconformityApi.list(projectId)
      setNonconformities(unwrapList(response))
    } catch (error: any) {
      message.error(error.response?.data?.detail || error.response?.data?.message || '获取不符合项失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchNonconformities()
  }, [projectId])

  const handleConfirm = async (item: NonconformityItem) => {
    setConfirmingId(item.id)
    try {
      await nonconformityApi.confirm(projectId, item.id)
      message.success('AI 不符合项草稿已确认并进入整改流程')
      await fetchNonconformities()
    } catch (error: any) {
      message.error(error.response?.data?.detail || error.response?.data?.message || '确认不符合项失败')
    } finally {
      setConfirmingId(undefined)
    }
  }

  const showCreate = () => {
    setEditing(undefined)
    form.resetFields()
    form.setFieldsValue({ severity: 'minor', certification_system: 'Q', status: 'open' })
    setModalOpen(true)
  }

  const showEdit = (item: NonconformityItem) => {
    setEditing(item)
    form.setFieldsValue({
      ...item,
      due_date: item.due_date ? dayjs(item.due_date) : undefined,
      correction_date: item.correction_date ? dayjs(item.correction_date) : undefined,
      verification_photos_text: (item.verification_photos || []).join('\n'),
    })
    setModalOpen(true)
  }

  const handleSave = async (values: any) => {
    if (editing && ['corrected', 'verified', 'closed'].includes(values.status) && !String(values.corrective_action || '').trim()) {
      message.warning('进入已整改或后续状态前，请填写整改措施')
      return
    }
    if (editing && ['verified', 'closed'].includes(values.status) && !String(values.verification_result || '').trim()) {
      message.warning('进入已验证或关闭状态前，请填写验证结果')
      return
    }
    setSaving(true)
    try {
      const baseData = {
        severity: values.severity,
        certification_system: values.certification_system,
        clause_no: values.clause_no,
        description: values.description,
        evidence: values.evidence,
        corrective_action_required: values.corrective_action_required,
        due_date: values.due_date?.format('YYYY-MM-DD'),
      }
      if (editing) {
        await nonconformityApi.update(editing.id, {
          ...baseData,
          corrective_action: values.corrective_action,
          correction_date: values.correction_date?.format('YYYY-MM-DD'),
          verification_result: values.verification_result,
          verification_photos: String(values.verification_photos_text || '')
            .split(/\r?\n/)
            .map((item) => item.trim())
            .filter(Boolean),
          status: values.status,
        })
        message.success('不符合项及整改状态已更新')
      } else {
        await nonconformityApi.create(projectId, baseData)
        message.success('人工不符合项已创建')
      }
      setModalOpen(false)
      form.resetFields()
      await fetchNonconformities()
    } catch (error: any) {
      message.error(error.response?.data?.detail || error.response?.data?.message || '保存不符合项失败')
    } finally {
      setSaving(false)
    }
  }

  const draftCount = nonconformities.filter((item) => item.status === 'draft').length

  const columns: TableColumnsType<NonconformityItem> = [
    {
      title: '编号',
      dataIndex: 'nc_no',
      key: 'nc_no',
      width: 140,
      render: (value?: string, item?: NonconformityItem) => (
        <Space size={6}>
          {(item?.ai_generated || item?.source === 'ai') && <RobotOutlined aria-label="AI 生成" style={{ color: '#1677ff' }} />}
          <Text>{value || '待编号'}</Text>
        </Space>
      ),
    },
    {
      title: '严重程度',
      dataIndex: 'severity',
      key: 'severity',
      width: 120,
      render: (value?: string) => {
        const config = severityConfig[value || ''] || { text: value || '未判定', color: 'default' }
        return <Tag color={config.color}>{config.text}</Tag>
      },
    },
    {
      title: '条款',
      key: 'clause',
      width: 150,
      render: (_, item) => (
        <Space direction="vertical" size={0}>
          <Text>{item.clause_no || '-'}</Text>
          {item.certification_system && <Text type="secondary">{item.certification_system}</Text>}
        </Space>
      ),
    },
    {
      title: '问题描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (value?: string) => {
        const config = statusConfig[value || ''] || { text: value || '未知', color: 'default' }
        return <Tag color={config.color}>{config.text}</Tag>
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 230,
      render: (_, item) => (
        <Space size="small">
          {item.status === 'draft' && (
            <Popconfirm
              title="确认不符合项草稿"
              description="确认后将进入正式整改流程。请先展开核对客观证据和 AI 判断理由。"
              okText="确认进入整改"
              cancelText="暂不确认"
              onConfirm={() => handleConfirm(item)}
            >
              <Button
                type="primary"
                size="small"
                icon={<CheckOutlined />}
                loading={confirmingId === item.id}
              >
                确认
              </Button>
            </Popconfirm>
          )}
          <Button size="small" icon={<EditOutlined />} onClick={() => showEdit(item)}>
            {item.status === 'draft' ? '复核编辑' : '整改/验证'}
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {draftCount > 0 && (
        <Alert
          type="warning"
          showIcon
          message={`有 ${draftCount} 条 AI 不符合项草稿等待人工确认`}
          description="AI 不会直接发出正式不符合项。请核对证据、条款和严重程度后再确认。"
        />
      )}

      <div>
        <Button type="primary" icon={<PlusOutlined />} onClick={showCreate}>
          人工开具不符合项
        </Button>
      </div>

      <Table<NonconformityItem>
        columns={columns}
        dataSource={nonconformities}
        rowKey="id"
        loading={loading}
        scroll={{ x: 900 }}
        locale={{
          emptyText: (
            <Empty description="暂无不符合项">
              <Text type="secondary">现场审核发现的异常会先作为 AI 草稿进入这里，由审核组确认。</Text>
            </Empty>
          ),
        }}
        expandable={{
          expandedRowRender: (item) => (
            <Descriptions size="small" bordered column={1}>
              <Descriptions.Item label="问题描述">
                <Paragraph style={{ marginBottom: 0 }}>{item.description || '-'}</Paragraph>
              </Descriptions.Item>
              <Descriptions.Item label="客观证据">
                <Paragraph style={{ marginBottom: 0 }}>{item.objective_evidence || item.evidence || '-'}</Paragraph>
              </Descriptions.Item>
              <Descriptions.Item label="AI 判断理由">
                <Paragraph style={{ marginBottom: 0 }}>{item.analysis_reasoning || '-'}</Paragraph>
              </Descriptions.Item>
              <Descriptions.Item label="置信度">
                {typeof item.confidence === 'number'
                  ? `${Math.round(item.confidence <= 1 ? item.confidence * 100 : item.confidence)}%`
                  : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="发现来源">{item.source || (item.ai_generated ? 'AI 草稿' : '人工记录')}</Descriptions.Item>
              <Descriptions.Item label="整改要求">{item.corrective_action_required || '-'}</Descriptions.Item>
              <Descriptions.Item label="整改措施">{item.corrective_action || '-'}</Descriptions.Item>
              <Descriptions.Item label="验证结果">{item.verification_result || '-'}</Descriptions.Item>
            </Descriptions>
          ),
          rowExpandable: (item) => Boolean(item.description || item.objective_evidence || item.evidence || item.analysis_reasoning),
        }}
      />

      <Modal
        title={editing ? `处理不符合项 ${editing.nc_no || ''}` : '人工开具不符合项'}
        open={modalOpen}
        width={760}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
        onOk={() => form.submit()}
        onCancel={() => setModalOpen(false)}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Space size="large" align="start" style={{ width: '100%' }}>
            <Form.Item
              label="严重程度"
              name="severity"
              rules={[{ required: true, message: '请选择严重程度' }]}
              style={{ minWidth: 180 }}
            >
              <Select
                options={[
                  { value: 'major', label: '严重不符合' },
                  { value: 'minor', label: '一般不符合' },
                  { value: 'observation', label: '观察项' },
                ]}
              />
            </Form.Item>
            <Form.Item label="体系" name="certification_system" style={{ minWidth: 150 }}>
              <Select options={['Q', 'E', 'S', 'En'].map((value) => ({ value, label: value }))} />
            </Form.Item>
            <Form.Item label="条款" name="clause_no" style={{ minWidth: 180 }}>
              <Input placeholder="如 10.2" />
            </Form.Item>
          </Space>

          <Form.Item
            label="不符合描述"
            name="description"
            rules={[{ required: true, message: '请填写不符合描述' }]}
          >
            <TextArea rows={3} placeholder="描述事实、要求与差距，避免只写结论" />
          </Form.Item>
          <Form.Item label="客观证据" name="evidence">
            <TextArea rows={3} placeholder="记录抽样对象、编号、日期及现场观察" />
          </Form.Item>
          <Space size="large" align="start" style={{ width: '100%' }}>
            <Form.Item label="整改要求" name="corrective_action_required" style={{ flex: 1, minWidth: 420 }}>
              <TextArea rows={2} />
            </Form.Item>
            <Form.Item label="整改期限" name="due_date">
              <DatePicker />
            </Form.Item>
          </Space>

          {editing && (
            <>
              <Form.Item label="整改措施" name="corrective_action">
                <TextArea rows={3} placeholder="填写原因分析、纠正与纠正措施" />
              </Form.Item>
              <Space size="large" align="start" style={{ width: '100%' }}>
                <Form.Item label="整改日期" name="correction_date">
                  <DatePicker />
                </Form.Item>
                <Form.Item label="状态" name="status" style={{ minWidth: 220 }}>
                  <Select
                    options={[
                      { value: 'draft', label: 'AI 草稿·待确认' },
                      { value: 'open', label: '待整改' },
                      { value: 'corrected', label: '已整改·待验证' },
                      { value: 'verified', label: '已验证·待关闭' },
                      { value: 'closed', label: '已关闭' },
                      { value: 'rejected', label: '已驳回' },
                    ]}
                  />
                </Form.Item>
              </Space>
              <Form.Item label="验证结果" name="verification_result">
                <TextArea rows={3} placeholder="记录验证方法、证据和结论；关闭前必须填写" />
              </Form.Item>
              <Form.Item
                label="验证证据文件/链接"
                name="verification_photos_text"
                extra="每行一条。当前用于登记已上传证据的路径或链接。"
              >
                <TextArea rows={3} />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </Space>
  )
}
