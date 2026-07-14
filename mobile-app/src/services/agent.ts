import { useAuthStore } from '../stores/auth'

/**
 * AI 助手 SSE 客户端。
 *
 * 对接 POST /api/agent/chat（见 backend/app/routers/agent.py）。
 * 注意：`conversation_id` 是请求体的顶层字段（与 context 同级），不在 context 内部。
 */

export interface ChatContext {
  record_id?: string
  current_item_id?: string
  enterprise_id?: string
  media_file_id?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ActionProposalData {
  record_id?: string
  item_id?: string
  item_title?: string
  result?: string
  problem_description?: string
  rectification_suggestion?: string
  verdict?: string
  comment?: string
  [key: string]: unknown
}

export interface ActionProposalEvent {
  type: 'action_proposal'
  action: string
  status: 'pending'
  title: string
  data: ActionProposalData
}

export interface ChatCallbacks {
  onConversation?: (conversationId: string) => void
  onContent?: (content: string) => void
  onToolCall?: (tool: string, status: string) => void
  onToolResult?: (tool: string, status: string) => void
  onActionProposal?: (proposal: ActionProposalEvent) => void
  onDone?: () => void
  onError?: (message: string) => void
}

export interface ChatWithAgentParams {
  message: string
  context?: ChatContext
  conversation?: ChatMessage[]
  conversationId?: string
}

/**
 * 发送消息到 AI 助手 (SSE 流式响应)。
 *
 * 与 h5-app 的 api/agent.js 保持一致的回调风格，同时补充了 conversation /
 * action_proposal 事件（h5 端最新的 AgentChatPanel.vue 已支持，但旧版
 * api/agent.js 尚未跟进）。调用方需要自行创建 AbortController 并通过
 * `signal` 传入，取消请求时调用 controller.abort() 即可。
 */
export async function chatWithAgent(
  params: ChatWithAgentParams,
  callbacks: ChatCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const token = useAuthStore.getState().token

  const response = await fetch('/api/agent/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : '',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({
      message: params.message,
      context: params.context,
      conversation: params.conversation,
      conversation_id: params.conversationId,
    }),
    signal,
  })

  if (!response.ok) {
    let detail = '请求失败'
    try {
      const err = await response.json()
      detail = err?.detail || detail
    } catch {
      // ignore parse errors on error body
    }
    callbacks.onError?.(detail)
    return
  }

  if (!response.body) {
    callbacks.onError?.('无法读取响应')
    return
  }

  const reader = response.body.getReader()
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
        switch (event.type) {
          case 'conversation':
            callbacks.onConversation?.(event.conversation_id)
            break
          case 'content':
            callbacks.onContent?.(event.content)
            break
          case 'tool_call':
            callbacks.onToolCall?.(event.tool, event.status)
            break
          case 'tool_result':
            callbacks.onToolResult?.(event.tool, event.status)
            break
          case 'action_proposal':
            callbacks.onActionProposal?.(event as ActionProposalEvent)
            break
          case 'done':
            callbacks.onDone?.()
            break
          case 'error':
            callbacks.onError?.(event.content)
            break
          default:
            break
        }
      } catch {
        // 忽略解析错误
      }
    }
  }
}
