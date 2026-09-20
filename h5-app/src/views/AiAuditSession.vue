<template>
  <main class="audit-session-page">
    <van-nav-bar title="现场审核" left-arrow fixed placeholder @click-left="goBack" />

    <section class="session-summary">
      <div>
        <p class="eyebrow">{{ planItem?.area_name || session.title || '现场审核' }}</p>
        <h1>{{ isCompleted ? '审核记录已提交' : (planItem?.area_name || session.title || '现场审核') }}</h1>
        <p>{{ planItem ? `${planItem.plan_date} ${planItem.time_start || ''}-${planItem.time_end || ''}` : '正在加载审核任务' }}</p>
        <p v-if="isCompleted" class="progress-hint success">
          <van-icon name="checked" /> 本区域审核记录已提交，可返回继续其他任务
        </p>
        <p v-else-if="templateTotalItems > 0" class="progress-hint" :class="{ success: uncoveredItems.length === 0, warning: uncoveredItems.length > 0 }">
          <van-icon :name="uncoveredItems.length === 0 ? 'checked' : 'info-o'" />
          检查项进度：{{ templateCoveredItems }} / {{ templateTotalItems }} 项已完成（{{ displayProgress }}%）
        </p>
        <p v-else-if="session.model_status === 'fallback'" class="progress-hint warning">
          <van-icon name="warning-o" /> {{ session.model_status_message || '部分草稿由保守回退生成，需人工复核' }}
        </p>
      </div>
      <van-progress :percentage="displayProgress" stroke-width="8" color="#0369A1" />
      <p v-if="templateTotalItems > 0 && uncoveredItems.length > 0 && !isCompleted" class="progress-step-label">
        尚有 {{ uncoveredItems.length }} 项未完成审核
      </p>
    </section>

    <!-- 提交成功引导 -->
    <section v-if="isCompleted" class="work-card success-card">
      <div class="success-hero">
        <van-icon name="checked" size="36" color="#059669" />
        <div>
          <p class="eyebrow">已完成</p>
          <h2>审核记录已提交</h2>
          <p class="success-copy">区域结论与已确认条款已同步到任务进度。你可以返回继续其他区域，或留在本页查看已提交内容。</p>
        </div>
      </div>
      <div class="review-actions">
        <van-button block type="primary" @click="goTodayAudit">返回今日审核</van-button>
        <van-button block plain type="primary" @click="goResultPage">查看完整结果</van-button>
        <van-button block plain type="primary" @click="goAuditTasks">查看全部审核任务</van-button>
      </div>
    </section>

    <section v-if="blockers.length" class="alert-card" role="alert">
      <div class="card-title"><van-icon name="warning-o" /> 提交前必须处理</div>
      <ul><li v-for="item in blockers" :key="item.code || item.message">{{ item.message || item.title }}</li></ul>
    </section>

    <!-- 快捷跳转到表格式模板检查 -->
    <section v-if="!isCompleted && (planItem?.inspection_task_id || planItem?.template_id)" class="template-nav-card">
      <div class="template-nav-inner">
        <div class="template-nav-info">
          <van-icon name="todo-list-o" size="20" color="#0284C7" />
          <div>
            <strong>关联模板逐项检查</strong>
            <p>可直接在模板检查表上打分与拍照，确保每项条款无遗漏</p>
          </div>
        </div>
        <van-button size="small" type="primary" plain @click="goToTemplateInspection">
          前往检查表
        </van-button>
      </div>
    </section>

    <section v-if="!isCompleted" class="mode-card" aria-label="记录方式">
      <div class="mode-switch" role="tablist">
        <button
          type="button"
          role="tab"
          :aria-selected="entryMode === 'manual'"
          :class="{ active: entryMode === 'manual' }"
          @click="entryMode = 'manual'"
        >
          手工记录
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="entryMode === 'ai'"
          :class="{ active: entryMode === 'ai' }"
          @click="entryMode = 'ai'"
        >
          AI 辅助
        </button>
      </div>
    </section>

    <section v-if="!isCompleted && entryMode === 'manual'" class="work-card">
      <div class="section-title">
        <div>
          <p class="eyebrow">审核员记录</p>
          <h2>新增正式现场记录</h2>
          <p class="section-subhint">文字会自动保存在本机，保存后直接进入正式审核记录。</p>
        </div>
        <van-tag type="success">默认</van-tag>
      </div>
      <van-field v-model="manualForm.item_title" label="检查项" maxlength="300" placeholder="例如：受控文件管理" />
      <van-field
        v-model="manualForm.clause_text"
        label="条款"
        maxlength="1000"
        placeholder="例如：7.5, 8.1（可填写多个）"
      />
      <van-field label="认证体系">
        <template #input>
          <van-radio-group v-model="manualForm.certification_system" direction="horizontal" class="inline-radios">
            <van-radio v-for="system in certificationSystemOptions" :key="system.value" :name="system.value">
              {{ system.label }}
            </van-radio>
          </van-radio-group>
        </template>
      </van-field>
      <van-field label="审核评价">
        <template #input>
          <van-radio-group v-model="manualForm.evaluation_3level" direction="horizontal" class="inline-radios evaluation-radios">
            <van-radio name="1">1 符合</van-radio>
            <van-radio name="2">2 基本符合</van-radio>
            <van-radio name="3">3 不符合</van-radio>
          </van-radio-group>
        </template>
      </van-field>
      <van-field
        v-model="manualForm.audit_evidence"
        type="textarea"
        rows="5"
        maxlength="30000"
        show-word-limit
        label="现场记录"
        placeholder="记录抽样对象、文件编号、时间、人员和观察到的客观事实"
      />
      <van-field
        v-if="manualForm.evaluation_3level !== '1'"
        v-model="manualForm.audit_findings"
        type="textarea"
        rows="3"
        maxlength="10000"
        label="审核发现"
        :placeholder="manualForm.evaluation_3level === '3' ? '请描述不符合事实' : '请描述需要关注或改进的事项'"
      />
      <van-field
        v-if="manualForm.evaluation_3level === '3'"
        v-model="manualForm.rectification_suggestion"
        type="textarea"
        rows="2"
        maxlength="5000"
        label="整改建议"
        placeholder="填写整改要求或建议"
      />
      <div class="photo-field">
        <div class="photo-field__label">现场照片</div>
        <van-uploader
          v-model="manualPhotoFiles"
          multiple
          :max-count="5"
          :disabled="manualSubmitting"
          :after-read="uploadManualPhoto"
        />
        <p class="field-hint">
          照片会立即上传，需保持联网<span v-if="manualMediaFileIds.length">；已上传 {{ manualMediaFileIds.length }} 张</span>
        </p>
      </div>
      <van-button
        block
        type="primary"
        class="primary-action"
        :loading="manualSubmitting"
        @click="saveManualRecord"
      >
        保存正式记录
      </van-button>
      <div v-if="manualRecords.length" class="saved-manual-list">
        <van-divider>已保存手工记录（{{ manualRecords.length }}）</van-divider>
        <article v-for="recordItem in manualRecords" :key="recordItem.id || recordItem.submission_id" class="saved-evidence-card">
          <div class="draft-heading">
            <strong>{{ recordItem.item_title || '现场记录' }}</strong>
            <van-tag :type="evaluationType({ evaluation: recordItem.evaluation_3level })">
              {{ evaluationText({ evaluation: recordItem.evaluation_3level }) }}
            </van-tag>
          </div>
          <p class="draft-meta">{{ recordItem.certification_system || '-' }} · {{ recordItem.clause_no || recordItem.clause_nos?.join(' / ') || '未填条款' }}</p>
          <p class="draft-evidence">{{ recordItem.audit_evidence }}</p>
        </article>
      </div>
    </section>

    <template v-if="!isCompleted && entryMode === 'ai'">
      <section class="work-card">
        <div class="section-title">
          <div><p class="eyebrow">可选辅助</p><h2>AI 多条款分析</h2></div>
          <button type="button" class="icon-button" aria-label="语音输入" :disabled="isCompleted || analyzing" @click="toggleVoice">
            <van-icon :name="listening ? 'stop-circle-o' : 'volume-o'" size="22" />
          </button>
        </div>
        <van-field
          v-model="evidenceText"
          type="textarea"
          rows="5"
          maxlength="30000"
          show-word-limit
          label="现场描述"
          placeholder="一次描述完整现场情况，AI 会拆分并匹配多个条款"
          :disabled="analyzing"
        />
        <van-uploader v-model="photoFiles" multiple :max-count="5" :disabled="isCompleted || analyzing" :after-read="uploadPhoto" />
        <p class="field-hint">文字会自动保存在本机；照片需联网后立即上传。</p>
        <van-button block plain type="primary" icon="service-o" class="agent-entry" :disabled="isCompleted || analyzing" @click="showAgent = true">
          打开 AI 审核助手
        </van-button>
        <van-button block type="primary" class="primary-action" :loading="analyzing" :loading-text="analyzeStepText" :disabled="isCompleted || !evidenceText.trim()" @click="analyzeEvidence">
          {{ analyzing ? analyzeStepText : '生成多条款 AI 记录' }}
        </van-button>

        <!-- AI 分析中状态进度与步骤展示：仅在生成按钮下方展示唯一一个进度条 -->
        <div v-if="analyzing" class="work-card analyze-status-card" style="margin-top: 14px;">
          <div class="section-title" style="margin-bottom: 8px;">
            <div>
              <p class="eyebrow" style="color: #0284c7;">AI 正在分析</p>
              <h2 style="font-size: 16px;">{{ analyzeStepText }}</h2>
            </div>
            <van-tag type="primary" size="medium">{{ Math.round(analyzeProgress) }}%</van-tag>
          </div>
          <van-progress :percentage="Math.round(analyzeProgress)" :show-pivot="false" color="#0284c7" stroke-width="4" style="margin-bottom: 12px;" />
          <ul class="analyze-steps">
            <li v-for="step in analyzeSteps" :key="step.key" :class="stepClass(step.key)">
              <div class="step-dot">
                <van-icon v-if="isStepDone(step.key)" name="success" size="14" />
                <span v-else>{{ step.index }}</span>
              </div>
              <div class="step-body">
                <strong>{{ step.title }}</strong>
                <p>{{ step.desc }}</p>
              </div>
            </li>
          </ul>
          <div class="analyze-tip">
            <van-icon name="info-o" style="margin-right: 4px;" />
            AI 正在对照检查模板中的各个检查项进行多条款匹配与合规判定，请稍候...
          </div>
        </div>
      </section>

      <!-- 分析完成后的结论：仅在有待确认记录时才在按钮下方展示人工复核卡片 -->
      <section v-if="pendingDrafts.length > 0" class="work-card">
        <div class="section-title">
          <div>
            <p class="eyebrow">人工复核</p>
            <h2>待确认 AI 记录</h2>
            <p class="section-subhint">
              待确认 {{ pendingDrafts.length }} 条 · 已确认 {{ confirmedDrafts.length }} 条
            </p>
          </div>
          <van-tag type="warning">{{ pendingDrafts.length }} 条</van-tag>
        </div>
        <van-checkbox-group v-model="selectedDraftIds">
          <article v-for="draft in sortedDrafts" :key="draft.id" class="draft-card" :class="{ abnormal: isAbnormal(draft), fallback: isFallback(draft) }">
            <van-checkbox :name="draft.id" shape="square" :disabled="isFallback(draft) || isCompleted">
              <div class="draft-heading">
                <strong>{{ clauseText(draft) }}</strong>
                <van-tag :type="evaluationType(draft)">{{ evaluationText(draft) }}</van-tag>
              </div>
            </van-checkbox>
            <p v-if="isFallback(draft)" class="draft-fallback-notice">
              <van-icon name="warning-o" /> 模型异常：此为保守回退结果，不可批量采纳，必须逐条编辑复核
            </p>
            <p class="draft-evidence">{{ draft.finding_text || draft.record_payload?.audit_evidence || '未提供证据摘要' }}</p>
            <div class="draft-meta">
              <span>证据：{{ qualityText(draft) }}</span>
              <span class="confidence-cell">
                置信度：
                <van-tag size="mini" :type="confidenceTagType(draft)">{{ confidenceText(draft) }} · {{ confidenceLabel(draft) }}</van-tag>
              </span>
              <van-tag v-if="isFallback(draft)" size="mini" type="danger">需人工复核</van-tag>
            </div>
            <p class="reasoning">{{ draft.reasoning }}</p>
            <details v-if="draft.citations?.length">
              <summary>查看 {{ draft.citations.length }} 条引用（请核对来源）</summary>
              <p v-for="(citation, index) in draft.citations" :key="index" class="citation">
                <van-tag size="mini" plain>{{ citationSourceLabel(citation) }}</van-tag>
                {{ citation.document_title || citation.file_name || '资料' }}：{{ citation.content }}
              </p>
            </details>
            <div class="draft-actions">
              <van-button size="small" plain type="primary" icon="edit" :disabled="confirming" @click.stop="openDraftEditor(draft)">
                编辑并采纳
              </van-button>
              <van-button size="small" plain type="danger" icon="delete-o" :disabled="confirming" @click.stop="rejectDraft(draft)">
                拒绝草稿
              </van-button>
            </div>
          </article>
        </van-checkbox-group>
        <div v-if="!isCompleted" class="review-actions">
          <van-button block plain type="primary" :loading="confirming" :disabled="isCompleted || safeDraftCount === 0" @click="confirmSafeDrafts">
            批量采纳安全项（排除回退/异常）
          </van-button>
          <van-button block type="primary" :loading="confirming" :disabled="isCompleted || selectedDraftIds.length === 0" @click="confirmSelected">
            采纳已选择记录 ({{ selectedDraftIds.length }})
          </van-button>
        </div>
      </section>

      <section v-if="!loading && savedSubmissions.length" class="work-card">
        <div class="section-title">
          <div><p class="eyebrow">已保存</p><h2>AI 证据提交</h2></div>
          <van-tag type="primary">{{ savedSubmissions.length }} 条</van-tag>
        </div>
        <article v-for="submission in savedSubmissions" :key="submission.id" class="saved-evidence-card">
          <div class="draft-heading">
            <strong>{{ submissionTitle(submission) }}</strong>
            <van-tag :type="submission.status === 'completed' ? 'success' : 'warning'">
              {{ submission.status === 'completed' ? '已处理' : '处理中' }}
            </van-tag>
          </div>
          <p class="draft-evidence">{{ submission.description || '已保存现场证据' }}</p>
          <p class="draft-meta">{{ submission.source_files?.length || 0 }} 个附件 · {{ formatSubmissionTime(submission) }}</p>
        </article>
      </section>
    </template>

    <section v-if="confirmedDrafts.length" class="work-card">
      <div class="section-title">
        <div><p class="eyebrow">已确认</p><h2>审核记录</h2></div>
        <van-tag type="success">{{ confirmedDrafts.length }} 条</van-tag>
      </div>
      <article v-for="draft in confirmedDrafts" :key="draft.id" class="saved-evidence-card">
        <div class="draft-heading">
          <strong>{{ clauseText(draft) }}</strong>
          <van-tag :type="evaluationType(draft)">{{ evaluationText(draft) }}</van-tag>
        </div>
        <p class="draft-evidence">{{ draft.finding_text || draft.record_payload?.audit_evidence || '已确认审核记录' }}</p>
        <p class="draft-meta">
          证据：{{ qualityText(draft) }}
          <span class="confidence-cell">
            · 置信度：
            <van-tag size="mini" :type="confidenceTagType(draft)">{{ confidenceText(draft) }} · {{ confidenceLabel(draft) }}</van-tag>
          </span>
        </p>
      </article>
    </section>

    <section v-if="!isCompleted" class="work-card final-card">
      <div class="section-title"><div><p class="eyebrow">提交</p><h2>最终结论与提交</h2></div></div>
      <van-field v-model="conclusion" type="textarea" rows="4" label="区域结论" :readonly="isCompleted" placeholder="根据已确认记录形成最终审核结论" />
      <div class="review-actions">
        <van-button block plain type="primary" :loading="checking" @click="runQualityCheck">检查完整性</van-button>
        <van-button block type="primary" :loading="submitting" :disabled="isCompleted" @click="submitSession">提交审核记录</van-button>
      </div>
    </section>

    <van-popup v-model:show="editDraftVisible" position="bottom" round :style="{ height: '82%' }">
      <div class="edit-sheet">
        <div class="edit-sheet__header">
          <button type="button" @click="editDraftVisible = false">取消</button>
          <strong>编辑并采纳 AI 草稿</strong>
          <button type="button" :disabled="savingDraft" @click="saveEditedDraft">保存</button>
        </div>
        <div class="edit-sheet__body">
          <p class="edit-sheet__clause">{{ editingDraft ? clauseText(editingDraft) : '条款' }}</p>
          <van-field label="审核评价">
            <template #input>
              <van-radio-group v-model="editDraftForm.evaluation_3level" direction="horizontal" class="inline-radios evaluation-radios">
                <van-radio name="1">1 符合</van-radio>
                <van-radio name="2">2 基本符合</van-radio>
                <van-radio name="3">3 不符合</van-radio>
              </van-radio-group>
            </template>
          </van-field>
          <van-field
            v-model="editDraftForm.audit_evidence"
            type="textarea"
            rows="5"
            maxlength="30000"
            show-word-limit
            label="客观证据"
            placeholder="核对并修正客观证据"
          />
          <van-field
            v-model="editDraftForm.audit_findings"
            type="textarea"
            rows="4"
            maxlength="10000"
            label="审核发现"
            placeholder="核对并修正审核发现"
          />
          <van-field
            v-model="editDraftForm.rectification_suggestion"
            type="textarea"
            rows="3"
            maxlength="5000"
            label="整改建议"
            placeholder="不符合时填写整改要求或建议"
          />
          <van-button block type="primary" class="primary-action" :loading="savingDraft" @click="saveEditedDraft">
            保存并采纳
          </van-button>
        </div>
      </div>
    </van-popup>
    <AgentChatPanel
      v-model:show="showAgent"
      :context="agentContext"
      @project-action-applied="loadSession"
    />
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showDialog, showToast } from 'vant'
import AgentChatPanel from '@/components/agent/AgentChatPanel.vue'
import { citationSourceLabel } from '@/utils/display.js'

import {
  checkAuditQuality,
  confirmAuditDrafts,
  createManualSessionRecord,
  getAuditPlanItem,
  getAuditSession,
  submitAuditSession,
  submitSessionEvidence,
  uploadAuditSessionMedia
} from '../api/auditProjects'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => String(route.query.projectId || ''))
const sessionId = computed(() => String(route.params.sessionId || ''))
const planItemId = computed(() => String(route.query.planItemId || ''))

const session = ref({})
const planItem = ref(null)
const entryMode = ref('manual')
const loading = ref(true)
const analyzing = ref(false)
const analyzeProgress = ref(0)
const analyzeStepKey = ref('idle')
const confirming = ref(false)
const checking = ref(false)
const submitting = ref(false)
const listening = ref(false)
const usedVoiceInput = ref(false)
const showAgent = ref(false)
const evidenceText = ref('')
const conclusion = ref('')
const photoFiles = ref([])
const mediaFileIds = ref([])
const manualSubmitting = ref(false)
const manualPhotoFiles = ref([])
const manualMediaFileIds = ref([])
const selectedDraftIds = ref([])
const qualityCheck = ref({ blockers: [], warnings: [] })
const editDraftVisible = ref(false)
const editingDraft = ref(null)
const savingDraft = ref(false)

const certificationSystemOptions = [
  { label: 'Q', value: 'Q' },
  { label: 'E', value: 'E' },
  { label: 'S', value: 'S' },
  { label: 'En', value: 'En' }
]

const emptyManualForm = () => ({
  item_title: '',
  clause_text: '',
  certification_system: '',
  evaluation_3level: '1',
  audit_evidence: '',
  audit_findings: '',
  rectification_suggestion: '',
  template_item_id: ''
})

const manualForm = ref(emptyManualForm())
const editDraftForm = ref({
  evaluation_3level: '2',
  audit_evidence: '',
  audit_findings: '',
  rectification_suggestion: ''
})
let speechRecognition = null
let analyzeTimer = null

const analyzeSteps = [
  { key: 'submit', index: 1, title: '提交现场证据', desc: '保存文字描述与附件' },
  { key: 'match', index: 2, title: '匹配候选条款', desc: '从计划模板中筛选相关条款' },
  { key: 'llm', index: 3, title: 'AI 多条款判定', desc: '模型分析证据并生成草稿' },
  { key: 'done', index: 4, title: '整理待确认记录', desc: '生成结果并刷新列表' }
]

const stepOrder = analyzeSteps.map((s) => s.key)

const analyzeStepText = computed(() => {
  const current = analyzeSteps.find((s) => s.key === analyzeStepKey.value)
  if (!current) return 'AI 正在分析...'
  return current.title
})

const drafts = computed(() => session.value.drafts || [])
const pendingDrafts = computed(() => drafts.value.filter((item) => item.status === 'draft'))
const confirmedDrafts = computed(() => drafts.value.filter((item) => item.status === 'confirmed'))
const manualRecords = computed(() => session.value.manual_records || [])
const savedSubmissions = computed(() => (session.value.submissions || []).filter((item) => item.status !== 'failed'))
const isCompleted = computed(() => session.value.status === 'completed')
const blockers = computed(() => qualityCheck.value.blockers || qualityCheck.value.blocking_items || [])

const templateTotalItems = computed(() => qualityCheck.value.template_total_items || 0)
const templateCoveredItems = computed(() => qualityCheck.value.template_covered_items ?? (confirmedDrafts.value.length + manualRecords.value.length))
const uncoveredItems = computed(() => qualityCheck.value.uncovered_items || [])

const displayProgress = computed(() => {
  if (isCompleted.value) return 100
  if (templateTotalItems.value > 0) {
    return Math.round((templateCoveredItems.value / templateTotalItems.value) * 100)
  }
  const total = drafts.value.length + manualRecords.value.length
  if (total > 0) {
    return Math.round(((confirmedDrafts.value.length + manualRecords.value.length) / total) * 100)
  }
  return session.value.progress || 0
})
const statusText = computed(() => {
  if (session.value.status === 'completed') return '审核记录已提交'
  if (analyzing.value) return 'AI 正在生成多条款记录'
  return '现场审核记录'
})
const sortedDrafts = computed(() => [...pendingDrafts.value].sort((left, right) => Number(isAbnormal(right)) - Number(isAbnormal(left))))
const agentContext = computed(() => ({
  projectId: projectId.value,
  auditSessionId: sessionId.value,
  planItemId: planItemId.value,
  currentItemTitle: planItem.value?.area_name || session.value.title || '现场审核'
}))

const evaluationCode = (draft) => String(draft.record_payload?.evaluation_3level || draft.evaluation || '2')
const isAbnormal = (draft) => evaluationCode(draft) === '3' || ['insufficient', 'partial'].includes(draft.quality?.level)
const isFallback = (draft) => draft.model_status === 'fallback' || draft.quality?.model_status === 'fallback' || draft.source_snapshot?.model_status === 'fallback'
const safeDraftCount = computed(
  () => pendingDrafts.value.filter((d) => !isFallback(d) && !isAbnormal(d)).length
)
const evaluationText = (draft) => ({ 1: '符合', 2: '基本符合', 3: '不符合' }[evaluationCode(draft)] || '待确认')
const evaluationType = (draft) => ({ 1: 'success', 2: 'warning', 3: 'danger' }[evaluationCode(draft)] || 'default')
const clauseText = (draft) => {
  const itemTitle = draft.record_payload?.item_title || draft.clause_refs?.[0]?.title
  if (itemTitle) return itemTitle
  return draft.primary_clause_no || draft.clause_refs?.map((item) => item.clause_no).filter(Boolean).join(' / ') || '检查项'
}
const qualityText = (draft) => ({ sufficient: '充分', partial: '部分充分', insufficient: '不足' }[draft.quality?.level || draft.quality?.evidence_quality] || '待复核')
const confidenceText = (draft) => `${Math.round(Number(draft.confidence || 0) * 100)}%`
const confidenceLevel = (draft) => {
  const value = Number(draft.confidence || 0)
  if (value >= 0.8) return 'high'
  if (value >= 0.5) return 'medium'
  return 'low'
}
const confidenceLabel = (draft) => ({ high: '高', medium: '中', low: '低' }[confidenceLevel(draft)] || '低')
const confidenceTagType = (draft) => ({ high: 'success', medium: 'warning', low: 'danger' }[confidenceLevel(draft)] || 'default')
const submissionTitle = (submission) => submission.title || `${submission.input_type === 'voice' ? '语音' : '现场'}证据`
const formatSubmissionTime = (submission) => submission.submitted_at ? new Date(submission.submitted_at).toLocaleString('zh-CN', { hour12: false }) : '刚刚保存'

const isStepDone = (key) => stepOrder.indexOf(key) < stepOrder.indexOf(analyzeStepKey.value)
const isStepActive = (key) => analyzeStepKey.value === key
const stepClass = (key) => ({
  done: isStepDone(key),
  active: isStepActive(key),
  pending: !isStepDone(key) && !isStepActive(key)
})

const clearAnalyzeTimer = () => {
  if (analyzeTimer) {
    clearInterval(analyzeTimer)
    analyzeTimer = null
  }
}

const startAnalyzeProgress = () => {
  clearAnalyzeTimer()
  analyzeProgress.value = 8
  analyzeStepKey.value = 'submit'
  // 模拟阶段推进，真实接口返回后会跳到 done
  const timeline = [
    { at: 1200, key: 'match', progress: 28 },
    { at: 2800, key: 'llm', progress: 48 },
    { at: 8000, key: 'llm', progress: 72 },
    { at: 18000, key: 'llm', progress: 88 }
  ]
  const started = Date.now()
  analyzeTimer = setInterval(() => {
    const elapsed = Date.now() - started
    for (const point of timeline) {
      if (elapsed >= point.at && analyzeProgress.value < point.progress) {
        analyzeStepKey.value = point.key
        analyzeProgress.value = point.progress
      }
    }
    // 缓慢爬升，避免假进度卡住
    if (analyzeStepKey.value === 'llm' && analyzeProgress.value < 92) {
      analyzeProgress.value = Math.min(92, analyzeProgress.value + 0.4)
    }
  }, 400)
}

const finishAnalyzeProgress = () => {
  clearAnalyzeTimer()
  analyzeStepKey.value = 'done'
  analyzeProgress.value = 100
}

const unwrap = (response) => response?.data || response || {}

const localDraftKey = computed(() => `efis:audit-session-draft:${sessionId.value}`)

const persistSessionDraft = () => {
  if (!sessionId.value || isCompleted.value) return
  try {
    window.localStorage.setItem(localDraftKey.value, JSON.stringify({
      evidence_text: evidenceText.value,
      conclusion: conclusion.value,
      manual_form: manualForm.value,
      manual_media_file_ids: manualMediaFileIds.value,
      ai_media_file_ids: mediaFileIds.value,
      saved_at: new Date().toISOString()
    }))
  } catch {
    // Storage may be unavailable in private browsing; online saving remains usable.
  }
}

const restoreSessionDraft = () => {
  if (!sessionId.value) return false
  try {
    const raw = window.localStorage.getItem(localDraftKey.value)
    if (!raw) return false
    const saved = JSON.parse(raw)
    evidenceText.value = typeof saved.evidence_text === 'string' ? saved.evidence_text : ''
    conclusion.value = typeof saved.conclusion === 'string' ? saved.conclusion : ''
    manualForm.value = { ...emptyManualForm(), ...(saved.manual_form || {}) }
    manualMediaFileIds.value = Array.isArray(saved.manual_media_file_ids) ? saved.manual_media_file_ids : []
    mediaFileIds.value = Array.isArray(saved.ai_media_file_ids) ? saved.ai_media_file_ids : []
    return Boolean(
      evidenceText.value ||
      conclusion.value ||
      manualForm.value.item_title ||
      manualForm.value.audit_evidence
    )
  } catch {
    window.localStorage.removeItem(localDraftKey.value)
    return false
  }
}

const clearSessionDraft = () => {
  try {
    window.localStorage.removeItem(localDraftKey.value)
  } catch {
    // No action is needed when storage is unavailable.
  }
}

watch(
  [evidenceText, conclusion, manualForm, manualMediaFileIds, mediaFileIds],
  persistSessionDraft,
  { deep: true }
)

const loadSession = async () => {
  loading.value = true
  try {
    const [sessionResponse, planResponse] = await Promise.all([
      getAuditSession(projectId.value, sessionId.value),
      planItemId.value ? getAuditPlanItem(planItemId.value) : Promise.resolve(null)
    ])
    session.value = unwrap(sessionResponse)
    planItem.value = planResponse ? unwrap(planResponse) : null
    qualityCheck.value = session.value.quality_check || qualityCheck.value
    const savedConclusion = session.value.conclusion || session.value.context_snapshot?.conclusion
    if (savedConclusion) conclusion.value = savedConclusion
    if (!manualForm.value.certification_system) {
      manualForm.value.certification_system = planItem.value?.certification_systems?.[0] || ''
    }
    if (!manualForm.value.clause_text && Array.isArray(planItem.value?.clauses)) {
      manualForm.value.clause_text = planItem.value.clauses.join(', ')
    }
    if (session.value.status === 'completed') clearSessionDraft()
  } catch (error) {
    showToast(error?.message || '加载审核会话失败')
  } finally {
    loading.value = false
  }
}

const uploadSessionPhotos = async (fileItem, targetIds) => {
  const items = Array.isArray(fileItem) ? fileItem : [fileItem]
  for (const item of items) {
    if (!item.file) {
      item.status = 'failed'
      item.message = '未读取到图片文件'
      continue
    }
    item.status = 'uploading'
    try {
      const response = await uploadAuditSessionMedia(
        projectId.value,
        sessionId.value,
        item.file
      )
      const uploaded = unwrap(response)
      if (uploaded.id && !targetIds.value.includes(uploaded.id)) targetIds.value.push(uploaded.id)
      item.status = 'done'
    } catch (error) {
      item.status = 'failed'
      item.message = error?.message || '上传失败'
    }
  }
}

const uploadPhoto = (fileItem) => uploadSessionPhotos(fileItem, mediaFileIds)
const uploadManualPhoto = (fileItem) => uploadSessionPhotos(fileItem, manualMediaFileIds)

const parseClauseNumbers = (value) => [...new Set(
  String(value || '')
    .split(/[,，;；、\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
)]

const requestErrorMessage = (error, fallback) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  return error?.message || fallback
}

const resetManualForm = () => {
  manualForm.value = emptyManualForm()
  manualPhotoFiles.value = []
  manualMediaFileIds.value = []
}

const saveManualRecord = async () => {
  const values = manualForm.value
  const clauseNos = parseClauseNumbers(values.clause_text)
  if (!values.item_title.trim()) return showToast('请填写检查项')
  if (!clauseNos.length) return showToast('请至少填写一个条款号')
  if (!values.certification_system) return showToast('请选择认证体系')
  if (!values.audit_evidence.trim()) return showToast('请填写现场记录')
  if (values.evaluation_3level === '3' && !values.audit_findings.trim()) {
    return showToast('不符合项必须填写审核发现')
  }

  manualSubmitting.value = true
  try {
    await createManualSessionRecord(projectId.value, sessionId.value, {
      item_title: values.item_title.trim(),
      clause_nos: clauseNos,
      certification_system: values.certification_system,
      evaluation_3level: values.evaluation_3level,
      audit_evidence: values.audit_evidence.trim(),
      audit_findings: values.audit_findings.trim() || undefined,
      rectification_suggestion: values.rectification_suggestion.trim() || undefined,
      template_item_id: values.template_item_id || undefined,
      media_file_ids: manualMediaFileIds.value
    })
    await loadSession()
    resetManualForm()
    persistSessionDraft()
    showToast('正式现场记录已保存')
  } catch (error) {
    showToast(requestErrorMessage(error, '保存正式现场记录失败'))
  } finally {
    manualSubmitting.value = false
  }
}

const toggleVoice = () => {
  if (isCompleted.value || analyzing.value) return
  if (listening.value && speechRecognition) return speechRecognition.stop()
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!Recognition) return showToast('当前浏览器不支持语音识别，请使用文字输入')
  speechRecognition = new Recognition()
  speechRecognition.lang = 'zh-CN'
  speechRecognition.continuous = true
  speechRecognition.interimResults = false
  speechRecognition.onresult = (event) => {
    const text = Array.from(event.results).slice(event.resultIndex).map((result) => result[0].transcript).join('')
    evidenceText.value = `${evidenceText.value}${evidenceText.value ? '\n' : ''}${text}`
    usedVoiceInput.value = true
  }
  speechRecognition.onend = () => { listening.value = false }
  speechRecognition.onerror = () => { listening.value = false; showToast('语音识别中断，请重试') }
  listening.value = true
  speechRecognition.start()
}

const analyzeEvidence = async () => {
  if (isCompleted.value || !evidenceText.value.trim()) return
  analyzing.value = true
  startAnalyzeProgress()
  try {
    analyzeStepKey.value = 'submit'
    analyzeProgress.value = Math.max(analyzeProgress.value, 15)
    const res = await submitSessionEvidence(projectId.value, sessionId.value, {
      content: evidenceText.value.trim(),
      evidence_type: mediaFileIds.value.length ? 'mixed' : (usedVoiceInput.value ? 'voice' : 'text'),
      media_file_ids: mediaFileIds.value,
      source_metadata: { plan_item_id: planItemId.value, area_name: planItem.value?.area_name }
    })
    finishAnalyzeProgress()
    const payload = unwrap(res)
    const draftCount = Array.isArray(payload?.drafts) ? payload.drafts.length : 0
    const fallbackCount = Number(payload?.fallback_count || 0)
    evidenceText.value = ''
    photoFiles.value = []
    mediaFileIds.value = []
    usedVoiceInput.value = false
    if (draftCount === 0) {
      showToast(res?.message || '未生成待确认记录：请确认计划已绑定检查模板')
    } else if (fallbackCount > 0) {
      showToast(res?.message || `已生成 ${draftCount} 条记录（${fallbackCount} 条为保守回退，需人工复核）`)
    } else {
      showToast(res?.message || `AI 已生成 ${draftCount} 条待确认记录`)
    }
    await loadSession()
  } catch (error) {
    const detail = error?.response?.data?.detail || error?.message
    showToast(typeof detail === 'string' ? detail : 'AI 证据分析失败，请重试')
  } finally {
    clearAnalyzeTimer()
    analyzing.value = false
    analyzeStepKey.value = 'idle'
    analyzeProgress.value = 0
  }
}

const openDraftEditor = (draft) => {
  const payload = draft.record_payload || {}
  editingDraft.value = draft
  editDraftForm.value = {
    evaluation_3level: String(payload.evaluation_3level || draft.evaluation || '2'),
    audit_evidence: payload.audit_evidence || draft.finding_text || '',
    audit_findings: payload.audit_findings || draft.finding_text || '',
    rectification_suggestion: payload.rectification_suggestion || ''
  }
  editDraftVisible.value = true
}

const saveEditedDraft = async () => {
  const draftId = editingDraft.value?.id
  if (!draftId) return
  const values = editDraftForm.value
  if (!values.audit_evidence.trim()) return showToast('请填写客观证据')
  if (values.evaluation_3level === '3' && !values.audit_findings.trim()) {
    return showToast('不符合项必须填写审核发现')
  }

  savingDraft.value = true
  try {
    await confirmAuditDrafts(projectId.value, sessionId.value, {
      draft_ids: [draftId],
      action: 'confirm',
      safe_only: false,
      overrides: [{
        draft_id: draftId,
        evaluation_3level: values.evaluation_3level,
        audit_evidence: values.audit_evidence.trim(),
        audit_findings: values.audit_findings.trim() || undefined,
        rectification_suggestion: values.rectification_suggestion.trim() || undefined
      }]
    })
    selectedDraftIds.value = selectedDraftIds.value.filter((id) => id !== draftId)
    editDraftVisible.value = false
    editingDraft.value = null
    showToast('草稿已按审核员修改内容采纳')
    await loadSession()
  } catch (error) {
    showToast(requestErrorMessage(error, '编辑采纳失败'))
  } finally {
    savingDraft.value = false
  }
}

const rejectDraft = async (draft) => {
  try {
    await showConfirmDialog({
      title: '拒绝 AI 草稿',
      message: `确认拒绝条款 ${clauseText(draft)} 的本条 AI 草稿吗？拒绝后不会写入正式记录。`
    })
  } catch {
    return
  }

  confirming.value = true
  try {
    await confirmAuditDrafts(projectId.value, sessionId.value, {
      draft_ids: [draft.id],
      action: 'reject',
      safe_only: false,
      overrides: []
    })
    selectedDraftIds.value = selectedDraftIds.value.filter((id) => id !== draft.id)
    showToast('AI 草稿已拒绝')
    await loadSession()
  } catch (error) {
    showToast(requestErrorMessage(error, '拒绝草稿失败'))
  } finally {
    confirming.value = false
  }
}

const doConfirm = async (draftIds, safeOnly = false) => {
  if (isCompleted.value) return
  confirming.value = true
  try {
    await confirmAuditDrafts(projectId.value, sessionId.value, { draft_ids: draftIds, action: 'confirm', safe_only: safeOnly, overrides: [] })
    selectedDraftIds.value = []
    showToast('审核记录已采纳')
    await loadSession()
  } catch (error) {
    showToast(error?.message || '采纳记录失败')
  } finally {
    confirming.value = false
  }
}

const confirmSelected = () => {
  const selected = selectedDraftIds.value
    .map((id) => pendingDrafts.value.find((d) => d.id === id))
    .filter(Boolean)
  const fallbackIds = selected.filter((d) => isFallback(d)).map((d) => d.id)
  if (fallbackIds.length) {
    showToast('回退结果不可批量采纳，请逐条编辑并采纳')
    selectedDraftIds.value = selectedDraftIds.value.filter((id) => !fallbackIds.includes(id))
    return
  }
  return doConfirm(selectedDraftIds.value)
}
const confirmSafeDrafts = () => doConfirm([], true)

const runQualityCheck = async () => {
  checking.value = true
  try {
    qualityCheck.value = unwrap(await checkAuditQuality(projectId.value, sessionId.value))
    showToast(blockers.value.length ? `发现 ${blockers.value.length} 个阻断项` : '完整性检查通过')
  } finally {
    checking.value = false
  }
}

const goBack = () => {
  router.push('/today-audit')
}
const goTodayAudit = () => {
  router.replace('/today-audit')
}
const goAuditTasks = () => {
  router.replace('/audit-tasks')
}
const goToTemplateInspection = () => {
  // 不得回退到计划项 id —— 现场检查页只认「检查任务 id / 检查记录 id」，
  // 计划项 id 会必然落到「检查记录不存在」的死页（会议类计划项常见）。
  const targetId = planItem.value?.inspection_task_id
  if (targetId) {
    router.push(`/inspection/${targetId}`)
  } else {
    showToast('该任务没有检查表，请改用 AI 辅助审核')
  }
}
const goResultPage = () => {
  router.replace({
    name: 'AuditSessionResult',
    params: { sessionId: sessionId.value },
    query: { projectId: projectId.value, planItemId: planItemId.value }
  })
}

const submitSession = async () => {
  if (isCompleted.value) return showToast('审核记录已提交')
  await runQualityCheck()
  if (blockers.value.length) return
  if (!conclusion.value.trim()) return showToast('请填写最终审核结论')
  try {
    await showConfirmDialog({ title: '提交审核记录', message: '提交后将同步更新任务进度，确认继续吗？' })
  } catch { return }
  submitting.value = true
  try {
    await submitAuditSession(projectId.value, sessionId.value, { conclusion: conclusion.value.trim() })
    clearSessionDraft()
    await loadSession()
    try {
      await showDialog({
        title: '提交成功',
        message: '本区域审核记录已提交。可查看完整结果，或返回今日审核继续其他任务。',
        confirmButtonText: '查看结果',
        showCancelButton: true,
        cancelButtonText: '返回今日审核'
      })
      goResultPage()
    } catch {
      goTodayAudit()
    }
  } catch (error) {
    showToast(error?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const restored = restoreSessionDraft()
  await loadSession()
  if (restored && !isCompleted.value) showToast('已恢复本机保存的文字草稿')
})
onBeforeUnmount(() => {
  clearAnalyzeTimer()
  if (speechRecognition && listening.value) speechRecognition.stop()
  if (!isCompleted.value) persistSessionDraft()
})
</script>

<style scoped>
.audit-session-page{min-height:100dvh;padding:16px 12px calc(40px + env(safe-area-inset-bottom));background:var(--bg-light)}
.session-summary,.work-card,.alert-card{margin-bottom:14px;padding:18px;border:1px solid var(--border-light);border-radius:var(--radius-lg);background:#fff;box-shadow:var(--shadow-sm)}
.session-summary{color:#fff;background:var(--primary-gradient-dark)}.session-summary h1{margin:3px 0 5px;font-size:20px}.session-summary p{margin:0 0 14px;color:rgba(255,255,255,.84)}
.eyebrow{margin:0 0 3px;font-size:11px;font-weight:700;letter-spacing:.12em;color:var(--primary-color)}.session-summary .eyebrow{color:rgba(255,255,255,.72)}
.section-title,.card-title,.draft-heading,.draft-meta,.review-actions{display:flex;align-items:center}.section-title{justify-content:space-between;margin-bottom:12px;align-items:flex-start}.section-title h2{margin:0;font-size:18px}.section-subhint{margin:4px 0 0;font-size:12px;color:var(--text-secondary);font-weight:400;letter-spacing:0}.icon-button{width:44px;height:44px;border:0;border-radius:12px;color:var(--primary-color);background:var(--info-bg)}
.primary-action{min-height:48px;margin-top:14px}.alert-card{border-color:#fecaca;background:#fff7f7;color:#991b1b}.card-title{gap:8px;font-weight:700}.alert-card ul{margin:10px 0 0 20px}
.draft-card,.saved-evidence-card{margin:10px 0;padding:14px;border:1px solid var(--border-color);border-radius:12px}.draft-card.abnormal{border-color:#fca5a5;background:linear-gradient(90deg,var(--error-bg),#fff 45%)}.draft-card.fallback{border-color:#fbbf24;background:linear-gradient(90deg,#fef3c7,#fff 45%)}.draft-fallback-notice{margin:8px 0 6px;padding:6px 10px;border-radius:8px;background:#fef3c7;color:#92400e;font-size:12px;font-weight:600}.progress-hint{margin:6px 0 0;color:rgba(255,255,255,.92);font-size:13px;font-weight:500}.progress-hint.warning{color:#fde68a}.progress-hint.success{color:#bbf7d0}.progress-step-label{margin:8px 0 0!important;font-size:12px;color:rgba(255,255,255,.8)!important}.draft-heading{gap:8px;justify-content:space-between;min-width:220px}.draft-evidence,.reasoning{margin:10px 0;font-size:14px;line-height:1.6}.draft-meta{flex-wrap:wrap;gap:8px 14px;font-size:12px;color:var(--text-secondary)}.confidence-cell{display:inline-flex;align-items:center;gap:4px}.citation{padding:8px;border-radius:8px;background:var(--bg-light);font-size:12px}.review-actions{flex-direction:column;gap:10px;margin-top:14px}.final-card{margin-bottom:0}
.agent-entry{min-height:44px;margin-top:10px}
.analyze-status-card{border-color:#bae6fd;background:linear-gradient(180deg,#f0f9ff,#fff 55%)}
.analyze-steps{margin:0;padding:0;list-style:none}
.analyze-steps li{display:flex;gap:12px;padding:10px 0;border-bottom:1px dashed var(--border-light)}
.analyze-steps li:last-child{border-bottom:0}
.step-dot{flex:0 0 28px;width:28px;height:28px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:var(--bg-light);color:var(--text-secondary);font-size:12px;font-weight:700}
.analyze-steps li.active .step-dot{background:#e0f2fe;color:var(--primary-color)}
.analyze-steps li.done .step-dot{background:#d1fae5;color:#059669}
.step-body strong{display:block;font-size:14px;color:var(--text-primary)}
.step-body p{margin:2px 0 0;font-size:12px;color:var(--text-secondary)}
.analyze-steps li.pending{opacity:.55}
.analyze-tip{margin:12px 0 0;padding:10px 12px;border-radius:10px;background:#eff6ff;color:#1e40af;font-size:12px;line-height:1.5}
.success-card{border-color:#a7f3d0;background:linear-gradient(180deg,#ecfdf5,#fff 50%)}
.success-hero{display:flex;gap:14px;align-items:flex-start}
.success-hero h2{margin:0 0 6px;font-size:18px}
.success-copy{margin:0;color:var(--text-secondary);font-size:13px;line-height:1.55}
.mode-card{margin-bottom:14px;padding:4px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:#fff;box-shadow:var(--shadow-sm)}
.mode-switch{display:grid;grid-template-columns:1fr 1fr;gap:4px}
.mode-switch button{min-height:42px;border:0;border-radius:calc(var(--radius-md) - 3px);color:var(--text-secondary);background:transparent;font:inherit;font-size:14px;font-weight:600}
.mode-switch button.active{color:#fff;background:var(--primary-color)}
.inline-radios{display:flex;flex-wrap:wrap;gap:10px 14px;padding:4px 0}
.evaluation-radios{gap:10px 12px}
.photo-field{padding:14px 16px;border-top:1px solid var(--border-light)}
.photo-field__label{margin-bottom:10px;color:var(--text-primary);font-size:14px}
.field-hint{margin:7px 0 0;color:var(--text-secondary);font-size:12px;line-height:1.5}
.saved-manual-list{margin-top:18px}
.draft-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}
.edit-sheet{height:100%;display:flex;flex-direction:column;background:var(--bg-light)}
.edit-sheet__header{min-height:54px;display:grid;grid-template-columns:64px 1fr 64px;align-items:center;border-bottom:1px solid var(--border-light);background:#fff;text-align:center}
.edit-sheet__header button{height:44px;border:0;color:var(--primary-color);background:transparent;font:inherit}
.edit-sheet__header button:disabled{color:var(--text-light)}
.edit-sheet__header strong{font-size:16px}
.edit-sheet__body{flex:1;overflow-y:auto;padding:12px 12px calc(24px + env(safe-area-inset-bottom))}
.edit-sheet__clause{margin:0 0 10px;padding:10px 16px;border-radius:var(--radius-sm);color:var(--text-primary);background:#fff;font-size:14px;font-weight:600}
.template-nav-card{margin-bottom:14px;padding:12px 14px;border:1px solid #bae6fd;border-radius:var(--radius-lg);background:#f0f9ff;box-shadow:var(--shadow-sm)}
.template-nav-inner{display:flex;align-items:center;justify-content:space-between;gap:10px}
.template-nav-info{display:flex;align-items:center;gap:10px}
.template-nav-info strong{display:block;font-size:14px;color:#0369a1}
.template-nav-info p{margin:2px 0 0;font-size:11px;color:#0284c7}
@media(min-width:700px){.audit-session-page{max-width:680px;margin:0 auto}}
</style>
