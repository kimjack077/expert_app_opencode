<template>
  <div class="inspection-execution-page">
    <div class="page-header">
      <div class="header-bg"></div>
      <div class="header-content">
        <div class="header-nav">
          <div class="back-btn" @click="goBack">
            <van-icon name="arrow-left" size="24" color="#fff" />
          </div>
          <h1 class="header-title">现场检查</h1>
          <div class="header-actions" @click="showSubmitConfirm">
            <van-icon name="success" size="24" color="#fff" />
          </div>
        </div>
        <div v-if="record" class="header-info">
          <div class="enterprise-name">
            <span class="enterprise-name-text">{{ record.enterprise_name || '未指定企业' }}</span>
            <span v-if="riskProfile" class="risk-badge" :class="riskLevelClass" @click="showRiskAlert = true">
              <van-icon name="warning-o" size="12" />
              {{ riskLevelText }}
            </span>
            <span v-if="showQuantified" class="total-score-badge">总分: {{ totalScore }}</span>
          </div>
          <div class="template-name">{{ record.template?.name }} ({{ record.template?.version }})</div>
          <div class="offline-row">
            <span v-if="offlineMode" class="offline-chip offline">
              <van-icon name="warning-o" size="12" /> 离线模式 · 本地缓存，填写不会上传
            </span>
            <span v-else-if="cachedEntry" class="offline-chip cached">
              <van-icon name="passed" size="12" /> 离线可用 · {{ formatCachedAt(cachedEntry.cachedAt) }}
            </span>
            <van-button
              v-if="!offlineMode"
              size="mini"
              plain
              round
              :loading="caching"
              class="offline-cache-btn"
              @click="cacheCurrentForOffline"
            >
              {{ cachedEntry ? '更新缓存' : '缓存到本地' }}
            </van-button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <van-skeleton title :row="10" />
    </div>

    <div v-else-if="record" class="inspection-content">
      <!-- 进度条 -->
      <div class="progress-card">
        <div class="progress-header">
          <span class="progress-label">检查进度</span>
          <span class="progress-count">{{ completedCount }}/{{ totalCheckItems }}
            <span v-if="requiredCheckItems < totalCheckItems" style="font-size:11px;color:#888;font-weight:400"> (必填 {{ requiredCompletedCount }}/{{ requiredCheckItems }})</span>
          </span>
        </div>
        <van-progress
          :percentage="progressPercentage"
          :stroke-width="8"
          :show-pivot="false"
          :color="progressColor"
        />
        <div class="progress-hint">
          <span v-if="totalCheckItems === 0">检查项加载中，请稍候…</span>
          <span v-else-if="completedCount === 0">请开始填写检查项</span>
          <span v-else-if="requiredCompletedCount < requiredCheckItems">必填项还有 {{ requiredCheckItems - requiredCompletedCount }} 项未完成</span>
          <span v-else class="complete">必填项已全完成，请在下方填写最终判定</span>
        </div>
      </div>

      <!-- 检查项列表 -->
      <div class="items-container">
        <van-empty
          v-if="flattenItems.length === 0"
          description="暂无检查项。请确认任务已关联检查模板（Web 端计划项需选择模板）"
        />
        <template v-for="item in flattenItems" :key="item.id">
          <!-- 分类节点 -->
          <div
            v-if="item.is_category"
            class="category-node"
            :style="{ paddingLeft: (item.level * 16) + 'px' }"
            @click="toggleCategory(item.id)"
          >
            <div class="category-icon" :class="{ expanded: expandedItems.includes(item.id) }">
              <van-icon :name="expandedItems.includes(item.id) ? 'arrow-down' : 'arrow-right'" size="14" />
            </div>
            <span class="category-title">{{ item.title }}</span>
            <span class="category-count">{{ getCategoryProgress(item) }}</span>
          </div>

          <!-- 检查项 - 带快速录入 -->
          <div
            v-else-if="isItemVisible(item)"
            class="check-item-card"
            :class="{ 'has-result': isItemCompleted(item) }"
            :style="{ paddingLeft: (item.level * 16 + 16) + 'px' }"
          >
            <div class="item-main" @click="goToItem(item)">
              <div class="item-status" :class="getItemStatus(item)">
                <van-icon v-if="isItemCompleted(item)" name="success" size="16" />
                <span v-else class="status-dot"></span>
              </div>
              <div class="item-info">
                <div class="item-title-row">
                  <span class="item-title">{{ item.title }} <span v-if="showQuantified && getItemScore(item) !== null" class="item-score">({{ getItemScore(item) }}分)</span></span>
                  <span v-if="item.is_required !== false" class="item-required-tag">必填</span>
                  <span v-if="item.attachment_required" class="item-attachment-tag">
                    <van-icon name="photo-o" size="10" /> 附件
                  </span>
                  <span class="item-type-tag">{{ getResultTypeLabel(item.result_type) }}</span>
                </div>
                <div v-if="isItemCompleted(item)" class="item-result-preview">
                  {{ getItemResultText(item) }}
                </div>
                <div v-else-if="item.attachment_required && itemResults[item.id]?.radio_value && !hasAttachment(item)" class="item-incomplete-hint">
                  <van-icon name="info-o" size="12" /> 需上传附件
                </div>
              </div>
              <van-icon name="arrow" size="14" color="#999" class="detail-arrow" />
            </div>

            <!-- 快速录入区域 -->
            <div class="quick-input-area" @click.stop>
              <!-- 判定型 (pass_fail / radio) -->
              <div v-if="item.result_type === 'pass_fail' || item.check_type === 'pass_fail' || item.check_type === 'radio' || (!item.result_type && !item.check_type)" class="quick-radio">
                <van-radio-group
                  v-model="quickInputs[item.id].radio_value"
                  direction="horizontal"
                  @change="(val) => onQuickInput(item, 'radio_value', val)"
                >
                  <van-radio
                    v-for="opt in getItemResultOptions(item)"
                    :key="opt.value"
                    :name="opt.value"
                    shape="square"
                  >{{ opt.label }}</van-radio>
                </van-radio-group>
                <div
                  v-if="getItemResultOptions(item).some(o => o.value === 'not_applicable' || o.value === 'na')"
                  class="na-tip"
                >
                  「不适用」= 该条款不涉及本次受审对象，不计入不合格、不触发整改、不纳入合规率
                </div>
                <div v-if="quickInputs[item.id].radio_value === 'fail'" class="fail-description">
                  <van-field
                    v-model="quickInputs[item.id].problem_description"
                    type="textarea"
                    rows="2"
                    placeholder="请描述不合格问题（必填）..."
                    autosize
                    @blur="onQuickInput(item, 'problem_description', quickInputs[item.id].problem_description)"
                  />
                </div>
              </div>

              <!-- 数值型 -->
              <div v-else-if="item.result_type === 'numeric'" class="quick-numeric">
                <van-field
                  v-model="quickInputs[item.id].numeric_value"
                  type="number"
                  :placeholder="`输入数值${item.unit ? '(' + item.unit + ')' : ''}`"
                  @blur="onQuickInput(item, 'numeric_value', quickInputs[item.id].numeric_value)"
                  @keyup.enter="onQuickInput(item, 'numeric_value', quickInputs[item.id].numeric_value)"
                >
                  <template #button v-if="item.unit">
                    <span class="unit-label">{{ item.unit }}</span>
                  </template>
                </van-field>
                <div v-if="item.min_value !== null || item.max_value !== null" class="range-hint">
                  标准: {{ formatRange(item.min_value, item.max_value, item.unit) }}
                </div>
                <!-- 自动范围判定 -->
                <div v-if="getNumericJudgmentClass(item) && quickInputs[item.id].numeric_value !== '' && quickInputs[item.id].numeric_value !== null" class="numeric-judgment" :class="getNumericJudgmentClass(item)">
                  <van-icon :name="getNumericJudgmentIcon(item)" />
                  <span>{{ getNumericJudgmentText(item) }}</span>
                </div>
              </div>

              <!-- 文本型 -->
              <div v-else-if="item.result_type === 'text'" class="quick-text">
                <van-field
                  v-model="quickInputs[item.id].text_value"
                  type="textarea"
                  rows="2"
                  placeholder="输入检查描述..."
                  autosize
                  @blur="onQuickInput(item, 'text_value', quickInputs[item.id].text_value)"
                />
              </div>

              <!-- 打分型 -->
              <div v-else-if="item.result_type === 'score'" class="quick-score">
                <div class="score-row">
                  <van-stepper
                    v-model="quickInputs[item.id].score_value"
                    :min="0"
                    :max="Number(item.max_score) || 100"
                    :step="Number(item.score_step) || 1"
                    theme="round"
                    button-size="24"
                    @change="(val) => onQuickInput(item, 'score_value', val)"
                  />
                  <span class="score-max">/ {{ item.max_score || 100 }} 分</span>
                </div>
                <div v-if="item.pass_score" class="pass-hint">
                  合格线: {{ item.pass_score }} 分
                </div>
                <!-- 自动合格判定 -->
                <div v-if="item.pass_score && quickInputs[item.id].score_value !== null && quickInputs[item.id].score_value !== undefined" class="score-judgment" :class="getScoreJudgmentClass(item)">
                  <van-icon :name="getScoreJudgmentIcon(item)" />
                  <span>{{ getScoreJudgmentText(item) }}</span>
                </div>
              </div>

              <!-- 多选型 -->
              <div v-else-if="item.result_type === 'multi_check'" class="quick-multi">
                <van-checkbox-group
                  v-model="quickInputs[item.id].multi_value"
                  direction="horizontal"
                  @change="(val) => onQuickInput(item, 'multi_value', val)"
                >
                  <van-checkbox
                    v-for="opt in getItemResultOptions(item)"
                    :key="opt.value"
                    :name="opt.value"
                    shape="square"
                  >{{ opt.label }}</van-checkbox>
                </van-checkbox-group>
              </div>
            </div>
          </div>
        </template>

        <van-empty v-if="flattenItems.length === 0" description="该模板暂无检查项目" image="search">
          <template #description>
            <p>该模板尚未配置检查项目</p>
            <p class="empty-hint">请联系管理员添加检查项</p>
          </template>
        </van-empty>
      </div>

      <!-- 最终判定区域 -->
      <div v-if="requiredCompletedCount >= requiredCheckItems && requiredCheckItems > 0" class="final-judgment-section">
        <div class="section-title">
          <van-icon name="certificate" color="#4F46E5" />
          <span>最终判定结论</span>
        </div>

        <!-- 统计汇总 -->
        <div class="stats-summary-card">
          <div class="stats-title">检查结果汇总</div>
          <div class="stats-grid">
            <div class="stat-item pass">
              <div class="stat-value">{{ passCount }}</div>
              <div class="stat-label">符合项</div>
            </div>
            <div class="stat-item fail">
              <div class="stat-value">{{ failCount }}</div>
              <div class="stat-label">不符合项</div>
            </div>
            <div class="stat-item na">
              <div class="stat-value">{{ naCount }}</div>
              <div class="stat-label">不适用项</div>
            </div>
            <div class="stat-item total">
              <div class="stat-value">{{ totalCheckItems }}</div>
              <div class="stat-label">总检查项</div>
            </div>
            <div v-if="showQuantified" class="stat-item score">
              <div class="stat-value" style="color:#F59E0B">{{ totalScore }}</div>
              <div class="stat-label">最终得分</div>
            </div>
          </div>
        </div>

        <div class="judgment-card">
          <div class="judgment-label">判定结果</div>
          <van-radio-group v-model="finalJudgment.result" direction="horizontal" class="judgment-radio">
            <van-radio name="pass" shape="square">
              <span class="pass-text">合格</span>
            </van-radio>
            <van-radio name="partial_pass" shape="square">
              <span class="partial-text">基本合格</span>
            </van-radio>
            <van-radio name="fail" shape="square">
              <span class="fail-text">不合格</span>
            </van-radio>
          </van-radio-group>

          <div class="judgment-label">判定说明</div>
          
          <!-- AI 生成按钮 -->
          <van-button
            type="primary"
            block
            :loading="aiJudgmentLoading"
            loading-text="AI 分析中..."
            @click="generateFinalJudgment"
            class="ai-judgment-btn"
          >
            <van-icon name="chat-o" size="18" />
            AI 生成最终判定
          </van-button>

          <!-- AI 思考过程 -->
          <div v-if="aiJudgmentThinking || aiJudgmentResult" class="ai-judgment-result">
            <div v-if="aiJudgmentThinking" class="ai-thinking">
              <div class="ai-thinking-header">
                <van-loading size="16" color="#667eea" />
                <span>AI 分析中...</span>
              </div>
              <div class="ai-thinking-content">{{ aiJudgmentThinkingContent }}</div>
            </div>
            
            <div v-if="aiJudgmentResult" class="ai-final">
              <div class="ai-result-header">
                <van-icon name="success" color="#4CAF50" />
                <span>AI 建议已生成</span>
              </div>
              <div v-if="aiJudgmentResultType" class="ai-judgment-type">
                建议判定：
                <span v-if="aiJudgmentResultType === 'pass'" class="pass-text">合格</span>
                <span v-else-if="aiJudgmentResultType === 'partial_pass'" class="partial-text">基本合格</span>
                <span v-else-if="aiJudgmentResultType === 'fail'" class="fail-text">不合格</span>
              </div>
              <div class="ai-result-content">
                {{ aiJudgmentResult }}
              </div>
              <div class="ai-actions">
                <van-button size="small" type="primary" @click="acceptAIJudgment">采纳建议</van-button>
                <van-button size="small" @click="clearAIJudgment">取消</van-button>
              </div>
            </div>
          </div>

          <van-field
            v-model="finalJudgment.remarks"
            type="textarea"
            rows="4"
            placeholder="请输入判定说明（如有问题请详细描述）..."
            autosize
            show-word-limit
            maxlength="1000"
          />
        </div>
      </div>
    </div>

    <van-empty v-else description="检查记录不存在" />

    <!-- 底部提交按钮 -->
    <div class="action-bar">
      <van-button
        type="primary"
        block
        :disabled="!canSubmit"
        :loading="submitting"
        @click="showSubmitConfirm"
        class="submit-btn"
        :class="{ 'ready-submit': canSubmit }"
      >
        {{ submitButtonText }}
      </van-button>
      <div class="submit-hint" v-if="!canSubmit">
        <span v-if="totalCheckItems === 0">
          检查项加载中，请稍候…
        </span>
        <span v-else-if="completedCount < totalCheckItems">
          需完成全部 {{ totalCheckItems }} 项检查，当前已完成 {{ completedCount }} 项
        </span>
        <span v-else-if="!finalJudgment.result">
          ✓ 检查项已全部完成，请在上方填写【最终判定结论】后提交
        </span>
      </div>
    </div>

    <!-- 风险预警弹窗 -->
    <RiskAlertPopup
      v-model:show="showRiskAlert"
      :enterprise-id="record?.enterprise_id"
      :enterprise-name="record?.enterprise_name"
      :risk-profile="riskProfile"
      @confirm="onRiskAlertConfirm"
      @view-history="onViewRiskHistory"
    />

    <!-- AI 助手 -->
    <AgentFab @click="showAgentPanel = true" />
    <AgentChatPanel
      v-model:show="showAgentPanel"
      :context="agentContext"
      @result-applied="onAgentResultApplied"
      @verdict-applied="onAgentVerdictApplied"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import { getRecord, submitRecord, updateRecord, createOrUpdateRecordItem, getEnterpriseRiskProfile } from '../api/records'
import {
  getTask,
  getTaskRecords,
  getTemplateItems,
  submitCheckRecord,
  startTask,
  completeTask,
  updateTask,
} from '../api/tasks'
import RiskAlertPopup from '../components/RiskAlertPopup.vue'
import AgentFab from '../components/agent/AgentFab.vue'
import AgentChatPanel from '../components/agent/AgentChatPanel.vue'
import {
  cacheRecordForOffline,
  cacheTaskForOffline,
  formatCachedAt,
  getCachedEntry,
  isOnline,
} from '@/utils/offlineCache.js'
import { hasQuantifiedItems } from '@/utils/display.js'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const submitting = ref(false)
const record = ref(null)
const expandedItems = ref([])
const itemResults = ref({})
const quickInputs = ref({})
const pendingItemSaves = new Set()
/** record: 独立检查记录；task: 检查任务（与 Web 同一条任务数据链） */
const executionMode = ref('record')
const currentTaskId = ref(null)

const aiJudgmentLoading = ref(false)
const aiJudgmentThinking = ref(false)
const aiJudgmentThinkingContent = ref('')
const aiJudgmentResult = ref('')
const aiJudgmentResultType = ref('')

const showRiskAlert = ref(false)
const riskProfile = ref(null)

const showAgentPanel = ref(false)
const currentItemId = ref(null)

// 离线缓存：断网时用本机缓存渲染检查项（只读，不排队上传）
const offlineMode = ref(false)
const cachedEntry = ref(null)
const caching = ref(false)
let offlineWriteWarned = false

const finalJudgment = reactive({
  result: '',
  remarks: ''
})

const defaultMultiOptions = [
  { label: '符合', value: 'compliant' },
  { label: '部分符合', value: 'partial' },
  { label: '不符合', value: 'non_compliant' }
]

const defaultResultOptions = [
  { label: '合格', value: 'pass' },
  { label: '不合格', value: 'fail' },
  { label: '不适用', value: 'not_applicable' }
]

const riskLevelText = computed(() => {
  const levelMap = {
    'high': '高风险',
    'medium': '中风险',
    'low': '低风险'
  }
  return levelMap[riskProfile.value?.risk_level] || ''
})

const riskLevelClass = computed(() => {
  return `risk-${riskProfile.value?.risk_level || 'low'}`
})

const resetState = () => {
  record.value = null
  expandedItems.value = []
  itemResults.value = {}
  quickInputs.value = {}
  loading.value = true
  finalJudgment.result = ''
  finalJudgment.remarks = ''
  offlineMode.value = false
  cachedEntry.value = null
  offlineWriteWarned = false
}

const flattenItems = computed(() => {
  if (!record.value?.template?.items) return []

  const result = []
  const flatten = (items, level = 0) => {
    items.forEach(item => {
      const hasChildren = Array.isArray(item.children) && item.children.length > 0
      // 兜底：只要节点下挂着子项，就一律按「分类目录」处理，
      // 兼容历史脏数据（根节点 is_category 缺失/false），避免根节点被当成检查项、
      // 其子项因父节点未展开而整体被隐藏。
      result.push({
        ...item,
        level,
        is_category: item.is_category === true || hasChildren,
      })
      if (hasChildren) {
        flatten(item.children, level + 1)
      }
    })
  }

  flatten(record.value.template.items)
  return result
})

// 仅当模板真的配置了量化计分项时才展示分数，兜住「定性模板被误标为量化」的场景
const showQuantified = computed(
  () => !!record.value?.template?.is_quantified && hasQuantifiedItems(record.value?.template)
)

const hasAIEnabledItems = computed(() => {
  return flattenItems.value.some(item => item.use_ai === true && !item.is_category)
})

const totalCheckItems = computed(() => {
  return flattenItems.value.filter(item => item.is_category !== true).length
})

// 必填的检查项数量
const requiredCheckItems = computed(() => {
  return flattenItems.value.filter(item => item.is_category !== true && item.is_required !== false).length
})

// 必填项中已完成的数量
const requiredCompletedCount = computed(() => {
  let count = 0
  for (const item of flattenItems.value) {
    if (item.is_category !== true && item.is_required !== false && isItemCompleted(item)) {
      count++
    }
  }
  return count
})

const completedCount = computed(() => {
  let count = 0
  for (const item of flattenItems.value) {
    if (item.is_category !== true && isItemCompleted(item)) {
      count++
    }
  }
  return count
})

const getItemScore = (item) => {
  if (!itemResults.value[item.id]) return null
  const result = itemResults.value[item.id]
  
  // 已经是独立打分项
  if (result.score_value !== null && result.score_value !== undefined && result.score_value !== '') {
    return Number(result.score_value)
  }
  
  // 依据是否合格打分
  const radio = result.radio_value
  if (radio === 'pass') {
    return Number(item.score_weight || item.default_score || 0)
  } else if (radio === 'fail') {
    return 0
  } else if (radio === 'na') {
    return Number(item.default_score || 0)
  }
  return null
}

const totalScore = computed(() => {
  if (!showQuantified.value) return null
  let total = 0
  for (const item of flattenItems.value) {
    if (item.is_category !== true && isItemCompleted(item)) {
       const score = getItemScore(item) || 0
       total += score
    }
  }
  return total
})

// 统计符合项和不符合项
const passCount = computed(() => {
  let count = 0
  for (const item of flattenItems.value) {
    if (item.is_category !== true && isItemCompleted(item)) {
      const status = getItemStatus(item)
      if (status === 'pass') count++
    }
  }
  return count
})

const failCount = computed(() => {
  let count = 0
  for (const item of flattenItems.value) {
    if (item.is_category !== true && isItemCompleted(item)) {
      const status = getItemStatus(item)
      if (status === 'fail') count++
    }
  }
  return count
})

const naCount = computed(() => {
  let count = 0
  for (const item of flattenItems.value) {
    if (item.is_category !== true && isItemCompleted(item)) {
      const result = itemResults.value[item.id]
      const radioValue = result?.radio_value
      // 数据库里「不适用」既可能是 not_applicable，也可能是历史值 na
      if (radioValue === 'not_applicable' || radioValue === 'na') count++
    }
  }
  return count
})

const progressPercentage = computed(() => {
  if (totalCheckItems.value === 0) return 0
  return Math.round((completedCount.value / totalCheckItems.value) * 100)
})

const progressColor = computed(() => {
  const percentage = progressPercentage.value
  if (percentage >= 100) return '#4CAF50'
  if (percentage >= 50) return '#4F46E5'
  return '#FF9800'
})

const canSubmit = computed(() => {
  // All required items must be completed, plus final judgment
  return requiredCompletedCount.value >= requiredCheckItems.value &&
         requiredCheckItems.value > 0 &&
         finalJudgment.result
})

const submitButtonText = computed(() => {
  const remaining = requiredCheckItems.value - requiredCompletedCount.value
  if (remaining > 0) {
    return `还需完成 ${remaining} 个必填项`
  }
  if (!finalJudgment.result) {
    return '请填写最终判定'
  }
  return '提交检查结果'
})

const actualRecordId = ref(null)

const currentRecordId = computed(() => actualRecordId.value || record.value?.id || route.params.id)

const agentContext = computed(() => ({
  recordId: executionMode.value === 'record' ? currentRecordId.value : '',
  taskId: executionMode.value === 'task' ? currentTaskId.value : '',
  currentItemTitle: currentItemId.value ? flattenItems.value.find(i => i.id === currentItemId.value)?.title : '',
  currentItemId: currentItemId.value,
  enterpriseId: record.value?.enterprise_id
}))

const mergeTemplateResults = (items, resultByItemId) => {
  return (items || []).map((item) => {
    const id = String(item.id)
    const existing = resultByItemId[id] || {}
    return {
      ...item,
      id,
      template_item_id: id,
      radio_value: existing.radio_value || '',
      text_value: existing.text_value || '',
      numeric_value: existing.numeric_value ?? '',
      score_value: existing.score_value ?? '',
      problem_description: existing.problem_description || '',
      multi_value: existing.multi_value || [],
      children: item.children ? mergeTemplateResults(item.children, resultByItemId) : [],
    }
  })
}

/** 将任务结果映射到检查表单字段（与 Web 端 task_item_records 一致） */
const mapTaskRecordToForm = (taskRecord) => {
  const result = taskRecord?.result || ''
  const resultValue = taskRecord?.result_value
  return {
    radio_value: result || '',
    text_value: taskRecord?.result_text || '',
    numeric_value: resultValue ?? '',
    score_value: resultValue ?? '',
    problem_description: taskRecord?.inspector_note || '',
    multi_value: [],
  }
}

/** 表单字段映射为任务检查项写入载荷 */
const buildTaskItemPayload = (item, inputs = {}) => {
  const checkType = item.check_type || item.result_type || 'pass_fail'
  const payload = {
    template_item_id: item.template_item_id || item.id,
  }

  if (checkType === 'pass_fail' || checkType === 'radio' || (!item.result_type && !item.check_type)) {
    if (inputs.radio_value) payload.result = inputs.radio_value
  } else if (checkType === 'text') {
    if (inputs.text_value) payload.result_text = inputs.text_value
  } else if (checkType === 'numeric' || checkType === 'score') {
    const val = checkType === 'score' ? inputs.score_value : inputs.numeric_value
    if (val !== '' && val != null) {
      payload.result_value = String(val)
      payload.result = inputs.radio_value || 'pass'
    }
  } else if (checkType === 'multi_check') {
    if (Array.isArray(inputs.multi_value) && inputs.multi_value.length) {
      payload.result_text = inputs.multi_value.join(',')
    }
  }

  if (inputs.problem_description) {
    payload.inspector_note = inputs.problem_description
  }
  return payload
}

const saveItemResult = async (item, field, value) => {
  // 离线只读：不做写队列，避免给审核员「已保存」的错觉
  if (!isOnline()) {
    if (!offlineWriteWarned) {
      offlineWriteWarned = true
      showToast('当前离线，填写内容不会上传，恢复网络后请重新填写')
    }
    return
  }

  if (executionMode.value === 'task') {
    if (!currentTaskId.value) throw new Error('任务 ID 无效')
    const inputs = {
      ...(quickInputs.value[item.id] || {}),
      ...(itemResults.value[item.id] || {}),
      [field]: value,
    }
    const payload = buildTaskItemPayload(item, inputs)
    // 至少要有可保存字段
    if (
      payload.result == null &&
      payload.result_value == null &&
      payload.result_text == null &&
      payload.inspector_note == null
    ) {
      return
    }
    await submitCheckRecord(currentTaskId.value, payload)
    return
  }

  let sendValue = value
  if ((field === 'score_value' || field === 'numeric_value') && sendValue !== '' && sendValue != null) {
    sendValue = String(sendValue)
  }
  const data = {
    template_item_id: item.template_item_id || item.id,
    [field]: sendValue,
  }
  const checkType = item.check_type || item.result_type || 'pass_fail'
  if (field === 'radio_value' && checkType === 'pass_fail') {
    data.problem_description = quickInputs.value[item.id]?.problem_description || ''
  }
  await createOrUpdateRecordItem(currentRecordId.value, data)
}

/**
 * 以任务模式加载执行页：与 Web /inspection/:taskId 使用同一任务数据链
 * （InspectionTask + TaskItemRecord），不再错误地创建孤立 InspectionRecord。
 */
const loadTaskExecution = async (task) => {
  executionMode.value = 'task'
  currentTaskId.value = String(task.id)
  actualRecordId.value = String(task.id)

  if (task.status === 'pending') {
    try {
      await startTask(task.id)
      task.status = 'in_progress'
    } catch (e) {
      console.warn('自动开始任务失败，继续加载检查项', e)
    }
  }

  let templateId = task.template_id
  let taskRecords = []
  try {
    const recordsRes = await getTaskRecords(task.id)
    if (recordsRes.code === 200) {
      taskRecords = Array.isArray(recordsRes.data) ? recordsRes.data : []
    }
  } catch (e) {
    console.warn('获取任务检查项失败', e)
  }

  // 历史任务可能 template_id 为空：尝试从已有 task_item_records 反推
  if (!templateId) {
    const linked = taskRecords.find((r) => r.template_item_id || r.template_item?.template_id)
    if (linked?.template_item?.template_id) {
      templateId = linked.template_item.template_id
    }
  }

  // 若后端按模板补齐了检查项，重新拉取一次以拿到最新 task_item_records
  if (templateId && !taskRecords.some((r) => r.template_item_id)) {
    try {
      const recordsRes = await getTaskRecords(task.id)
      if (recordsRes.code === 200) {
        taskRecords = Array.isArray(recordsRes.data) ? recordsRes.data : []
      }
    } catch (e) {
      console.warn('刷新任务检查项失败', e)
    }
  }

  let template = null
  if (templateId) {
    try {
      const tplRes = await getTemplateItems(templateId)
      if (tplRes.code === 200 && tplRes.data) {
        template = tplRes.data
      }
    } catch (e) {
      console.error('获取任务模板失败', e)
      showToast('获取检查模板失败，请确认模板仍可访问')
    }
  } else {
    showToast('该任务未关联检查模板，暂无检查项可填写')
  }

  await applyTaskExecutionData(task, template, taskRecords)
}

/**
 * 用已取到的任务数据渲染执行页。抽出来是为了让离线缓存能复用同一套装配逻辑。
 */
const applyTaskExecutionData = async (task, rawTemplate, taskRecords = []) => {
  executionMode.value = 'task'
  currentTaskId.value = String(task.id)
  actualRecordId.value = String(task.id)

  const template = {
    id: rawTemplate?.id || task.template_id || null,
    name: rawTemplate?.name || task.title || '检查任务',
    version: rawTemplate?.version || '',
    is_quantified: !!rawTemplate?.is_quantified,
    items: rawTemplate?.items || [],
  }

  const resultByItemId = {}
  for (const tr of taskRecords) {
    if (!tr.template_item_id) continue
    resultByItemId[String(tr.template_item_id)] = mapTaskRecordToForm(tr)
  }

  record.value = {
    id: task.id,
    enterprise_name: task.target_name,
    enterprise_address: task.target_address,
    contact_person: task.target_contact,
    contact_phone: task.target_phone,
    remarks: task.remarks,
    status: task.status,
    overall_result: null,
    template: {
      ...template,
      items: mergeTemplateResults(template.items || [], resultByItemId),
    },
    items: taskRecords.map((tr) => ({
      id: tr.id,
      template_item_id: tr.template_item_id,
      result: tr.result,
      result_value: tr.result_value,
      result_text: tr.result_text,
      inspector_note: tr.inspector_note,
    })),
  }

  loadExistingResults()
  await initQuickInputs()
  initExpandedItems()
}

const applyRecordData = async (data, recordId) => {
  executionMode.value = 'record'
  currentTaskId.value = null
  actualRecordId.value = recordId
  record.value = data
  loadExistingResults()
  await initQuickInputs()
  if (data.overall_result) {
    finalJudgment.result = data.overall_result
  }
  if (data.remarks) {
    finalJudgment.remarks = data.remarks
  }
  initExpandedItems()

  // 离线时不去请求风险画像，避免弹出网络错误提示
  if (!isOnline()) return

  const shownRecordId = sessionStorage.getItem('riskAlertShownRecordId')
  if (shownRecordId !== String(recordId) && data.enterprise_id) {
    await fetchAndShowRiskProfile(data.enterprise_id, recordId)
  } else if (data.enterprise_id) {
    fetchRiskProfileSilent(data.enterprise_id)
  }
}

// Agent 写回后，同步本地状态，让检查表单立即显示 Agent 填写的结果
const onAgentResultApplied = ({ itemId, result, problemDescription }) => {
  if (!itemId) return

  if (!itemResults.value[itemId]) {
    itemResults.value[itemId] = {}
  }
  itemResults.value[itemId].radio_value = result
  itemResults.value[itemId].problem_description = problemDescription || ''

  if (quickInputs.value[itemId]) {
    quickInputs.value[itemId].radio_value = result
    quickInputs.value[itemId].problem_description = problemDescription || ''
  }
}

const onAgentVerdictApplied = ({ verdict, comment }) => {
  finalJudgment.result = verdict
  finalJudgment.remarks = comment || ''

  if (record.value) {
    record.value.overall_result = verdict
    record.value.remarks = comment || ''
  }
}

/** 断网时用出发前缓存渲染检查项；成功返回 true */
const loadFromOfflineCache = async (id) => {
  const taskEntry = getCachedEntry('task', id)
  if (taskEntry?.payload?.task) {
    await applyTaskExecutionData(
      taskEntry.payload.task,
      taskEntry.payload.template,
      taskEntry.payload.taskRecords || [],
    )
    offlineMode.value = true
    cachedEntry.value = taskEntry
    showToast('离线模式：已加载本地缓存的检查项')
    return true
  }

  const recordEntry = getCachedEntry('record', id)
  if (recordEntry?.payload?.record) {
    await applyRecordData(recordEntry.payload.record, id)
    offlineMode.value = true
    cachedEntry.value = recordEntry
    showToast('离线模式：已加载本地缓存的检查项')
    return true
  }

  return false
}

/** 联网时把当前检查表存到本机，供进厂后离线查看 */
const cacheCurrentForOffline = async () => {
  if (caching.value || !isOnline()) return
  caching.value = true
  try {
    if (executionMode.value === 'task') {
      await cacheTaskForOffline(currentTaskId.value)
    } else {
      await cacheRecordForOffline(currentRecordId.value)
    }
    refreshCachedEntry()
    showSuccessToast('已缓存到本地，断网也能查看检查项')
  } catch (error) {
    console.error('缓存到本地失败:', error)
    showToast(error?.message || '缓存失败，请检查网络')
  } finally {
    caching.value = false
  }
}

const refreshCachedEntry = () => {
  const id = route.params.id
  cachedEntry.value =
    getCachedEntry(executionMode.value === 'task' ? 'task' : 'record', id) ||
    getCachedEntry('task', id) ||
    getCachedEntry('record', id)
}

const fetchRecord = async () => {
  try {
    const id = route.params.id
    if (!id || id === 'undefined' || id === 'null') {
      showToast('无效的检查 ID')
      return
    }

    // 断网优先读缓存，别让审核员卡在加载失败页
    if (!isOnline() && (await loadFromOfflineCache(id))) {
      return
    }

    const isTaskRoute = route.path.includes('/task/') && route.path.includes('/execute')

    // 任务执行路由：直接走任务数据链（与 Web 一致）
    if (isTaskRoute) {
      const taskRes = await getTask(id)
      if (taskRes.code === 200 && taskRes.data) {
        await loadTaskExecution(taskRes.data)
        refreshCachedEntry()
        return
      }
      if (await loadFromOfflineCache(id)) return
      showToast(taskRes.message || '获取任务失败')
      return
    }

    // 记录路由：先按检查记录加载（静默探测）
    try {
      const res = await getRecord(id, { skipErrorToast: true })
      if (res.code === 200 && res.data) {
        await applyRecordData(res.data, id)
        refreshCachedEntry()
        return
      }
    } catch (e) {
      // 可能是任务 ID 被传到 /inspection/:id（兼容 Web 跳转）
      console.log('Not a record, trying as task...', e?.message || e)
    }

    // 兼容：/inspection/:taskId 按任务加载
    try {
      const taskRes = await getTask(id)
      if (taskRes.code === 200 && taskRes.data) {
        await loadTaskExecution(taskRes.data)
        refreshCachedEntry()
        return
      }
    } catch (e) {
      console.error('Failed to load task execution:', e)
    }

    if (await loadFromOfflineCache(id)) return

    showToast('获取记录失败')
  } catch (error) {
    console.error('获取记录失败:', error)
    if (await loadFromOfflineCache(route.params.id)) return
    const msg =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      '获取记录失败'
    showToast(typeof msg === 'string' ? msg : '获取记录失败')
    // 详细日志以便调试
    if (error.response) {
      console.error('完整错误:', error.response.data)
    }
  } finally {
    loading.value = false
  }
}

const fetchRiskProfileSilent = async (enterpriseId) => {
  try {
    const res = await getEnterpriseRiskProfile(enterpriseId)
    if (res.code === 200 && res.data) {
      riskProfile.value = res.data
    }
  } catch (error) {
    console.warn('获取风险画像失败:', error)
  }
}

const fetchAndShowRiskProfile = async (enterpriseId, recordId) => {
  try {
    const res = await getEnterpriseRiskProfile(enterpriseId)
    if (res.code === 200 && res.data) {
      riskProfile.value = res.data
      
      if (res.data.risk_level === 'high' || res.data.risk_level === 'medium') {
        showRiskAlert.value = true
        sessionStorage.setItem('riskAlertShownRecordId', recordId)
      }
    }
  } catch (error) {
    console.warn('获取风险画像失败:', error)
  }
}

const onRiskAlertConfirm = () => {
  showRiskAlert.value = false
}

const onViewRiskHistory = (enterpriseId) => {
  router.push(`/records?enterprise_id=${enterpriseId}`)
}

const loadExistingResults = () => {
  if (!record.value?.template?.items) return

  const loadItems = (items) => {
    items.forEach(item => {
      if (item.is_category !== true) {
        itemResults.value[item.id] = {
          radio_value: item.radio_value || '',
          score_value: item.score_value,
          numeric_value: item.numeric_value,
          text_value: item.text_value,
          multi_value: item.multi_value || [],
          problem_description: item.problem_description || '',
        }
      }
      if (item.children && item.children.length > 0) {
        loadItems(item.children)
      }
    })
  }

  loadItems(record.value.template.items)
}

const normalizeResultOptions = (rawOptions, defaultOptions = defaultResultOptions) => {
  if (!rawOptions) return defaultOptions
  let opts = rawOptions
  if (typeof opts === 'string') {
    try {
      opts = JSON.parse(opts)
    } catch (e) {
      return defaultOptions
    }
  }
  if (opts && typeof opts === 'object' && !Array.isArray(opts)) {
    if (Array.isArray(opts.options)) {
      opts = opts.options
    } else if (Array.isArray(opts.items)) {
      opts = opts.items
    } else {
      return defaultOptions
    }
  }
  if (!Array.isArray(opts) || opts.length === 0) {
    return defaultOptions
  }
  return opts.map((opt) => {
    if (typeof opt === 'string') {
      return { label: opt, value: opt }
    }
    if (opt && typeof opt === 'object') {
      const val = opt.value !== undefined ? opt.value : (opt.label || opt.name || '')
      const lbl = opt.label || opt.name || (val === 'pass' ? '合格' : val === 'fail' ? '不合格' : (val === 'na' || val === 'not_applicable') ? '不适用' : val)
      return {
        label: String(lbl),
        value: String(val),
        criteria: opt.criteria || '',
      }
    }
    return { label: String(opt), value: String(opt) }
  })
}

const getItemResultOptions = (item) => {
  return normalizeResultOptions(item?.result_options)
}

const initQuickInputs = () => {
  for (const item of flattenItems.value) {
    if (item.is_category !== true) {
      const existing = itemResults.value[item.id] || {}
      
      quickInputs.value[item.id] = {
        radio_value: existing.radio_value || '',
        score_value: existing.score_value ?? '',
        numeric_value: existing.numeric_value ?? '',
        text_value: existing.text_value || '',
        multi_value: existing.multi_value || [],
        problem_description: existing.problem_description || '',
      }
    }
  }
}

const initExpandedItems = () => {
  expandedItems.value = flattenItems.value
    .filter(item => item.is_category)
    .map(item => item.id)
}

const toggleCategory = (itemId) => {
  const index = expandedItems.value.indexOf(itemId)
  if (index > -1) {
    expandedItems.value.splice(index, 1)
  } else {
    expandedItems.value.push(itemId)
  }
}

const isItemVisible = (item) => {
  if (!item.parent_id) return true
  let currentParentId = item.parent_id
  while (currentParentId) {
    if (!expandedItems.value.includes(currentParentId)) {
      return false
    }
    const parentNode = flattenItems.value.find(i => i.id === currentParentId)
    currentParentId = parentNode?.parent_id
  }
  return true
}

const isItemCompleted = (item) => {
  const result = itemResults.value[item.id]
  // 如果没有结果记录，返回 false
  if (!result) return false

  const checkType = item.check_type || item.result_type || 'pass_fail'
  let resultFilled = false
  switch (checkType) {
    case 'radio':
    case 'pass_fail':
      // 必须有明确的 radio_value
      resultFilled = !!result.radio_value
      // 不合格项还必须填写问题描述，避免页面显示已完成但数据库只保存了半条结果
      if (result.radio_value === 'fail') {
        resultFilled = !!result.problem_description?.trim()
      }
      break
    case 'score':
      // 必须有明确的分数值，且不能是空字符串
      const scoreVal = result.score_value
      resultFilled = scoreVal !== null && scoreVal !== undefined && scoreVal !== '' && scoreVal !== 'null'
      break
    case 'numeric':
      // 必须有明确的数值
      const numVal = result.numeric_value
      resultFilled = numVal !== null && numVal !== undefined && numVal !== '' && numVal !== 'null'
      break
    case 'text':
      // 必须有明确的文本内容
      const textVal = result.text_value
      resultFilled = textVal !== null && textVal !== undefined && textVal !== '' && textVal !== 'null'
      break
    case 'multi_check':
      // 必须有选中的选项
      resultFilled = Array.isArray(result.multi_value) && result.multi_value.length > 0
      break
    default:
      resultFilled = false
  }

  if (!resultFilled) return false

  // 如果附件必填，还需确保已上传至少一张照片
  if (item.attachment_required) {
    const photos = item.photos || result.photos || []
    if (photos.length === 0) return false
  }

  return true
}

const hasAttachment = (item) => {
  const result = itemResults.value[item.id]
  const photos = item.photos || result?.photos || []
  return photos.length > 0
}

const getItemStatus = (item) => {
  if (!isItemCompleted(item)) return 'pending'

  const result = itemResults.value[item.id]
  const checkType = item.check_type || item.result_type || 'pass_fail'

  if (checkType === 'radio' || checkType === 'pass_fail') {
    const value = result.radio_value
    if (value === 'pass') return 'pass'
    if (value === 'fail') return 'fail'
    if (value === 'na' || value === 'not_applicable') return 'na'
    if (value === 'pending_rectification') return 'pending_rectification'
  }

  return 'completed'
}

const getItemResultText = (item) => {
  const result = itemResults.value[item.id]
  if (!result) return ''

  const checkType = item.check_type || item.result_type || 'pass_fail'

  switch (checkType) {
    case 'radio':
    case 'pass_fail': {
      const value = result.radio_value
      if (!value) return ''
      const options = getItemResultOptions(item)
      const opt = options.find(o => o.value === value)
      if (opt?.label) return opt.label
      if (value === 'pass') return '合格'
      if (value === 'fail') return '不合格'
      if (value === 'na' || value === 'not_applicable') return '不适用'
      if (value === 'pending_rectification') return '待整改'
      return value
    }
    case 'score':
      return `${result.score_value} 分`
    case 'numeric':
      return `${result.numeric_value} ${item.unit || ''}`.trim()
    case 'text': {
      const text = result.text_value || ''
      return text.length > 30 ? text.substring(0, 30) + '...' : text
    }
    case 'multi_check': {
      const values = result.multi_value || []
      const options = getItemResultOptions(item)
      return values.map(v => {
        const opt = options.find(o => o.value === v)
        return opt?.label || v
      }).join('、')
    }
    default:
      return ''
  }
}

const getResultTypeLabel = (resultType) => {
  const labels = {
    'pass_fail': '判定',
    'numeric': '数值',
    'text': '描述',
    'score': '打分',
    'multi_check': '多选'
  }
  return labels[resultType] || '判定'
}

const formatRange = (min, max, unit) => {
  const u = unit || ''
  if (min !== null && min !== undefined && max !== null && max !== undefined) {
    return `${min} ~ ${max} ${u}`.trim()
  }
  if (min !== null && min !== undefined) {
    return `≥ ${min} ${u}`.trim()
  }
  if (max !== null && max !== undefined) {
    return `≤ ${max} ${u}`.trim()
  }
  return ''
}

// 数值类型自动判定函数
const getNumericJudgmentClass = (item) => {
  const val = quickInputs.value[item.id]?.numeric_value
  if (val === '' || val === null || val === undefined) return ''

  const numVal = Number(val)
  const min = item.min_value
  const max = item.max_value

  // 没有范围限制则无法判定
  if (min === null && max === null) return ''

  const inRange = (min === null || numVal >= Number(min)) && (max === null || numVal <= Number(max))
  return inRange ? 'pass' : 'fail'
}

const getNumericJudgmentIcon = (item) => {
  return getNumericJudgmentClass(item) === 'pass' ? 'success' : 'cross'
}

const getNumericJudgmentText = (item) => {
  return getNumericJudgmentClass(item) === 'pass' ? '符合标准' : '超出标准范围'
}

// 打分类型自动判定函数
const getScoreJudgmentClass = (item) => {
  const val = quickInputs.value[item.id]?.score_value
  if (val === null || val === undefined) return ''

  const passScore = item.pass_score
  if (passScore === null || passScore === undefined) return ''

  return Number(val) >= Number(passScore) ? 'pass' : 'fail'
}

const getScoreJudgmentIcon = (item) => {
  return getScoreJudgmentClass(item) === 'pass' ? 'success' : 'cross'
}

const getScoreJudgmentText = (item) => {
  return getScoreJudgmentClass(item) === 'pass' ? '合格' : '不合格'
}

const getCategoryProgress = (category) => {
  const children = flattenItems.value.filter(item => {
    if (item.is_category) return false
    let parent = item.parent_id
    while (parent) {
      if (parent === category.id) return true
      const parentItem = flattenItems.value.find(i => i.id === parent)
      parent = parentItem?.parent_id
    }
    return false
  })

  const completed = children.filter(item => isItemCompleted(item)).length
  const total = children.length
  return `${completed}/${total}`
}

// 快速录入处理
const onQuickInput = async (item, field, value) => {
  if (!itemResults.value[item.id]) {
    itemResults.value[item.id] = {}
  }
  itemResults.value[item.id][field] = value

  const checkType = item.check_type || item.result_type || 'pass_fail'
  if (field === 'radio_value' && value === 'fail' && checkType === 'pass_fail') {
    if (!quickInputs.value[item.id]?.problem_description) {
      showToast('请填写不合格问题描述')
    }
  }

  try {
    const savePromise = saveItemResult(item, field, value)
    pendingItemSaves.add(savePromise)
    try {
      await savePromise
    } finally {
      pendingItemSaves.delete(savePromise)
    }
  } catch (error) {
    console.error('保存失败:', error)
    showToast('保存失败')
  }
}

const goToItem = (item) => {
  currentItemId.value = item.id
  const itemId = item.id
  router.push({
    path: `/inspection/${currentRecordId.value}/item/${itemId}`,
    query: { mode: executionMode.value }
  })
}

const showSubmitConfirm = async () => {
  if (!canSubmit.value) {
    if (completedCount.value < totalCheckItems.value) {
      showToast('还有未完成的检查项')
    } else if (!finalJudgment.result) {
      showToast('请选择最终判定结果')
    }
    return
  }

  const passNum = passCount.value
  const failNum = failCount.value
  const naNum = naCount.value
  const totalNum = totalCheckItems.value

  const summaryLines = [
    `检查项目统计：`,
    `✅ 合格：${passNum} 项`,
    failNum > 0 ? `❌ 不合格：${failNum} 项` : null,
    naNum > 0 ? `⚪ 不适用：${naNum} 项` : null,
    `━━━━━━━━━━━━`,
    `共计：${totalNum} 项`,
    '',
    '确定要提交本次检查结果吗？提交后将无法修改。'
  ].filter(Boolean).join('\n')

  try {
    await showConfirmDialog({
      title: '确认提交',
      message: summaryLines,
    })

    await completeInspection()
  } catch (error) {
    if (error?.message !== 'cancel' && error !== 'cancel') {
      console.error('提交确认失败:', error)
    }
  }
}

const completeInspection = async () => {
  if (!canSubmit.value) return

  submitting.value = true
  try {
    // 先保存所有检查项结果（确保默认值也被持久化到后端）
    const savePromises = []
    for (const item of flattenItems.value) {
      if (item.is_category === true) continue
      const inputs = quickInputs.value[item.id]
      if (!inputs) continue

      if (executionMode.value === 'task') {
        const payload = buildTaskItemPayload(item, inputs)
        if (
          payload.result != null ||
          payload.result_value != null ||
          payload.result_text != null ||
          payload.inspector_note != null
        ) {
          savePromises.push(submitCheckRecord(currentTaskId.value, payload))
        }
        continue
      }

      const data = {
        template_item_id: item.template_item_id || item.id,
      }
      const resultType = item.result_type || (!item.check_type ? 'pass_fail' : item.check_type)
      let hasValue = false

      // 判定型（pass_fail / 默认）
      if (resultType === 'pass_fail' || (!resultType && !item.check_type)) {
        if (inputs.radio_value) { data.radio_value = inputs.radio_value; hasValue = true }
        if (inputs.problem_description) { data.problem_description = inputs.problem_description; hasValue = true }
      }

      // 数值型
      else if (resultType === 'numeric') {
        if (inputs.numeric_value !== '' && inputs.numeric_value != null) {
          data.numeric_value = String(inputs.numeric_value)
          hasValue = true
        }
      }

      // 文本型
      else if (resultType === 'text') {
        if (inputs.text_value) { data.text_value = inputs.text_value; hasValue = true }
      }

      // 打分型
      else if (resultType === 'score') {
        if (inputs.score_value !== '' && inputs.score_value != null && inputs.score_value !== 0) {
          data.score_value = String(inputs.score_value)
          hasValue = true
        }
      }

      // 多选型
      else if (resultType === 'multi_check') {
        if (inputs.multi_value && inputs.multi_value.length) { data.multi_value = inputs.multi_value; hasValue = true }
      }

      // 通用：problem_description 始终发送（若存在）
      if (inputs.problem_description && !data.problem_description) {
        data.problem_description = inputs.problem_description
        hasValue = true
      }

      if (hasValue) {
        savePromises.push(createOrUpdateRecordItem(currentRecordId.value, data))
      }
    }
    if (savePromises.length > 0) {
      await Promise.all(savePromises)
    }

    // 等待之前的异步保存完成
    if (pendingItemSaves.size > 0) {
      await Promise.all(Array.from(pendingItemSaves))
    }

    if (executionMode.value === 'task') {
      // 任务模式：备注写入任务，并完成任务（与 Web 一致）
      try {
        await updateTaskStatusAndRemarks()
      } catch (e) {
        console.warn('更新任务备注失败，继续完成任务', e)
      }
      const res = await completeTask(currentTaskId.value)
      if (res.code === 200) {
        showSuccessToast('检查已完成')
        setTimeout(() => {
          router.push('/tasks')
        }, 1500)
      } else {
        showToast(res.message || '提交失败')
      }
      return
    }

    // 再保存最终判定
    await updateRecord(currentRecordId.value, {
      overall_result: finalJudgment.result,
      remarks: finalJudgment.remarks,
      total_score: totalScore.value
    })

    // 再提交记录
    const res = await submitRecord(currentRecordId.value)
    if (res.code === 200) {
      showSuccessToast('检查已完成')
      setTimeout(() => {
        router.push('/records')
      }, 1500)
    } else {
      showToast(res.message || '提交失败')
    }
  } catch (error) {
    console.error('完成检查失败:', error)
    // 后端提交校验会返回具体原因（未填结论 / 必填检查项未填），要透传给用户
    const detail = error?.response?.data?.detail || error?.response?.data?.message
    showToast(typeof detail === 'string' && detail ? detail : '操作失败')
  } finally {
    submitting.value = false
  }
}

const updateTaskStatusAndRemarks = async () => {
  const remarksParts = []
  if (finalJudgment.result) {
    // 判定结论写中文，避免 pass/fail 落库并回显到备注
    const verdictCn =
      finalJudgment.result === 'pass'
        ? '合格'
        : finalJudgment.result === 'fail'
          ? '不合格'
          : finalJudgment.result === 'partial_pass'
            ? '基本合格'
            : finalJudgment.result
    remarksParts.push(`最终判定: ${verdictCn}`)
  }
  if (finalJudgment.remarks) {
    remarksParts.push(finalJudgment.remarks)
  }
  if (remarksParts.length) {
    await updateTask(currentTaskId.value, {
      remarks: remarksParts.join(' | '),
    })
  }
}

const goBack = () => {
  router.back()
}

// 生成最终判定
const generateFinalJudgment = async () => {
  aiJudgmentLoading.value = true
  aiJudgmentThinking.value = true
  aiJudgmentThinkingContent.value = ''
  aiJudgmentResult.value = ''
  aiJudgmentResultType.value = ''
  
  try {
    // 单选、输入框失焦保存可能仍在进行，必须等数据库同步后再让后端统计。
    const pendingSaves = [...pendingItemSaves]
    if (pendingSaves.length > 0) {
      const saveResults = await Promise.allSettled(pendingSaves)
      if (saveResults.some(result => result.status === 'rejected')) {
        throw new Error('检查项尚未保存成功')
      }
    }

    const token = localStorage.getItem('token')
    const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

    // 任务模式走任务数据链；记录模式走 InspectionRecord
    const streamUrl =
      executionMode.value === 'task'
        ? `${API_BASE_URL}/api/tasks/${currentTaskId.value}/final-judgment-stream`
        : `${API_BASE_URL}/api/records/${currentRecordId.value}/final-judgment-stream`

    const response = await fetch(streamUrl, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'text/event-stream',
      },
    })
    
    if (!response.ok) {
      let detail = `请求失败 (${response.status})`
      try {
        const errBody = await response.json()
        detail = errBody.detail || errBody.message || detail
      } catch (_) {
        // ignore parse error
      }
      throw new Error(detail)
    }
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let receivedDone = false
    
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
              aiJudgmentThinkingContent.value += data.content
            } else if (data.type === 'done') {
              aiJudgmentResult.value = data.content
              aiJudgmentResultType.value = data.result || ''
              aiJudgmentThinking.value = false
              receivedDone = true
            } else if (data.type === 'error') {
              showToast('AI 生成失败: ' + data.content)
              aiJudgmentThinking.value = false
              receivedDone = true
            }
          } catch (e) {
            console.error('解析数据失败:', e)
          }
        }
      }
    }

    if (!receivedDone && !aiJudgmentResult.value) {
      throw new Error('AI 未返回结果，请稍后重试')
    }
  } catch (error) {
    console.error('AI 生成失败:', error)
    showToast(error?.message || 'AI 生成失败，请稍后重试')
    aiJudgmentThinking.value = false
  } finally {
    aiJudgmentLoading.value = false
  }
}

// 采纳 AI 判定
const acceptAIJudgment = () => {
  if (aiJudgmentResultType.value) {
    finalJudgment.result = aiJudgmentResultType.value
  }
  if (aiJudgmentResult.value) {
    finalJudgment.remarks = aiJudgmentResult.value
  }
  clearAIJudgment()
  showSuccessToast('已采纳 AI 建议')
}

// 清除 AI 判定
const clearAIJudgment = () => {
  aiJudgmentResult.value = ''
  aiJudgmentThinkingContent.value = ''
  aiJudgmentResultType.value = ''
}

onMounted(() => {
  fetchRecord()
})

watch(
  () => route.params.id,
  async (newId, oldId) => {
    if (newId && newId !== oldId) {
      resetState()
      await fetchRecord()
    }
  }
)
</script>

<style scoped>
.inspection-execution-page {
  min-height: 100vh;
  background: var(--bg-light);
  padding-bottom: 120px;
  /* 明确开放纵向滚动，并启用移动端惯性滚动，避免内容超屏时滑不动 */
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.na-tip {
  margin-top: 8px;
  font-size: 11px;
  line-height: 1.5;
  color: #94a3b8;
}

.page-header {
  position: relative;
  padding: 0 0 12px;
  overflow: hidden;
}

.header-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--primary-gradient-dark);
}

.header-bg::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: radial-gradient(circle at 30% 20%, rgba(14, 165, 233, 0.25) 0%, transparent 50%),
              radial-gradient(circle at 70% 80%, rgba(56, 189, 248, 0.2) 0%, transparent 50%);
}

.header-content {
  position: relative;
  z-index: 1;
}

.header-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: calc(env(safe-area-inset-top) + 18px) 16px 8px;
}

.back-btn,
.header-actions {
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
}

.header-info {
  padding: 0 16px 8px;
}

.enterprise-name {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.enterprise-name-text {
  flex-shrink: 0;
}

.risk-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.risk-badge:hover {
  transform: scale(1.05);
}

.risk-badge.risk-high {
  background: rgba(255, 77, 79, 0.9);
  color: #fff;
}

.risk-badge.risk-medium {
  background: rgba(255, 151, 106, 0.9);
  color: #fff;
}

.risk-badge.risk-low {
  background: rgba(7, 193, 96, 0.9);
  color: #fff;
}

.template-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.offline-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.offline-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 11px;
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
}

.offline-chip.offline {
  background: rgba(251, 146, 60, 0.28);
}

.offline-chip.cached {
  background: rgba(34, 197, 94, 0.28);
}

.offline-cache-btn {
  height: 24px;
  padding: 0 10px;
  font-size: 11px;
  background: transparent;
  border-color: rgba(255, 255, 255, 0.5);
  color: #fff;
}

.loading-container {
  padding: 20px;
}

.inspection-content {
  padding: 0 16px;
  margin-top: -10px;
}

.progress-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-md);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.progress-label {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.progress-count {
  font-size: 16px;
  color: var(--primary-color);
  font-weight: 600;
}

.progress-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 8px;
  text-align: center;
}

.progress-hint .complete {
  color: #4CAF50;
  font-weight: 500;
}

.items-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.category-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  background: var(--bg-white);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s;
}

.category-node:active {
  background: var(--bg-gray);
}

.category-icon {
  width: 24px;
  height: 24px;
  background: var(--info-bg);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-color);
  transition: all 0.2s;
}

.category-icon.expanded {
  background: var(--primary-color);
  color: #fff;
}

.category-title {
  flex: 1;
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
}

.category-count {
  font-size: 12px;
  color: var(--primary-color);
  background: var(--info-bg);
  padding: 2px 8px;
  border-radius: 10px;
}

.check-item-card {
  background: var(--bg-white);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  transition: all 0.2s;
}

.check-item-card.has-result {
  border-left: 3px solid #4CAF50;
}

.item-main {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  cursor: pointer;
}

.item-main:active {
  background: var(--bg-gray);
}

.item-status {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.item-status.pending {
  background: var(--bg-gray);
}

.item-status .status-dot {
  width: 8px;
  height: 8px;
  background: var(--text-muted);
  border-radius: 50%;
}

.item-status.pass {
  background: #E8F5E9;
  color: #4CAF50;
}

.item-status.fail {
  background: #FFEBEE;
  color: #F44336;
}

.item-status.completed {
  background: #E3F2FD;
  color: #2196F3;
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-title {
  font-weight: 500;
  font-size: 14px;
  color: var(--text-primary);
  flex: 1;
}

.item-type-tag {
  font-size: 11px;
  color: var(--primary-color);
  background: var(--info-bg);
  padding: 2px 6px;
  border-radius: 4px;
}

.item-required-tag {
  font-size: 11px;
  color: #ff4d4f;
  background: rgba(255, 77, 79, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.item-attachment-tag {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  color: #1989fa;
  background: rgba(25, 137, 250, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.item-incomplete-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #ff976a;
  display: flex;
  align-items: center;
  gap: 4px;
}

.item-result-preview {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-light);
  padding: 4px 8px;
  border-radius: 4px;
  display: inline-block;
}

.detail-arrow {
  flex-shrink: 0;
  margin-top: 4px;
}

/* 快速录入区域 */
.quick-input-area {
  padding: 12px 16px;
  background: var(--bg-light);
  border-top: 1px solid var(--border-light);
}

.quick-radio :deep(.van-radio-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.quick-numeric :deep(.van-field) {
  background: var(--bg-white);
  border-radius: 8px;
  padding: 8px 12px;
}

.quick-numeric .unit-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.quick-numeric .range-hint {
  font-size: 11px;
  color: #FF9500;
  margin-top: 6px;
}

.quick-text :deep(.van-field) {
  background: var(--bg-white);
  border-radius: 8px;
}

.quick-score .score-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quick-score .score-max {
  font-size: 14px;
  color: var(--text-secondary);
}

.quick-score .pass-hint {
  font-size: 11px;
  color: #4CAF50;
  margin-top: 6px;
}

/* 数值类型自动判定样式 */
.quick-numeric .numeric-judgment {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.quick-numeric .numeric-judgment.pass {
  background: rgba(52, 199, 89, 0.1);
  color: #34C759;
}

.quick-numeric .numeric-judgment.fail {
  background: rgba(255, 59, 48, 0.1);
  color: #FF3B30;
}

/* 打分类型自动判定样式 */
.quick-score .score-judgment {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.quick-score .score-judgment.pass {
  background: rgba(52, 199, 89, 0.1);
  color: #34C759;
}

.quick-score .score-judgment.fail {
  background: rgba(255, 59, 48, 0.1);
  color: #FF3B30;
}

.quick-multi :deep(.van-checkbox-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.fail-description {
  margin-top: 12px;
}

.fail-description :deep(.van-field) {
  background: var(--bg-white);
  border-radius: 8px;
  border: 1px solid rgba(255, 77, 79, 0.3);
}

.fail-description :deep(.van-field__control) {
  min-height: 60px;
}

/* 最终判定区域 */
.final-judgment-section {
  margin-top: 20px;
  margin-bottom: 20px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding: 0 4px;
}

/* 统计汇总卡片 */
.stats-summary-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-md);
}

.stats-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-item {
  text-align: center;
  padding: 12px 8px;
  border-radius: var(--radius-md);
  background: var(--bg-light);
}

.stat-item.pass {
  background: #E8F5E9;
}

.stat-item.fail {
  background: #FFEBEE;
}

.stat-item.na {
  background: #F5F5F5;
}

.stat-item.total {
  background: #E3F2FD;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
  margin-bottom: 4px;
}

.stat-item.pass .stat-value {
  color: #4CAF50;
}

.stat-item.fail .stat-value {
  color: #F44336;
}

.stat-item.na .stat-value {
  color: #9E9E9E;
}

.stat-item.total .stat-value {
  color: #2196F3;
}

.stat-label {
  font-size: 11px;
  color: var(--text-secondary);
}

.judgment-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  box-shadow: var(--shadow-md);
}

.judgment-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.judgment-label:not(:first-child) {
  margin-top: 16px;
}

.judgment-radio {
  background: var(--bg-light);
  border-radius: var(--radius-md);
  padding: 16px;
}

.judgment-radio :deep(.van-radio-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.pass-text {
  color: #4CAF50;
  font-weight: 500;
}

.partial-text {
  color: #FF9500;
  font-weight: 500;
}

.fail-text {
  color: #F44336;
  font-weight: 500;
}

.judgment-card :deep(.van-field) {
  background: var(--bg-light);
  border-radius: 8px;
  padding: 12px;
}

.ai-judgment-btn {
  background: var(--primary-gradient);
  border: none;
  font-weight: 500;
  margin-bottom: 12px;
}

.ai-judgment-result {
  margin-bottom: 12px;
  padding: 16px;
  background: var(--bg-light);
  border-radius: var(--radius-md);
}

.ai-judgment-result .ai-thinking {
  margin-bottom: 12px;
}

.ai-judgment-result .ai-thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
  color: var(--primary-color);
}

.ai-judgment-result .ai-thinking-content {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg-white);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--border-light);
}

.ai-judgment-result .ai-final {
  margin-top: 12px;
}

.ai-judgment-result .ai-result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
  color: #4CAF50;
}

.ai-judgment-result .ai-judgment-type {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--bg-white);
  border-radius: 8px;
  border: 1px solid var(--border-light);
}

.ai-judgment-result .ai-result-content {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
  background: var(--bg-white);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--border-light);
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.ai-judgment-result .ai-actions {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.action-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 20px 24px;
  background: var(--bg-white);
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.08);
}

.submit-btn {
  background: var(--primary-gradient);
  border: none;
  font-weight: 500;
  transition: all 0.3s ease;
  transform: scale(1);
}

.submit-btn:disabled {
  background: var(--text-muted);
  background-image: none;
}

.submit-btn.ready-submit {
  background: linear-gradient(135deg, #4CAF50 0%, #2E7D32 100%);
  box-shadow: 0 4px 12px rgba(76, 175, 80, 0.4);
  animation: pulse-ready 1.5s ease-in-out infinite;
}

@keyframes pulse-ready {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 4px 12px rgba(76, 175, 80, 0.4);
  }
  50% {
    transform: scale(1.02);
    box-shadow: 0 6px 16px rgba(76, 175, 80, 0.5);
  }
}

.submit-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #888;
  text-align: center;
  line-height: 1.5;
  padding: 0 4px;
}

.submit-hint span {
  display: block;
}

.empty-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 8px;
}

.total-score-badge {
  display: inline-block;
  margin-left: 12px;
  padding: 2px 8px;
  background: #FEF3C7;
  color: #D97706;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
  vertical-align: middle;
}

.item-score {
  font-size: 13px;
  color: #D97706;
  margin-left: 6px;
  font-weight: normal;
}

:deep(.van-progress) {
  background: var(--info-bg);
}

:deep(.van-radio__label) {
  font-size: 14px;
}

:deep(.van-checkbox__label) {
  font-size: 14px;
}
</style>
