<template>
  <div class="audit-tasks-page">
    <van-nav-bar title="我的审核任务" fixed placeholder left-arrow @click-left="router.push('/home')" />

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
              <span class="label">项目：</span>
              <span class="value">{{ task.project_title || task.project_no || '-' }}</span>
            </div>
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
                  v-for="sys in (task.certification_systems || [])"
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
              @click="handleTaskClick(task)"
            >
              {{ actionButtonText(task) }}
            </van-button>
          </div>
        </van-cell-group>
      </van-list>
    </van-pull-refresh>

    <!-- 审核模式选择面板 -->
    <van-action-sheet
      v-model:show="showModeSheet"
      :title="selectedTask ? `选择审核方式 - ${selectedTask.area_name || '现场审核'}` : '选择审核方式'"
      :actions="modeActions"
      cancel-text="取消"
      close-on-click-action
      description="建议优先采用【表格式模板检查】逐项核对并录入记录；也可使用【AI 辅助】进行拍照分析与会话问答。"
      @select="onSelectMode"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { createAuditSession, getMyAuditTasks, listAuditSessions } from '../api/auditProjects'

const router = useRouter()
const tasks = ref([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const openingId = ref('')
const showModeSheet = ref(false)
const selectedTask = ref(null)

const modeActions = [
  {
    name: '📋 表格式模板检查（推荐）',
    subname: '依据检查模板逐项采集、判定与打分，生成正式条款审核记录',
    value: 'template',
  },
  {
    name: '🤖 AI 辅助现场审核',
    subname: '现场拍照识别、多条款证据智能抽取与辅助会话',
    value: 'agent',
  },
]

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
    const context = session.context_snapshot || session.context || {}
    return String(context.plan_item_id || session.plan_item_id || '') === String(taskId)
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

const handleTaskClick = (task) => {
  if (task.status === 'completed') {
    openCompletedResult(task)
    return
  }
  selectedTask.value = task
  showModeSheet.value = true
}

const openCompletedResult = async (task) => {
  if (openingId.value) return
  openingId.value = task.id
  try {
    const response = await listAuditSessions(task.project_id)
    const sessions = Array.isArray(response?.data) ? response.data : []
    const session = matchSession(sessions, task.id, ['completed', 'active'])
    if (session?.id) {
      router.push({
        name: 'AuditSessionResult',
        params: { sessionId: session.id },
        query: { projectId: task.project_id, planItemId: task.id }
      })
      return
    }
    if (task.inspection_task_id) {
      router.push(`/inspection/${task.inspection_task_id}`)
      return
    }
    showToast('未找到该任务的审核结果')
  } catch (error) {
    showToast(error.message || '打开审核结果失败')
  } finally {
    openingId.value = ''
  }
}

const openTemplateInspection = (task) => {
  const targetId = task.inspection_task_id || task.id
  router.push(`/inspection/${targetId}`)
}

const openAgentSession = async (task) => {
  if (openingId.value) return
  openingId.value = task.id
  try {
    const response = await listAuditSessions(task.project_id)
    const sessions = Array.isArray(response?.data) ? response.data : []
    let session = matchSession(sessions, task.id, ['active'])
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
    showToast(error.message || '创建审核会话失败')
  } finally {
    openingId.value = ''
  }
}

const onSelectMode = (action) => {
  const task = selectedTask.value
  if (!task) return
  if (action.value === 'template') {
    openTemplateInspection(task)
  } else if (action.value === 'agent') {
    openAgentSession(task)
  }
}
</script>

<style scoped>
.audit-tasks-page {
  min-height: 100vh;
  background-color: #f7f8fa;
  padding-bottom: 20px;
}

.task-card {
  margin: 12px 16px;
  padding: 16px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebedf0;
}

.task-title {
  font-size: 16px;
  font-weight: bold;
  color: #323233;
}

.task-info {
  margin-bottom: 12px;
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

.info-row .label {
  color: #969799;
  width: 80px;
  flex-shrink: 0;
}

.info-row .value {
  color: #323233;
  flex: 1;
}

.tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.task-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
  border-top: 1px solid #ebedf0;
}

.empty-state {
  padding: 40px 0;
}
</style>
