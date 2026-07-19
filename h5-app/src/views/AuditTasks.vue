<template>
  <div class="audit-tasks-page">
    <van-nav-bar title="我的审核任务" fixed placeholder />

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <van-list
        v-model:loading="loading"
        :finished="finished"
        finished-text="没有更多了"
        @load="onLoad"
      >
        <div v-if="tasks.length === 0 && !loading" class="empty-state">
          <van-empty description="暂无审核任务" />
        </div>

        <van-cell-group v-for="task in tasks" :key="task.id" class="task-card">
          <div class="task-header">
            <div class="task-title">{{ task.area_name }}</div>
            <van-tag :type="getStatusType(task.status)">
              {{ getStatusText(task.status) }}
            </van-tag>
          </div>

          <div class="task-info">
            <div class="info-row">
              <span class="label">审核日期：</span>
              <span class="value">{{ task.plan_date }}</span>
            </div>
            <div class="info-row">
              <span class="label">审核时间：</span>
              <span class="value">{{ task.time_start }} - {{ task.time_end }}</span>
            </div>
            <div class="info-row">
              <span class="label">工作组：</span>
              <span class="value">{{ task.group_no }}</span>
            </div>
            <div class="info-row">
              <span class="label">认证体系：</span>
              <div class="tags">
                <van-tag
                  v-for="sys in task.certification_systems"
                  :key="sys"
                  size="small"
                  plain
                >
                  {{ sys }}
                </van-tag>
              </div>
            </div>
          </div>

          <div class="task-actions">
            <van-button
              type="primary"
              size="small"
              :loading="openingId === task.id"
              @click="goToTask(task)"
            >
              {{ actionButtonText(task) }}
            </van-button>
          </div>
        </van-cell-group>
      </van-list>
    </van-pull-refresh>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { createAuditSession, getMyAuditTasks, listAuditSessions } from '../api/auditProjects'

const router = useRouter()
const tasks = ref([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const openingId = ref('')

const getStatusType = (status) => {
  const typeMap = {
    pending: 'default',
    in_progress: 'primary',
    completed: 'success'
  }
  return typeMap[status] || 'default'
}

const getStatusText = (status) => {
  const textMap = {
    pending: '待开始',
    in_progress: '进行中',
    completed: '已完成'
  }
  return textMap[status] || status
}

const actionButtonText = (task) => {
  if (task?.status === 'pending') return '开始审核'
  if (task?.status === 'completed') return '查看结果'
  return '继续审核'
}

const fetchTasks = async () => {
  try {
    const response = await getMyAuditTasks({ today_only: false })
    tasks.value = response.data || []
    finished.value = true
  } catch (error) {
    showToast(error.message || '获取任务列表失败')
  }
}

const onLoad = async () => {
  if (refreshing.value) {
    tasks.value = []
    refreshing.value = false
  }
  
  loading.value = true
  await fetchTasks()
  loading.value = false
}

const onRefresh = () => {
  finished.value = false
  onLoad()
}

const matchSession = (sessions, taskId, preferredStatuses) => {
  const matched = sessions.filter((session) => {
    const context = session.context_snapshot || {}
    return String(context.plan_item_id || '') === String(taskId)
  })
  for (const status of preferredStatuses) {
    const hits = matched
      .filter((s) => s.status === status)
      .sort((a, b) => String(b.completed_at || b.updated_at || b.created_at || '')
        .localeCompare(String(a.completed_at || a.updated_at || a.created_at || '')))
    if (hits[0]) return hits[0]
  }
  return matched[0] || null
}

const goToTask = async (task) => {
  if (openingId.value) return
  openingId.value = task.id
  try {
    const response = await listAuditSessions(task.project_id)
    const sessions = Array.isArray(response?.data) ? response.data : []

    // 已完成：进入只读结果页，不进现场审核录入
    if (task.status === 'completed') {
      const session = matchSession(sessions, task.id, ['completed', 'active'])
      if (!session?.id) {
        showToast('未找到该任务的审核结果')
        return
      }
      router.push({
        name: 'AuditSessionResult',
        params: { sessionId: session.id },
        query: { projectId: task.project_id, planItemId: task.id }
      })
      return
    }

    let session = matchSession(sessions, task.id, ['active'])
    if (!session) {
      const created = await createAuditSession(task.project_id, {
        title: `${task.area_name || '现场'}审核`,
        plan_item_id: task.id
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
    showToast(error.message || '进入任务失败')
  } finally {
    openingId.value = ''
  }
}

onMounted(() => {
  fetchTasks()
})
</script>

<style scoped>
.audit-tasks-page {
  min-height: 100vh;
  background-color: var(--bg-gray);
  padding-bottom: 20px;
}

.empty-state {
  padding: 60px 0;
}

.task-card {
  margin: 12px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-white);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
}

.task-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.task-info {
  padding: 12px 16px;
}

.info-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  font-size: 14px;
}

.info-row:last-child {
  margin-bottom: 0;
}

.label {
  color: var(--text-secondary);
  min-width: 80px;
}

.value {
  color: var(--text-primary);
}

.tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.task-actions {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
}
</style>
