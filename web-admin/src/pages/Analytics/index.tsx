import { useState, useEffect } from 'react'
import { Card, Table, Tag, Tabs, Tooltip } from 'antd'
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

/** 审计日志「METHOD /api/xxx/...」→ 业务动作（动词 + 对象），未匹配的原样显示 */
const AUDIT_RESOURCES: Array<[RegExp, string]> = [
  [/^\/api\/auth\/login/, '登录系统'],
  [/^\/api\/auth\/logout/, '退出登录'],
  [/^\/api\/auth\/me\/password/, '修改密码'],
  [/^\/api\/agent\/notifications/, '智审提醒'],
  [/^\/api\/agent\/actions\/confirm/, '确认 Agent 动作'],
  [/^\/api\/agent\/chat/, '智审 Agent 对话'],
  [/^\/api\/audit-projects\/[^/]+\/sessions\/[^/]+\/evidence/, '现场证据'],
  [/^\/api\/audit-projects\/[^/]+\/sessions\/[^/]+\/submit/, '提交现场审核'],
  [/^\/api\/audit-projects\/[^/]+\/sessions/, '现场审核会话'],
  [/^\/api\/audit-projects\/[^/]+\/nonconformities\/[^/]+\/confirm/, '确认不符合项草稿'],
  [/^\/api\/audit-projects\/(?:[^/]+\/)?nonconformities/, '不符合项'],
  [/^\/api\/audit-projects\/(?:[^/]+\/)?meetings/, '会议记录'],
  [/^\/api\/audit-projects\/(?:[^/]+\/)?team/, '审核组成员'],
  [/^\/api\/audit-projects\/(?:[^/]+\/)?plan/, '审核计划'],
  [/^\/api\/audit-projects\/[^/]+\/documents/, '项目资料'],
  [/^\/api\/audit-projects\/[^/]+\/artifacts/, '报告/资料包'],
  [/^\/api\/audit-projects/, '审核项目'],
  [/^\/api\/enterprises\/rectifications\/[^/]+\/review/, '复核整改'],
  [/^\/api\/enterprises\/rectifications/, '企业整改'],
  [/^\/api\/enterprises\/(?:[^/]+\/)?qualifications/, '企业资质'],
  [/^\/api\/enterprises\/[^/]+\/products/, '企业产品'],
  [/^\/api\/enterprises/, '企业'],
  [/^\/api\/tasks\/[^/]+\/start/, '开始检查任务'],
  [/^\/api\/tasks\/[^/]+\/complete/, '完成检查任务'],
  [/^\/api\/tasks\/[^/]+\/cancel/, '取消检查任务'],
  [/^\/api\/tasks\/(?:[^/]+\/)?records/, '检查项填报'],
  [/^\/api\/tasks/, '检查任务'],
  [/^\/api\/records\/[^/]+\/submit/, '提交检查记录'],
  [/^\/api\/records\/[^/]+\/items/, '检查项填报'],
  [/^\/api\/records/, '检查记录'],
  [/^\/api\/templates/, '检查模板'],
  [/^\/api\/knowledge\/guidelines/, '审查细则'],
  [/^\/api\/knowledge/, '知识库文档'],
  [/^\/api\/media/, '附件'],
  [/^\/api\/users/, '用户'],
  [/^\/api\/industries/, '行业分类'],
]

const AUDIT_VERBS: Record<string, { text: string; color: string }> = {
  POST: { text: '新增/提交', color: 'green' },
  PUT: { text: '修改', color: 'blue' },
  PATCH: { text: '修改', color: 'blue' },
  DELETE: { text: '删除', color: 'red' },
}

function describeAuditAction(action?: string): { verb: string; target: string; color: string } {
  const m = /^(GET|POST|PUT|PATCH|DELETE)\s+(\S+)/.exec(action || '')
  if (!m) return { verb: '操作', target: action || '-', color: 'default' }
  const [, method, path] = m
  const target = AUDIT_RESOURCES.find(([re]) => re.test(path))?.[1] || path
  // 登录/退出/确认/提交/开始等本身已含动作的，不再叠加「新增」
  const selfDescribing = /登录|退出|确认|提交|开始|完成|取消|复核|对话|修改密码/.test(target)
  const verb = AUDIT_VERBS[method] || { text: method, color: 'default' }
  return { verb: selfDescribing ? '操作' : verb.text, target, color: selfDescribing ? 'purple' : verb.color }
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
    {
      title: '用户',
      dataIndex: 'username',
      key: 'username',
      width: 120,
      // 登录请求发生在认证之前，日志里没有用户名
      render: (v: string, r: any) => v || (/auth\/login/.test(r.action || '') ? '（登录请求）' : '-'),
    },
    {
      // 审计中间件记录的是「METHOD /api/xxx」原始路径，管理员看不懂；这里翻译成业务动作，原始路径放在悬浮提示里
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      width: 260,
      render: (action: string) => {
        const info = describeAuditAction(action)
        return (
          <Tooltip title={action}>
            <span>
              <Tag color={info.color} style={{ marginInlineEnd: 6 }}>{info.verb}</Tag>
              {info.target}
            </span>
          </Tooltip>
        )
      },
    },
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
