<template>
  <van-popup
    v-model:show="visible"
    position="bottom"
    :style="{ height: '55%', borderRadius: '16px 16px 0 0' }"
    @close="handleClose"
  >
    <div class="chat-panel">
      <div class="panel-header">
        <div class="drag-indicator"></div>
        <div class="header-content">
          <div class="header-left">
            <van-icon name="service-o" size="20" color="#1677FF" />
            <span class="header-title">智审 Agent</span>
          </div>
          <van-icon name="arrow-down" size="20" color="#999" @click="handleClose" />
        </div>
      </div>

      <div class="messages-container" ref="messagesRef">
        <div v-if="messages.length === 0" class="welcome-message">
          <div class="welcome-icon">🤖</div>
          <div class="welcome-text">
            <p>你好！正在检查</p>
            <p class="current-item">「{{ context.currentItemTitle || '检查项' }}」</p>
            <p>有什么可以帮你的？</p>
          </div>
        </div>

        <AgentMessage
          v-for="(msg, index) in messages"
          :key="index"
          :message="msg"
          @confirm-action="handleConfirmAction(index, $event)"
          @cancel-action="handleCancelAction(index, $event)"
        />

        <div v-if="isThinking" class="thinking-indicator">
          <div class="thinking-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span class="thinking-text">正在思考中...</span>
        </div>
      </div>

      <div class="quick-actions" v-if="!isThinking && messages.length === 0">
        <van-tag
          v-for="action in quickActions"
          :key="action.text"
          type="primary"
          plain
          size="medium"
          round
          @click="sendQuickAction(action.text)"
        >
          {{ action.text }}
        </van-tag>
      </div>

      <div class="input-area">
        <div class="disclaimer">⚠️ AI 建议仅供参考，请以专业判断为准</div>
        <div v-if="isListening" class="listening-hint">
          <van-icon name="volume-o" size="14" color="#1677FF" />
          <span>正在听...点击麦克风结束</span>
        </div>
        <div class="input-row">
          <van-field
            v-model="inputText"
            placeholder="输入你的问题，或点击麦克风说话..."
            :disabled="isThinking"
            @keyup.enter="sendMessage"
            class="input-field"
          />
          <van-button
            v-if="speechSupported"
            :type="isListening ? 'danger' : 'default'"
            round
            :disabled="isThinking"
            @click="toggleVoiceInput"
            class="voice-btn"
          >
            <van-icon :name="isListening ? 'pause-circle-o' : 'mic-o'" size="18" />
          </van-button>
          <van-button
            v-if="!isThinking"
            type="primary"
            round
            :disabled="!inputText.trim()"
            @click="sendMessage"
            class="send-btn"
          >
            <van-icon name="send-o" size="18" />
          </van-button>
          <van-button
            v-else
            type="danger"
            round
            @click="stopGeneration"
            class="stop-btn"
          >
            <van-icon name="stop-circle-o" size="18" />
          </van-button>
        </div>
      </div>
    </div>
  </van-popup>
</template>

<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import AgentMessage from './AgentMessage.vue'
import { confirmAgentAction, getAgentActionRegistry } from '../../api/agent'

const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  context: {
    type: Object,
    default: () => ({
      recordId: '',
      currentItemTitle: '',
      currentItemId: '',
      enterpriseId: '',
      mediaFileId: '',
      projectId: '',
      auditSessionId: '',
      sessionId: '',
      planItemId: ''
    })
  }
})

const emit = defineEmits(['update:show', 'result-applied', 'verdict-applied', 'project-action-applied'])

const visible = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val)
})

const messages = ref([])
const inputText = ref('')
const isThinking = ref(false)
const messagesRef = ref(null)
const currentStreamContent = ref('')
const abortController = ref(null)
const conversationId = ref(null)
// 服务端本轮助手消息的 ID：确认动作时只回传 (message_id, action_index)
const currentMessageId = ref(null)

// 语音输入（现场审核员戴手套/环境嘈杂时的降门槛入口）
const SpeechRecognitionApi = window.SpeechRecognition || window.webkitSpeechRecognition
const speechSupported = !!SpeechRecognitionApi
const isListening = ref(false)
let recognizer = null

const toggleVoiceInput = () => {
  if (!speechSupported) return

  if (isListening.value) {
    recognizer?.stop()
    return
  }

  recognizer = new SpeechRecognitionApi()
  recognizer.lang = 'zh-CN'
  recognizer.continuous = false
  recognizer.interimResults = true

  recognizer.onresult = (event) => {
    let transcript = ''
    for (let i = 0; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript
    }
    // 识别结果先填入输入框让用户确认/编辑，不直接发送
    inputText.value = transcript
  }

  recognizer.onerror = () => {
    isListening.value = false
    showToast('语音识别失败，请重试或手动输入')
  }

  recognizer.onend = () => {
    isListening.value = false
  }

  isListening.value = true
  recognizer.start()
}

// 快捷指令根据当前上下文动态调整，减少审核员打字
const quickActions = computed(() => {
  const actions = []

  if (props.context.mediaFileId) {
    actions.push({ text: '帮我看看这张照片有没有问题' })
  }
  if (props.context.currentItemTitle) {
    actions.push({ text: '这项怎么查？' })
    actions.push({ text: '帮我判断合不合格' })
  } else {
    actions.push({ text: '今天的检查还有哪些没做完？' })
  }
  if (props.context.recordId) {
    actions.push({ text: '生成最终判定' })
  }

  return actions
})

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

const handleClose = () => {
  visible.value = false
}

const sendQuickAction = (text) => {
  inputText.value = text
  sendMessage()
}

const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || isThinking.value) return

  messages.value.push({
    role: 'user',
    content: text,
    timestamp: Date.now()
  })
  
  inputText.value = ''
  scrollToBottom()

  await streamChat(text)
}

const streamChat = async (message) => {
  isThinking.value = true
  currentStreamContent.value = ''
  currentMessageId.value = null

  const messageIndex = messages.value.length
  messages.value.push({
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    toolCalls: []
  })
  scrollToBottom()

  abortController.value = new AbortController()

  try {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/api/agent/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({
        message,
        context: {
          record_id: props.context.recordId,
          current_item_id: props.context.currentItemId,
          enterprise_id: props.context.enterpriseId,
          media_file_id: props.context.mediaFileId || undefined,
          project_id: props.context.projectId || undefined,
          audit_session_id: props.context.auditSessionId || props.context.sessionId || undefined,
          plan_item_id: props.context.planItemId || undefined
        },
        conversation: messages.value.slice(0, -1).map(m => ({
          role: m.role,
          content: m.content
        })),
        conversation_id: conversationId.value || undefined
      }),
      signal: abortController.value.signal
    })

    if (!response.ok) {
      throw new Error('请求失败')
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
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))

            if (data.type === 'conversation') {
              conversationId.value = data.conversation_id
              currentMessageId.value = data.message_id || null
            } else if (data.type === 'content') {
              // Use reactive update by assigning to the array element
              messages.value[messageIndex] = {
                ...messages.value[messageIndex],
                content: messages.value[messageIndex].content + data.content
              }
              scrollToBottom()
            } else if (data.type === 'tool_call') {
              const currentMsg = messages.value[messageIndex]
              messages.value[messageIndex] = {
                ...currentMsg,
                toolCalls: [...(currentMsg.toolCalls || []), {
                  name: data.tool,
                  status: data.status
                }]
              }
              scrollToBottom()
            } else if (data.type === 'tool_result') {
              const currentMsg = messages.value[messageIndex]
              const toolCalls = (currentMsg.toolCalls || []).map(t =>
                t.name === data.tool ? { ...t, status: 'done' } : t
              )
              messages.value[messageIndex] = { ...currentMsg, toolCalls }
            } else if (data.type === 'action_proposal') {
              const currentMsg = messages.value[messageIndex]
              messages.value[messageIndex] = {
                ...currentMsg,
                actionProposal: buildActionProposal(data)
              }
              scrollToBottom()
            } else if (data.type === 'done') {
              const currentMsg = messages.value[messageIndex]
              if (currentMsg.toolCalls && currentMsg.toolCalls.length > 0) {
                messages.value[messageIndex] = { ...currentMsg, toolCalls: [] }
              }
            } else if (data.type === 'error') {
              messages.value[messageIndex] = {
                ...messages.value[messageIndex],
                content: data.content || 'AI 助手暂时无法完成这次请求，请稍后重试。'
              }
            }
          } catch (e) {
            console.error('解析数据失败:', e)
          }
        }
      }
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      messages.value[messageIndex] = {
        ...messages.value[messageIndex],
        content: messages.value[messageIndex].content + '\n\n[已停止生成]'
      }
    } else {
      console.error('Stream error:', error)
      messages.value[messageIndex] = {
        ...messages.value[messageIndex],
        content: '抱歉，AI 服务暂时不可用，请稍后再试。'
      }
    }
  } finally {
    isThinking.value = false
    abortController.value = null
    scrollToBottom()
  }
}

const stopGeneration = () => {
  if (abortController.value) {
    abortController.value.abort()
  }
}

// 服务端动作注册表尚未收录的动作，仍走旧的直连写入路径。
// 注册表取不到时用这份兜底名单。
const LEGACY_ACTIONS = ['submit_audit_evidence']

const registryActions = ref(null)

/** 懒加载服务端动作注册表：注册表收录的动作走统一确认接口 */
const loadActionRegistry = async () => {
  if (registryActions.value) return registryActions.value
  try {
    const res = await getAgentActionRegistry()
    const actions = res?.data?.actions
    if (Array.isArray(actions)) {
      registryActions.value = actions
    }
  } catch (error) {
    console.warn('获取动作注册表失败，按兜底名单处理', error)
  }
  return registryActions.value
}

const buildActionProposal = (data) => {
  // 动作提案的执行凭据：服务端持久化了提案内容，前端只记住「哪一条」
  const ref_ = {
    action: data.action || '',
    messageId: data.message_id || currentMessageId.value || '',
    actionIndex: typeof data.action_index === 'number' ? data.action_index : 0
  }

  if (data.action === 'apply_check_result') {
    return {
      ...ref_,
      type: 'judgment',
      title: '建议记录检查结果',
      status: 'pending',
      data: {
        recordId: data.data.record_id,
        itemId: data.data.item_id,
        checkItem: data.data.item_title,
        result: data.data.result,
        problemDescription: data.data.problem_description,
        rectificationSuggestion: data.data.rectification_suggestion
      }
    }
  }
  if (data.action === 'apply_final_verdict') {
    return {
      ...ref_,
      type: 'final_verdict',
      title: '建议记录最终判定',
      status: 'pending',
      data: {
        recordId: data.data.record_id,
        verdict: data.data.verdict,
        comment: data.data.comment
      }
    }
  }
  return {
    ...ref_,
    type: 'operation',
    title: data.title || '建议操作',
    status: 'pending',
    data: data.data || {}
  }
}

/**
 * 审核员在卡片上确认的内容。服务端只接受这几个可覆写字段，
 * 保证「写到哪条记录」由服务端提案决定，前端改不了定位字段。
 */
const buildOverrides = (action) => {
  const data = action.data || {}
  if (action.type === 'judgment') {
    return {
      result: data.result,
      problem_description: data.problemDescription || '',
      rectification_suggestion: data.rectificationSuggestion || ''
    }
  }
  if (action.type === 'final_verdict') {
    return {
      verdict: data.verdict,
      comment: data.comment || ''
    }
  }
  return {}
}

/**
 * 旧路径：submit_audit_evidence 尚未进入服务端动作注册表，
 * 暂时保留受当前项目约束的直连写入。其余动作一律走 /api/agent/actions/confirm。
 */
const executeLegacyProjectAction = async (action) => {
  const data = action.data || {}
  const projectId = String(data.project_id || props.context.projectId || '')
  const endpoint = String(data.confirm_endpoint || data.endpoint || '')
  const method = String(data.confirm_method || data.method || 'POST').toUpperCase()
  const expectedPrefix = `/api/audit-projects/${projectId}/`

  if (!projectId || projectId !== String(props.context.projectId || '') || !endpoint.startsWith(expectedPrefix) || !['POST', 'PUT', 'PATCH'].includes(method)) {
    throw new Error('该确认卡缺少受当前项目约束的写入协议')
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
    },
    body: JSON.stringify(data.confirm_payload || {})
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok || (payload && payload.code && payload.code >= 400)) {
    throw new Error(payload?.detail?.message || payload?.detail || payload?.message || '确认写入失败')
  }
  return payload?.data || payload
}

const handleConfirmAction = async (messageIndex, action) => {
  const currentMsg = messages.value[messageIndex]

  try {
    let result = null

    const registry = await loadActionRegistry()
    const serverExecutable = registry
      ? registry.includes(action.action)
      : !LEGACY_ACTIONS.includes(action.action)

    if (!serverExecutable) {
      result = await executeLegacyProjectAction(action)
    } else {
      if (!action.messageId) {
        throw new Error('该确认卡缺少服务端动作标识，无法执行')
      }
      const res = await confirmAgentAction({
        messageId: action.messageId,
        actionIndex: action.actionIndex,
        overrides: buildOverrides(action)
      })
      if (res?.code && res.code >= 400) {
        throw new Error(res.detail || res.message || '确认写入失败')
      }
      result = res?.data || null
    }

    if (action.type === 'judgment') {
      emit('result-applied', {
        itemId: action.data.itemId,
        result: action.data.result,
        problemDescription: action.data.problemDescription,
        rectificationSuggestion: action.data.rectificationSuggestion
      })
      showSuccessToast('已填写检查结果')
    } else if (action.type === 'final_verdict') {
      emit('verdict-applied', {
        verdict: action.data.verdict,
        comment: action.data.comment
      })
      showSuccessToast('已填写最终判定')
    } else {
      emit('project-action-applied', { action: action.data || {}, result })
      showSuccessToast('已确认并写入当前审核项目')
    }

    messages.value[messageIndex] = {
      ...currentMsg,
      actionProposal: { ...action, status: 'confirmed' }
    }
  } catch (error) {
    console.error('采纳建议失败:', error)
    showFailToast('填写失败，请手动填写')
    messages.value[messageIndex] = {
      ...currentMsg,
      actionProposal: { ...action, status: 'failed' }
    }
  }
}

const handleCancelAction = (messageIndex, action) => {
  const currentMsg = messages.value[messageIndex]
  messages.value[messageIndex] = {
    ...currentMsg,
    actionProposal: { ...action, status: 'cancelled' }
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    scrollToBottom()
    // 如果带着待分析照片打开面板，且还没聊过，自动帮用户问一句
    if (props.context.mediaFileId && messages.value.length === 0) {
      inputText.value = '帮我看看这张照片有没有问题'
      sendMessage()
    }
  }
})
</script>

<style scoped>
.chat-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.panel-header {
  padding: 8px 16px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.drag-indicator {
  width: 36px;
  height: 4px;
  background: #ddd;
  border-radius: 2px;
  margin: 0 auto 12px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #FAFAFA;
}

.welcome-message {
  text-align: center;
  padding: 24px 16px;
}

.welcome-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.welcome-text {
  font-size: 15px;
  color: #666;
  line-height: 1.8;
}

.welcome-text .current-item {
  font-weight: 600;
  color: #1677FF;
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: #F5F5F5;
  border-radius: 12px;
  width: fit-content;
}

.thinking-dots {
  display: flex;
  gap: 4px;
}

.thinking-dots span {
  width: 6px;
  height: 6px;
  background: #1677FF;
  border-radius: 50%;
  animation: pulse 1.4s infinite ease-in-out both;
}

.thinking-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.thinking-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes pulse {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.thinking-text {
  font-size: 13px;
  color: #999;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 16px;
  background: #fff;
  border-top: 1px solid #f0f0f0;
}

.quick-actions .van-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.quick-actions .van-tag:active {
  transform: scale(0.95);
}

.input-area {
  padding: 8px 16px 16px;
  background: #fff;
  border-top: 1px solid #f0f0f0;
}

.disclaimer {
  font-size: 11px;
  color: #999;
  text-align: center;
  margin-bottom: 8px;
}

.input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.input-field {
  flex: 1;
  background: #F7F8FA;
  border-radius: 22px;
  padding: 8px 16px;
}

.input-field :deep(.van-field__control) {
  font-size: 14px;
}

.send-btn,
.stop-btn,
.voice-btn {
  width: 36px;
  height: 36px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.send-btn {
  background: linear-gradient(135deg, #1677FF 0%, #0958d9 100%);
  border: none;
}

.voice-btn.listening {
  background: #FFF2F0;
  border-color: #FF4D4F;
  animation: voice-pulse 1.2s infinite ease-in-out;
}

@keyframes voice-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255, 77, 79, 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(255, 77, 79, 0); }
}

.listening-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px;
  margin-bottom: 8px;
  background: #FFF2F0;
  border-radius: 8px;
  color: #FF4D4F;
  font-size: 12px;
}

.send-btn:disabled {
  background: #ccc;
  opacity: 0.6;
}
</style>
