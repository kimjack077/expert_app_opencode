import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button, Empty, Input, List, Spin, Tabs, Tag, Tooltip, Typography, message } from 'antd'
import {
  CloseOutlined,
  HistoryOutlined,
  MessageOutlined,
  PlusOutlined,
  RobotOutlined,
  SearchOutlined,
  SendOutlined,
  StopOutlined,
} from '@ant-design/icons'

import { recordApi } from '@/services/api'
import { nonconformityApi } from '@/services/auditProjectApi'
import { useAuthStore } from '@/stores/auth'
import AgentActionConfirm, { type AgentAction } from './AgentActionConfirm'
import AgentMessageRenderer from './AgentMessageRenderer'
import './AgentSidebar.css'
import './index.css'

const { Text } = Typography
const HISTORY_KEY = 'efis-agent-conversations-v2'
const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

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

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  toolCalls?: ToolCall[]
  actionConfirm?: AgentAction
  citations?: Citation[]
}

interface Conversation {
  id: string
  contextKey: string
  title: string
  lastMessage: string
  updatedAt: number
  messages: ChatMessage[]
}

export interface AgentContext {
  page?: string
  enterpriseId?: string
  enterpriseName?: string
  recordId?: string
  templateId?: string
  projectId?: string
  auditSessionId?: string
  planItemId?: string
}

interface Props {
  context?: AgentContext
}

const asCitation = (value: any, index: number): Citation => ({
  id: String(value?.id || value?.chunk_id || `citation-${index}`),
  source: String(value?.source || value?.file_name || value?.document_name || '项目资料'),
  content: String(value?.content || value?.text || value?.excerpt || ''),
  relevance: Math.round(Number(value?.relevance ?? value?.score ?? 0) * (Number(value?.relevance ?? value?.score ?? 0) <= 1 ? 100 : 1)),
})

const normalizeAction = (event: any): AgentAction => {
  const serverAction = String(event?.action || event?.type || 'operation')
  const raw = event?.data || event?.action?.data || {}

  if (serverAction === 'apply_check_result') {
    return {
      type: 'judgment',
      serverAction,
      title: event.title || '建议记录检查结果',
      status: 'pending',
      data: {
        ...raw,
        recordId: raw.record_id,
        itemId: raw.item_id,
        checkItem: raw.item_title,
        problemDescription: raw.problem_description,
        rectificationSuggestion: raw.rectification_suggestion,
      },
    }
  }

  if (serverAction === 'apply_final_verdict') {
    return {
      type: 'final_verdict',
      serverAction,
      title: event.title || '建议记录最终结论',
      status: 'pending',
      data: { ...raw, recordId: raw.record_id },
    }
  }

  if (serverAction === 'create_task') {
    return { type: 'create_task', serverAction, title: event.title || '建议创建任务', status: 'pending', data: raw }
  }

  return {
    type: 'operation',
    serverAction,
    title: event.title || '建议执行项目操作',
    status: 'pending',
    data: raw,
  }
}

const loadStoredConversations = (): Conversation[] => {
  try {
    const stored = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
    return Array.isArray(stored) ? stored.slice(0, 20) : []
  } catch {
    return []
  }
}

export default function AgentSidebar({ context }: Props) {
  const [collapsed, setCollapsed] = useState(true)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'chat' | 'history'>('chat')
  const [conversationId, setConversationId] = useState<string>()
  const [conversations, setConversations] = useState<Conversation[]>(loadStoredConversations)
  const [historyQuery, setHistoryQuery] = useState('')
  const [applyingMessageId, setApplyingMessageId] = useState<string>()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const previousContextKeyRef = useRef<string>()
  const token = useAuthStore((state) => state.token)

  const contextKey = useMemo(
    () => context?.projectId
      ? `project:${context.projectId}`
      : context?.recordId
        ? `record:${context.recordId}`
        : context?.enterpriseId
          ? `enterprise:${context.enterpriseId}`
          : `page:${context?.page || 'global'}`,
    [context?.enterpriseId, context?.page, context?.projectId, context?.recordId]
  )

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    if (previousContextKeyRef.current && previousContextKeyRef.current !== contextKey) {
      abortControllerRef.current?.abort()
      setMessages([])
      setConversationId(undefined)
      setActiveTab('chat')
    }
    previousContextKeyRef.current = contextKey
  }, [contextKey])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  useEffect(() => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(conversations.slice(0, 20)))
  }, [conversations])

  useEffect(() => {
    if (!conversationId || !messages.some((item) => item.role === 'user')) return
    const timer = window.setTimeout(() => {
      setConversations((current) => {
        const firstQuestion = messages.find((item) => item.role === 'user')?.content || '新对话'
        const lastMessage = [...messages].reverse().find((item) => item.content)?.content || ''
        const next: Conversation = {
          id: conversationId,
          contextKey,
          title: firstQuestion.slice(0, 28),
          lastMessage: lastMessage.slice(0, 60),
          updatedAt: Date.now(),
          messages,
        }
        return [next, ...current.filter((item) => item.id !== conversationId)].slice(0, 20)
      })
    }, 350)
    return () => window.clearTimeout(timer)
  }, [contextKey, conversationId, messages])

  const quickActions = useMemo(() => {
    if (context?.projectId) {
      return [
        '总结当前项目的审核风险和待办',
        '检查项目资料还缺什么',
        '根据已确认记录给出报告建议',
      ]
    }
    if (context?.recordId) {
      return ['总结当前检查异常', '检查还有哪些项目未完成', '生成最终判定建议']
    }
    return ['查看企业风险画像', '准备下次检查', '查看历史检查记录']
  }, [context?.projectId, context?.recordId])

  const updateAssistant = (id: string, updater: (message: ChatMessage) => ChatMessage) => {
    setMessages((current) => current.map((item) => item.id === id ? updater(item) : item))
  }

  const sendMessage = async (text?: string) => {
    const messageText = (text || inputValue).trim()
    if (!messageText || isLoading) return

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: messageText,
      timestamp: Date.now(),
    }
    const assistantId = `assistant-${Date.now()}`
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      toolCalls: [],
    }

    const conversationForRequest = messages.map((item) => ({
      role: item.role,
      content: item.content,
    }))
    setMessages((current) => [...current, userMessage, assistantMessage])
    setInputValue('')
    setIsLoading(true)
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(`${API_BASE_URL}/api/agent/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          message: messageText,
          context: {
            page: context?.page,
            enterprise_id: context?.enterpriseId,
            record_id: context?.recordId,
            project_id: context?.projectId,
            audit_session_id: context?.auditSessionId,
            plan_item_id: context?.planItemId,
          },
          conversation: conversationForRequest,
          conversation_id: conversationId,
        }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) throw new Error(`Agent 请求失败（${response.status}）`)
      const reader = response.body?.getReader()
      if (!reader) throw new Error('无法读取 Agent 流式响应')

      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'conversation') {
              setConversationId(String(event.conversation_id))
            } else if (event.type === 'content') {
              updateAssistant(assistantId, (item) => ({ ...item, content: item.content + String(event.content || '') }))
            } else if (event.type === 'tool_call') {
              updateAssistant(assistantId, (item) => ({
                ...item,
                toolCalls: [...(item.toolCalls || []), { name: String(event.tool), status: 'calling' }],
              }))
            } else if (event.type === 'tool_result') {
              updateAssistant(assistantId, (item) => ({
                ...item,
                toolCalls: (item.toolCalls || []).map((tool) => tool.name === event.tool ? { ...tool, status: 'done' } : tool),
                citations: Array.isArray(event.citations)
                  ? event.citations.map(asCitation)
                  : item.citations,
              }))
            } else if (event.type === 'action_proposal' || event.type === 'action_confirm') {
              const proposal = typeof event.action === 'object' ? event.action : event
              updateAssistant(assistantId, (item) => ({ ...item, actionConfirm: normalizeAction(proposal) }))
            } else if (event.type === 'citations' || event.type === 'citation') {
              const values = event.type === 'citation' ? [event.citation || event] : event.citations || []
              updateAssistant(assistantId, (item) => ({ ...item, citations: values.map(asCitation) }))
            } else if (event.type === 'error') {
              updateAssistant(assistantId, (item) => ({ ...item, content: String(event.content || 'Agent 暂时无法完成本次请求。') }))
            }
          } catch {
            // 忽略不完整的单条事件，后续事件仍可继续处理。
          }
        }
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        updateAssistant(assistantId, (item) => ({
          ...item,
          content: `Agent 暂时不可用：${(error as Error).message || '请稍后重试'}`,
        }))
      }
    } finally {
      setIsLoading(false)
      abortControllerRef.current = null
    }
  }

  const persistAction = async (action: AgentAction, modifiedData?: Record<string, unknown>) => {
    const data = { ...action.data, ...(modifiedData || {}) }
    if (action.serverAction === 'apply_check_result') {
      const recordId = String(data.recordId || data.record_id || '')
      if (!recordId) throw new Error('缺少检查记录 ID')
      await recordApi.createRecordItem(recordId, {
        id: data.itemId || data.item_id,
        radio_value: data.result,
        problem_description: data.problemDescription || data.problem_description || '',
        rectification_suggestion: data.rectificationSuggestion || data.rectification_suggestion || '',
        ai_generated: true,
      })
      return
    }

    if (action.serverAction === 'apply_final_verdict') {
      const recordId = String(data.recordId || data.record_id || '')
      if (!recordId) throw new Error('缺少检查记录 ID')
      await recordApi.updateRecord(recordId, {
        overall_result: data.verdict,
        remarks: data.comment || '',
      })
      return
    }

    if (action.serverAction === 'confirm_nonconformity') {
      const projectId = String(data.project_id || context?.projectId || '')
      const ncId = String(data.nonconformity_id || data.nc_id || '')
      if (!projectId || !ncId) throw new Error('缺少项目或不符合项 ID')
      await nonconformityApi.confirm(projectId, ncId, data)
      return
    }

    const endpoint = String(data.confirm_endpoint || data.endpoint || '')
    const method = String(data.confirm_method || data.method || 'POST').toUpperCase()
    const isAllowedEndpoint = /^\/api\/(?:v1\/)?audit-projects\/[0-9a-f-]+\//i.test(endpoint)
    const belongsToCurrentProject = !context?.projectId || endpoint.includes(`/audit-projects/${context.projectId}/`)
    if (!endpoint || !isAllowedEndpoint || !belongsToCurrentProject || !['POST', 'PUT', 'PATCH'].includes(method)) {
      throw new Error('该建议没有可执行的受控写入协议')
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(data.confirm_payload || modifiedData || {}),
    })
    if (!response.ok) throw new Error(`执行失败（${response.status}）`)
  }

  const handleActionConfirm = async (messageId: string, action: AgentAction, modifiedData?: Record<string, unknown>) => {
    setApplyingMessageId(messageId)
    try {
      await persistAction(action, modifiedData)
      updateAssistant(messageId, (item) => ({
        ...item,
        actionConfirm: item.actionConfirm ? { ...item.actionConfirm, status: 'confirmed', data: { ...item.actionConfirm.data, ...(modifiedData || {}) } } : undefined,
      }))
      message.success('操作已确认并写入系统')
    } catch (error) {
      updateAssistant(messageId, (item) => ({
        ...item,
        actionConfirm: item.actionConfirm ? { ...item.actionConfirm, status: 'failed' } : undefined,
      }))
      message.error((error as Error).message || '确认操作失败')
    } finally {
      setApplyingMessageId(undefined)
    }
  }

  const cancelAction = (messageId: string) => {
    updateAssistant(messageId, (item) => ({
      ...item,
      actionConfirm: item.actionConfirm ? { ...item.actionConfirm, status: 'cancelled' } : undefined,
    }))
  }

  const startNewConversation = () => {
    abortControllerRef.current?.abort()
    setMessages([])
    setConversationId(undefined)
    setActiveTab('chat')
  }

  const visibleConversations = conversations.filter((item) => {
    if (item.contextKey !== contextKey) return false
    const keyword = historyQuery.trim().toLowerCase()
    return !keyword || item.title.toLowerCase().includes(keyword) || item.lastMessage.toLowerCase().includes(keyword)
  })

  if (collapsed) {
    return (
      <Tooltip title="打开项目 Agent" placement="left">
        <Button
          className="agent-sidebar-collapsed"
          type="primary"
          shape="circle"
          icon={<RobotOutlined />}
          aria-label="打开项目 Agent"
          onClick={() => setCollapsed(false)}
        />
      </Tooltip>
    )
  }

  return (
    <aside className="agent-sidebar" aria-label="项目 Agent">
      <div className="sidebar-header">
        <div className="header-title"><RobotOutlined className="header-icon" /><span>智检 Agent</span></div>
        <div className="header-actions">
          <Tooltip title="新对话"><Button type="text" icon={<PlusOutlined />} aria-label="新建对话" onClick={startNewConversation} /></Tooltip>
          <Tooltip title="收起"><Button type="text" icon={<CloseOutlined />} aria-label="收起 Agent" onClick={() => setCollapsed(true)} /></Tooltip>
        </div>
      </div>

      {(context?.projectId || context?.enterpriseName) && (
        <div className="context-bar">
          <span className="context-label">当前上下文：</span>
          <span className="context-value">{context.projectId ? '审核项目（资料已隔离）' : context.enterpriseName}</span>
          {context.auditSessionId && <Tag color="blue">审核会话</Tag>}
        </div>
      )}

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as 'chat' | 'history')}
        className="sidebar-tabs"
        items={[
          { key: 'chat', label: <span><MessageOutlined /> 对话</span> },
          { key: 'history', label: <span><HistoryOutlined /> 历史</span> },
        ]}
      />

      {activeTab === 'chat' ? (
        <>
          <div className="messages-container" aria-live="polite">
            {messages.length === 0 ? (
              <div className="welcome-message">
                <RobotOutlined className="welcome-icon" aria-hidden="true" />
                <div className="welcome-text">
                  <p><strong>告诉我你想完成什么</strong></p>
                  <p>{context?.projectId ? '我会只使用当前项目的资料、会话和审核记录。' : '我会先检索事实，再给出可确认的操作建议。'}</p>
                </div>
                <div className="quick-actions">
                  {quickActions.map((action) => (
                    <Button key={action} type="dashed" size="small" disabled={isLoading} onClick={() => sendMessage(action)}>
                      {action}
                    </Button>
                  ))}
                </div>
              </div>
            ) : messages.map((chatMessage) => (
              <div key={chatMessage.id} className={`message-wrapper ${chatMessage.role}`}>
                {chatMessage.role === 'assistant' && <div className="message-avatar"><RobotOutlined /></div>}
                <div className="message-content">
                  <AgentMessageRenderer message={chatMessage} />
                  {chatMessage.actionConfirm?.status === 'pending' && (
                    <AgentActionConfirm
                      action={chatMessage.actionConfirm}
                      applying={applyingMessageId === chatMessage.id}
                      onConfirm={(data) => handleActionConfirm(chatMessage.id, chatMessage.actionConfirm!, data)}
                      onCancel={() => cancelAction(chatMessage.id)}
                    />
                  )}
                  <div className="message-time">{new Date(chatMessage.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</div>
                </div>
              </div>
            ))}
            {isLoading && messages[messages.length - 1]?.content === '' && (
              <div className="thinking-indicator"><Spin size="small" /><span>正在检索并分析…</span></div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            <Text type="secondary" className="disclaimer">Agent 只在你确认后写入业务数据</Text>
            <div className="input-row">
              <Input
                value={inputValue}
                onChange={(event) => setInputValue(event.target.value)}
                placeholder={context?.projectId ? '例如：检查当前项目资料是否完整' : '输入你的审核问题'}
                onPressEnter={() => sendMessage()}
                disabled={isLoading}
                aria-label="向 Agent 提问"
                className="chat-input"
              />
              {isLoading ? (
                <Button type="primary" danger icon={<StopOutlined />} aria-label="停止生成" onClick={() => abortControllerRef.current?.abort()} className="send-btn" />
              ) : (
                <Button type="primary" icon={<SendOutlined />} aria-label="发送" onClick={() => sendMessage()} disabled={!inputValue.trim()} className="send-btn" />
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="history-container">
          <div className="history-search">
            <Input
              value={historyQuery}
              onChange={(event) => setHistoryQuery(event.target.value)}
              placeholder="搜索当前上下文的对话"
              prefix={<SearchOutlined />}
              allowClear
            />
          </div>
          {visibleConversations.length === 0 ? (
            <Empty description="当前项目暂无对话历史" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <List
              dataSource={visibleConversations}
              renderItem={(item) => (
                <List.Item
                  className="history-item"
                  onClick={() => { setConversationId(item.id); setMessages(item.messages); setActiveTab('chat') }}
                >
                  <List.Item.Meta title={item.title} description={item.lastMessage} />
                  <span className="history-time">{new Date(item.updatedAt).toLocaleDateString('zh-CN')}</span>
                </List.Item>
              )}
            />
          )}
        </div>
      )}
    </aside>
  )
}
