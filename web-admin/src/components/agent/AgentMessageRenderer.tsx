import { Card, Tag, Typography, Collapse, Tooltip, Button } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
  ToolOutlined,
  BookOutlined,
  CopyOutlined,
} from '@ant-design/icons'

const { Paragraph } = Typography
const { Panel } = Collapse

interface ToolCall {
  name: string
  status: 'calling' | 'done' | 'error'
  result?: string
}

interface ActionConfirm {
  type: 'create_task' | 'judgment' | 'operation'
  title: string
  data: Record<string, unknown>
  status: 'pending' | 'confirmed' | 'cancelled'
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
  actionConfirm?: ActionConfirm
  citations?: Citation[]
}

interface AgentMessageRendererProps {
  message: Message
}

const toolLabels: Record<string, string> = {
  get_check_item_details: '获取检查项详情',
  get_inspection_summary: '汇总检查结果',
  generate_final_verdict: '生成最终判定',
  search_knowledge: '检索知识库',
  get_enterprise_info: '查询企业信息',
  analyze_photo: '分析照片',
}

export default function AgentMessageRenderer({ message }: AgentMessageRendererProps) {
  const renderMarkdown = (content: string) => {
    if (!content) return null

    const parts = content.split(/(\*\*.*?\*\*|\n|• |\d+\. )/g)

    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={index}>{part.slice(2, -2)}</strong>
      }
      if (part === '\n') {
        return <br key={index} />
      }
      if (part === '• ') {
        return <span key={index}>&bull; </span>
      }
      if (/^\d+\. $/.test(part)) {
        return (
          <span key={index} className="list-number">
            {part}
          </span>
        )
      }
      return <span key={index}>{part}</span>
    })
  }

  const getToolIcon = (name: string) => {
    if (name.includes('knowledge') || name.includes('search')) {
      return <BookOutlined />
    }
    return <ToolOutlined />
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div className="agent-message-renderer">
      {message.role === 'assistant' && message.toolCalls && message.toolCalls.length > 0 && (
        <div className="tool-calls-section">
          <Collapse
            defaultActiveKey={message.toolCalls.some(t => t.status === 'calling') ? ['tools'] : []}
            ghost
            items={[
              {
                key: 'tools',
                label: (
                  <span className="tool-calls-header">
                    <ToolOutlined />
                    调用了 {message.toolCalls.length} 个工具
                  </span>
                ),
                children: (
                  <div className="tool-calls-list">
                    {message.toolCalls.map((tool, index) => (
                      <div key={index} className={`tool-item ${tool.status}`}>
                        <div className="tool-icon">{getToolIcon(tool.name)}</div>
                        <div className="tool-info">
                          <span className="tool-name">
                            {toolLabels[tool.name] || tool.name}
                          </span>
                          {tool.status === 'calling' && (
                            <Tag color="processing">执行中</Tag>
                          )}
                          {tool.status === 'done' && (
                            <Tag color="success">完成</Tag>
                          )}
                          {tool.status === 'error' && (
                            <Tag color="error">失败</Tag>
                          )}
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
        <div className="message-text">{renderMarkdown(message.content)}</div>
      </div>

      {message.citations && message.citations.length > 0 && (
        <div className="citations-section">
          <Collapse
            ghost
            items={[
              {
                key: 'citations',
                label: (
                  <span className="citations-header">
                    <BookOutlined />
                    引用来源 ({message.citations.length})
                  </span>
                ),
                children: (
                  <div className="citations-list">
                    {message.citations.map((citation) => (
                      <Card
                        key={citation.id}
                        size="small"
                        className="citation-card"
                        title={
                          <span className="citation-source">{citation.source}</span>
                        }
                        extra={
                          <span className="citation-relevance">
                            相关度: {citation.relevance}%
                          </span>
                        }
                      >
                        <Paragraph
                          ellipsis={{ rows: 2, expandable: true }}
                          className="citation-content"
                        >
                          {citation.content}
                        </Paragraph>
                        <div className="citation-actions">
                          <Tooltip title="复制">
                            <Button
                              type="text"
                              size="small"
                              icon={<CopyOutlined />}
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

      {message.actionConfirm && message.actionConfirm.status !== 'pending' && (
        <div className={`action-status ${message.actionConfirm.status}`}>
          {message.actionConfirm.status === 'confirmed' ? (
            <>
              <CheckCircleOutlined /> 已确认
            </>
          ) : (
            <>
              <CloseCircleOutlined /> 已取消
            </>
          )}
        </div>
      )}
    </div>
  )
}