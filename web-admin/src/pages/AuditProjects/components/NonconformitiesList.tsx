import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Descriptions,
  Empty,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'
import { CheckOutlined, RobotOutlined } from '@ant-design/icons'

import { nonconformityApi } from '@/services/auditProjectApi'

const { Paragraph, Text } = Typography

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
  closed: { text: '已关闭', color: 'success' },
  rejected: { text: '已驳回', color: 'default' },
}

export default function NonconformitiesList({ projectId }: Props) {
  const [loading, setLoading] = useState(false)
  const [confirmingId, setConfirmingId] = useState<string>()
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
      width: 130,
      render: (_, item) => item.status === 'draft' ? (
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
            确认草稿
          </Button>
        </Popconfirm>
      ) : <Text type="secondary">查看详情</Text>,
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
            </Descriptions>
          ),
          rowExpandable: (item) => Boolean(item.description || item.objective_evidence || item.evidence || item.analysis_reasoning),
        }}
      />
    </Space>
  )
}
