import React, { useMemo } from 'react'
import { MessageOutline, SearchOutline } from 'antd-mobile-icons'
import AgentActionCard from './AgentActionCard'
import type { ChatMessageState } from './types'
import './AgentMessage.css'

const TOOL_LABELS: Record<string, string> = {
  list_check_items: '列出检查项',
  get_check_item_details: '获取检查项详情',
  get_inspection_summary: '汇总检查结果',
  generate_final_verdict: '生成最终判定',
  search_knowledge_base: '搜索知识库',
  get_enterprise_history: '查询企业历史',
  recommend_template: '推荐检查模板',
  analyze_photo: '分析照片',
  fill_check_result: '分析检查发现',
  apply_check_result: '生成检查结果卡片',
  apply_final_verdict: '生成最终判定卡片',
}

const toolLabel = (name: string) => TOOL_LABELS[name] || name

const formatTime = (timestamp: number) =>
  new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

/**
 * 极简 markdown 渲染：粗体 **text**、换行、• 项目符号、数字列表。
 * 不引入 markdown 库，与 h5-app AgentMessage.vue 的 renderedContent 保持一致的规则。
 */
function renderContent(content: string): { __html: string } {
  const escaped = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  const html = escaped
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
    .replace(/• /g, '&bull; ')
    .replace(/(\d+)\. /g, '<span class="list-num">$1.</span> ')

  return { __html: html }
}

interface AgentMessageProps {
  message: ChatMessageState
  /** 本条消息的动作提案未登记在服务端注册表中，只能复制手填。 */
  advisoryOnly?: boolean
  onConfirmAction: () => void
  onCancelAction: () => void
}

const AgentMessage: React.FC<AgentMessageProps> = ({
  message,
  advisoryOnly = false,
  onConfirmAction,
  onCancelAction,
}) => {
  const html = useMemo(
    () => (message.role === 'assistant' ? renderContent(message.content) : null),
    [message.role, message.content]
  )

  return (
    <div className={`agent-message ${message.role}`}>
      {message.role === 'assistant' && (
        <div className="avatar">
          <MessageOutline fontSize={18} color="#1677ff" />
        </div>
      )}

      <div className="message-content">
        <div className={`message-bubble ${message.role}`}>
          {message.role === 'assistant' && html ? (
            <div className="message-text" dangerouslySetInnerHTML={html} />
          ) : (
            <div className="message-text">{message.content}</div>
          )}

          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className="tool-calls">
              {message.toolCalls.map((tool) => (
                <div key={tool.name} className="tool-call-item">
                  <SearchOutline fontSize={12} />
                  <span>{toolLabel(tool.name)}</span>
                </div>
              ))}
            </div>
          )}

          {message.actionProposal && (
            <AgentActionCard
              action={message.actionProposal}
              advisoryOnly={advisoryOnly}
              onConfirm={onConfirmAction}
              onCancel={onCancelAction}
            />
          )}
        </div>

        <div className="message-time">{formatTime(message.timestamp)}</div>
      </div>
    </div>
  )
}

export default AgentMessage
