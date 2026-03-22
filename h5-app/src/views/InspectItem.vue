<template>
  <div class="inspect-item-page">
    <!-- 导航栏 -->
    <van-nav-bar
      :title="itemData?.title || '检查项详情'"
      left-arrow
      @click-left="goBack"
      fixed
      placeholder
    >
      <template #right>
        <van-icon name="success" size="20" @click="saveItem" />
      </template>
    </van-nav-bar>

    <div v-if="loading" class="loading-container">
      <van-skeleton title :row="10" />
    </div>

    <div v-else-if="itemData" class="item-content">
      <!-- 检查项基本信息 -->
      <div class="item-header-card">
        <div class="item-title-row">
          <h3 class="item-title">{{ itemData.title }}</h3>
          <div v-if="itemData.risk_level" class="risk-tag" :class="itemData.risk_level">
            {{ riskLevelText }}
          </div>
        </div>
        <p v-if="itemData.description" class="item-description">{{ itemData.description }}</p>
      </div>

      <!-- 历史检查统计 -->
      <div v-if="loadingHistory" class="history-card loading">
        <van-loading size="20" color="#007AFF" />
        <span>加载历史记录...</span>
      </div>
      <div v-else-if="historyStats && historyStats.has_history" class="history-card" :class="getHistoryCardClass">
        <div class="history-header">
          <van-icon name="clock-o" size="18" :color="getHistoryIconColor" />
          <span class="history-title">历史检查记录</span>
          <span v-if="historyStats.fail_count > 0" class="history-warning-badge">
            {{ historyStats.fail_count }}次不合格
          </span>
          <!-- 高频不合格预警 -->
          <span v-if="historyStats.fail_rate >= 50" class="high-risk-badge">
            <van-icon name="warning" size="12" /> 高风险项
          </span>
        </div>

        <div class="history-stats-row">
          <div class="stat-item">
            <span class="stat-value">{{ historyStats.total_inspections }}</span>
            <span class="stat-label">检查次数</span>
          </div>
          <div class="stat-item">
            <span class="stat-value fail">{{ historyStats.fail_count }}</span>
            <span class="stat-label">不合格</span>
          </div>
          <div class="stat-item">
            <span class="stat-value pass">{{ historyStats.pass_count }}</span>
            <span class="stat-label">合格</span>
          </div>
          <div class="stat-item">
            <span class="stat-value" :class="{ 'high-fail': historyStats.fail_rate >= 50 }">
              {{ historyStats.fail_rate }}%
            </span>
            <span class="stat-label">不合格率</span>
          </div>
        </div>

        <!-- 趋势图表 -->
        <div v-if="historyStats.history_records && historyStats.history_records.length >= 2" class="trend-chart-section">
          <div class="trend-header">
            <span>检查结果趋势</span>
            <span class="trend-period">最近{{ historyStats.history_records.length }}次</span>
          </div>
          <canvas ref="trendCanvas" class="trend-canvas" width="320" height="120"></canvas>
          <div class="trend-legend">
            <span class="legend-item"><span class="legend-dot pass"></span>合格</span>
            <span class="legend-item"><span class="legend-dot fail"></span>不合格</span>
          </div>
          <!-- 整改效果对比 -->
          <div v-if="trendImprovement" class="improvement-section">
            <van-icon name="arrow-up" :color="trendImprovement > 0 ? '#34C759' : '#ff4d4f'" />
            <span :class="trendImprovement > 0 ? 'text-success' : 'text-danger'">
              {{ trendImprovement > 0 ? '整改有效' : '需加强整改' }}
            </span>
            <span class="improvement-detail">
              合格率提升 {{ Math.abs(trendImprovement) }}%
            </span>
          </div>
        </div>

        <div v-if="historyStats.last_result" class="last-result-row">
          <span class="last-result-label">上次检查：</span>
          <span class="last-result-value" :class="historyStats.last_result">
            <van-icon :name="historyStats.last_result === 'pass' ? 'success' : (historyStats.last_result === 'fail' ? 'cross' : 'minus')" />
            {{ historyStats.last_result === 'pass' ? '合格' : (historyStats.last_result === 'fail' ? '不合格' : '不适用') }}
          </span>
          <span v-if="historyStats.last_inspection_date" class="last-result-date">
            {{ formatDate(historyStats.last_inspection_date) }}
          </span>
        </div>

        <div v-if="historyStats.fail_count > 0 && historyStats.history_records && historyStats.history_records.length > 0" class="history-detail">
          <div class="detail-header" @click="showHistoryDetail = !showHistoryDetail">
            <span>查看不合格记录详情</span>
            <van-icon :name="showHistoryDetail ? 'arrow-up' : 'arrow-down'" size="14" />
          </div>
          <div v-if="showHistoryDetail" class="detail-list">
            <div v-for="record in historyStats.history_records.filter(r => r.result === 'fail')" :key="record.record_id" class="detail-item">
              <div class="detail-date">{{ formatDate(record.inspection_date) }}</div>
              <div v-if="record.problem_description" class="detail-problem">
                <van-icon name="warning-o" color="#ff4d4f" size="12" />
                {{ record.problem_description }}
              </div>
              <div v-if="record.inspector_name" class="detail-inspector">检查员：{{ record.inspector_name }}</div>
            </div>
          </div>
        </div>

        <div v-if="historyStats.fail_count > 0" class="history-tip">
          <van-icon name="info-o" color="#ff976a" />
          <span>该检查项历史存在不合格记录，建议重点关注</span>
        </div>
      </div>
      <div v-else-if="historyStats && !historyStats.has_history && historyStats.enterprise_name" class="history-card empty">
        <van-icon name="clock-o" size="18" color="#999" />
        <span>该企业此检查项暂无历史检查记录</span>
      </div>

      <!-- 知识库支撑 -->
      <div v-if="hasKnowledgeBase" class="knowledge-card">
        <div class="knowledge-header" @click="showKnowledge = !showKnowledge">
          <van-icon name="bookmark-o" size="18" color="#007AFF" />
          <span class="knowledge-title">知识库支撑</span>
          <van-icon :name="showKnowledge ? 'arrow-up' : 'arrow-down'" size="16" color="#999" />
        </div>
        <div v-if="showKnowledge" class="knowledge-content">
          <div v-if="itemData.description" class="knowledge-item">
            <div class="knowledge-label">
              <van-icon name="description" size="14" color="#FF9500" />
              项目描述
            </div>
            <div class="knowledge-value">{{ itemData.description }}</div>
          </div>
          <div v-if="itemData.check_method" class="knowledge-item">
            <div class="knowledge-label">
              <van-icon name="search" size="14" color="#007AFF" />
              检查方法
            </div>
            <div class="knowledge-value method-value">{{ itemData.check_method }}</div>
          </div>
          <div v-if="itemData.legal_basis" class="knowledge-item">
            <div class="knowledge-label">
              <van-icon name="description" size="14" color="#FF9500" />
              法律依据
            </div>
            <div class="knowledge-value">{{ itemData.legal_basis }}</div>
          </div>
          <div v-if="itemData.standard_ref" class="knowledge-item">
            <div class="knowledge-label">
              <van-icon name="bars" size="14" color="#34C759" />
              标准依据
            </div>
            <div class="knowledge-value">{{ itemData.standard_ref }}</div>
          </div>
        </div>
      </div>

      <!-- 检查结论 -->
      <div class="result-card">
        <div class="card-header">
          <span class="card-title">检查结论</span>
          <span v-if="itemData.is_required" class="required-tag">必填</span>
        </div>

        <div class="result-input">
          <!-- 单选类型（包括 pass_fail） -->
          <div v-if="itemData.result_type === 'pass_fail' || (itemData.result_type === null && itemData.check_type === 'radio')" class="radio-input">
            <van-radio-group v-model="formData.radio_value" direction="horizontal">
              <van-radio
                v-for="opt in resultOptions"
                :key="opt.value"
                :name="opt.value"
                shape="square"
              >{{ opt.label }}</van-radio>
            </van-radio-group>
            <div v-if="formData.radio_value === 'fail'" class="fail-hint-box">
              <div class="fail-hint-header">
                <van-icon name="warning-o" color="#ff4d4f" />
                <span>不合格项需填写问题描述</span>
              </div>
            </div>
          </div>

          <!-- 打分类型 -->
          <div v-else-if="itemData.result_type === 'score' || (itemData.result_type === null && itemData.check_type === 'score')" class="score-input">
            <div class="score-header">
              <span class="score-label">得分</span>
              <span class="score-value">{{ formData.score_value || 0 }} / {{ itemData.max_score || 100 }}</span>
            </div>
            <van-stepper
              v-model="formData.score_value"
              :min="0"
              :max="Number(itemData.max_score) || 100"
              :step="Number(itemData.score_step) || 1"
              theme="round"
              button-size="22"
              disable-input
            />
            <div v-if="itemData.pass_score" class="pass-score-hint">
              合格线：{{ itemData.pass_score }} 分
            </div>
            <!-- 自动合格判定 -->
            <div v-if="itemData.pass_score && formData.score_value !== '' && formData.score_value !== null" class="score-judgment" :class="scoreJudgmentClass">
              <van-icon :name="scoreJudgmentIcon" />
              <span>{{ scoreJudgmentText }}</span>
              <span class="judgment-detail">
                （{{ formData.score_value }}分 {{ formData.score_value >= Number(itemData.pass_score) ? '≥' : '<' }} {{ itemData.pass_score }}分）
              </span>
            </div>
          </div>

          <!-- 数值类型 -->
          <div v-else-if="itemData.result_type === 'numeric' || (itemData.result_type === null && itemData.check_type === 'numeric')" class="numeric-input">
            <van-field
              v-model="formData.numeric_value"
              type="number"
              :placeholder="numericPlaceholder"
              clearable
            >
              <template #button v-if="itemData.unit">
                <span class="unit-text">{{ itemData.unit }}</span>
              </template>
            </van-field>
            <div v-if="itemData.min_value !== null || itemData.max_value !== null" class="numeric-range">
              <van-icon name="info-o" size="12" />
              <span>标准范围：{{ formatRange }}</span>
            </div>
            <!-- 自动范围判定 -->
            <div v-if="numericJudgmentClass && formData.numeric_value !== '' && formData.numeric_value !== null" class="numeric-judgment" :class="numericJudgmentClass">
              <van-icon :name="numericJudgmentIcon" />
              <span>{{ numericJudgmentText }}</span>
              <span class="judgment-detail">{{ numericJudgmentDetail }}</span>
            </div>
          </div>

          <!-- 文本类型 -->
          <div v-else-if="itemData.result_type === 'text' || (itemData.result_type === null && itemData.check_type === 'text')" class="text-input">
            <van-field
              v-model="formData.text_value"
              type="textarea"
              rows="4"
              placeholder="请输入检查结论描述"
              autosize
              show-word-limit
              maxlength="500"
            />
          </div>

          <!-- 多选类型 -->
          <div v-else-if="itemData.result_type === 'multi_check' || (itemData.result_type === null && itemData.check_type === 'multi_check')" class="multi-input">
            <van-checkbox-group v-model="formData.multi_value">
              <van-checkbox
                v-for="opt in resultOptions"
                :key="opt.value"
                :name="opt.value"
                shape="square"
              >{{ opt.label }}</van-checkbox>
            </van-checkbox-group>
            <!-- 多选结果汇总 -->
            <div v-if="formData.multi_value && formData.multi_value.length > 0" class="multi-summary">
              <div class="summary-header">
                <van-icon name="description" size="14" color="#007AFF" />
                <span>已选 {{ formData.multi_value.length }} 项</span>
              </div>
              <div class="summary-tags">
                <van-tag
                  v-for="val in formData.multi_value"
                  :key="val"
                  type="primary"
                  size="medium"
                  round
                >{{ getMultiCheckLabel(val) }}</van-tag>
              </div>
            </div>
          </div>

          <!-- 默认：通过/不通过 -->
          <div v-else class="default-input">
            <van-radio-group v-model="formData.radio_value" direction="horizontal">
              <van-radio name="pass" shape="square">合格</van-radio>
              <van-radio name="fail" shape="square">不合格</van-radio>
              <van-radio name="na" shape="square">不适用</van-radio>
            </van-radio-group>
          </div>
        </div>
      </div>

      <!-- 问题描述 -->
      <div class="problem-card" :class="{ 'required-problem': isFailRequired }">
        <div class="card-header">
          <span class="card-title">问题描述</span>
          <span v-if="isFailRequired" class="required-tag">必填</span>
          <span v-else style="color:#888;font-size:12px">（如有问题）</span>
        </div>
        <van-field
          v-model="formData.problem_description"
          type="textarea"
          rows="3"
          :placeholder="isFailRequired ? '请描述发现的问题（必填）...' : '请描述发现的问题...'"
          autosize
          show-word-limit
          maxlength="500"
        />
      </div>

      <!-- 附件 -->
      <div class="attachment-card" :class="{ 'attachment-required': itemData.attachment_required && formData.photos.length === 0 }">
        <div class="card-header">
          <span class="card-title">附件</span>
          <div style="display:flex;align-items:center;gap:8px">
            <span v-if="itemData.attachment_required" class="required-tag" style="font-size:12px;color:#ff4d4f;background:rgba(255,77,79,0.1);padding:2px 7px;border-radius:4px">📎 必传</span>
            <span class="photo-count">{{ formData.photos.length }}/5</span>
          </div>
        </div>
        
        <!-- 附件必填提示 -->
        <div v-if="itemData.attachment_required && formData.photos.length === 0" class="attachment-required-notice">
          <van-icon name="info-o" color="#ff976a" />
          <span>此项需要上传至少1张照片作为检查凭证</span>
        </div>
        
        <div class="upload-area">
          <van-uploader
            v-model="photoList"
            :multiple="true"
            :max-count="5"
            preview-size="80"
            :after-read="onPhotoRead"
            @delete="onPhotoDelete"
          >
            <template #preview-cover="{ file }">
              <div class="preview-cover"></div>
            </template>
          </van-uploader>
          <div class="upload-tip">
            <van-icon name="photo-o" size="20" />
            <span>拍照或上传图片</span>
          </div>
        </div>
        
        <div class="upload-info">
          <van-icon name="info-o" size="12" color="#999" />
          <span>照片将自动压缩至500KB以下并添加时间、位置水印</span>
        </div>
      </div>

      <!-- AI 生成建议 -->
      <div v-if="itemData?.use_ai" class="ai-card">
        <van-button
          type="primary"
          block
          :loading="aiLoading"
          loading-text="AI 分析中..."
          @click="generateAI"
          class="ai-button"
        >
          <van-icon name="chat-o" size="18" />
          AI 生成检查结论
        </van-button>

        <div v-if="aiThinking || aiResult" class="ai-result">
          <div v-if="aiThinking" class="ai-thinking">
            <div class="ai-thinking-header">
              <van-loading size="16" color="#667eea" />
              <span>AI 思考中...</span>
            </div>
            <div class="ai-thinking-content">{{ aiThinkingContent }}</div>
          </div>
          
          <div v-if="aiResult" class="ai-final">
            <div class="ai-result-header">
              <van-icon name="success" color="#4CAF50" />
              <span>AI 建议已生成</span>
            </div>
            <div class="ai-result-content">
              <div v-if="aiResult.suggestion" class="ai-section">
                <div class="ai-label">检查建议</div>
                <div class="ai-value">{{ aiResult.suggestion }}</div>
              </div>
            </div>
            <div class="ai-actions">
              <van-button size="small" type="primary" @click="acceptAI">采纳建议</van-button>
              <van-button size="small" @click="clearAI">取消</van-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 备注说明 -->
      <div class="note-card">
        <div class="card-header">
          <span class="card-title">备注说明</span>
        </div>
        <van-field
          v-model="formData.inspector_note"
          type="textarea"
          rows="2"
          placeholder="添加备注（可选）"
          autosize
        />
      </div>
    </div>

    <!-- 底部保存按钮 -->
    <div class="bottom-bar">
      <van-button type="primary" block @click="saveItem" :loading="saving">
        保存结果
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showSuccessToast, showNotify } from 'vant'
import request from '../api/request.js'
import { processPhoto, blobToBase64 } from '../utils/photoUtils.js'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const saving = ref(false)
const aiLoading = ref(false)
const aiThinking = ref(false)
const aiThinkingContent = ref('')
const itemData = ref(null)
const aiResult = ref(null)
const showKnowledge = ref(false)
const historyStats = ref(null)
const loadingHistory = ref(false)
const showHistoryDetail = ref(false)
const trendCanvas = ref(null)

const formData = ref({
  result: '',
  result_value: '',
  result_text: '',
  score_value: 0,
  radio_value: '',
  multi_value: [],
  numeric_value: '',
  text_value: '',
  problem_description: '',
  rectification_suggestion: '',
  inspector_note: '',
  photos: [],
})

const photoList = ref([])

// 计算属性
const hasKnowledgeBase = computed(() => {
  return itemData.value?.description || itemData.value?.legal_basis || itemData.value?.standard_ref || itemData.value?.check_method
})

const resultOptions = computed(() => {
  if (itemData.value?.result_options && Array.isArray(itemData.value.result_options)) {
    return itemData.value.result_options
  }
  return [
    { label: '合格', value: 'pass' },
    { label: '不合格', value: 'fail' },
    { label: '不适用', value: 'na' }
  ]
})

const isFailRequired = computed(() => {
  const checkType = itemData.value?.result_type || itemData.value?.check_type || 'pass_fail'
  return checkType === 'pass_fail' && formData.value.radio_value === 'fail'
})

const riskLevelText = computed(() => {
  const map = {
    'high': '高风险',
    'medium': '中风险',
    'low': '低风险'
  }
  return map[itemData.value?.risk_level] || ''
})

const numericPlaceholder = computed(() => {
  if (itemData.value?.min_value !== null && itemData.value?.max_value !== null) {
    return `请输入 ${itemData.value.min_value} ~ ${itemData.value.max_value}`
  }
  return '请输入测量值'
})

const formatRange = computed(() => {
  const min = itemData.value?.min_value
  const max = itemData.value?.max_value
  const unit = itemData.value?.unit || ''

  if (min !== null && max !== null) {
    return `${min} ~ ${max} ${unit}`.trim()
  } else if (min !== null) {
    return `≥ ${min} ${unit}`.trim()
  } else if (max !== null) {
    return `≤ ${max} ${unit}`.trim()
  }
  return ''
})

// 打分类型自动判定
const scoreJudgmentClass = computed(() => {
  if (!itemData.value?.pass_score || formData.value.score_value === '' || formData.value.score_value === null) return ''
  return Number(formData.value.score_value) >= Number(itemData.value.pass_score) ? 'pass' : 'fail'
})

const scoreJudgmentIcon = computed(() => {
  return scoreJudgmentClass.value === 'pass' ? 'success' : 'cross'
})

const scoreJudgmentText = computed(() => {
  return scoreJudgmentClass.value === 'pass' ? '合格' : '不合格'
})

// 数值类型自动判定
const numericJudgmentClass = computed(() => {
  const val = formData.value.numeric_value
  if (val === '' || val === null || val === undefined) return ''

  const numVal = Number(val)
  const min = itemData.value?.min_value
  const max = itemData.value?.max_value

  // 没有范围限制则无法判定
  if (min === null && max === null) return ''

  // 检查是否在范围内
  const inRange = (min === null || numVal >= Number(min)) && (max === null || numVal <= Number(max))
  return inRange ? 'pass' : 'fail'
})

const numericJudgmentIcon = computed(() => {
  return numericJudgmentClass.value === 'pass' ? 'success' : 'cross'
})

const numericJudgmentText = computed(() => {
  return numericJudgmentClass.value === 'pass' ? '符合标准' : '超出标准范围'
})

const numericJudgmentDetail = computed(() => {
  const val = formData.value.numeric_value
  const min = itemData.value?.min_value
  const max = itemData.value?.max_value
  const unit = itemData.value?.unit || ''

  if (min !== null && max !== null) {
    const range = `${min} ~ ${max} ${unit}`.trim()
    return `（${val}${unit} ${numericJudgmentClass.value === 'pass' ? '在' : '不在'}范围 ${range} 内）`
  } else if (min !== null) {
    return `（${val}${unit} ${Number(val) >= Number(min) ? '≥' : '<'} ${min}${unit}）`
  } else if (max !== null) {
    return `（${val}${unit} ${Number(val) <= Number(max) ? '≤' : '>'} ${max}${unit}）`
  }
  return ''
})

const getHistoryCardClass = computed(() => {
  if (!historyStats.value) return ''
  if (historyStats.value.fail_count > 0) return 'has-fail'
  return 'all-pass'
})

const getHistoryIconColor = computed(() => {
  if (!historyStats.value) return '#007AFF'
  if (historyStats.value.fail_count > 0) return '#ff4d4f'
  return '#34C759'
})

// 整改效果改善率计算
const trendImprovement = computed(() => {
  if (!historyStats.value?.history_records || historyStats.value.history_records.length < 2) {
    return null
  }
  const records = historyStats.value.history_records
  // 取前半部分和后半部分比较
  const mid = Math.floor(records.length / 2)
  const earlier = records.slice(0, mid)
  const later = records.slice(mid)

  const earlierPassRate = earlier.filter(r => r.result === 'pass').length / earlier.length * 100
  const laterPassRate = later.filter(r => r.result === 'pass').length / later.length * 100

  return Math.round(laterPassRate - earlierPassRate)
})

// 绘制趋势图表
const drawTrendChart = () => {
  const canvas = trendCanvas.value
  if (!canvas || !historyStats.value?.history_records) return

  const records = historyStats.value.history_records
  if (records.length < 2) return

  const ctx = canvas.getContext('2d')
  const width = canvas.width
  const height = canvas.height
  const padding = 30
  const chartWidth = width - padding * 2
  const chartHeight = height - padding * 2

  // 清空画布
  ctx.clearRect(0, 0, width, height)

  // 绘制背景网格
  ctx.strokeStyle = '#f0f0f0'
  ctx.lineWidth = 1
  for (let i = 0; i <= 4; i++) {
    const y = padding + (chartHeight / 4) * i
    ctx.beginPath()
    ctx.moveTo(padding, y)
    ctx.lineTo(width - padding, y)
    ctx.stroke()
  }

  // 计算数据点
  const points = records.map((record, index) => {
    const x = padding + (chartWidth / (records.length - 1)) * index
    // Y轴：合格为高点，不合格为低点
    const y = record.result === 'pass' ? padding + chartHeight * 0.2 : padding + chartHeight * 0.8
    return { x, y, result: record.result }
  })

  // 绘制折线
  ctx.beginPath()
  ctx.strokeStyle = '#007AFF'
  ctx.lineWidth = 2
  points.forEach((point, index) => {
    if (index === 0) {
      ctx.moveTo(point.x, point.y)
    } else {
      ctx.lineTo(point.x, point.y)
    }
  })
  ctx.stroke()

  // 绘制数据点
  points.forEach(point => {
    ctx.beginPath()
    ctx.arc(point.x, point.y, 5, 0, Math.PI * 2)
    ctx.fillStyle = point.result === 'pass' ? '#34C759' : '#ff4d4f'
    ctx.fill()
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.stroke()
  })

  // 绘制X轴标签（检查日期）
  ctx.fillStyle = '#999'
  ctx.font = '10px sans-serif'
  ctx.textAlign = 'center'
  records.forEach((record, index) => {
    const x = padding + (chartWidth / (records.length - 1)) * index
    const dateStr = record.inspection_date ? record.inspection_date.substring(5, 10) : ''
    ctx.fillText(dateStr, x, height - 5)
  })
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

// 获取多选项标签
const getMultiCheckLabel = (value) => {
  const opt = resultOptions.value?.find(o => o.value === value)
  return opt?.label || value
}

// 加载数据
const fetchItemData = async () => {
  loading.value = true
  try {
    const recordId = route.params.id
    const itemId = route.params.itemId

    const res = await request.get(`/records/${recordId}/items/${itemId}`)
    itemData.value = res.data

    // 填充表单数据
    formData.value = {
      result: itemData.value.result || '',
      result_value: itemData.value.result_value || '',
      result_text: itemData.value.result_text || '',
      score_value: itemData.value.score_value || '',
      radio_value: itemData.value.radio_value || '',
      multi_value: itemData.value.multi_value || [],
      numeric_value: itemData.value.numeric_value || '',
      text_value: itemData.value.text_value || '',
      problem_description: itemData.value.problem_description || '',
      rectification_suggestion: itemData.value.rectification_suggestion || '',
      inspector_note: itemData.value.inspector_note || '',
      photos: itemData.value.photos || [],
    }

    // Normalize photo URLs (ensure forward slashes and leading /)
    const normalizeUrl = (url) => {
      if (!url) return url
      url = url.replace(/\\/g, '/')
      if (url.startsWith('http')) return url
      if (!url.startsWith('/')) url = '/' + url
      return url
    }
    formData.value.photos = formData.value.photos.map(normalizeUrl)

    // 设置照片列表
    photoList.value = formData.value.photos.map((url, index) => ({
      url,
      isImage: true,
    }))

    // 获取历史统计数据
    fetchHistoryStats()

  } catch (error) {
    console.error('获取检查项失败:', error)
    showToast('获取检查项失败')
  } finally {
    loading.value = false
  }
}

// 获取历史统计数据
const fetchHistoryStats = async () => {
  loadingHistory.value = true
  try {
    const recordId = route.params.id
    const itemId = route.params.itemId
    const res = await request.get(`/records/${recordId}/items/${itemId}/history-stats`)
    historyStats.value = res.data
    // 等待 DOM 更新后绘制趋势图
    await nextTick()
    drawTrendChart()
  } catch (error) {
    console.error('获取历史统计失败:', error)
  } finally {
    loadingHistory.value = false
  }
}

// 照片上传
const onPhotoRead = async (file) => {
  try {
    if (Array.isArray(file)) {
      for (const f of file) {
        await handlePhotoUpload(f)
      }
    } else {
      await handlePhotoUpload(file)
    }
  } catch (error) {
    console.error('照片处理失败:', error)
    showToast('照片处理失败')
  }
}

const handlePhotoUpload = async (file) => {
  file.status = 'uploading'
  file.message = '处理中...'

  try {
    const inspectorName = localStorage.getItem('userName') || '检查员'
    
    const processed = await processPhoto(file.file, {
      addWatermark: true,
      compress: true,
      inspector: inspectorName,
      targetSize: 500 * 1024
    })

    console.log(`照片处理完成: 原始 ${processed.originalSize} -> 最终 ${processed.finalSize} bytes`)

    const uploadFormData = new FormData()
    const processedFile = new File([processed.blob], `photo_${Date.now()}.jpg`, { type: 'image/jpeg' })
    uploadFormData.append('file', processedFile)
    if (itemData.value?.task_id) {
      uploadFormData.append('task_id', itemData.value.task_id)
    }
    uploadFormData.append('record_id', route.params.id)

    const res = await request.post('/media/upload', uploadFormData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    const filePath = res.data?.file_path || res.file_path
    if (filePath) {
      formData.value.photos.push(filePath)
      file.status = 'done'
      file.url = filePath
      file.isImage = true
      showSuccessToast('上传成功')
    } else {
      throw new Error('上传响应无效')
    }
  } catch (error) {
    console.error('照片上传失败:', error)
    file.status = 'failed'
    file.message = '上传失败'
    showToast('照片上传失败: ' + error.message)
  }
}

const onPhotoDelete = (file, detail) => {
  const index = detail?.index ?? 0
  formData.value.photos.splice(index, 1)
}

// AI 生成
const generateAI = async () => {
  aiLoading.value = true
  aiThinking.value = true
  aiThinkingContent.value = ''
  aiResult.value = null
  
  try {
    const recordId = route.params.id
    const itemId = route.params.itemId
    const token = localStorage.getItem('token')
    
    const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const response = await fetch(`${API_BASE_URL}/api/records/${recordId}/items/${itemId}/ai-stream`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'text/event-stream',
      },
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
            
            if (data.type === 'thinking') {
              aiThinkingContent.value += data.content
            } else if (data.type === 'done') {
              aiResult.value = {
                suggestion: data.content,
                fullContent: data.full_content,
              }
              aiThinking.value = false
            } else if (data.type === 'error') {
              showToast('AI 生成失败: ' + data.content)
              aiThinking.value = false
            }
          } catch (e) {
            console.error('解析数据失败:', e)
          }
        }
      }
    }
  } catch (error) {
    console.error('AI 生成失败:', error)
    showToast('AI 生成失败，请稍后重试')
    aiThinking.value = false
  } finally {
    aiLoading.value = false
  }
}

// 清除 AI 结果
const clearAI = () => {
  aiResult.value = null
  aiThinkingContent.value = ''
}

// 采纳 AI 建议
const acceptAI = () => {
  if (aiResult.value?.suggestion) {
    formData.value.inspector_note = aiResult.value.suggestion
  }
  aiResult.value = null
  showSuccessToast('已采纳 AI 建议')
}

// 保存
const saveItem = async () => {
  saving.value = true
  try {
    const recordId = route.params.id
    const checkType = itemData.value?.result_type || itemData.value?.check_type || 'pass_fail'

    if (itemData.value?.attachment_required && formData.value.photos.length === 0) {
      showToast('该检查项需要上传附件照片，请至少上传一张照片')
      saving.value = false
      return
    }

    if (checkType === 'pass_fail' && formData.value.radio_value === 'fail') {
      if (!formData.value.problem_description || formData.value.problem_description.trim() === '') {
        showToast('不合格项必须填写问题描述')
        saving.value = false
        return
      }
    }

    const saveData = {
      id: itemData.value.id,
      template_item_id: itemData.value.template_item_id,
      ...formData.value,
    }

    await request.post(`/records/${recordId}/items`, saveData)
    showSuccessToast('保存成功')

    router.replace(`/inspection/${recordId}?t=${Date.now()}`)
  } catch (error) {
    console.error('保存失败:', error)
    showToast('保存失败')
  } finally {
    saving.value = false
  }
}

// 返回
const goBack = () => {
  router.back()
}

onMounted(async () => {
  await fetchItemData()
})
</script>

<style scoped>
.inspect-item-page {
  min-height: 100vh;
  background: var(--bg-light);
  padding-bottom: 80px;
}

.loading-container {
  padding: 20px;
}

.item-content {
  padding: 12px;
}

.item-header-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

.item-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  flex: 1;
  line-height: 1.4;
  font-family: var(--font-primary);
}

.item-description {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 8px 0 0;
  line-height: 1.5;
}

.risk-tag {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 6px;
  border-radius: var(--radius-xs);
  font-size: 11px;
  font-weight: 500;
  flex-shrink: 0;
}

.risk-tag.high {
  background: var(--error-bg);
  color: var(--error-color);
}

.risk-tag.medium {
  background: var(--warning-bg);
  color: var(--warning-color);
}

.risk-tag.low {
  background: var(--success-bg);
  color: var(--success-color);
}

.knowledge-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  margin-bottom: 12px;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

.knowledge-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  cursor: pointer;
}

.knowledge-title {
  flex: 1;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

.knowledge-content {
  padding: 0 16px 16px;
}

.knowledge-item {
  margin-bottom: 12px;
}

.knowledge-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.knowledge-value {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
  background: var(--bg-light);
  padding: 10px;
  border-radius: var(--radius-sm);
}

.knowledge-value.method-value {
  background: var(--info-bg);
  color: var(--primary-color);
}

.result-card,
.problem-card,
.attachment-card,
.note-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.card-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

.required-tag {
  font-size: 12px;
  color: var(--error-color);
  background: var(--error-bg);
  padding: 2px 8px;
  border-radius: var(--radius-xs);
}

.photo-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.attachment-card.attachment-required {
  border: 2px dashed var(--primary-light);
  background: rgba(14, 165, 233, 0.03);
}

.attachment-required-notice {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  background: var(--info-bg);
  border-radius: var(--radius-sm);
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--primary-color);
}

.result-input {
  background: var(--bg-light);
  border-radius: var(--radius-sm);
  padding: 12px;
}

.radio-input :deep(.van-radio-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.fail-hint-box {
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--error-bg);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--error-color);
}

.fail-hint-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--error-color);
}

.problem-card.required-problem {
  border: 1px solid rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.02);
}

.score-input {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.score-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.score-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.score-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--primary-color);
}

.pass-score-hint {
  font-size: 12px;
  color: var(--success-color);
}

.score-judgment,
.numeric-judgment {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  margin-top: 12px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
}

.score-judgment.pass,
.numeric-judgment.pass {
  background: rgba(52, 199, 89, 0.1);
  color: var(--success-color);
  border: 1px solid rgba(52, 199, 89, 0.3);
}

.score-judgment.fail,
.numeric-judgment.fail {
  background: rgba(255, 77, 79, 0.1);
  color: var(--error-color);
  border: 1px solid rgba(255, 77, 79, 0.3);
}

.judgment-detail {
  font-weight: 400;
  opacity: 0.8;
}

.multi-summary {
  margin-top: 12px;
  padding: 12px;
  background: rgba(0, 122, 255, 0.05);
  border-radius: var(--radius-sm);
  border: 1px solid rgba(0, 122, 255, 0.2);
}

.summary-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--primary-color);
  margin-bottom: 8px;
}

.summary-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.numeric-input .numeric-range {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--warning-color);
  margin-top: 8px;
}

.unit-text {
  font-size: 13px;
  color: var(--text-secondary);
}

.upload-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.upload-tip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: var(--text-secondary);
  font-size: 12px;
}

.ai-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

.ai-button {
  background: var(--primary-gradient);
  border: none;
  font-weight: 500;
  box-shadow: var(--shadow-primary);
}

.ai-result {
  margin-top: 16px;
  padding: 16px;
  background: var(--bg-light);
  border-radius: var(--radius-sm);
}

.ai-thinking {
  margin-bottom: 16px;
}

.ai-thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
  color: var(--primary-color);
}

.ai-thinking-content {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg-white);
  padding: 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.ai-final {
  margin-top: 16px;
}

.ai-result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
  color: var(--success-color);
}

.ai-section {
  margin-bottom: 12px;
}

.ai-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.ai-value {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
}

.ai-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px;
  background: var(--bg-white);
  box-shadow: 0 -2px 10px rgba(3, 105, 161, 0.05);
}

:deep(.van-radio__label) {
  font-size: 14px;
  color: var(--text-primary);
}

:deep(.van-checkbox__label) {
  font-size: 14px;
  color: var(--text-primary);
}

.upload-info {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
}

.history-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

.history-card.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 14px;
}

.history-card.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 13px;
  padding: 16px;
}

.history-card.has-fail {
  border: 1px solid rgba(239, 68, 68, 0.3);
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.02) 0%, rgba(239, 68, 68, 0.05) 100%);
}

.history-card.all-pass {
  border: 1px solid rgba(16, 185, 129, 0.2);
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.02) 0%, rgba(16, 185, 129, 0.04) 100%);
}

.history-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.history-title {
  flex: 1;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

.history-warning-badge {
  background: var(--error-bg);
  color: var(--error-color);
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.history-stats-row {
  display: flex;
  justify-content: space-around;
  padding: 12px 0;
  background: var(--bg-light);
  border-radius: var(--radius-sm);
  margin-bottom: 12px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-value.fail {
  color: var(--error-color);
}

.stat-value.pass {
  color: var(--success-color);
}

.stat-value.high-fail {
  color: var(--error-color);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.last-result-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-light);
  border-radius: var(--radius-sm);
  margin-bottom: 12px;
}

.last-result-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.last-result-value {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 500;
}

.last-result-value.pass {
  color: var(--success-color);
}

.last-result-value.fail {
  color: var(--error-color);
}

.last-result-value.na {
  color: var(--text-muted);
}

.last-result-date {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: auto;
}

.history-detail {
  border-top: 1px solid var(--border-light);
  padding-top: 12px;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: var(--primary-color);
  cursor: pointer;
  padding: 4px 0;
}

.detail-list {
  margin-top: 12px;
}

.detail-item {
  padding: 10px 12px;
  background: var(--error-bg);
  border-radius: var(--radius-sm);
  margin-bottom: 8px;
  border-left: 3px solid var(--error-color);
}

.detail-item:last-child {
  margin-bottom: 0;
}

.detail-date {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.detail-problem {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
  margin-bottom: 4px;
}

.detail-inspector {
  font-size: 12px;
  color: var(--text-secondary);
}

.history-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  background: var(--warning-bg);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--warning-color);
  margin-top: 12px;
}

/* 趋势图表样式 */
.trend-chart-section {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-light);
  border-radius: var(--radius-sm);
}

.trend-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.trend-period {
  font-size: 11px;
  color: var(--text-muted);
}

.trend-canvas {
  width: 100%;
  height: 120px;
  background: var(--bg-white);
  border-radius: var(--radius-xs);
}

.trend-legend {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-secondary);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-dot.pass {
  background: var(--success-color);
}

.legend-dot.fail {
  background: var(--error-color);
}

.improvement-section {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--bg-white);
  border-radius: var(--radius-xs);
  font-size: 13px;
}

.improvement-section .text-success {
  color: var(--success-color);
  font-weight: 500;
}

.improvement-section .text-danger {
  color: var(--error-color);
  font-weight: 500;
}

.improvement-detail {
  color: var(--text-secondary);
  font-size: 12px;
}

/* 高风险预警徽章 */
.high-risk-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: rgba(255, 77, 79, 0.15);
  color: var(--error-color);
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: 500;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
</style>