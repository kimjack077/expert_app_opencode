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
  /** 服务端持久化提案的坐标，确认时回传这两个值即可。 */
  message_id?: string
  action_index?: number
}

export interface ChatCallbacks {
  /** conversation 事件同时预告本轮助手消息 ID（动作提案挂在这条消息上）。 */
  onConversation?: (conversationId: string, messageId?: string) => void
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
            callbacks.onConversation?.(event.conversation_id, event.message_id)
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

let actionRegistryPromise: Promise<string[]> | null = null

/**
 * 拉取服务端支持的 Agent 动作列表（GET /api/agent/actions/registry）。
 * 结果按模块级缓存，只请求一次；失败时不缓存，下次调用可重试。
 * 未登记的动作不提供一键写入，只能复制后手动填写。
 */
export function fetchActionRegistry(): Promise<string[]> {
  if (!actionRegistryPromise) {
    const token = useAuthStore.getState().token
    actionRegistryPromise = fetch('/api/agent/actions/registry', {
      headers: { Authorization: token ? `Bearer ${token}` : '' },
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

/**
 * 确认并执行一条动作提案（POST /api/agent/actions/confirm）。
 *
 * 客户端只说明「执行哪一条」（message_id + action_index），
 * 「执行什么」由服务端持久化的提案 + 动作注册表决定，
 * 因此这里不需要知道任何业务端点，也不区分 task-flow / record-flow。
 * `overrides` 仅 result / verdict / problem_description /
 * rectification_suggestion / comment 会被服务端采纳，其余键一律丢弃。
 * 接口是幂等的：重复确认返回首次结果。
 */
export async function confirmAgentAction(
  messageId: string,
  actionIndex: number,
  overrides?: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const token = useAuthStore.getState().token

  const response = await fetch('/api/agent/actions/confirm', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : '',
    },
    body: JSON.stringify({
      message_id: messageId,
      action_index: actionIndex,
      ...(overrides ? { overrides } : {}),
    }),
  })

  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(String(body?.detail || `执行失败（${response.status}）`))
  }
  return (body?.data || {}) as Record<string, unknown>
}
