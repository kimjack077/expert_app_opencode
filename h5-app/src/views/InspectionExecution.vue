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
            <span v-if="record.template?.is_quantified" class="total-score-badge">总分: {{ totalScore }}</span>
          </div>
          <div class="template-name">{{ record.template?.name }} ({{ record.template?.version }})</div>
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
          <span v-if="completedCount === 0">请开始填写检查项</span>
          <span v-else-if="requiredCompletedCount < requiredCheckItems">必填项还有 {{ requiredCheckItems - requiredCompletedCount }} 项未完成</span>
          <span v-else class="complete">必填项已全完成，请在下方填写最终判定</span>
        </div>
      </div>

      <!-- 检查项列表 -->
      <div class="items-container">
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
                  <span class="item-title">{{ item.title }} <span v-if="record?.template?.is_quantified && getItemScore(item) !== null" class="item-score">({{ getItemScore(item) }}分)</span></span>
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
              <!-- 判定型 (pass_fail) -->
              <div v-if="item.result_type === 'pass_fail' || (!item.result_type && !item.check_type)" class="quick-radio">
                <van-radio-group
                  v-model="quickInputs[item.id].radio_value"
                  direction="horizontal"
                  @change="(val) => onQuickInput(item, 'radio_value', val)"
                >
                  <van-radio
                    v-for="opt in (item.result_options || defaultResultOptions)"
                    :key="opt.value"
                    :name="opt.value"
                    shape="square"
                  >{{ opt.label }}</van-radio>
                </van-radio-group>
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
                    v-for="opt in (item.result_options || defaultMultiOptions)"
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
              <div class="stat-label">未涉及项</div>
            </div>
            <div class="stat-item total">
              <div class="stat-value">{{ totalCheckItems }}</div>
              <div class="stat-label">总检查项</div>
            </div>
            <div v-if="record?.template?.is_quantified" class="stat-item score">
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
        <span v-if="completedCount < totalCheckItems">
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
import { getRecord, submitRecord, updateRecord, createRecord, createOrUpdateRecordItem, getEnterpriseRiskProfile } from '../api/records'
import { getTask } from '../api/tasks'
import RiskAlertPopup from '../components/RiskAlertPopup.vue'
import AgentFab from '../components/agent/AgentFab.vue'
import AgentChatPanel from '../components/agent/AgentChatPanel.vue'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const submitting = ref(false)
const record = ref(null)
const expandedItems = ref([])
const itemResults = ref({})
const quickInputs = ref({})

const aiJudgmentLoading = ref(false)
const aiJudgmentThinking = ref(false)
const aiJudgmentThinkingContent = ref('')
const aiJudgmentResult = ref('')
const aiJudgmentResultType = ref('')

const showRiskAlert = ref(false)
const riskProfile = ref(null)

const showAgentPanel = ref(false)
const currentItemId = ref(null)

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
  { label: '待整改', value: 'pending_rectification' },
  { label: '未涉及', value: 'not_applicable' }
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
}

const flattenItems = computed(() => {
  if (!record.value?.template?.items) return []

  const result = []
  const flatten = (items, level = 0) => {
    items.forEach(item => {
      result.push({
        ...item,
        level,
      })
      if (item.children && item.children.length > 0) {
        flatten(item.children, level + 1)
      }
    })
  }

  flatten(record.value.template.items)
  return result
})

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
  if (!record.value?.template?.is_quantified) return null
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
      if (radioValue === 'not_applicable') count++
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
  recordId: currentRecordId.value,
  currentItemTitle: currentItemId.value ? flattenItems.value.find(i => i.id === currentItemId.value)?.title : '',
  currentItemId: currentItemId.value,
  enterpriseId: record.value?.enterprise_id
}))

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
  if (comment) {
    finalJudgment.remarks = comment
  }
}

const fetchRecord = async () => {
  try {
    const id = route.params.id
    let recordId = id

    // First try to get as a record
    try {
      const res = await getRecord(id)
      if (res.code === 200) {
        actualRecordId.value = id
        record.value = res.data
        loadExistingResults()
        await initQuickInputs()
        if (res.data.overall_result) {
          finalJudgment.result = res.data.overall_result
        }
        if (res.data.remarks) {
          finalJudgment.remarks = res.data.remarks
        }
        initExpandedItems()

        const shownRecordId = sessionStorage.getItem('riskAlertShownRecordId')
        if (shownRecordId !== recordId && res.data.enterprise_id) {
          await fetchAndShowRiskProfile(res.data.enterprise_id, recordId)
        } else if (res.data.enterprise_id) {
          fetchRiskProfileSilent(res.data.enterprise_id)
        }
        return
      }
    } catch (e) {
      // Not a record, try as a task
      console.log('Not a record, trying as task...')
    }

    // If record not found, try to get as a task and create a record
    try {
      const taskRes = await getTask(id)
      if (taskRes.code === 200) {
        const task = taskRes.data
        // Create a new record from the task
        const createRes = await createRecord({
          template_id: task.template_id,
          enterprise_name: task.target_name,
          enterprise_address: task.target_address,
          contact_person: task.target_contact,
          contact_phone: task.target_phone,
          remarks: task.remarks
        })
        if (createRes.code === 200) {
          recordId = createRes.data.id
          actualRecordId.value = recordId
          // Now fetch the newly created record
          const res = await getRecord(recordId)
          if (res.code === 200) {
            record.value = res.data
            loadExistingResults()
            await initQuickInputs()
            initExpandedItems()
            return
          }
        }
      }
    } catch (e) {
      console.error('Failed to create record from task:', e)
    }

    showToast('获取记录失败')
  } catch (error) {
    console.error('获取记录失败:', error)
    showToast('获取记录失败')
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

const initQuickInputs = async () => {
  for (const item of flattenItems.value) {
    if (item.is_category !== true) {
      const existing = itemResults.value[item.id] || {}
      const checkType = item.check_type || item.result_type || 'pass_fail'
      const isDefaultPass = !existing.radio_value && checkType === 'pass_fail' && !item.attachment_required
      
      quickInputs.value[item.id] = {
        radio_value: existing.radio_value || (isDefaultPass ? 'pass' : ''),
        score_value: existing.score_value || 0,
        numeric_value: existing.numeric_value || '',
        text_value: existing.text_value || '',
        multi_value: existing.multi_value || [],
        problem_description: existing.problem_description || '',
      }
      
      if (isDefaultPass) {
        await onQuickInput(item, 'radio_value', 'pass')
      }
    }
  }
}

const initExpandedItems = () => {
  flattenItems.value.forEach(item => {
    if (item.is_category) {
      expandedItems.value.push(item.id)
    }
  })
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
  return expandedItems.value.includes(item.parent_id)
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
      if (value === 'pass') return '合格'
      if (value === 'fail') return '不合格'
      if (value === 'pending_rectification') return '待整改'
      if (value === 'not_applicable') return '未涉及'
      const options = item.result_options || []
      const opt = options.find(o => o.value === value)
      return opt?.label || value
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
      const options = item.result_options || defaultMultiOptions
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
    if (!quickInputs.value[item.id].problem_description) {
      showToast('请填写不合格问题描述')
      return
    }
  }

  try {
    const data = {
      template_item_id: item.template_item_id || item.id,
      [field]: value
    }
    
    if (field === 'radio_value' && checkType === 'pass_fail') {
      data.problem_description = quickInputs.value[item.id].problem_description || ''
    }

    await createOrUpdateRecordItem(currentRecordId.value, data)
  } catch (error) {
    console.error('保存失败:', error)
    showToast('保存失败')
  }
}

const goToItem = (item) => {
  currentItemId.value = item.id
  const recordItem = record.value?.items?.find(i =>
    i.template_item_id === item.id || i.id === item.id
  )

  const itemId = recordItem?.id || item.id
  router.push(`/inspection/${currentRecordId.value}/item/${itemId}`)
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
    naNum > 0 ? `⚪ 未涉及：${naNum} 项` : null,
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
    // 先保存最终判定
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
    showToast('操作失败')
  } finally {
    submitting.value = false
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
    const recordId = currentRecordId.value
    const token = localStorage.getItem('token')
    
    const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const response = await fetch(`${API_BASE_URL}/api/records/${recordId}/final-judgment-stream`, {
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
              aiJudgmentThinkingContent.value += data.content
            } else if (data.type === 'done') {
              aiJudgmentResult.value = data.content
              aiJudgmentResultType.value = data.result || ''
              aiJudgmentThinking.value = false
            } else if (data.type === 'error') {
              showToast('AI 生成失败: ' + data.content)
              aiJudgmentThinking.value = false
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
  padding-bottom: 100px;
}

.page-header {
  position: relative;
  padding: 0 0 30px;
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
  padding: 50px 20px 20px;
}

.back-btn,
.header-actions {
  width: 40px;
  height: 40px;
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
  padding: 0 20px 20px;
}

.enterprise-name {
  font-size: 18px;
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
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
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