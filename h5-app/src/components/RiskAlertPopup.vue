<template>
  <van-popup
    v-model:show="visible"
    position="center"
    round
    :close-on-click-overlay="false"
    class="risk-alert-popup"
  >
    <div class="risk-alert-content">
      <div class="alert-header" :class="riskLevelClass">
        <div class="alert-icon">
          <van-icon name="warning-o" size="28" />
        </div>
        <h3 class="alert-title">风险预警</h3>
      </div>

      <div class="alert-body">
        <div class="enterprise-info">
          <div class="info-label">企业</div>
          <div class="info-value">{{ enterpriseName }}</div>
        </div>

        <div class="risk-level-section">
          <div class="info-label">风险等级</div>
          <div class="risk-level-display">
            <span class="risk-dot" :class="riskLevelClass"></span>
            <span class="risk-text" :class="riskLevelClass">{{ riskLevelText }}</span>
          </div>
        </div>

        <div v-if="riskProfile?.history_records?.length" class="history-section">
          <div class="section-title">
            <van-icon name="clock-o" size="14" color="#666" />
            <span>历史记录</span>
          </div>
          <div class="history-list">
            <div
              v-for="(record, index) in riskProfile.history_records"
              :key="index"
              class="history-item"
            >
              <span class="history-date">{{ record.date }}</span>
              <span class="history-result" :class="getResultClass(record.result)">
                {{ record.result }}
                <span v-if="record.fail_count" class="fail-count">({{ record.fail_count }} 项)</span>
              </span>
            </div>
          </div>
        </div>

        <div v-if="riskProfile?.focus_points?.length" class="focus-section">
          <div class="section-title">
            <van-icon name="eye-o" size="14" color="#ff6b6b" />
            <span>重点关注</span>
          </div>
          <div class="focus-list">
            <div
              v-for="(point, index) in riskProfile.focus_points"
              :key="index"
              class="focus-item"
            >
              <span class="focus-index">{{ index + 1 }}</span>
              <span class="focus-text">{{ point }}</span>
            </div>
          </div>
        </div>

        <div v-if="riskProfile?.risk_score !== undefined" class="risk-score-section">
          <div class="score-header">
            <span class="score-label">风险评分</span>
            <span class="score-value" :class="riskLevelClass">{{ riskProfile.risk_score }}</span>
          </div>
          <van-progress
            :percentage="riskProfile.risk_score"
            :stroke-width="6"
            :show-pivot="false"
            :color="getScoreColor(riskProfile.risk_score)"
          />
        </div>
      </div>

      <div class="alert-footer">
        <van-button
          type="default"
          size="small"
          @click="viewHistory"
          class="history-btn"
        >
          查看完整历史
        </van-button>
        <van-button
          type="primary"
          size="small"
          @click="confirmStart"
          class="confirm-btn"
        >
          开始检查
        </van-button>
      </div>
    </div>
  </van-popup>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  enterpriseId: {
    type: [String, Number],
    default: null
  },
  enterpriseName: {
    type: String,
    default: ''
  },
  riskProfile: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:show', 'confirm', 'viewHistory'])

const router = useRouter()
const visible = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val)
})

const riskLevelClass = computed(() => {
  const level = props.riskProfile?.risk_level || 'low'
  return `risk-${level}`
})

const riskLevelText = computed(() => {
  const levelMap = {
    'high': '高风险',
    'medium': '中风险',
    'low': '低风险'
  }
  return levelMap[props.riskProfile?.risk_level] || '低风险'
})

const getResultClass = (result) => {
  if (!result) return ''
  if (result.includes('不合格')) return 'result-fail'
  if (result.includes('基本合格')) return 'result-partial'
  return 'result-pass'
}

const getScoreColor = (score) => {
  if (score >= 80) return '#ff4d4f'
  if (score >= 50) return '#ff976a'
  return '#07c160'
}

const viewHistory = () => {
  emit('viewHistory', props.enterpriseId)
  visible.value = false
}

const confirmStart = () => {
  emit('confirm')
  visible.value = false
}
</script>

<style scoped>
.risk-alert-popup {
  width: 90%;
  max-width: 380px;
  overflow: hidden;
}

.risk-alert-content {
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
}

.alert-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 20px;
  color: #fff;
}

.alert-header.risk-high {
  background: linear-gradient(135deg, #ff4d4f 0%, #ff7875 100%);
}

.alert-header.risk-medium {
  background: linear-gradient(135deg, #ff976a 0%, #ffbb96 100%);
}

.alert-header.risk-low {
  background: linear-gradient(135deg, #07c160 0%, #52c41a 100%);
}

.alert-icon {
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.alert-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.alert-body {
  padding: 16px 20px;
  max-height: 400px;
  overflow-y: auto;
}

.enterprise-info {
  margin-bottom: 16px;
}

.info-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}

.info-value {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
}

.risk-level-section {
  margin-bottom: 16px;
}

.risk-level-display {
  display: flex;
  align-items: center;
  gap: 8px;
}

.risk-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.risk-dot.risk-high {
  background: #ff4d4f;
  box-shadow: 0 0 8px rgba(255, 77, 79, 0.5);
}

.risk-dot.risk-medium {
  background: #ff976a;
  box-shadow: 0 0 8px rgba(255, 151, 106, 0.5);
}

.risk-dot.risk-low {
  background: #07c160;
  box-shadow: 0 0 8px rgba(7, 193, 96, 0.5);
}

.risk-text {
  font-size: 15px;
  font-weight: 600;
}

.risk-text.risk-high {
  color: #ff4d4f;
}

.risk-text.risk-medium {
  color: #ff976a;
}

.risk-text.risk-low {
  color: #07c160;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #333;
  margin-bottom: 10px;
}

.history-section {
  margin-bottom: 16px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.history-date {
  color: #666;
}

.history-result {
  font-weight: 500;
}

.history-result.result-pass {
  color: #07c160;
}

.history-result.result-partial {
  color: #ff976a;
}

.history-result.result-fail {
  color: #ff4d4f;
}

.fail-count {
  font-size: 12px;
  color: #888;
}

.focus-section {
  margin-bottom: 16px;
  padding: 12px;
  background: rgba(255, 77, 79, 0.05);
  border-radius: 8px;
  border-left: 3px solid #ff4d4f;
}

.focus-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.focus-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 13px;
  color: #333;
  line-height: 1.5;
}

.focus-index {
  width: 18px;
  height: 18px;
  background: #ff4d4f;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.focus-text {
  flex: 1;
}

.risk-score-section {
  margin-top: 16px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.score-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.score-label {
  font-size: 13px;
  color: #666;
}

.score-value {
  font-size: 18px;
  font-weight: 700;
}

.score-value.risk-high {
  color: #ff4d4f;
}

.score-value.risk-medium {
  color: #ff976a;
}

.score-value.risk-low {
  color: #07c160;
}

.alert-footer {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #eee;
}

.history-btn {
  flex: 1;
  border-radius: 8px;
}

.confirm-btn {
  flex: 2;
  border-radius: 8px;
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  border: none;
}
</style>
