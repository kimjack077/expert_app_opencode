import { useState, useEffect } from 'react'
import { Card, Table, Tag, Tabs } from 'antd'
import { analyticsApi } from '@/services/api'
import dayjs from 'dayjs'

const PAGE_SIZE = 20

const CALL_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  suggestion: { label: '审核建议', color: 'gold' },
  basis: { label: '法规依据', color: 'purple' },
  agent_chat: { label: 'Agent 对话', color: 'blue' },
  agent_briefing: { label: '审核简报', color: 'cyan' },
  agent_briefing_stream: { label: '审核简报（流式）', color: 'cyan' },
  evidence_analysis: { label: '证据分析', color: 'volcano' },
  planner_plan: { label: 'Agent 规划', color: 'geekblue' },
  planner_synthesis: { label: '规划汇总', color: 'geekblue' },
}

export default function Analytics() {
  const [auditLogs, setAuditLogs] = useState<any[]>([])
  const [llmLogs, setLlmLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [auditTotal, setAuditTotal] = useState(0)
  const [llmTotal, setLlmTotal] = useState(0)
  const [auditPage, setAuditPage] = useState(1)
  const [llmPage, setLlmPage] = useState(1)

  useEffect(() => {
    fetchLogs(auditPage, llmPage)
  }, [auditPage, llmPage])

  const fetchLogs = async (nextAuditPage: number, nextLlmPage: number) => {
    setLoading(true)
    try {
      const [auditRes, llmRes]: any[] = await Promise.all([
        analyticsApi.getAuditLogs({ skip: (nextAuditPage - 1) * PAGE_SIZE, limit: PAGE_SIZE }),
        analyticsApi.getLLMLogs({ skip: (nextLlmPage - 1) * PAGE_SIZE, limit: PAGE_SIZE }),
      ])
      setAuditLogs(auditRes.data?.items || [])
      setLlmLogs(llmRes.data?.items || [])
      setAuditTotal(auditRes.data?.total || 0)
      setLlmTotal(llmRes.data?.total || 0)
    } catch (error) {
      console.error('Failed to fetch logs:', error)
    } finally {
      setLoading(false)
    }
  }

  const auditColumns = [
    { title: '用户', dataIndex: 'username', key: 'username', width: 120 },
    { title: '操作', dataIndex: 'action', key: 'action', width: 200 },
    { title: '资源类型', dataIndex: 'resource_type', key: 'resource_type', width: 100 },
    { title: '资源ID', dataIndex: 'resource_id', key: 'resource_id', ellipsis: true },
    { title: 'IP地址', dataIndex: 'ip_address', key: 'ip_address', width: 140 },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm:ss'),
    },
  ]

  const llmColumns = [
    { title: '调用类型', dataIndex: 'call_type', key: 'call_type', width: 100,
      render: (type: string) => {
        const display = CALL_TYPE_LABELS[type] || { label: type || '未知类型', color: 'default' }
        return <Tag color={display.color}>{display.label}</Tag>
      }
    },
    { title: '模型', dataIndex: 'model', key: 'model', ellipsis: true },
    { title: 'Token数', dataIndex: 'tokens_used', key: 'tokens_used', width: 100 },
    { title: '耗时(ms)', dataIndex: 'duration_ms', key: 'duration_ms', width: 100 },
    {
      title: '状态',
      dataIndex: 'is_success',
      key: 'is_success',
      width: 80,
      render: (success: string) => (
        <Tag color={success === 'true' ? 'success' : 'error'}>
          {success === 'true' ? '成功' : '失败'}
        </Tag>
      ),
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm:ss'),
    },
  ]

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">数据分析与审计日志</h1>
      </div>

      <Tabs
        items={[
          {
            key: 'audit',
            label: '操作审计日志',
            children: (
              <Card>
                <Table
                  dataSource={auditLogs}
                  columns={auditColumns}
                  rowKey="id"
                  loading={loading}
                  scroll={{ x: 1000 }}
                  size="small"
                  pagination={{
                    current: auditPage,
                    pageSize: PAGE_SIZE,
                    total: auditTotal,
                    showSizeChanger: false,
                    onChange: setAuditPage,
                  }}
                />
              </Card>
            ),
          },
          {
            key: 'llm',
            label: 'LLM调用记录',
            children: (
              <Card>
                <Table
                  dataSource={llmLogs}
                  columns={llmColumns}
                  rowKey="id"
                  loading={loading}
                  scroll={{ x: 800 }}
                  size="small"
                  pagination={{
                    current: llmPage,
                    pageSize: PAGE_SIZE,
                    total: llmTotal,
                    showSizeChanger: false,
                    onChange: setLlmPage,
                  }}
                />
              </Card>
            ),
          },
        ]}
      />
    </div>
  )
}
