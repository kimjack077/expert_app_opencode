<template>
  <div class="ai-assist-card" :class="riskLevel">
    <div class="card-header">
      <div class="header-icon">
        <van-icon name="service-o" size="18" color="#1677FF" />
      </div>
      <span class="header-title">AI 检查助手</span>
      <van-icon
        :name="expanded ? 'arrow-up' : 'arrow-down'"
        size="16"
        color="#999"
        @click="expanded = !expanded"
      />
    </div>

    <template v-if="expanded">
      <div class="risk-indicator">
        <span class="risk-label">风险等级：</span>
        <van-tag :type="riskTagType" size="medium">{{ riskText }}</van-tag>
      </div>

      <div v-if="historyIssues.length > 0" class="focus-section">
        <div class="section-title">
          <van-icon name="warning-o" color="#FAAD14" />
          重点关注
        </div>
        <ul class="focus-list">
          <li v-for="(issue, index) in historyIssues" :key="index">
            {{ issue }}
          </li>
        </ul>
      </div>

      <div v-if="checkPoints.length > 0" class="check-section">
        <div class="section-title">
          <van-icon name="description" color="#1677FF" />
          检查要点
        </div>
        <ol class="check-list">
          <li v-for="(point, index) in checkPoints" :key="index">
            {{ point }}
          </li>
        </ol>
      </div>

      <div class="card-actions">
        <van-button type="primary" size="small" plain @click="$emit('ask-ai')">
          <van-icon name="chat-o" /> 问AI
        </van-button>
        <van-button size="small" plain @click="expanded = false">
          <van-icon name="cross" /> 忽略
        </van-button>
      </div>
    </template>

    <div v-else class="collapsed-hint" @click="expanded = true">
      <van-icon name="info-o" size="14" />
      <span>点击展开AI辅助信息</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  riskLevel: {
    type: String,
    default: 'low',
    validator: (value) => ['high', 'medium', 'low'].includes(value)
  },
  historyIssues: {
    type: Array,
    default: () => []
  },
  checkPoints: {
    type: Array,
    default: () => []
  }
})

defineEmits(['ask-ai'])

const expanded = ref(true)

const riskTagType = computed(() => {
  const types = {
    high: 'danger',
    medium: 'warning',
    low: 'success'
  }
  return types[props.riskLevel] || 'default'
})

const riskText = computed(() => {
  const texts = {
    high: '高',
    medium: '中',
    low: '低'
  }
  return texts[props.riskLevel] || '低'
})
</script>

<style scoped>
.ai-assist-card {
  background: #fff;
  border-radius: 8px;
  margin: 12px 0;
  border: 1px solid #E8E8E8;
  overflow: hidden;
}

.ai-assist-card.high {
  border-left: 3px solid #FF4D4F;
}

.ai-assist-card.medium {
  border-left: 3px solid #FAAD14;
}

.ai-assist-card.low {
  border-left: 3px solid #52C41A;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: #F8F9FA;
}

.header-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #E6F4FF;
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.risk-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: #FAFAFA;
  border-bottom: 1px solid #F0F0F0;
}

.risk-label {
  font-size: 13px;
  color: #666;
}

.focus-section,
.check-section {
  padding: 12px;
  border-bottom: 1px solid #F0F0F0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  margin-bottom: 8px;
}

.focus-list,
.check-list {
  margin: 0;
  padding-left: 16px;
}

.focus-list li,
.check-list li {
  font-size: 13px;
  color: #666;
  line-height: 1.8;
}

.card-actions {
  display: flex;
  gap: 8px;
  padding: 12px;
}

.card-actions .van-button {
  flex: 1;
}

.collapsed-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  color: #999;
  font-size: 13px;
  cursor: pointer;
}

.collapsed-hint:hover {
  background: #FAFAFA;
}
</style>