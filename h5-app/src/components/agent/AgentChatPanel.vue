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
            <span class="header-title">检查助手</span>
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
        <div class="input-row">
          <van-field
            v-model="inputText"
            placeholder="输入你的问题..."
            :disabled="isThinking"
            @keyup.enter="sendMessage"
            class="input-field"
          />
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
import { showToast } from 'vant'
import AgentMessage from './AgentMessage.vue'

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
      enterpriseId: ''
    })
  }
})

const emit = defineEmits(['update:show'])

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

const quickActions = computed(() => [
  { text: '这项怎么查？' },
  { text: '帮我判断合不合格' },
  { text: '生成最终判定' }
])

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
    const response = await fetch('/api/agent/chat', {
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
          enterprise_id: props.context.enterpriseId
        },
        conversation: messages.value.slice(0, -1).map(m => ({
          role: m.role,
          content: m.content
        }))
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

            if (data.type === 'content') {
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
            } else if (data.type === 'done') {
              const currentMsg = messages.value[messageIndex]
              if (currentMsg.toolCalls && currentMsg.toolCalls.length > 0) {
                messages.value[messageIndex] = { ...currentMsg, toolCalls: [] }
              }
            } else if (data.type === 'error') {
              messages.value[messageIndex] = {
                ...messages.value[messageIndex],
                content: `抱歉，发生了错误：${data.content}`
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

watch(() => props.show, (newVal) => {
  if (newVal) {
    scrollToBottom()
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
.stop-btn {
  width: 36px;
  height: 36px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.send-btn {
  background: linear-gradient(135deg, #1677FF 0%, #0958d9 100%);
  border: none;
}

.send-btn:disabled {
  background: #ccc;
  opacity: 0.6;
}
</style>
