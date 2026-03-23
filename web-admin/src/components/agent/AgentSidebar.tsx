import { useState, useRef, useEffect, useCallback } from 'react'
import { Badge, Button, Input, Spin, Tabs, List, Empty, Tooltip } from 'antd'
import {
  RobotOutlined,
  SendOutlined,
  CloseOutlined,
  HistoryOutlined,
  MessageOutlined,
  ReloadOutlined,
  StopOutlined,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import AgentMessageRenderer from './AgentMessageRenderer'
import AgentActionConfirm from './AgentActionConfirm'
import { useAuthStore } from '@/stores/auth'
import './AgentSidebar.css'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  toolCalls?: ToolCall[]
  actionConfirm?: ActionConfirm
  citations?: Citation[]
}

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

interface Conversation {
  id: string
  title: string
  lastMessage: string
  updatedAt: string
}

interface AgentSidebarProps {
  context?: {
    page?: string
    enterpriseId?: string
    enterpriseName?: string
    recordId?: string
    templateId?: string
  }
}

export default function AgentSidebar({ context }: AgentSidebarProps) {
  const [collapsed, setCollapsed] = useState(true)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'chat' | 'history'>('chat')
  const [conversations, setConversations] = useState<Conversation[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const token = useAuthStore((state) => state.token)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const quickActions = [
    { text: '查看企业风险画像', action: () => sendMessage('查看该企业的风险画像') },
    { text: '准备下次检查', action: () => sendMessage('帮我准备下次检查') },
    { text: '查看历史记录', action: () => sendMessage('查看该企业的历史检查记录') },
  ]

  const sendMessage = async (text?: string) => {
    const messageText = text || inputValue.trim()
    if (!messageText || isLoading) return

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: messageText,
      timestamp: Date.now(),
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    const assistantMessage: Message = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      toolCalls: [],
    }

    setMessages(prev => [...prev, assistantMessage])

    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({
          message: messageText,
          context: {
            enterprise_id: context?.enterpriseId,
            record_id: context?.recordId,
          },
          conversation: messages.map(m => ({
            role: m.role,
            content: m.content,
          })),
        }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error('请求失败')
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('无法读取响应')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              setMessages(prev => {
                const newMessages = [...prev]
                const lastMsg = newMessages[newMessages.length - 1]

                if (data.type === 'content') {
                  lastMsg.content += data.content
                } else if (data.type === 'tool_call') {
                  lastMsg.toolCalls = [
                    ...(lastMsg.toolCalls || []),
                    { name: data.tool, status: 'calling' },
                  ]
                } else if (data.type === 'tool_result') {
                  lastMsg.toolCalls = lastMsg.toolCalls?.map(t =>
                    t.name === data.tool ? { ...t, status: 'done' } : t
                  )
                } else if (data.type === 'action_confirm') {
                  lastMsg.actionConfirm = data.action
                } else if (data.type === 'error') {
                  lastMsg.content = `抱歉，发生了错误：${data.content}`
                }

                return newMessages
              })
            } catch {
              // ignore parse errors
            }
          }
        }
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        setMessages(prev => {
          const newMessages = [...prev]
          const lastMsg = newMessages[newMessages.length - 1]
          lastMsg.content = '抱歉，AI 服务暂时不可用，请稍后再试。'
          return newMessages
        })
      }
    } finally {
      setIsLoading(false)
      abortControllerRef.current = null
    }
  }

  const stopGeneration = () => {
    abortControllerRef.current?.abort()
    setIsLoading(false)
  }

  const handleActionConfirm = (actionId: string, result: 'confirmed' | 'cancelled', modifiedData?: Record<string, unknown>) => {
    setMessages(prev => prev.map(msg => {
      if (msg.actionConfirm && msg.id === actionId) {
        return {
          ...msg,
          actionConfirm: {
            ...msg.actionConfirm,
            status: result,
            data: modifiedData || msg.actionConfirm.data,
          },
        }
      }
      return msg
    }))
  }

  const startNewConversation = () => {
    setMessages([])
    setActiveTab('chat')
  }

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  if (collapsed) {
    return (
      <div className="agent-sidebar-collapsed" onClick={() => setCollapsed(false)}>
        <Tooltip title="智检助手" placement="left">
          <div className="collapsed-icon">
            <RobotOutlined />
          </div>
        </Tooltip>
        <Badge count={0} dot offset={[-5, 5]}>
          <div className="collapsed-expand">
            <span onClick={(e) => { e.stopPropagation(); setCollapsed(false) }}>»</span>
          </div>
        </Badge>
      </div>
    )
  }

  return (
    <div className="agent-sidebar">
      <div className="sidebar-header">
        <div className="header-title">
          <RobotOutlined className="header-icon" />
          <span>智检助手</span>
        </div>
        <div className="header-actions">
          <Tooltip title="新对话">
            <Button type="text" size="small" icon={<PlusOutlined />} onClick={startNewConversation} />
          </Tooltip>
          <Tooltip title="收起">
            <Button type="text" size="small" icon={<CloseOutlined />} onClick={() => setCollapsed(true)} />
          </Tooltip>
        </div>
      </div>

      {context?.enterpriseName && (
        <div className="context-bar">
          <span className="context-label">当前企业：</span>
          <span className="context-value">{context.enterpriseName}</span>
        </div>
      )}

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as 'chat' | 'history')}
        className="sidebar-tabs"
        items={[
          {
            key: 'chat',
            label: (
              <span>
                <MessageOutlined /> 对话
              </span>
            ),
          },
          {
            key: 'history',
            label: (
              <span>
                <HistoryOutlined /> 历史
              </span>
            ),
          },
        ]}
      />

      {activeTab === 'chat' ? (
        <>
          <div className="messages-container">
            {messages.length === 0 ? (
              <div className="welcome-message">
                <div className="welcome-icon">🤖</div>
                <div className="welcome-text">
                  <p>你好！我是智检助手</p>
                  {context?.enterpriseName && (
                    <p className="context-info">当前正在查看：{context.enterpriseName}</p>
                  )}
                  <p>有什么可以帮你的？</p>
                </div>
                <div className="quick-actions">
                  {quickActions.map((action, index) => (
                    <Button
                      key={index}
                      type="dashed"
                      size="small"
                      onClick={action.action}
                      disabled={isLoading}
                    >
                      {action.text}
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <div key={message.id} className={`message-wrapper ${message.role}`}>
                  {message.role === 'assistant' && (
                    <div className="message-avatar">
                      <RobotOutlined />
                    </div>
                  )}
                  <div className="message-content">
                    <AgentMessageRenderer message={message} />
                    {message.actionConfirm && message.actionConfirm.status === 'pending' && (
                      <AgentActionConfirm
                        action={message.actionConfirm}
                        onConfirm={(data) => handleActionConfirm(message.id, 'confirmed', data)}
                        onCancel={() => handleActionConfirm(message.id, 'cancelled')}
                      />
                    )}
                    <div className="message-time">{formatTime(message.timestamp)}</div>
                  </div>
                </div>
              ))
            )}
            {isLoading && messages[messages.length - 1]?.content === '' && (
              <div className="thinking-indicator">
                <Spin size="small" />
                <span>思考中...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            <div className="disclaimer">AI 建议仅供参考，请以专业判断为准</div>
            <div className="input-row">
              <Input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="输入你的问题..."
                onPressEnter={() => sendMessage()}
                disabled={isLoading}
                className="chat-input"
              />
              {isLoading ? (
                <Button
                  type="primary"
                  danger
                  icon={<StopOutlined />}
                  onClick={stopGeneration}
                  className="send-btn"
                />
              ) : (
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={() => sendMessage()}
                  disabled={!inputValue.trim()}
                  className="send-btn"
                />
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="history-container">
          <div className="history-search">
            <Input
              placeholder="搜索对话历史..."
              prefix={<SearchOutlined />}
              allowClear
            />
          </div>
          {conversations.length === 0 ? (
            <Empty description="暂无对话历史" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <List
              dataSource={conversations}
              renderItem={(item) => (
                <List.Item className="history-item" onClick={() => setActiveTab('chat')}>
                  <List.Item.Meta
                    title={item.title}
                    description={item.lastMessage}
                  />
                  <span className="history-time">{item.updatedAt}</span>
                </List.Item>
              )}
            />
          )}
        </div>
      )}
    </div>
  )
}