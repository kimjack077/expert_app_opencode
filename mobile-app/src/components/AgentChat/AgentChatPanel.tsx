import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Popup, Input, Button, Toast } from 'antd-mobile'
import {
  MessageOutline,
  SendOutline,
  StopOutline,
  AudioOutline,
  DownOutline,
} from 'antd-mobile-icons'
import AgentMessage from './AgentMessage'
import { chatWithAgent, confirmAgentAction, fetchActionRegistry } from '../../services/agent'
import type { ChatContext, ChatMessage as AgentChatMessage, ActionProposalEvent } from '../../services/agent'
import type { ActionProposalState, AgentChatContext, ChatMessageState } from './types'
import './AgentChatPanel.css'

// 极简语音识别类型声明（浏览器原生 Web Speech API，DOM lib 未内置）。
interface SpeechRecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((event: any) => void) | null
  onerror: ((event: any) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike

const SpeechRecognitionImpl: SpeechRecognitionCtor | undefined =
  (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
const SPEECH_SUPPORTED = !!SpeechRecognitionImpl

export interface AgentResultAppliedPayload {
  itemId?: string
  result?: string
  problemDescription?: string
  rectificationSuggestion?: string
}

interface AgentChatPanelProps {
  visible: boolean
  onClose: () => void
  context: AgentChatContext
  onResultApplied?: (payload: AgentResultAppliedPayload) => void
}

const buildActionProposal = (
  event: ActionProposalEvent,
  fallbackMessageId?: string
): ActionProposalState => {
  const coords = {
    action: event.action,
    messageId: event.message_id || fallbackMessageId,
    actionIndex: event.action_index ?? 0,
  }

  if (event.action === 'apply_check_result') {
    return {
      ...coords,
      type: 'judgment',
      title: event.title || '建议记录检查结果',
      status: 'pending',
      data: {
        recordId: event.data.record_id,
        itemId: event.data.item_id,
        checkItem: event.data.item_title,
        result: event.data.result,
        problemDescription: event.data.problem_description,
        rectificationSuggestion: event.data.rectification_suggestion,
      },
    }
  }
  if (event.action === 'apply_final_verdict') {
    return {
      ...coords,
      type: 'final_verdict',
      title: event.title || '建议记录最终判定',
      status: 'pending',
      data: {
        recordId: event.data.record_id,
        verdict: event.data.verdict,
        comment: event.data.comment,
      },
    }
  }
  return {
    ...coords,
    type: 'operation',
    title: event.title || '建议操作',
    status: 'pending',
    data: event.data || {},
  }
}

const appliedToastText = (action: string) => {
  if (action === 'apply_check_result') return '已填写检查结果'
  if (action === 'apply_final_verdict') return '已填写最终判定'
  return '操作已执行'
}

let messageSeq = 0
const nextId = (prefix: string) => `${prefix}-${Date.now()}-${messageSeq++}`

const AgentChatPanel: React.FC<AgentChatPanelProps> = ({
  visible,
  onClose,
  context,
  onResultApplied,
}) => {
  const [messages, setMessages] = useState<ChatMessageState[]>([])
  const [inputText, setInputText] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [isListening, setIsListening] = useState(false)
  // 服务端支持一键执行的动作；不在表内的提案只提供复制，不提供"采纳并填写"。
  const [registeredActions, setRegisteredActions] = useState<string[]>([])

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const conversationIdRef = useRef<string | undefined>(undefined)
  const serverMessageIdRef = useRef<string | undefined>(undefined)
  const recognizerRef = useRef<SpeechRecognitionLike | null>(null)
  const autoTriggeredMediaIdRef = useRef<string | undefined>(undefined)

  useEffect(() => {
    if (!visible) return
    let cancelled = false
    void fetchActionRegistry().then((actions) => {
      if (!cancelled) setRegisteredActions(actions)
    })
    return () => {
      cancelled = true
    }
  }, [visible])

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const buildContextPayload = useCallback(
    (): ChatContext => ({
      record_id: context.recordId,
      current_item_id: context.currentItemId,
      enterprise_id: context.enterpriseId,
      media_file_id: context.mediaFileId || undefined,
    }),
    [context.recordId, context.currentItemId, context.enterpriseId, context.mediaFileId]
  )

  const sendMessage = useCallback(
    async (text?: string) => {
      const content = (text ?? inputText).trim()
      if (!content || isThinking) return

      const userMessage: ChatMessageState = {
        id: nextId('user'),
        role: 'user',
        content,
        timestamp: Date.now(),
      }
      const assistantId = nextId('assistant')
      const assistantMessage: ChatMessageState = {
        id: assistantId,
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
        toolCalls: [],
      }

      const history: AgentChatMessage[] = messages.map((m) => ({ role: m.role, content: m.content }))

      setMessages((prev) => [...prev, userMessage, assistantMessage])
      setInputText('')
      setIsThinking(true)

      const controller = new AbortController()
      abortControllerRef.current = controller

      try {
        await chatWithAgent(
          {
            message: content,
            context: buildContextPayload(),
            conversation: history,
            conversationId: conversationIdRef.current,
          },
          {
            onConversation: (id, serverMessageId) => {
              conversationIdRef.current = id
              serverMessageIdRef.current = serverMessageId
            },
            onContent: (chunk) => {
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + chunk } : m))
              )
            },
            onToolCall: (tool) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, toolCalls: [...(m.toolCalls || []), { name: tool, status: 'calling' }] }
                    : m
                )
              )
            },
            onToolResult: (tool) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: (m.toolCalls || []).map((t) =>
                          t.name === tool ? { ...t, status: 'done' } : t
                        ),
                      }
                    : m
                )
              )
            },
            onActionProposal: (event) => {
              const proposal = buildActionProposal(event, serverMessageIdRef.current)
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, actionProposal: proposal } : m))
              )
            },
            onDone: () => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId && m.toolCalls && m.toolCalls.length > 0
                    ? { ...m, toolCalls: [] }
                    : m
                )
              )
            },
            onError: (message) => {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: `抱歉，发生了错误：${message}` } : m
                )
              )
            },
          },
          controller.signal
        )
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: `${m.content}\n\n[已停止生成]` } : m
            )
          )
        } else {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: '抱歉，AI 服务暂时不可用，请稍后再试。' } : m
            )
          )
        }
      } finally {
        setIsThinking(false)
        abortControllerRef.current = null
      }
    },
    [inputText, isThinking, messages, buildContextPayload]
  )

  useEffect(() => {
    if (!visible) return
    if (context.mediaFileId && autoTriggeredMediaIdRef.current !== context.mediaFileId) {
      autoTriggeredMediaIdRef.current = context.mediaFileId
      void sendMessage('帮我看看这张照片有没有问题')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, context.mediaFileId])

  const stopGeneration = () => {
    abortControllerRef.current?.abort()
  }

  const toggleVoiceInput = () => {
    if (!SpeechRecognitionImpl) return

    if (isListening) {
      recognizerRef.current?.stop()
      return
    }

    const recognizer = new SpeechRecognitionImpl()
    recognizer.lang = 'zh-CN'
    recognizer.continuous = false
    recognizer.interimResults = true

    recognizer.onresult = (event: any) => {
      let transcript = ''
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript
      }
      // 识别结果先填入输入框让用户确认/编辑，不直接发送
      setInputText(transcript)
    }

    recognizer.onerror = () => {
      setIsListening(false)
      Toast.show({ content: '语音识别失败，请重试或手动输入' })
    }

    recognizer.onend = () => {
      setIsListening(false)
    }

    recognizerRef.current = recognizer
    setIsListening(true)
    recognizer.start()
  }

  const quickActions = useMemo(() => {
    const actions: string[] = []
    if (context.mediaFileId) actions.push('帮我看看这张照片有没有问题')
    if (context.currentItemTitle) {
      actions.push('这项怎么查？')
      actions.push('帮我判断合不合格')
    } else {
      actions.push('今天的检查还有哪些没做完？')
    }
    if (context.recordId) actions.push('生成最终判定')
    return actions
  }, [context.mediaFileId, context.currentItemTitle, context.recordId])

  /** 只有服务端注册表登记过的动作才允许一键写入，其余保持"复制后手填"。 */
  const isActionWritable = useCallback(
    (action: ActionProposalState) => !!action.messageId && registeredActions.includes(action.action),
    [registeredActions]
  )

  /**
   * 一键执行：只回传 (message_id, action_index)，由服务端动作注册表
   * 决定写哪张表、写什么。页面走 task-flow 还是 record-flow 不再影响这里。
   */
  const handleConfirmAction = async (messageId: string, action: ActionProposalState) => {
    if (!isActionWritable(action) || !action.messageId) return

    try {
      await confirmAgentAction(action.messageId, action.actionIndex)

      if (action.type === 'judgment') {
        onResultApplied?.({
          itemId: action.data.itemId,
          result: action.data.result,
          problemDescription: action.data.problemDescription,
          rectificationSuggestion: action.data.rectificationSuggestion,
        })
      }
      Toast.show({ icon: 'success', content: appliedToastText(action.action) })

      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId && m.actionProposal
            ? { ...m, actionProposal: { ...m.actionProposal, status: 'confirmed' } }
            : m
        )
      )
    } catch (err) {
      Toast.show({
        icon: 'fail',
        content: err instanceof Error && err.message ? err.message : '填写失败，请手动填写',
      })
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId && m.actionProposal
            ? { ...m, actionProposal: { ...m.actionProposal, status: 'failed' } }
            : m
        )
      )
    }
  }

  const handleCancelAction = (messageId: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId && m.actionProposal
          ? { ...m, actionProposal: { ...m.actionProposal, status: 'cancelled' } }
          : m
      )
    )
  }

  return (
    <Popup
      visible={visible}
      onMaskClick={onClose}
      onClose={onClose}
      position="bottom"
      bodyStyle={{
        height: '58vh',
        borderTopLeftRadius: '16px',
        borderTopRightRadius: '16px',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <div className="agent-chat-panel">
        <div className="panel-header">
          <div className="drag-indicator" />
          <div className="header-content">
            <div className="header-left">
              <MessageOutline fontSize={20} color="#1677ff" />
              <span className="header-title">检查助手</span>
            </div>
            <DownOutline fontSize={20} color="#999" onClick={onClose} />
          </div>
        </div>

        <div className="messages-container">
          {messages.length === 0 && (
            <div className="welcome-message">
              <div className="welcome-icon">🤖</div>
              <div className="welcome-text">
                <p>你好！正在检查</p>
                {context.currentItemTitle && (
                  <p className="current-item">「{context.currentItemTitle}」</p>
                )}
                <p>有什么可以帮你的？</p>
              </div>
            </div>
          )}

          {messages.map((message) => (
            <AgentMessage
              key={message.id}
              message={message}
              advisoryOnly={!!message.actionProposal && !isActionWritable(message.actionProposal)}
              onConfirmAction={() => message.actionProposal && handleConfirmAction(message.id, message.actionProposal)}
              onCancelAction={() => handleCancelAction(message.id)}
            />
          ))}

          {isThinking && (
            <div className="thinking-indicator">
              <div className="thinking-dots">
                <span />
                <span />
                <span />
              </div>
              <span className="thinking-text">正在思考中...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {!isThinking && messages.length === 0 && (
          <div className="quick-actions">
            {quickActions.map((action) => (
              <span key={action} className="quick-action-tag" onClick={() => sendMessage(action)}>
                {action}
              </span>
            ))}
          </div>
        )}

        <div className="input-area">
          <div className="disclaimer">AI 建议仅供参考，请以专业判断为准</div>
          {isListening && (
            <div className="listening-hint">
              <AudioOutline fontSize={14} color="#1677ff" />
              <span>正在听...点击麦克风结束</span>
            </div>
          )}
          <div className="input-row">
            <Input
              value={inputText}
              onChange={setInputText}
              placeholder="输入你的问题，或点击麦克风说话..."
              disabled={isThinking}
              onEnterPress={() => sendMessage()}
              className="chat-input"
            />
            {SPEECH_SUPPORTED && (
              <Button
                shape="rounded"
                color={isListening ? 'danger' : 'default'}
                disabled={isThinking}
                onClick={toggleVoiceInput}
                className="voice-btn"
              >
                {isListening ? <StopOutline fontSize={18} /> : <AudioOutline fontSize={18} />}
              </Button>
            )}
            {isThinking ? (
              <Button color="danger" shape="rounded" onClick={stopGeneration} className="send-btn">
                <StopOutline fontSize={18} />
              </Button>
            ) : (
              <Button
                color="primary"
                shape="rounded"
                disabled={!inputText.trim()}
                onClick={() => sendMessage()}
                className="send-btn"
              >
                <SendOutline fontSize={18} />
              </Button>
            )}
          </div>
        </div>
      </div>
    </Popup>
  )
}

export default AgentChatPanel
