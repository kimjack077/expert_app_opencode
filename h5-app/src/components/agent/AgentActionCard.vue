<template>
  <div class="agent-action-card" :class="[actionType, action.status]">
    <div class="card-header">
      <van-icon :name="getActionIcon" size="16" :color="getActionColor" />
      <span class="card-title">{{ action.title }}</span>
    </div>

    <div class="card-content">
      <template v-if="action.type === 'create_task'">
        <div class="info-row">
          <span class="label">企业：</span>
          <span class="value">{{ action.data.enterprise }}</span>
        </div>
        <div class="info-row">
          <span class="label">模板：</span>
          <span class="value">{{ action.data.template }}</span>
        </div>
        <div class="info-row">
          <span class="label">日期：</span>
          <span class="value">{{ action.data.date }}</span>
        </div>
        <div class="info-row">
          <span class="label">检查员：</span>
          <span class="value">{{ action.data.inspector }}</span>
        </div>
      </template>

      <template v-else-if="action.type === 'judgment'">
        <div class="info-row">
          <span class="label">检查项：</span>
          <span class="value">{{ action.data.checkItem }}</span>
        </div>
        <div class="info-row">
          <span class="label">建议结果：</span>
          <van-tag :type="getResultTagType" size="medium">
            {{ getResultText }}
          </van-tag>
        </div>
        <div v-if="action.data.problemDescription" class="info-block">
          <span class="label">问题描述：</span>
          <div class="description-box">{{ action.data.problemDescription }}</div>
        </div>
        <div v-if="action.data.rectificationSuggestion" class="info-block">
          <span class="label">整改建议：</span>
          <div class="description-box">{{ action.data.rectificationSuggestion }}</div>
        </div>
      </template>

      <template v-else-if="action.type === 'final_verdict'">
        <div class="info-row">
          <span class="label">最终判定：</span>
          <van-tag :type="getResultTagType" size="medium">
            {{ getResultText }}
          </van-tag>
        </div>
        <div v-if="action.data.comment" class="info-block">
          <span class="label">总体评价：</span>
          <div class="description-box">{{ action.data.comment }}</div>
        </div>
      </template>

      <template v-else>
        <pre class="operation-data">{{ JSON.stringify(action.data, null, 2) }}</pre>
      </template>
    </div>

    <div v-if="action.status === 'pending'" class="card-actions">
      <van-button type="primary" size="small" @click="$emit('confirm')">
        <van-icon name="success" /> 采纳并填写
      </van-button>
      <van-button v-if="action.type === 'create_task'" size="small" @click="$emit('edit')">
        <van-icon name="edit" /> 修改
      </van-button>
      <van-button size="small" @click="$emit('cancel')">
        <van-icon name="cross" /> 忽略
      </van-button>
    </div>

    <div v-else class="card-status">
      <template v-if="action.status === 'confirmed'">
        <van-icon name="success" color="#52C41A" /> 已填写
      </template>
      <template v-else-if="action.status === 'cancelled'">
        <van-icon name="cross" color="#FF4D4F" /> 已忽略
      </template>
      <template v-else-if="action.status === 'failed'">
        <van-icon name="warning" color="#FF4D4F" /> 填写失败，请重试或手动填写
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  action: {
    type: Object,
    required: true,
    validator: (value) => {
      return value.type && value.title && value.data && value.status
    }
  }
})

defineEmits(['confirm', 'edit', 'cancel'])

const actionType = computed(() => props.action.type)

const getActionIcon = computed(() => {
  const icons = {
    create_task: 'orders-o',
    judgment: 'warning-o',
    final_verdict: 'certificate',
    operation: 'info-o'
  }
  return icons[props.action.type] || 'info-o'
})

const getActionColor = computed(() => {
  const colors = {
    create_task: '#1677FF',
    judgment: '#FAAD14',
    final_verdict: '#1677FF',
    operation: '#FAAD14'
  }
  return colors[props.action.type] || '#FAAD14'
})

const getResultTagType = computed(() => {
  const result = props.action.data?.result || props.action.data?.verdict
  const types = {
    pass: 'success',
    fail: 'danger',
    na: 'default',
    partial_pass: 'warning'
  }
  return types[result] || 'default'
})

const getResultText = computed(() => {
  const result = props.action.data?.result || props.action.data?.verdict
  const texts = {
    pass: '合格',
    fail: '不合格',
    na: '不适用',
    partial_pass: '基本合格'
  }
  return texts[result] || result
})
</script>

<style scoped>
.agent-action-card {
  margin-top: 12px;
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  border-left: 4px solid #FAAD14;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.agent-action-card.create_task {
  border-left-color: #1677FF;
}

.agent-action-card.judgment {
  border-left-color: #FAAD14;
}

.agent-action-card.confirmed {
  border-left-color: #52C41A;
  opacity: 0.8;
}

.agent-action-card.cancelled {
  border-left-color: #D9D9D9;
  opacity: 0.6;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
  font-size: 15px;
}

.card-title {
  color: #333;
}

.card-content {
  font-size: 14px;
}

.info-row {
  display: flex;
  margin-bottom: 8px;
}

.info-row .label {
  color: #999;
  min-width: 70px;
}

.info-row .value {
  color: #333;
  flex: 1;
}

.info-block {
  margin-bottom: 12px;
}

.info-block .label {
  display: block;
  color: #999;
  font-size: 13px;
  margin-bottom: 4px;
}

.description-box {
  background: #FAFAFA;
  padding: 8px;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.operation-data {
  margin: 0;
  font-size: 12px;
  background: #FAFAFA;
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
}

.card-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #F0F0F0;
}

.card-actions .van-button {
  flex: 1;
}

.card-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #F0F0F0;
  font-size: 13px;
  color: #666;
}
</style>