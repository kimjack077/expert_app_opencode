<template>
  <main class="today-audit-page">
    <van-nav-bar title="今日审核" fixed placeholder>
      <template #right>
        <button class="nav-action" type="button" aria-label="进入全部功能" @click="router.push('/home')">
          <van-icon name="apps-o" size="22" />
        </button>
      </template>
    </van-nav-bar>

    <van-pull-refresh v-model="refreshing" @refresh="loadTasks">
      <section class="summary-panel" aria-labelledby="today-summary-title">
        <div>
          <p class="eyebrow">现场工作台</p>
          <h1 id="today-summary-title">先处理最重要的审核事项</h1>
          <p class="summary-copy">Agent 会整理证据、匹配条款并把异常自动排到前面。</p>
        </div>
        <div class="summary-metrics" aria-label="任务概览">
          <div><strong>{{ activeCount }}</strong><span>进行中</span></div>
          <div><strong>{{ pendingCount }}</strong><span>待开始</span></div>
          <div><strong>{{ completedCount }}</strong><span>已完成</span></div>
        </div>
      </section>

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
              <h3>{{ priorityTask.area_name || '审核任务' }}</h3>
              <p>{{ formatSchedule(priorityTask) }}</p>
            </div>
          </div>
          <div class="task-details">
            <span><van-icon name="friends-o" /> {{ priorityTask.group_no || '审核组待确认' }}</span>
            <span><van-icon name="records-o" /> {{ systemText(priorityTask) }}</span>
          </div>
          <van-button
            block
            type="primary"
            class="primary-action"
            :loading="openingTaskId === priorityTask.id"
            @click="openAgentSession(priorityTask)"
          >
            {{ priorityTask.status === 'pending' ? '开始 AI 现场审核' : '继续 AI 现场审核' }}
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
            :class="{ 'task-row--exception': task.exception_count > 0 }"
            @click="openAgentSession(task)"
          >
            <span class="task-row__status" :class="`status-${task.status}`" aria-hidden="true"></span>
            <span class="task-row__content">
              <strong>{{ task.area_name || '审核任务' }}</strong>
              <small>{{ formatSchedule(task) }} · {{ systemText(task) }}</small>
              <span v-if="task.exception_count > 0" class="exception-label">
                <van-icon name="warning-o" /> {{ task.exception_count }} 项异常待处理
              </span>
            </span>
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
  return String(left.time_start || '').localeCompare(String(right.time_start || ''))
}))

const priorityTask = computed(() => sortedTasks.value.find((task) => task.status !== 'completed') || sortedTasks.value[0])
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

const systemText = (task) => {
  const systems = Array.isArray(task.certification_systems) ? task.certification_systems : []
  return systems.length ? systems.join(' / ') : '体系待确认'
}

const formatSchedule = (task) => {
  const date = task.plan_date || '日期待定'
  const time = task.time_start && task.time_end ? `${task.time_start}-${task.time_end}` : '时间待定'
  return `${date} ${time}`
}

const loadTasks = async () => {
  if (!refreshing.value) loading.value = true
  try {
    const response = await getMyAuditTasks()
    tasks.value = Array.isArray(response?.data) ? response.data : []
  } catch (error) {
    showToast(error?.message || '获取今日审核任务失败，请下拉重试')
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const openAgentSession = async (task) => {
  if (!task?.project_id || openingTaskId.value) return
  openingTaskId.value = task.id
  try {
    const sessionsResponse = await listAuditSessions(task.project_id)
    const sessions = Array.isArray(sessionsResponse?.data) ? sessionsResponse.data : []
    const existing = sessions.find((session) => {
      const context = session.context_snapshot || session.context || {}
      return session.status === 'active' && String(context.plan_item_id || session.plan_item_id || '') === String(task.id)
    })

    let session = existing
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

onMounted(loadTasks)
</script>

<style scoped>
.today-audit-page {
  min-height: 100dvh;
  padding-bottom: calc(72px + env(safe-area-inset-bottom));
  background: var(--bg-light);
}

.nav-action,
.text-action,
.task-row {
  border: 0;
  font: inherit;
  cursor: pointer;
}

.nav-action {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  color: var(--primary-color);
  background: transparent;
}

.summary-panel {
  margin: 16px;
  padding: 22px 20px;
  color: #fff;
  border-radius: var(--radius-lg);
  background: var(--primary-gradient-dark);
}

.eyebrow {
  margin: 0 0 4px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--primary-color);
}

.summary-panel .eyebrow { color: rgba(255, 255, 255, 0.76); }
.summary-panel h1 { margin: 0; font-size: 22px; line-height: 1.35; }
.summary-copy { margin: 8px 0 0; font-size: 14px; color: rgba(255, 255, 255, 0.86); }

.summary-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
}

.summary-metrics div { display: flex; flex-direction: column; align-items: center; }
.summary-metrics strong { font-size: 24px; line-height: 1.2; }
.summary-metrics span { margin-top: 3px; font-size: 12px; color: rgba(255, 255, 255, 0.78); }

.priority-section,
.task-list-section { padding: 4px 16px 20px; }

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
.priority-card__top { display: flex; gap: 12px; align-items: center; }
.icon-tile { width: 48px; height: 48px; display: grid; flex: 0 0 auto; place-items: center; border-radius: 12px; color: var(--primary-color); background: var(--info-bg); }
.priority-card__title h3 { margin: 0; font-size: 17px; }
.priority-card__title p { margin: 4px 0 0; font-size: 13px; color: var(--text-secondary); }
.task-details { display: flex; flex-wrap: wrap; gap: 8px 16px; margin: 16px 0; font-size: 13px; color: var(--text-secondary); }
.task-details span { display: inline-flex; align-items: center; gap: 5px; }
.primary-action { min-height: 48px; }

.loading-card { padding: 18px; }
.task-row { width: 100%; min-height: 76px; display: flex; align-items: center; gap: 12px; padding: 14px 16px; text-align: left; color: inherit; background: #fff; border-bottom: 1px solid var(--border-light); }
.task-row:last-child { border-bottom: 0; }
.task-row:active { background: var(--bg-light); }
.task-row__status { width: 10px; height: 10px; flex: 0 0 auto; border-radius: 50%; background: var(--text-light); }
.status-in_progress { background: var(--primary-color); }
.status-pending { background: var(--warning-color); }
.status-completed { background: var(--success-color); }
.task-row__content { min-width: 0; display: flex; flex: 1; flex-direction: column; }
.task-row__content strong { font-size: 15px; }
.task-row__content small { margin-top: 3px; color: var(--text-secondary); line-height: 1.45; }
.task-row__arrow { color: var(--text-muted); }
.exception-label { display: inline-flex; align-items: center; gap: 4px; margin-top: 7px; font-size: 12px; color: var(--error-color); }
.task-row--exception { background: linear-gradient(90deg, var(--error-bg), #fff 40%); }

@media (min-width: 700px) {
  .today-audit-page { max-width: 680px; margin: 0 auto; }
}
</style>
