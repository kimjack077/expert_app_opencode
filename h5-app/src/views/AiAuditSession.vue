<template>
  <main class="audit-session-page">
    <van-nav-bar title="AI 现场审核" left-arrow fixed placeholder @click-left="router.push('/today-audit')" />

    <section class="session-summary">
      <div>
        <p class="eyebrow">{{ planItem?.area_name || session.title || '现场审核' }}</p>
        <h1>{{ statusText }}</h1>
        <p>{{ planItem ? `${planItem.plan_date} ${planItem.time_start || ''}-${planItem.time_end || ''}` : '正在加载审核任务' }}</p>
      </div>
      <van-progress :percentage="progress" stroke-width="8" color="#0369A1" />
    </section>

    <section v-if="blockers.length" class="alert-card" role="alert">
      <div class="card-title"><van-icon name="warning-o" /> 提交前必须处理</div>
      <ul><li v-for="item in blockers" :key="item.code || item.message">{{ item.message || item.title }}</li></ul>
    </section>

    <section v-if="!loading && savedSubmissions.length" class="work-card">
      <div class="section-title">
        <div><p class="eyebrow">SAVED</p><h2>已保存现场证据</h2></div>
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

    <section class="work-card">
      <div class="section-title">
        <div><p class="eyebrow">EVIDENCE</p><h2>采集现场证据</h2></div>
        <button type="button" class="icon-button" aria-label="语音输入" :disabled="isCompleted" @click="toggleVoice">
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
        placeholder="一次描述完整现场情况，Agent 会自动拆分并匹配多个条款"
      />
      <van-uploader v-model="photoFiles" multiple :max-count="5" :disabled="isCompleted" :after-read="uploadPhoto" />
      <van-button block type="primary" class="primary-action" :loading="analyzing" :disabled="isCompleted || !evidenceText.trim()" @click="analyzeEvidence">
        生成多条款 AI 记录
      </van-button>
    </section>

    <section class="work-card">
      <div class="section-title">
        <div><p class="eyebrow">REVIEW</p><h2>待确认 AI 记录</h2></div>
        <van-tag v-if="pendingDrafts.length" type="warning">{{ pendingDrafts.length }} 条</van-tag>
      </div>
      <van-empty v-if="!loading && pendingDrafts.length === 0" description="提交现场证据后，AI 草稿会显示在这里" />
      <van-checkbox-group v-else v-model="selectedDraftIds">
        <article v-for="draft in sortedDrafts" :key="draft.id" class="draft-card" :class="{ abnormal: isAbnormal(draft) }">
          <van-checkbox :name="draft.id" shape="square">
            <div class="draft-heading">
              <strong>{{ clauseText(draft) }}</strong>
              <van-tag :type="evaluationType(draft)">{{ evaluationText(draft) }}</van-tag>
            </div>
          </van-checkbox>
          <p class="draft-evidence">{{ draft.finding_text || draft.record_payload?.audit_evidence || '未提供证据摘要' }}</p>
          <div class="draft-meta">
            <span>证据：{{ qualityText(draft) }}</span>
            <span>置信度：{{ confidenceText(draft) }}</span>
          </div>
          <p class="reasoning">{{ draft.reasoning }}</p>
          <details v-if="draft.citations?.length">
            <summary>查看 {{ draft.citations.length }} 条引用</summary>
            <p v-for="(citation, index) in draft.citations" :key="index" class="citation">
              {{ citation.document_title || citation.file_name || '项目资料' }}：{{ citation.content }}
            </p>
          </details>
        </article>
      </van-checkbox-group>
      <div v-if="pendingDrafts.length" class="review-actions">
        <van-button block plain type="primary" :loading="confirming" :disabled="isCompleted" @click="confirmSafeDrafts">批量采纳安全项</van-button>
        <van-button block type="primary" :loading="confirming" :disabled="isCompleted || selectedDraftIds.length === 0" @click="confirmSelected">采纳已选择记录</van-button>
      </div>
    </section>

    <section v-if="confirmedDrafts.length" class="work-card">
      <div class="section-title">
        <div><p class="eyebrow">CONFIRMED</p><h2>已确认审核记录</h2></div>
        <van-tag type="success">{{ confirmedDrafts.length }} 条</van-tag>
      </div>
      <article v-for="draft in confirmedDrafts" :key="draft.id" class="saved-evidence-card">
        <div class="draft-heading">
          <strong>{{ clauseText(draft) }}</strong>
          <van-tag :type="evaluationType(draft)">{{ evaluationText(draft) }}</van-tag>
        </div>
        <p class="draft-evidence">{{ draft.finding_text || draft.record_payload?.audit_evidence || '已确认审核记录' }}</p>
        <p class="draft-meta">证据：{{ qualityText(draft) }} · 置信度：{{ confidenceText(draft) }}</p>
      </article>
    </section>

    <section class="work-card final-card">
      <div class="section-title"><div><p class="eyebrow">CONCLUSION</p><h2>最终结论与提交</h2></div></div>
      <van-field v-model="conclusion" type="textarea" rows="4" label="区域结论" :readonly="isCompleted" placeholder="根据已确认记录形成最终审核结论" />
      <div class="review-actions">
        <van-button block plain type="primary" :loading="checking" @click="runQualityCheck">检查完整性</van-button>
        <van-button block type="primary" :loading="submitting" :disabled="isCompleted" @click="submitSession">提交审核记录</van-button>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'

import {
  checkAuditQuality,
  confirmAuditDrafts,
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
const loading = ref(true)
const analyzing = ref(false)
const confirming = ref(false)
const checking = ref(false)
const submitting = ref(false)
const listening = ref(false)
const evidenceText = ref('')
const conclusion = ref('')
const photoFiles = ref([])
const mediaFileIds = ref([])
const selectedDraftIds = ref([])
const qualityCheck = ref({ blockers: [], warnings: [] })
let speechRecognition = null

const drafts = computed(() => session.value.drafts || [])
const pendingDrafts = computed(() => drafts.value.filter((item) => item.status === 'draft'))
const confirmedDrafts = computed(() => drafts.value.filter((item) => item.status === 'confirmed'))
const savedSubmissions = computed(() => (session.value.submissions || []).filter((item) => item.status !== 'failed'))
const isCompleted = computed(() => session.value.status === 'completed')
const blockers = computed(() => qualityCheck.value.blockers || qualityCheck.value.blocking_items || [])
const progress = computed(() => session.value.progress ?? (drafts.value.length ? Math.min(95, 20 + drafts.value.filter((item) => item.status === 'confirmed').length * 15) : 10))
const statusText = computed(() => session.value.status === 'completed' ? '审核记录已提交' : 'Agent 正在协助整理现场证据')
const sortedDrafts = computed(() => [...pendingDrafts.value].sort((left, right) => Number(isAbnormal(right)) - Number(isAbnormal(left))))

const evaluationCode = (draft) => String(draft.record_payload?.evaluation_3level || draft.evaluation || '2')
const isAbnormal = (draft) => evaluationCode(draft) === '3' || ['insufficient', 'partial'].includes(draft.quality?.level)
const evaluationText = (draft) => ({ 1: '符合', 2: '基本符合', 3: '不符合' }[evaluationCode(draft)] || '待确认')
const evaluationType = (draft) => ({ 1: 'success', 2: 'warning', 3: 'danger' }[evaluationCode(draft)] || 'default')
const clauseText = (draft) => draft.primary_clause_no || draft.clause_refs?.map((item) => item.clause_no).filter(Boolean).join(' / ') || '候选条款'
const qualityText = (draft) => ({ sufficient: '充分', partial: '部分充分', insufficient: '不足' }[draft.quality?.level || draft.quality?.evidence_quality] || '待复核')
const confidenceText = (draft) => `${Math.round(Number(draft.confidence || 0) * 100)}%`
const submissionTitle = (submission) => submission.title || `${submission.input_type === 'voice' ? '语音' : '现场'}证据`
const formatSubmissionTime = (submission) => submission.submitted_at ? new Date(submission.submitted_at).toLocaleString('zh-CN', { hour12: false }) : '刚刚保存'

const unwrap = (response) => response?.data || response || {}

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
    conclusion.value = session.value.conclusion || session.value.context_snapshot?.conclusion || ''
  } catch (error) {
    showToast(error?.message || '加载审核会话失败')
  } finally {
    loading.value = false
  }
}

const uploadPhoto = async (fileItem) => {
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
      if (uploaded.id) mediaFileIds.value.push(uploaded.id)
      item.status = 'done'
    } catch (error) {
      item.status = 'failed'
      item.message = error?.message || '上传失败'
    }
  }
}

const toggleVoice = () => {
  if (isCompleted.value) return
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
  }
  speechRecognition.onend = () => { listening.value = false }
  speechRecognition.onerror = () => { listening.value = false; showToast('语音识别中断，请重试') }
  listening.value = true
  speechRecognition.start()
}

const analyzeEvidence = async () => {
  if (isCompleted.value || !evidenceText.value.trim()) return
  analyzing.value = true
  try {
    await submitSessionEvidence(projectId.value, sessionId.value, {
      content: evidenceText.value.trim(),
      evidence_type: mediaFileIds.value.length ? 'mixed' : (listening.value ? 'voice' : 'text'),
      media_file_ids: mediaFileIds.value,
      source_metadata: { plan_item_id: planItemId.value, area_name: planItem.value?.area_name }
    })
    evidenceText.value = ''
    photoFiles.value = []
    mediaFileIds.value = []
    showToast('AI 已生成待确认记录')
    await loadSession()
  } catch (error) {
    showToast(error?.message || 'AI 证据分析失败，请重试')
  } finally {
    analyzing.value = false
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

const confirmSelected = () => doConfirm(selectedDraftIds.value)
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
    showToast('审核记录提交成功')
    await loadSession()
  } catch (error) {
    showToast(error?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(loadSession)
</script>

<style scoped>
.audit-session-page{min-height:100dvh;padding:16px 12px calc(40px + env(safe-area-inset-bottom));background:var(--bg-light)}
.session-summary,.work-card,.alert-card{margin-bottom:14px;padding:18px;border:1px solid var(--border-light);border-radius:var(--radius-lg);background:#fff;box-shadow:var(--shadow-sm)}
.session-summary{color:#fff;background:var(--primary-gradient-dark)}.session-summary h1{margin:3px 0 5px;font-size:20px}.session-summary p{margin:0 0 14px;color:rgba(255,255,255,.84)}
.eyebrow{margin:0 0 3px;font-size:11px;font-weight:700;letter-spacing:.12em;color:var(--primary-color)}.session-summary .eyebrow{color:rgba(255,255,255,.72)}
.section-title,.card-title,.draft-heading,.draft-meta,.review-actions{display:flex;align-items:center}.section-title{justify-content:space-between;margin-bottom:12px}.section-title h2{margin:0;font-size:18px}.icon-button{width:44px;height:44px;border:0;border-radius:12px;color:var(--primary-color);background:var(--info-bg)}
.primary-action{min-height:48px;margin-top:14px}.alert-card{border-color:#fecaca;background:#fff7f7;color:#991b1b}.card-title{gap:8px;font-weight:700}.alert-card ul{margin:10px 0 0 20px}
.draft-card,.saved-evidence-card{margin:10px 0;padding:14px;border:1px solid var(--border-color);border-radius:12px}.draft-card.abnormal{border-color:#fca5a5;background:linear-gradient(90deg,var(--error-bg),#fff 45%)}.draft-heading{gap:8px;justify-content:space-between;min-width:220px}.draft-evidence,.reasoning{margin:10px 0;font-size:14px;line-height:1.6}.draft-meta{flex-wrap:wrap;gap:8px 14px;font-size:12px;color:var(--text-secondary)}.citation{padding:8px;border-radius:8px;background:var(--bg-light);font-size:12px}.review-actions{flex-direction:column;gap:10px;margin-top:14px}.final-card{margin-bottom:0}
@media(min-width:700px){.audit-session-page{max-width:680px;margin:0 auto}}
</style>
