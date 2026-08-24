<template>
  <main class="result-page">
    <van-nav-bar title="审核结果" left-arrow fixed placeholder @click-left="router.push('/today-audit')" />

    <van-skeleton v-if="loading" title :row="8" class="loading-card" />

    <template v-else-if="session.id">
      <section class="hero" :class="{ completed: isCompleted }">
        <p class="eyebrow">{{ planItem?.area_name || session.title || '现场审核' }}</p>
        <h1>{{ isCompleted ? '审核记录已提交' : '审核会话详情' }}</h1>
        <p class="hero-meta">
          {{ scheduleText }}
          <van-tag size="medium" :type="isCompleted ? 'success' : 'primary'">
            {{ isCompleted ? '已完成' : statusLabel }}
          </van-tag>
        </p>
        <p v-if="session.completed_at" class="hero-time">
          提交时间：{{ formatTime(session.completed_at) }}
        </p>
      </section>

      <section class="card">
        <div class="section-title">
          <div>
            <p class="eyebrow">区域结论</p>
            <h2>最终结论</h2>
          </div>
        </div>
        <p class="conclusion">{{ conclusion || '（未填写结论）' }}</p>
      </section>

      <!-- 模板检查项覆盖进度 -->
      <section v-if="templateTotalItems > 0" class="card">
        <div class="section-title">
          <div>
            <p class="eyebrow">检查完整性</p>
            <h2>检查项覆盖率</h2>
          </div>
          <van-tag :type="uncoveredItems.length === 0 ? 'success' : 'warning'">
            {{ templateCoveredItems }} / {{ templateTotalItems }} 项 ({{ completionRate }}%)
          </van-tag>
        </div>
        <van-progress :percentage="completionRate" :color="uncoveredItems.length === 0 ? '#059669' : '#d97706'" stroke-width="6" style="margin-bottom: 10px;" />
        <div v-if="uncoveredItems.length" class="uncovered-notice">
          <div class="uncovered-title">
            <van-icon name="warning-o" color="#d97706" />
            <span>尚有 {{ uncoveredItems.length }} 项未完成审核：</span>
          </div>
          <ul class="uncovered-list">
            <li v-for="item in uncoveredItems" :key="item.id">
              <van-tag size="mini" type="danger" plain>未完成</van-tag>
              <span class="uncovered-name">{{ item.title }}</span>
            </li>
          </ul>
        </div>
      </section>

      <section v-if="confirmedDrafts.length" class="card">
        <div class="section-title">
          <div>
            <p class="eyebrow">审核条款</p>
            <h2>已确认记录</h2>
          </div>
          <van-tag type="success">{{ confirmedDrafts.length }} 条</van-tag>
        </div>
        <article v-for="draft in confirmedDrafts" :key="draft.id" class="record-card">
          <div class="record-head">
            <strong>{{ clauseText(draft) }}</strong>
            <van-tag :type="evaluationType(draft)">{{ evaluationText(draft) }}</van-tag>
          </div>
          <p class="record-body">
            {{ draft.finding_text || draft.record_payload?.audit_evidence || draft.record_payload?.audit_findings || '无发现描述' }}
          </p>
          <div class="record-meta">
            <span>证据：{{ qualityText(draft) }}</span>
            <span>置信度：{{ confidenceText(draft) }}</span>
          </div>
          <p v-if="draft.reasoning" class="reasoning">{{ draft.reasoning }}</p>
          <details v-if="draft.citations?.length">
            <summary>查看 {{ draft.citations.length }} 条引用</summary>
            <p v-for="(citation, index) in draft.citations" :key="index" class="citation">
              {{ citation.document_title || citation.file_name || '资料' }}：{{ citation.content }}
            </p>
          </details>
        </article>
      </section>

      <section v-if="submissions.length" class="card">
        <div class="section-title">
          <div>
            <p class="eyebrow">现场采集</p>
            <h2>证据提交记录</h2>
          </div>
          <van-tag type="primary">{{ submissions.length }} 条</van-tag>
        </div>
        <article v-for="item in submissions" :key="item.id" class="record-card muted">
          <div class="record-head">
            <strong>{{ item.description?.slice(0, 40) || '现场证据' }}</strong>
            <van-tag size="mini" plain>{{ item.status === 'completed' ? '已处理' : item.status }}</van-tag>
          </div>
          <p class="record-body">{{ item.description || '—' }}</p>
          <p class="record-meta">
            {{ item.source_files?.length || 0 }} 个附件
            · {{ formatTime(item.submitted_at) }}
          </p>
        </article>
      </section>

      <section class="card actions-card">
        <van-button block type="primary" @click="router.push('/today-audit')">返回今日审核</van-button>
        <van-button
          block
          plain
          type="warning"
          :loading="reauditing"
          @click="startReaudit"
        >
          重新审核
        </van-button>
        <van-button block plain type="primary" @click="router.push('/audit-tasks')">全部审核任务</van-button>
      </section>
    </template>

    <van-empty v-else description="未找到审核结果" />
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'

import {
  createAuditSession,
  getAuditPlanItem,
  getAuditSession
} from '../api/auditProjects'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => String(route.query.projectId || ''))
const sessionId = computed(() => String(route.params.sessionId || ''))
const planItemId = computed(() => String(route.query.planItemId || ''))

const loading = ref(true)
const reauditing = ref(false)
const session = ref({})
const planItem = ref(null)

const unwrap = (response) => response?.data || response || {}

const isCompleted = computed(() => session.value.status === 'completed')
const statusLabel = computed(() => ({
  active: '进行中',
  completed: '已完成',
  cancelled: '已取消'
}[session.value.status] || session.value.status || '未知'))

const conclusion = computed(
  () => session.value.conclusion
    || session.value.context_snapshot?.conclusion
    || ''
)

const drafts = computed(() => session.value.drafts || [])
const confirmedDrafts = computed(() => drafts.value.filter((d) => d.status === 'confirmed'))
const submissions = computed(() => (session.value.submissions || []).filter((s) => s.status !== 'failed'))

const qualityCheck = computed(() => session.value.quality_check || {})
const templateTotalItems = computed(() => qualityCheck.value.template_total_items || 0)
const templateCoveredItems = computed(() => qualityCheck.value.template_covered_items ?? confirmedDrafts.value.length)
const uncoveredItems = computed(() => qualityCheck.value.uncovered_items || [])
const completionRate = computed(() => {
  if (!templateTotalItems.value) return 100
  return Math.round((templateCoveredItems.value / templateTotalItems.value) * 100)
})

const scheduleText = computed(() => {
  if (!planItem.value) return '计划信息加载中'
  const date = planItem.value.plan_date || ''
  const time = planItem.value.time_start && planItem.value.time_end
    ? `${planItem.value.time_start}-${planItem.value.time_end}`
    : ''
  return [date, time].filter(Boolean).join(' ') || '时间待定'
})

const evaluationCode = (draft) => String(draft.record_payload?.evaluation_3level || draft.evaluation || '2')
const evaluationText = (draft) => ({ 1: '符合', 2: '基本符合', 3: '不符合' }[evaluationCode(draft)] || '待确认')
const evaluationType = (draft) => ({ 1: 'success', 2: 'warning', 3: 'danger' }[evaluationCode(draft)] || 'default')
const clauseText = (draft) => {
  const itemTitle = draft.record_payload?.item_title || draft.clause_refs?.[0]?.title
  if (itemTitle) return itemTitle
  return draft.primary_clause_no || draft.clause_refs?.map((c) => c.clause_no).filter(Boolean).join(' / ') || '检查项'
}
const qualityText = (draft) => ({ sufficient: '充分', partial: '部分充分', insufficient: '不足' }[draft.quality?.level || draft.quality?.evidence_quality] || '—')
const confidenceText = (draft) => `${Math.round(Number(draft.confidence || 0) * 100)}%`
const formatTime = (value) => {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return String(value)
  }
}

const load = async () => {
  loading.value = true
  try {
    if (!projectId.value || !sessionId.value) throw new Error('缺少项目或会话参数')
    const [sessionRes, planRes] = await Promise.all([
      getAuditSession(projectId.value, sessionId.value),
      planItemId.value ? getAuditPlanItem(planItemId.value) : Promise.resolve(null)
    ])
    session.value = unwrap(sessionRes)
    planItem.value = planRes ? unwrap(planRes) : null
  } catch (error) {
    showToast(error?.message || '加载审核结果失败')
  } finally {
    loading.value = false
  }
}

const startReaudit = async () => {
  if (!projectId.value || !planItemId.value) return
  try {
    await showConfirmDialog({
      title: '重新审核',
      message: `「${planItem.value?.area_name || '该区域'}」将开启新一轮现场记录，不会覆盖本次已提交结果。是否继续？`,
      confirmButtonText: '开始重新审核',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  reauditing.value = true
  try {
    const created = await createAuditSession(projectId.value, {
      title: `${planItem.value?.area_name || '现场'}审核`,
      plan_item_id: planItemId.value,
      reaudit: true
    })
    const next = unwrap(created)
    if (!next?.id) throw new Error('未能创建重新审核会话')
    showToast('已开启重新审核')
    router.replace({
      name: 'AiAuditSession',
      params: { sessionId: next.id },
      query: { projectId: projectId.value, planItemId: planItemId.value }
    })
  } catch (error) {
    showToast(error?.message || '开启重新审核失败')
  } finally {
    reauditing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.result-page {
  min-height: 100dvh;
  padding: 16px 12px calc(32px + env(safe-area-inset-bottom));
  background: var(--bg-light);
}
.loading-card {
  margin: 12px;
  padding: 16px;
  border-radius: 12px;
  background: #fff;
}
.hero,
.card {
  margin-bottom: 14px;
  padding: 18px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: #fff;
  box-shadow: var(--shadow-sm);
}
.hero {
  color: #fff;
  background: var(--primary-gradient-dark);
}
.hero.completed {
  background: linear-gradient(135deg, #047857, #059669 55%, #10b981);
}
.eyebrow {
  margin: 0 0 4px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--primary-color);
}
.hero .eyebrow { color: rgba(255, 255, 255, 0.75); }
.hero h1 { margin: 0 0 8px; font-size: 20px; }
.hero-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
}
.hero-time { margin: 10px 0 0; font-size: 12px; color: rgba(255, 255, 255, 0.8); }
.section-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
}
.section-title h2 { margin: 0; font-size: 17px; }
.conclusion {
  margin: 0;
  padding: 12px;
  border-radius: 10px;
  background: var(--bg-light);
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
}
.record-card {
  margin-top: 10px;
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
}
.record-card.muted { background: #fafafa; }
.record-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.record-body {
  margin: 10px 0;
  font-size: 14px;
  line-height: 1.55;
  color: var(--text-primary);
}
.record-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  font-size: 12px;
  color: var(--text-secondary);
}
.reasoning {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--text-secondary);
}
.citation {
  margin: 6px 0 0;
  padding: 8px;
  border-radius: 8px;
  background: var(--bg-light);
  font-size: 12px;
}
.uncovered-notice {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fffbeb;
  border: 1px solid #fde68a;
}
.uncovered-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 8px;
}
.uncovered-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.uncovered-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #78350f;
}
.uncovered-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.actions-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
@media (min-width: 700px) {
  .result-page { max-width: 680px; margin: 0 auto; }
}
</style>
