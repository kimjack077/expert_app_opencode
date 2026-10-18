import request from './request'

const API_BASE_URL =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : 'http://localhost:8000'

/**
 * 发送消息到 AI 助手 (SSE 流式响应)
 * @param {Object} params
 * @param {string} params.message - 用户消息
 * @param {Object} params.context - 上下文信息
 * @param {Array} params.conversation - 对话历史
 * @param {Function} onContent - 收到内容时的回调
 * @param {Function} onToolCall - 工具调用时的回调
 * @param {Function} onToolResult - 工具结果时的回调
 * @param {Function} onDone - 完成时的回调
 * @param {Function} onError - 错误时的回调
 * @returns {Promise<AbortController>} - 可用于取消请求
 */
export async function chatWithAgent({ message, context, conversation, onContent, onToolCall, onToolResult, onDone, onError }) {
  const token = localStorage.getItem('token')

  const response = await fetch(`${API_BASE_URL}/api/agent/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    },
    body: JSON.stringify({ message, context, conversation })
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '请求失败' }))
    onError?.(error.detail || '请求失败')
    return null
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const controller = new AbortController()

  // 异步处理流
  ;(async () => {
    let buffer = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6))
              switch (event.type) {
                case 'content':
                  onContent?.(event.content)
                  break
                case 'tool_call':
                  onToolCall?.(event.tool, event.status)
                  break
                case 'tool_result':
                  onToolResult?.(event.tool, event.status)
                  break
                case 'done':
                  onDone?.()
                  break
                case 'error':
                  onError?.(event.content)
                  break
              }
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        onError?.(e.message || '连接中断')
      }
    }
  })()

  return controller
}

/**
 * 获取企业检查前准备简报（阶段四：主动式搭档）
 * @param {string} enterpriseId - 企业ID
 */
export function getInspectionBriefing(enterpriseId, model) {
  return request.get(`/agent/briefing/${enterpriseId}`, {
    params: model ? { model } : {},
  })
}

/**
 * 流式生成企业检查准备简报。
 */
export async function streamInspectionBriefing(
  enterpriseId,
  model,
  { onMetadata, onContent, onDone },
) {
  const token = localStorage.getItem('token')
  const params = new URLSearchParams()
  if (model) params.set('model', model)
  const query = params.toString()
  const response = await fetch(
    `${API_BASE_URL}/api/agent/briefing/${enterpriseId}/stream${query ? `?${query}` : ''}`,
    {
      headers: {
        'Authorization': token ? `Bearer ${token}` : '',
        'Accept': 'text/event-stream',
      },
    },
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || '简报生成失败')
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
      const event = JSON.parse(line.slice(6))
      if (event.type === 'metadata') {
        onMetadata?.(event.data)
      } else if (event.type === 'content') {
        onContent?.(event.content)
      } else if (event.type === 'done') {
        onDone?.()
      } else if (event.type === 'error') {
        throw new Error(event.content || '简报生成失败')
      }
    }
  }
}

/**
 * 获取后端允许使用的 AI 模型列表。
 */
export function getAgentModels() {
  return request.get('/agent/models')
}

/**
 * 执行一条服务端已登记的动作提案。
 *
 * 安全边界：前端只回传「执行哪一条」(message_id + action_index)，
 * 不再回传「执行什么」——写入接口与请求体由服务端动作注册表决定。
 * overrides 仅允许 result / verdict / problem_description /
 * rectification_suggestion / comment，其余键会被服务端丢弃。
 *
 * @param {Object} params
 * @param {string} params.messageId - SSE conversation/action_proposal 事件里的 message_id
 * @param {number} [params.actionIndex] - 同一条消息内的提案序号，默认 0
 * @param {Object} [params.overrides] - 审核员确认前修改过的字段
 */
export function confirmAgentAction({ messageId, actionIndex = 0, overrides }) {
  return request.post('/agent/actions/confirm', {
    message_id: messageId,
    action_index: actionIndex,
    overrides: overrides && Object.keys(overrides).length > 0 ? overrides : undefined,
  })
}

/**
 * 获取服务端支持的动作列表，用于判断某张确认卡是否可一键执行。
 */
export function getAgentActionRegistry() {
  return request.get('/agent/actions/registry')
}

/**
 * 获取对话历史列表
 */
export function getConversations() {
  return request.get('/agent/conversations')
}

/**
 * 获取单个对话详情
 * @param {string} conversationId
 */
export function getConversation(conversationId) {
  return request.get(`/agent/conversations/${conversationId}`)
}

export default {
  chatWithAgent,
  getInspectionBriefing,
  streamInspectionBriefing,
  confirmAgentAction,
  getAgentActionRegistry,
  getConversations,
  getConversation,
}
