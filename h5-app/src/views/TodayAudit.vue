<template>
  <main class="today-audit-page">
    <!-- 与「检查记录 / 检查任务」统一的紧凑横幅 -->
    <div class="page-header">
      <div class="header-bg"></div>
      <div class="header-content">
        <div class="header-top">
          <div class="header-info">
            <h1 class="page-title">今日审核</h1>
            <p class="page-subtitle">现场工作台</p>
          </div>
          <button class="header-actions" type="button" aria-label="进入全部功能" @click="router.push('/home')">
            <van-icon name="apps-o" size="20" />
          </button>
        </div>
        <div class="stats-row" aria-label="任务概览">
          <div class="stat-item">
            <span class="stat-value">{{ activeCount }}</span>
            <span class="stat-label">进行中</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">{{ pendingCount }}</span>
            <span class="stat-label">待开始</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">{{ completedCount }}</span>
            <span class="stat-label">已完成</span>
          </div>
        </div>
      </div>
    </div>

    <van-pull-refresh v-model="refreshing" @refresh="loadTasks" class="refresh-container">
      <!-- 有未完成任务时：展示优先处理 -->
      <section v-if="priorityTask" class="priority-section" aria-labelledby="priority-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">优先处理</p>
            <h2 id="priority-title">当前优先任务</h2>
          </div>
          <van-tag :type="statusType(priorityTask.status)" size="medium">
            {{ statusText(priorityTask.status) }}
          </van-tag>
        </div>

        <article class="priority-card">
          <div class="priority-card__top">
            <div class="icon-tile" aria-hidden="true"><van-icon name="todo-list-o" size="24" /></div>
            <div class="priority-card__title">
              <p class="task-context">{{ taskContextText(priorityTask) }}</p>
              <h3>{{ priorityTask.area_name || '审核任务' }}</h3>
              <p>{{ formatSchedule(priorityTask) }}</p>
            </div>
          </div>
          <div class="task-details">
            <span><van-icon name="friends-o" /> {{ priorityTask.group_no || '审核组待确认' }}</span>
            <span><van-icon name="records-o" /> {{ systemText(priorityTask) }}</span>
            <span><van-icon name="completed" /> {{ taskProgressText(priorityTask) }}</span>
            <span v-if="hasTaskException(priorityTask)" class="task-details__exception">
              <van-icon name="warning-o" /> {{ taskExceptionText(priorityTask) }}
            </span>
          </div>
          <div class="task-progress" aria-label="条款完成进度">
            <span>完成度</span>
            <strong>{{ taskCompletionRate(priorityTask) }}%</strong>
          </div>
          <van-progress :percentage="taskCompletionRate(priorityTask)" stroke-width="7" color="#0369A1" />
          <van-button
            block
            type="primary"
            class="primary-action"
            :loading="openingTaskId === priorityTask.id"
            @click="openAgentSession(priorityTask)"
          >
            {{ actionButtonText(priorityTask) }}
          </van-button>
        </article>
      </section>

      <!-- 今日任务全部完成：不再把已完成项当成「优先」 -->
      <section
        v-else-if="!loading && tasks.length > 0 && allTasksDone"
        class="priority-section"
        aria-labelledby="done-title"
      >
        <div class="section-heading">
          <div>
            <p class="eyebrow">今日进度</p>
            <h2 id="done-title">今日任务已全部完成</h2>
          </div>
          <van-tag type="success" size="medium">已完成 {{ completedCount }}</van-tag>
        </div>
        <article class="priority-card priority-card--done">
          <div class="priority-card__top">
            <div class="icon-tile icon-tile--success" aria-hidden="true">
              <van-icon name="checked" size="24" />
            </div>
            <div class="priority-card__title">
              <h3>可以休息一下，或复盘已提交结果</h3>
              <p>下方已完成任务点进去可查看审核结果；需要时再在结果页发起重新审核。</p>
            </div>
          </div>
          <van-button block plain type="primary" class="primary-action" @click="router.push('/audit-tasks')">
            查看全部审核任务
          </van-button>
        </article>
      </section>

      <section class="task-list-section" aria-labelledby="task-list-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">今日安排</p>
            <h2 id="task-list-title">任务列表</h2>
          </div>
          <button class="text-action" type="button" @click="router.push('/audit-tasks')">查看全部</button>
        </div>

        <van-skeleton v-if="loading" title :row="4" class="loading-card" />
        <van-empty v-else-if="tasks.length === 0" image="search" description="今天没有分配给你的审核区域">
          <p class="empty-hint">可能原因：计划未指派、非今日计划、或账号角色不匹配</p>
          <van-button type="primary" size="small" @click="router.push('/audit-tasks')">查看全部审核任务</van-button>
          <van-button plain size="small" style="margin-left:8px" @click="router.push('/home')">返回工作台</van-button>
        </van-empty>
        <div v-else class="task-list">
          <button
            v-for="task in sortedTasks"
            :key="task.id"
            type="button"
            class="task-row"
            :class="{ 'task-row--exception': hasTaskException(task) }"
            @click="openTask(task)"
          >
            <span class="task-row__status" :class="`status-${task.status}`" aria-hidden="true"></span>
            <span class="task-row__content">
              <span class="task-row__context">{{ taskContextText(task) }}</span>
              <strong>{{ task.area_name || '审核任务' }}</strong>
              <small>{{ formatSchedule(task) }} · {{ systemText(task) }}</small>
              <span class="record-progress-label">
                {{ taskProgressText(task) }} · {{ taskCompletionRate(task) }}%
              </span>
              <span v-if="hasTaskException(task)" class="exception-label">
                <van-icon name="warning-o" /> {{ taskExceptionText(task) }}
              </span>
              <span v-if="task.status === 'completed'" class="completed-label">
                已完成 · 点击查看结果
              </span>
            </span>
            <span class="task-row__action">{{ actionButtonText(task) }}</span>
            <van-icon name="arrow" class="task-row__arrow" aria-hidden="true" />
          </button>
        </div>
      </section>
    </van-pull-refresh>
    <BottomNav />
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'

import {
  createAuditSession,
  getMyAuditTasks,
  listAuditSessions
} from '../api/auditProjects'
import BottomNav from '../components/BottomNav.vue'

const router = useRouter()
const tasks = ref([])
const loading = ref(true)
const refreshing = ref(false)
const openingTaskId = ref('')

const statusOrder = { in_progress: 0, pending: 1, completed: 2, cancelled: 3 }

const sortedTasks = computed(() => [...tasks.value].sort((left, right) => {
  const leftOrder = statusOrder[left.status] ?? 9
  const rightOrder = statusOrder[right.status] ?? 9
  if (leftOrder !== rightOrder) return leftOrder - rightOrder
  // 有异常的优先
  const leftEx = hasTaskException(left) ? 0 : 1
  const rightEx = hasTaskException(right) ? 0 : 1
  if (leftEx !== rightEx) return leftEx - rightEx
  return String(left.time_start || '').localeCompare(String(right.time_start || ''))
}))

// 仅从未完成任务中选优先项；全部完成后不再回退到已完成任务
const priorityTask = computed(() =>
  sortedTasks.value.find((task) => task.status === 'in_progress' || task.status === 'pending') || null
)
const allTasksDone = computed(
  () => tasks.value.length > 0 && tasks.value.every((task) => task.status === 'completed' || task.status === 'cancelled')
)
const activeCount = computed(() => tasks.value.filter((task) => task.status === 'in_progress').length)
const pendingCount = computed(() => tasks.value.filter((task) => task.status === 'pending').length)
const completedCount = computed(() => tasks.value.filter((task) => task.status === 'completed').length)

const statusText = (status) => ({
  pending: '待开始',
  in_progress: '进行中',
  completed: '已完成',
  cancelled: '已取消'
}[status] || '待处理')

const statusType = (status) => ({
  pending: 'warning',
  in_progress: 'primary',
  completed: 'success',
  cancelled: 'default'
}[status] || 'default')

const actionButtonText = (task) => {
  if (task?.status === 'pending') return '开始审核'
  if (task?.status === 'completed') return '查看结果'
  return '继续审核'
}

const systemText = (task) => {
  const systems = Array.isArray(task.certification_systems) ? task.certification_systems : []
  return systems.length ? systems.join(' / ') : '体系待确认'
}

const taskContextText = (task) => {
  const enterprise = task?.enterprise_name || '企业待确认'
  const project = task?.project_title || task?.project_no || '项目待确认'
  return `${enterprise} · ${project}`
}

const taskCompletionRate = (task) => {
  const provided = Number(task?.completion_rate)
  if (Number.isFinite(provided)) return Math.max(0, Math.min(100, Math.round(provided)))
  const confirmed = Number(task?.confirmed_record_count || 0)
  const total = Number(task?.total_clause_count || 0)
  return total > 0 ? Math.max(0, Math.min(100, Math.round(confirmed / total * 100))) : 0
}

const taskProgressText = (task) => {
  const confirmed = Number(task?.confirmed_record_count || 0)
  const total = Number(task?.total_clause_count || 0)
  return `已确认 ${confirmed}/${total} 条款`
}

const hasTaskException = (task) => Boolean(task?.has_nc || Number(task?.exception_count || 0) > 0)

const taskExceptionText = (task) => {
  const count = Number(task?.exception_count || 0)
  if (count > 0 && task?.has_nc) return `${count} 项异常，存在不符合项`
  if (count > 0) return `${count} 项异常待处理`
  return '存在不符合项'
}

const formatSchedule = (task) => {
  const date = task.plan_date || '日期待定'
  const time = task.time_start && task.time_end ? `${task.time_start}-${task.time_end}` : '时间待定'
  return `${date} ${time}`
}

const loadTasks = async () => {
  if (!refreshing.value) loading.value = true
  try {
    const response = await getMyAuditTasks({ today_only: true })
    tasks.value = Array.isArray(response?.data) ? response.data : []
  } catch (error) {
    showToast(error?.message || '获取今日审核任务失败，请下拉重试')
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const matchSessionForTask = (sessions, taskId, preferredStatuses) => {
  const matched = sessions.filter((session) => {
    const context = session.context_snapshot || session.context || {}
    return String(context.plan_item_id || session.plan_item_id || '') === String(taskId)
  })
  for (const status of preferredStatuses) {
    // 同状态可能有多条（历史会话），取最近
    const hits = matched
      .filter((session) => session.status === status)
      .sort((a, b) => String(b.completed_at || b.updated_at || b.created_at || '')
        .localeCompare(String(a.completed_at || a.updated_at || a.created_at || '')))
    if (hits[0]) return hits[0]
  }
  return matched.sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))[0] || null
}

const openCompletedResult = async (task) => {
  openingTaskId.value = task.id
  try {
    const sessionsResponse = await listAuditSessions(task.project_id)
    const sessions = Array.isArray(sessionsResponse?.data) ? sessionsResponse.data : []
    const session = matchSessionForTask(sessions, task.id, ['completed', 'active'])
    if (!session?.id) {
      showToast('未找到该任务的审核结果')
      return
    }
    router.push({
      name: 'AuditSessionResult',
      params: { sessionId: session.id },
      query: { projectId: task.project_id, planItemId: task.id }
    })
  } catch (error) {
    showToast(error?.message || '打开审核结果失败')
  } finally {
    openingTaskId.value = ''
  }
}

const openAgentSession = async (task) => {
  if (!task?.project_id || openingTaskId.value) return
  if (task.status === 'cancelled') {
    showToast('该任务已取消')
    return
  }

  openingTaskId.value = task.id
  try {
    const sessionsResponse = await listAuditSessions(task.project_id)
    const sessions = Array.isArray(sessionsResponse?.data) ? sessionsResponse.data : []
    let session = matchSessionForTask(sessions, task.id, ['active'])

    if (!session) {
      const created = await createAuditSession(task.project_id, {
        title: `${task.area_name || '现场'}审核`,
        plan_item_id: task.id,
        focus: Array.isArray(task.clauses) ? task.clauses.join('、') : ''
      })
      session = created?.data
    }

    if (!session?.id) throw new Error('未能创建审核会话')
    router.push({
      name: 'AiAuditSession',
      params: { sessionId: session.id },
      query: { projectId: task.project_id, planItemId: task.id }
    })
  } catch (error) {
    showToast(error?.message || '进入 AI 现场审核失败，请重试')
  } finally {
    openingTaskId.value = ''
  }
}

const openTask = (task) => {
  if (task?.status === 'completed') return openCompletedResult(task)
  return openAgentSession(task)
}

onMounted(loadTasks)
</script>

<style scoped>
.today-audit-page {
  min-height: 100dvh;
  padding-bottom: calc(72px + env(safe-area-inset-bottom));
  background: var(--bg-light);
}

/* —— 与检查记录页一致的紧凑 banner —— */
.page-header {
  position: relative;
  padding: 0 0 16px;
  overflow: hidden;
}
.header-bg {
  position: absolute;
  inset: 0;
  background: var(--primary-gradient-dark);
}
.header-bg::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 10% 20%, rgba(255, 255, 255, 0.1) 0%, transparent 40%),
    radial-gradient(circle at 90% 80%, rgba(56, 189, 248, 0.15) 0%, transparent 40%);
}
.header-content { position: relative; z-index: 1; }
.header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: calc(env(safe-area-inset-top) + 18px) 16px 10px;
}
.header-info {
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}
.page-title {
  margin: 0;
  font-size: 23px;
  font-weight: 700;
  color: var(--bg-white);
  font-family: var(--font-primary);
  letter-spacing: -0.5px;
  line-height: 1.25;
}
.page-subtitle {
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 400;
  white-space: nowrap;
}
.header-actions {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-md);
  color: var(--bg-white);
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(10px);
  cursor: pointer;
}
.stats-row {
  display: flex;
  justify-content: space-around;
  align-items: center;
  min-height: 44px;
  margin: 0 16px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(10px);
  border-radius: var(--radius-md);
  border: 1px solid rgba(255, 255, 255, 0.1);
}
.stat-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 7px;
  flex: 1;
}
.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--bg-white);
  font-family: var(--font-primary);
  letter-spacing: -0.5px;
  line-height: 1;
}
.stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
}
.stat-divider {
  width: 1px;
  height: 22px;
  background: rgba(255, 255, 255, 0.15);
}

.refresh-container { min-height: 40vh; }

.text-action,
.task-row {
  border: 0;
  font: inherit;
  cursor: pointer;
}

.eyebrow {
  margin: 0 0 4px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--primary-color);
}

.priority-section,
.task-list-section { padding: 12px 16px 20px; }

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 0 12px;
}

.section-heading h2 { margin: 0; font-size: 18px; color: var(--text-primary); }
.text-action { min-height: 44px; padding: 0 8px; color: var(--primary-color); background: transparent; }

.priority-card,
.loading-card,
.task-list {
  overflow: hidden;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--bg-white);
  box-shadow: var(--shadow-sm);
}

.priority-card { padding: 18px; }
.priority-card--done { border-color: #a7f3d0; background: linear-gradient(180deg, #ecfdf5, #fff 55%); }
.priority-card__top { display: flex; gap: 12px; align-items: center; }
.icon-tile { width: 48px; height: 48px; display: grid; flex: 0 0 auto; place-items: center; border-radius: 12px; color: var(--primary-color); background: var(--info-bg); }
.icon-tile--success { color: #059669; background: #d1fae5; }
.priority-card__title { min-width: 0; }
.priority-card__title h3 { margin: 0; font-size: 17px; }
.priority-card__title p { margin: 4px 0 0; font-size: 13px; color: var(--text-secondary); }
.priority-card__title .task-context { margin: 0 0 4px; overflow-wrap: anywhere; color: var(--text-muted); font-size: 12px; }
.task-details { display: flex; flex-wrap: wrap; gap: 8px 16px; margin: 16px 0; font-size: 13px; color: var(--text-secondary); }
.task-details span { display: inline-flex; align-items: center; gap: 5px; }
.task-details .task-details__exception { color: var(--error-color); }
.task-progress { display: flex; align-items: center; justify-content: space-between; margin: 0 0 6px; color: var(--text-secondary); font-size: 12px; }
.task-progress strong { color: var(--primary-color); font-size: 13px; }
.primary-action { min-height: 48px; margin-top: 4px; }

.loading-card { padding: 18px; }
.task-row { width: 100%; min-height: 76px; display: flex; align-items: center; gap: 12px; padding: 14px 16px; text-align: left; color: inherit; background: #fff; border-bottom: 1px solid var(--border-light); }
.task-row:last-child { border-bottom: 0; }
.task-row:active { background: var(--bg-light); }
.task-row__status { width: 10px; height: 10px; flex: 0 0 auto; border-radius: 50%; background: var(--text-light); }
.status-in_progress { background: var(--primary-color); }
.status-pending { background: var(--warning-color); }
.status-completed { background: var(--success-color); }
.task-row__content { min-width: 0; display: flex; flex: 1; flex-direction: column; }
.task-row__context { margin-bottom: 3px; overflow-wrap: anywhere; color: var(--text-muted); font-size: 11px; line-height: 1.35; }
.task-row__content strong { font-size: 15px; }
.task-row__content small { margin-top: 3px; color: var(--text-secondary); line-height: 1.45; }
.record-progress-label { margin-top: 6px; color: var(--primary-color); font-size: 12px; }
.task-row__action { flex: 0 0 auto; max-width: 5.5em; font-size: 12px; font-weight: 600; color: var(--primary-color); text-align: right; line-height: 1.3; }
.task-row__arrow { color: var(--text-muted); }
.exception-label { display: inline-flex; align-items: center; gap: 4px; margin-top: 7px; font-size: 12px; color: var(--error-color); }
.completed-label { margin-top: 6px; font-size: 12px; color: var(--success-color); }
.task-row--exception { background: linear-gradient(90deg, var(--error-bg), #fff 40%); }

@media (min-width: 700px) {
  .today-audit-page { max-width: 680px; margin: 0 auto; }
}
</style>
