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

import { useAuthStore } from '@/stores/auth'
import AgentActionConfirm, { type AgentAction } from './AgentActionConfirm'
import AgentMessageRenderer from './AgentMessageRenderer'
import './AgentSidebar.css'
import './index.css'

const { Text } = Typography
const HISTORY_KEY = 'efis-agent-conversations-v2'
const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

/**
 * 服务端 `agent_actions` 注册表允许审核员在确认前覆写的字段。
 * 其余键（record_id / item_id / project_id 等定位字段）由服务端提案决定，
 * 客户端传了也会被丢弃，这里提前过滤以免产生"改了却没生效"的错觉。
 */
const OVERRIDABLE_FIELDS = new Set([
  'result',
  'verdict',
  'problem_description',
  'rectification_suggestion',
  'comment',
])

/** 卡片内部用驼峰展示，服务端只认下划线。 */
const OVERRIDE_ALIASES: Record<string, string> = {
  problemDescription: 'problem_description',
  rectificationSuggestion: 'rectification_suggestion',
}

/** 尚未进入服务端动作注册表、仍需走旧确认协议的动作。 */
const LEGACY_CONFIRM_ACTIONS = new Set(['submit_audit_evidence'])

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

let actionRegistryPromise: Promise<string[]> | null = null

/** 拉取一次服务端动作注册表并缓存；失败不缓存，下次确认时可重试。 */
const loadActionRegistry = async (token?: string | null): Promise<string[]> => {
  if (!actionRegistryPromise) {
    actionRegistryPromise = fetch(`${API_BASE_URL}/api/agent/actions/registry`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('registry'))))
      .then((body) => (Array.isArray(body?.data?.actions) ? body.data.actions.map(String) : []))
      .catch(() => {
        actionRegistryPromise = null
        return [] as string[]
      })
  }
  return actionRegistryPromise
}

const buildOverrides = (data?: Record<string, unknown>): Record<string, unknown> | undefined => {
  if (!data) return undefined
  const overrides: Record<string, unknown> = {}
  Object.entries(data).forEach(([key, value]) => {
    const field = OVERRIDE_ALIASES[key] || key
    if (OVERRIDABLE_FIELDS.has(field) && value !== undefined) overrides[field] = value
  })
  return Object.keys(overrides).length > 0 ? overrides : undefined
}

/** 仅接受同源相对路径，返回解析后的 URL（用于严格前缀校验）。 */
const parseRelativeEndpoint = (endpoint: string): URL | null => {
  if (!endpoint.startsWith('/')) return null
  try {
    const url = new URL(endpoint, window.location.origin)
    return url.origin === window.location.origin ? url : null
  } catch {
    return null
  }
}

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
      // 服务端在 conversation 事件里预告了本轮助手消息的 ID，
      // 动作提案就挂在这条消息上；确认时需要它来定位提案。
      let serverMessageId = ''
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
              if (event.message_id) serverMessageId = String(event.message_id)
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
              const messageId = String(event.message_id || proposal?.message_id || serverMessageId || '')
              const actionIndex = Number(event.action_index ?? proposal?.action_index ?? 0)
              updateAssistant(assistantId, (item) => ({
                ...item,
                actionConfirm: {
                  ...normalizeAction(proposal),
                  messageId: messageId || undefined,
                  actionIndex: Number.isFinite(actionIndex) ? actionIndex : 0,
                },
              }))
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

  /**
   * 走服务端动作注册表执行。客户端只回传「执行哪一条提案」
   * （message_id + action_index）以及白名单内的字段覆写，
   * 「执行什么」完全由服务端持久化的提案决定。
   */
  const confirmRegisteredAction = async (action: AgentAction, modifiedData?: Record<string, unknown>) => {
    if (!action.messageId) throw new Error('缺少提案定位信息，请重新向 Agent 提问后再确认')

    const overrides = buildOverrides(modifiedData)
    const response = await fetch(`${API_BASE_URL}/api/agent/actions/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        message_id: action.messageId,
        action_index: action.actionIndex ?? 0,
        ...(overrides ? { overrides } : {}),
      }),
    })

    const body = await response.json().catch(() => null)
    if (!response.ok) throw new Error(String(body?.detail || `执行失败（${response.status}）`))
    return body
  }

  /**
   * 旧的「模型自带 confirm_endpoint」协议，仅保留给尚未进入注册表的
   * submit_audit_evidence。校验：必须有当前项目上下文 + 同源相对路径 +
   * 严格前缀命中当前项目，任何一条不满足都直接拒绝执行。
   */
  const confirmLegacyAction = async (action: AgentAction, modifiedData?: Record<string, unknown>) => {
    const data = { ...action.data, ...(modifiedData || {}) }
    const projectId = String(context?.projectId || '')
    if (!UUID_PATTERN.test(projectId)) {
      throw new Error('缺少当前项目上下文，无法执行该操作')
    }

    const endpoint = String(data.confirm_endpoint || data.endpoint || '')
    const method = String(data.confirm_method || data.method || 'POST').toUpperCase()
    const url = parseRelativeEndpoint(endpoint)
    const allowedPrefix = `/api/audit-projects/${projectId}/`
    if (!url || !url.pathname.startsWith(allowedPrefix) || !['POST', 'PUT', 'PATCH'].includes(method)) {
      throw new Error('该建议没有可执行的受控写入协议')
    }

    const response = await fetch(`${API_BASE_URL}${url.pathname}${url.search}`, {
      method,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(data.confirm_payload || modifiedData || {}),
    })
    if (!response.ok) throw new Error(`执行失败（${response.status}）`)
  }

  /** 返回服务端提示语（幂等重复确认时会是「该操作已执行过」）。 */
  const persistAction = async (action: AgentAction, modifiedData?: Record<string, unknown>): Promise<string | undefined> => {
    const serverAction = String(action.serverAction || '')
    const registry = await loadActionRegistry(token)

    if (!registry.includes(serverAction) && LEGACY_CONFIRM_ACTIONS.has(serverAction)) {
      await confirmLegacyAction(action, modifiedData)
      return undefined
    }
    // 注册表拉取失败或动作暂未登记时，仍交由服务端裁决（未注册动作会被拒绝并返回原因）。
    const body = await confirmRegisteredAction(action, modifiedData)
    return body?.message ? String(body.message) : undefined
  }

  const handleActionConfirm = async (messageId: string, action: AgentAction, modifiedData?: Record<string, unknown>) => {
    setApplyingMessageId(messageId)
    try {
      const serverMessage = await persistAction(action, modifiedData)
      updateAssistant(messageId, (item) => ({
        ...item,
        actionConfirm: item.actionConfirm ? { ...item.actionConfirm, status: 'confirmed', data: { ...item.actionConfirm.data, ...(modifiedData || {}) } } : undefined,
      }))
      message.success(serverMessage || '操作已确认并写入系统')
      // BUG-25：Agent 确认写入后，宿主页面（如项目详情的会议/计划/团队面板）无感知，
      // 需手动刷新才能看到新数据。这里广播确认事件，由各面板监听并自行刷新。
      window.dispatchEvent(
        new CustomEvent('efis:action-confirmed', {
          detail: { serverAction: action.serverAction, actionType: action.type },
        }),
      )
    } catch (error) {
      const reason = (error as Error)?.message || '确认操作失败'
      updateAssistant(messageId, (item) => ({
        ...item,
        actionConfirm: item.actionConfirm
          ? {
              ...item.actionConfirm,
              status: 'failed',
              // 把服务端具体原因（如「该项目已存在首次会议记录…」）带到卡片内联展示，
              // 而不是只弹一个转瞬即逝的全局提示。
              data: { ...item.actionConfirm.data, failure_reason: reason },
            }
          : undefined,
      }))
      message.error(reason)
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
      <Tooltip title="打开智审 Agent" placement="left">
        <Button
          className="agent-sidebar-collapsed"
          type="primary"
          shape="circle"
          icon={<RobotOutlined />}
          aria-label="打开智审 Agent"
          onClick={() => setCollapsed(false)}
        />
      </Tooltip>
    )
  }

  return (
    <aside className="agent-sidebar" aria-label="智审 Agent">
      <div className="sidebar-header">
        <div className="header-title"><RobotOutlined className="header-icon" /><span>智审 Agent</span></div>
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
