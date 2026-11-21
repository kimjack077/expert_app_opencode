import { lazy, Suspense } from 'react'
import { Button, Card, Collapse, Tag, Tooltip, Typography, message as antdMessage } from 'antd'
import {
  BookOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CopyOutlined,
  ExclamationCircleOutlined,
  ToolOutlined,
} from '@ant-design/icons'

import type { AgentAction } from './AgentActionConfirm'

const MarkdownView = lazy(() => import('@/components/common/MarkdownView'))

const { Paragraph } = Typography

interface ToolCall {
  name: string
  status: 'calling' | 'done' | 'error'
  result?: string
}

interface Citation {
  id: string
  source: string
  content: string
  relevance: number
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  toolCalls?: ToolCall[]
  actionConfirms?: AgentAction[]
  citations?: Citation[]
}

interface Props {
  message: Message
}

const toolLabels: Record<string, string> = {
  get_check_item_details: '获取检查项详情',
  get_inspection_summary: '汇总检查结果',
  generate_final_verdict: '生成最终判定',
  search_knowledge: '检索知识库',
  search_project_knowledge: '检索项目资料',
  get_enterprise_info: '查询企业信息',
  analyze_photo: '分析照片',
  get_project_summary: '汇总审核项目',
  check_project_quality: '检查资料质量',
}

export default function AgentMessageRenderer({ message }: Props) {
  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      antdMessage.success('引用内容已复制')
    } catch {
      antdMessage.error('复制失败，请手动选择文本')
    }
  }

  return (
    <div className="agent-message-renderer">
      {message.role === 'assistant' && Boolean(message.toolCalls?.length) && (
        <div className="tool-calls-section">
          <Collapse
            defaultActiveKey={message.toolCalls?.some((tool) => tool.status === 'calling') ? ['tools'] : []}
            ghost
            items={[
              {
                key: 'tools',
                label: <span className="tool-calls-header"><ToolOutlined /> 已调用 {message.toolCalls?.length} 个工具</span>,
                children: (
                  <div className="tool-calls-list">
                    {message.toolCalls?.map((tool, index) => (
                      <div key={`${tool.name}-${index}`} className={`tool-item ${tool.status}`}>
                        <div className="tool-icon">{tool.name.includes('knowledge') || tool.name.includes('search') ? <BookOutlined /> : <ToolOutlined />}</div>
                        <div className="tool-info">
                          <span className="tool-name">{toolLabels[tool.name] || tool.name}</span>
                          {tool.status === 'calling' && <Tag color="processing">执行中</Tag>}
                          {tool.status === 'done' && <Tag color="success">完成</Tag>}
                          {tool.status === 'error' && <Tag color="error">失败</Tag>}
                        </div>
                      </div>
                    ))}
                  </div>
                ),
              },
            ]}
          />
        </div>
      )}

      <div className={`message-bubble ${message.role}`}>
        {message.role === 'assistant' ? (
          <Suspense fallback={<div className="message-text">{message.content}</div>}>
            <MarkdownView content={message.content} />
          </Suspense>
        ) : (
          <div className="message-text">{message.content}</div>
        )}
      </div>

      {Boolean(message.citations?.length) && (
        <div className="citations-section">
          <Collapse
            ghost
            items={[
              {
                key: 'citations',
                label: <span className="citations-header"><BookOutlined /> 引用来源（{message.citations?.length}）</span>,
                children: (
                  <div className="citations-list">
                    {message.citations?.map((citation) => (
                      <Card
                        key={citation.id}
                        size="small"
                        className="citation-card"
                        title={<span className="citation-source">{citation.source}</span>}
                        extra={<span className="citation-relevance">相关度 {citation.relevance}%</span>}
                      >
                        <Paragraph ellipsis={{ rows: 3, expandable: true, symbol: '展开' }} className="citation-content">
                          {citation.content}
                        </Paragraph>
                        <div className="citation-actions">
                          <Tooltip title="复制引用">
                            <Button
                              type="text"
                              icon={<CopyOutlined />}
                              aria-label={`复制来自 ${citation.source} 的引用`}
                              onClick={() => copyToClipboard(citation.content)}
                            />
                          </Tooltip>
                        </div>
                      </Card>
                    ))}
                  </div>
                ),
              },
            ]}
          />
        </div>
      )}

      {message.actionConfirms?.filter((action) => action.status !== 'pending').map((action) => (
        <div key={action.actionIndex ?? 0} className={`action-status ${action.status}`} role="status">
          {action.status === 'confirmed' && <><CheckCircleOutlined /> 已确认并写入</>}
          {action.status === 'cancelled' && <><CloseCircleOutlined /> 已拒绝</>}
          {action.status === 'failed' && (
            <>
              <ExclamationCircleOutlined /> 写入失败
              {action.data?.failure_reason
                ? `：${String(action.data.failure_reason)}`
                : '，可重新向 Agent 发起操作'}
            </>
          )}
        </div>
      ))}
    </div>
  )
}
