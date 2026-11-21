<template>
  <div class="agent-message" :class="[message.role]">
    <div v-if="message.role === 'assistant'" class="avatar">
      <van-icon name="service-o" size="18" color="#1677FF" />
    </div>
    
    <div class="message-content">
      <div class="message-bubble" :class="[message.role, { 'has-card': hasCard }]">
        <div v-if="message.role === 'assistant'" class="message-text" v-html="renderedContent"></div>
        <div v-else class="message-text">{{ message.content }}</div>
        
        <div v-if="message.toolCalls && message.toolCalls.length > 0" class="tool-calls">
          <div v-for="tool in message.toolCalls" :key="tool.name" class="tool-call-item">
            <van-icon name="search" size="12" />
            <span>{{ getToolLabel(tool.name) }}</span>
          </div>
        </div>
        
        <div v-if="message.verdictCard" class="verdict-card" :class="message.verdictCard.type">
          <div class="verdict-header">
            <van-icon :name="getVerdictIcon(message.verdictCard.type)" size="16" />
            <span class="verdict-title">{{ message.verdictCard.title }}</span>
          </div>
          <div class="verdict-reason">{{ message.verdictCard.reason }}</div>
        </div>
        
        <div v-if="message.copyableText" class="copyable-section">
          <div class="copyable-label">{{ message.copyableText.label }}</div>
          <div class="copyable-content">
            <div class="copyable-text">{{ message.copyableText.text }}</div>
            <van-button size="small" type="primary" plain @click="copyText(message.copyableText.text)">
              复制
            </van-button>
          </div>
        </div>

        <template v-for="(proposal, pIndex) in message.actionProposals || []" :key="pIndex">
          <AgentActionCard
            v-if="proposal"
            :action="proposal"
            @confirm="$emit('confirm-action', proposal)"
            @cancel="$emit('cancel-action', proposal)"
          />
        </template>
      </div>

      <div class="message-time">{{ formatTime(message.timestamp) }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { showToast } from 'vant'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import AgentActionCard from './AgentActionCard.vue'

const props = defineProps({
  message: {
    type: Object,
    required: true
  }
})

defineEmits(['confirm-action', 'cancel-action'])

const hasCard = computed(() => {
  return props.message.verdictCard || props.message.copyableText
})

const renderedContent = computed(() => {
  if (!props.message.content) return ''
  return DOMPurify.sanitize(marked.parse(props.message.content, { breaks: true, gfm: true }))
})

const getToolLabel = (name) => {
  const labels = {
    'get_check_item_details': '获取检查项详情',
    'get_inspection_summary': '汇总检查结果',
    'generate_final_verdict': '生成最终判定'
  }
  return labels[name] || name
}

const getVerdictIcon = (type) => {
  const icons = {
    'pass': 'success',
    'fail': 'cross',
    'partial_pass': 'warning-o'
  }
  return icons[type] || 'info-o'
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    showToast('已复制到剪贴板')
  } catch (err) {
    showToast('复制失败')
  }
}
</script>

<style scoped>
.agent-message {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.agent-message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #E6F4FF;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message-content {
  max-width: 85%;
}

.agent-message.user .message-content {
  max-width: 75%;
}

.message-bubble {
  padding: 12px 14px;
  border-radius: 12px;
  word-break: break-word;
}

.message-bubble.user {
  background: #1677FF;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.message-bubble.assistant {
  background: #F5F5F5;
  color: #333;
  border-bottom-left-radius: 4px;
}

.message-bubble.has-card {
  padding: 12px;
}

.message-text {
  font-size: 14px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.message-text :deep(p) {
  margin: 6px 0;
}

.message-text :deep(p:first-child) {
  margin-top: 0;
}

.message-text :deep(p:last-child) {
  margin-bottom: 0;
}

.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3) {
  margin: 14px 0 6px;
  font-weight: 650;
  line-height: 1.4;
}

.message-text :deep(h1) {
  font-size: 17px;
}

.message-text :deep(h2) {
  font-size: 16px;
}

.message-text :deep(h3) {
  font-size: 15px;
}

.message-text :deep(h1:first-child),
.message-text :deep(h2:first-child),
.message-text :deep(h3:first-child) {
  margin-top: 0;
}

.message-text :deep(ul),
.message-text :deep(ol) {
  margin: 6px 0;
  padding-left: 20px;
}

.message-text :deep(li) {
  margin: 4px 0;
}

.message-text :deep(strong) {
  font-weight: 600;
}

.message-text :deep(hr) {
  margin: 12px 0;
  border: none;
  border-top: 1px solid rgba(0, 0, 0, 0.1);
}

.message-text :deep(blockquote) {
  margin: 8px 0;
  padding: 6px 10px;
  border-left: 3px solid #1677FF;
  background: rgba(22, 119, 255, 0.06);
  color: #666;
}

.message-bubble.user .message-text :deep(hr) {
  border-top-color: rgba(255, 255, 255, 0.3);
}

.message-bubble.user .message-text :deep(blockquote) {
  border-left-color: #fff;
  background: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.9);
}

.message-time {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
  text-align: right;
}

.agent-message.user .message-time {
  text-align: left;
}

.tool-calls {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #ddd;
}

.tool-call-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.verdict-card {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  border-left: 4px solid;
}

.verdict-card.pass {
  border-color: #52C41A;
  background: #F6FFED;
}

.verdict-card.fail {
  border-color: #FF4D4F;
  background: #FFF2F0;
}

.verdict-card.partial_pass {
  border-color: #FAAD14;
  background: #FFFBE6;
}

.verdict-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  margin-bottom: 8px;
}

.verdict-card.pass .verdict-header {
  color: #52C41A;
}

.verdict-card.fail .verdict-header {
  color: #FF4D4F;
}

.verdict-card.partial_pass .verdict-header {
  color: #FAAD14;
}

.verdict-title {
  font-size: 15px;
}

.verdict-reason {
  font-size: 13px;
  color: #666;
  line-height: 1.5;
}

.copyable-section {
  margin-top: 12px;
}

.copyable-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 6px;
}

.copyable-content {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: #FAFAFA;
  border: 1px dashed #D9D9D9;
  border-radius: 6px;
  padding: 8px;
}

.copyable-text {
  flex: 1;
  font-size: 13px;
  color: #333;
  line-height: 1.5;
  white-space: pre-wrap;
}

.copyable-content .van-button {
  flex-shrink: 0;
  font-size: 12px;
}
</style>
