<template>
  <div class="task-detail-page" :class="{ 'has-path-hint': isAuditLinkedTask }">
    <div class="page-header">
      <div class="header-nav">
        <div class="back-btn" @click="onClickLeft">
          <van-icon name="arrow-left" size="24" color="#fff" />
        </div>
        <h1 class="header-title">任务详情</h1>
        <div class="header-actions">
          <van-icon name="ellipsis" size="24" color="#fff" />
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <van-skeleton title :row="8" />
    </div>

    <div v-else-if="task" class="task-content">
      <div class="status-banner" :class="task.status">
        <div class="status-icon">
          <van-icon :name="getStatusIcon(task.status)" size="32" />
        </div>
        <div class="status-info">
          <h2 class="status-title">{{ getStatusText(task.status) }}</h2>
          <p class="status-desc">{{ getStatusDesc(task.status) }}</p>
        </div>
      </div>

      <div class="content-card">
        <h1 class="task-title">{{ task.title }}</h1>
        <p class="task-desc" :class="{ 'empty-desc': !task.description }">{{ task.description || '暂无详细描述' }}</p>

        <div class="info-section">
          <h3 class="section-title">基本信息</h3>
          <div class="info-grid">
            <div class="info-item">
              <div class="info-icon">
                <van-icon name="location-o" size="18" />
              </div>
              <div class="info-content">
                <span class="info-label">检查地点</span>
                <span class="info-value">{{ task.location || '未指定地点' }}</span>
              </div>
            </div>
            <div class="info-item">
              <div class="info-icon">
                <van-icon name="clock-o" size="18" />
              </div>
              <div class="info-content">
                <span class="info-label">创建时间</span>
                <span class="info-value">{{ formatDate(task.created_at) }}</span>
              </div>
            </div>
            <div class="info-item">
              <div class="info-icon">
                <van-icon name="user-o" size="18" />
              </div>
              <div class="info-content">
                <span class="info-label">执行人员</span>
                <span class="info-value">{{ task.assignee || '未分配' }}</span>
              </div>
            </div>
            <div class="info-item">
              <div class="info-icon">
                <van-icon name="flag-o" size="18" />
              </div>
              <div class="info-content">
                <span class="info-label">优先级</span>
                <span class="info-value" :class="task.priority">{{ getPriorityText(task.priority) }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="timeline-section">
          <h3 class="section-title">任务进度</h3>
          <div class="timeline">
            <div class="timeline-item completed">
              <div class="timeline-dot"></div>
              <div class="timeline-content">
                <span class="timeline-title">任务创建</span>
                <span class="timeline-time">{{ formatDate(task.created_at) }}</span>
              </div>
            </div>
            <div class="timeline-item" :class="{ completed: task.status !== 'pending' }">
              <div class="timeline-dot"></div>
              <div class="timeline-content">
                <span class="timeline-title">开始执行</span>
                <span class="timeline-time">{{ task.status !== 'pending' ? formatDate(task.started_at) : '待开始' }}</span>
              </div>
            </div>
            <div class="timeline-item" :class="{ completed: task.status === 'completed' }">
              <div class="timeline-dot"></div>
              <div class="timeline-content">
                <span class="timeline-title">任务完成</span>
                <span class="timeline-time">{{ task.status === 'completed' ? formatDate(task.completed_at) : '待完成' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="offline-card" :class="{ cached: !!cachedEntry }">
        <div class="offline-main">
          <div class="offline-icon">
            <van-icon :name="cachedEntry ? 'passed' : 'down'" size="18" />
          </div>
          <div class="offline-text">
            <span class="offline-title">{{ cachedEntry ? '离线可用' : '出发前缓存' }}</span>
            <span class="offline-desc">
              <template v-if="cachedEntry">
                已缓存 {{ cachedEntry.itemCount }} 个检查项 · {{ formatCachedAt(cachedEntry.cachedAt) }}
              </template>
              <template v-else>
                把检查项和企业信息存到手机，厂区没信号也能查看
              </template>
            </span>
          </div>
        </div>
        <div class="offline-actions">
          <van-button
            size="small"
            type="primary"
            plain
            round
            :loading="caching"
            :disabled="!online"
            @click="cacheForOffline"
          >
            {{ cachedEntry ? '更新缓存' : '缓存到本地' }}
          </van-button>
          <van-button v-if="cachedEntry" size="small" plain round @click="dropCache">
            清除
          </van-button>
        </div>
      </div>

      <div class="action-bar">
        <div v-if="isAuditLinkedTask" class="path-hint">
          <van-icon name="info-o" />
          <span>此任务关联认证审核项目。正式交付请走「AI 现场审核」；下方表格式检查仅作辅助填报。</span>
        </div>
        <van-button
          v-if="task.status === 'pending'"
          type="primary"
          block
          class="action-btn primary"
          @click="startTask"
        >
          <van-icon name="play-circle-o" size="20" />
          <span>开始任务</span>
        </van-button>
        <van-button
          v-if="task.status === 'in_progress' || task.status === 'pending'"
          type="primary"
          block
          class="action-btn primary"
          style="margin-top: 10px;"
          :loading="openingAiAudit"
          @click="openAiAuditSession"
        >
          <van-icon name="smile-comment-o" size="20" />
          <span>{{ isAuditLinkedTask ? '进入 AI 现场审核（推荐）' : '打开今日审核' }}</span>
        </van-button>
        <van-button
          v-if="task.status === 'in_progress'"
          type="success"
          block
          class="action-btn success"
          style="margin-top: 10px;"
          @click="goToExecution"
        >
          <van-icon name="edit" size="20" />
          <span>{{ isAuditLinkedTask ? '表格式检查（辅助）' : '执行检查' }}</span>
        </van-button>
        <van-button
          v-if="task.status === 'in_progress'"
          type="default"
          block
          class="action-btn"
          style="margin-top: 10px;"
          @click="completeTask"
        >
          <van-icon name="checked" size="20" />
          <span>完成任务</span>
        </van-button>
        <van-button
          v-if="task.status === 'pending' || task.status === 'in_progress'"
          type="danger"
          plain
          block
          class="action-btn"
          style="margin-top: 10px;"
          @click="cancelTask"
        >
          <van-icon name="close" size="20" />
          <span>取消任务</span>
        </van-button>
        <van-button
          v-if="task.status === 'completed'"
          type="primary"
          block
          class="action-btn primary"
          @click="goToExecution"
        >
          <van-icon name="records-o" size="20" />
          <span>查看检查记录</span>
        </van-button>
        <van-button
          v-if="task.status === 'completed'"
          disabled
          block
          class="action-btn disabled"
          style="margin-top: 10px;"
        >
          <van-icon name="passed" size="20" />
          <span>任务已完成</span>
        </van-button>
      </div>
    </div>

    <van-empty v-else :description="taskError || '任务不存在'" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import {
  cancelTask as cancelTaskApi,
  getTask,
  startTask as startTaskApi,
} from '../api/tasks.js'
import {
  createAuditSession,
  getMyAuditTasks,
  listAuditSessions,
} from '../api/auditProjects.js'
import {
  cacheTaskForOffline,
  formatCachedAt,
  getCachedEntry,
  isOnline,
  removeCachedEntry,
} from '@/utils/offlineCache.js'

const router = useRouter()
const route = useRoute()
const task = ref(null)
const loading = ref(true)
const taskError = ref('')
const openingAiAudit = ref(false)

// 出发前离线缓存
const cachedEntry = ref(null)
const caching = ref(false)
const online = ref(isOnline())

const syncOnline = () => {
  online.value = isOnline()
}

const refreshCachedEntry = () => {
  cachedEntry.value = getCachedEntry('task', route.params.id)
}

const cacheForOffline = async () => {
  if (caching.value) return
  caching.value = true
  try {
    await cacheTaskForOffline(route.params.id)
    refreshCachedEntry()
    showToast({ type: 'success', message: '已缓存到本地，断网也能查看检查项' })
  } catch (error) {
    console.error('缓存到本地失败:', error)
    showToast({ type: 'fail', message: error?.message || '缓存失败，请检查网络' })
  } finally {
    caching.value = false
  }
}

const dropCache = async () => {
  try {
    await showConfirmDialog({
      title: '清除离线缓存',
      message: '清除后断网将无法查看这份检查表，确定继续吗？',
    })
    removeCachedEntry('task', route.params.id)
    refreshCachedEntry()
    showToast('已清除本地缓存')
  } catch (error) {
    if (error?.message !== 'cancel' && error !== 'cancel') {
      console.error('清除缓存失败:', error)
    }
  }
}

const getStatusIcon = (status) => {
  const icons = {
    'pending': 'clock-o',
    'in_progress': 'play-circle-o',
    'completed': 'checked',
    'cancelled': 'close',
  }
  return icons[status] || 'circle-o'
}

const getStatusText = (status) => {
  const texts = {
    'pending': '待处理',
    'in_progress': '进行中',
    'completed': '已完成',
    'cancelled': '已取消',
  }
  return texts[status] || status
}

const getStatusDesc = (status) => {
  const descs = {
    'pending': '等待开始执行',
    'in_progress': '正在执行中',
    'completed': '任务已成功完成',
    'cancelled': '任务已取消',
  }
  return descs[status] || ''
}

const getPriorityText = (priority) => {
  const texts = {
    'high': '高',
    'normal': '普通',
    'low': '低',
  }
  return texts[priority] || '普通'
}

const formatDate = (dateStr) => {
  if (!dateStr) return '暂无'
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

/** 用本地缓存渲染任务详情，成功返回 true */
const loadTaskFromCache = (taskId) => {
  const cached = getCachedEntry('task', taskId)
  if (!cached?.payload?.task) return false
  task.value = cached.payload.task
  cachedEntry.value = cached
  showToast('离线模式：显示本地缓存的任务')
  return true
}

const fetchTask = async () => {
  const taskId = route.params.id
  taskError.value = ''
  console.log('获取任务详情, ID:', taskId)
  
  if (!taskId || taskId === 'undefined' || taskId === 'null') {
    console.error('任务ID无效:', taskId)
    showToast({ type: 'fail', message: '任务ID无效' })
    taskError.value = '任务ID无效'
    loading.value = false
    return
  }
  
  // 断网时直接用出发前缓存，别让审核员卡在空白页
  if (!isOnline() && loadTaskFromCache(taskId)) {
    loading.value = false
    return
  }

  try {
    const res = await getTask(taskId)
    console.log('任务详情响应:', res)
    if (res.code === 200) {
      // BUG-32：后端现返回 assigned_to_name（指派人姓名），映射到展示字段
      task.value = { ...res.data, assignee: res.data.assigned_to_name || res.data.assignee || '' }
    } else {
      taskError.value = res.message || '获取任务失败'
      showToast({ type: 'fail', message: res.message || '获取任务失败' })
    }
  } catch (error) {
    console.error('获取任务详情失败:', error)
    if (loadTaskFromCache(taskId)) {
      return
    }
    const errorMsg = error.response?.data?.detail || error.response?.data?.message || '获取任务详情失败'
    taskError.value = errorMsg
    showToast({ type: 'fail', message: errorMsg })
  } finally {
    loading.value = false
  }
}

const onClickLeft = () => {
  router.back()
}

const startTask = async () => {
  try {
    await showConfirmDialog({
      title: '确认开始',
      message: '确定要开始这个任务吗？',
    })
    const res = await startTaskApi(task.value.id)
    console.log('开始任务响应:', res)
    if (res.code === 200) {
      showToast({ type: 'success', message: '任务已开始' })
      fetchTask()
    } else {
      showToast({ type: 'fail', message: res.message || '操作失败' })
    }
  } catch (error) {
    if (error?.message !== 'cancel' && error !== 'cancel') {
      console.error('开始任务失败:', error)
      const errorMsg = error.response?.data?.detail || error.response?.data?.message || '开始任务失败'
      showToast({ type: 'fail', message: errorMsg })
    }
  }
}

/**
 * 完成任务需要填写「最终判定结论」，统一到执行页完成。
 * 直接在这里完成任务会落库一条没有结论的记录（后端已拦截），
 * 所以这里改为引导用户进入执行页填写结论后提交。
 */
const completeTask = async () => {
  try {
    await showConfirmDialog({
      title: '去填写最终判定',
      message: '完成任务前需要填写「最终判定结论」，将跳转到执行页，请在页面底部选择结论后提交。',
      confirmButtonText: '去填写',
    })
    router.push(`/task/${task.value.id}/execute`)
  } catch (error) {
    if (error?.message !== 'cancel' && error !== 'cancel') {
      console.error('跳转执行页失败:', error)
    }
  }
}

const cancelTask = async () => {
  try {
    await showConfirmDialog({
      title: '确认取消',
      message: '取消后该任务将停止流转，确定继续吗？',
      confirmButtonText: '确认取消',
      confirmButtonColor: '#ee0a24',
    })
    const res = await cancelTaskApi(task.value.id)
    if (res.code === 200) {
      showToast({ type: 'success', message: '任务已取消' })
      await fetchTask()
    } else {
      showToast({ type: 'fail', message: res.message || '取消失败' })
    }
  } catch (error) {
    if (error?.message !== 'cancel' && error !== 'cancel') {
      showToast({ type: 'fail', message: error.response?.data?.detail || '取消失败' })
    }
  }
}

const goToExecution = () => {
  router.push(`/task/${task.value.id}/execute`)
}

/** 标题含项目/计划特征时，视为认证审核关联任务 */
const isAuditLinkedTask = computed(() => {
  const t = task.value
  if (!t) return false
  const title = String(t.title || '')
  return /审核|初审|监督|再认证|车间|部门/.test(title) || !!t.audit_project_id
})

const openAiAuditSession = async () => {
  if (openingAiAudit.value) return

  let projectId = task.value?.audit_project_id
  let planItemId = task.value?.plan_item_id
  let areaName = task.value?.area_name || task.value?.target_name
  let clauses = task.value?.clauses

  openingAiAudit.value = true
  try {
    // 1. 若任务详情未直接返回 project_id/plan_item_id，尝试从分配任务列表中匹配
    if (!projectId || !planItemId) {
      try {
        const myTasksRes = await getMyAuditTasks({ today_only: false })
        const items = Array.isArray(myTasksRes?.data) ? myTasksRes.data : []
        const matched = items.find(
          (item) =>
            String(item.inspection_task_id) === String(task.value?.id) ||
            String(item.id) === String(task.value?.id)
        )
        if (matched) {
          projectId = matched.project_id
          planItemId = matched.id
          areaName = matched.area_name || areaName
          clauses = matched.clauses || clauses
        }
      } catch (err) {
        console.warn('查询我的审核任务匹配失败:', err)
      }
    }

    // 2. 匹配到审核项目与计划项，直接进入或创建 AI 现场审核会话
    if (projectId && planItemId) {
      const sessionsResponse = await listAuditSessions(projectId)
      const sessions = Array.isArray(sessionsResponse?.data) ? sessionsResponse.data : []
      let session = sessions.find(
        (s) => String(s.plan_item_id) === String(planItemId) && s.status === 'active'
      )

      if (!session) {
        const created = await createAuditSession(projectId, {
          title: `${areaName || '现场'}审核`,
          plan_item_id: planItemId,
          focus: Array.isArray(clauses) ? clauses.join('、') : '',
        })
        session = created?.data
      }

      if (session?.id) {
        // 如果处于未开始状态，自动触发开始
        if (task.value?.status === 'pending') {
          try {
            await startTaskApi(task.value.id)
          } catch (e) {
            console.warn('自动开始任务提示:', e)
          }
        }

        router.push({
          name: 'AiAuditSession',
          params: { sessionId: session.id },
          query: { projectId, planItemId },
        })
        return
      }
    }

    // 3. 兜底方案：无法关联具体项目计划项时跳转今日审核
    router.push('/today-audit')
  } catch (error) {
    console.error('进入 AI 现场审核失败:', error)
    showToast(error?.message || '进入 AI 现场审核失败，请重试')
  } finally {
    openingAiAudit.value = false
  }
}

onMounted(() => {
  fetchTask()
  refreshCachedEntry()
  window.addEventListener('online', syncOnline)
  window.addEventListener('offline', syncOnline)
})

onUnmounted(() => {
  window.removeEventListener('online', syncOnline)
  window.removeEventListener('offline', syncOnline)
})
</script>

<style scoped>
.task-detail-page {
  min-height: 100vh;
  background: var(--bg-light);
  /* 给固定底栏留出空间。底栏高度不是定值：关联认证审核项目时会多渲染一条
     .path-hint 提示（约 67px），若仍用固定的 100px，页面底部内容会被压住。
     因此按是否含提示条分别留白，并叠加安全区。 */
  padding-bottom: calc(108px + env(safe-area-inset-bottom));
}

.task-detail-page.has-path-hint {
  padding-bottom: calc(184px + env(safe-area-inset-bottom));
}

.page-header {
  background: var(--primary-gradient-dark);
  padding: calc(env(safe-area-inset-top) + 18px) 16px 12px;
  position: relative;
  overflow: hidden;
}

.page-header::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: radial-gradient(circle at 20% 80%, rgba(14, 165, 233, 0.2) 0%, transparent 50%);
  pointer-events: none;
}

.header-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
  z-index: 1;
}

.back-btn {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.header-actions {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-container {
  padding: 20px;
}

.task-content {
  margin-top: -20px;
  position: relative;
  z-index: 2;
}

.status-banner {
  margin: 0 20px 16px;
  padding: 24px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  color: #fff;
}

.status-banner.pending {
  background: linear-gradient(135deg, #FF9800 0%, #F57C00 100%);
}

.status-banner.in_progress {
  background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
}

.status-banner.completed {
  background: linear-gradient(135deg, #4CAF50 0%, #388E3C 100%);
}

.status-banner.cancelled {
  background: linear-gradient(135deg, #F44336 0%, #D32F2F 100%);
}

.status-icon {
  width: 56px;
  height: 56px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-title {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 4px;
}

.status-desc {
  font-size: 14px;
  opacity: 0.9;
}

.content-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  margin: 0 20px;
  padding: 24px;
  box-shadow: var(--shadow-md);
}

.task-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
  line-height: 1.4;
}

.task-desc {
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border-light);
}

.task-desc.empty-desc {
  color: #94a3b8;
  font-style: italic;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
}

.info-section {
  margin-bottom: 24px;
}

.info-grid {
  display: grid;
  gap: 16px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.info-icon {
  width: 44px;
  height: 44px;
  background: var(--bg-light);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-color);
}

.info-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-label {
  font-size: 13px;
  color: var(--text-muted);
}

.info-value {
  font-size: 15px;
  color: var(--text-primary);
  font-weight: 500;
}

.info-value.high {
  color: #D32F2F;
}

.info-value.normal {
  color: #666;
}

.info-value.low {
  color: #388E3C;
}

.timeline-section {
  padding-top: 24px;
  border-top: 1px solid var(--border-light);
}

.timeline {
  position: relative;
  padding-left: 24px;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 7px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--border-light);
}

.timeline-item {
  position: relative;
  padding-bottom: 24px;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-dot {
  position: absolute;
  left: -24px;
  top: 4px;
  width: 16px;
  height: 16px;
  background: var(--text-muted);
  border-radius: 50%;
  border: 3px solid var(--bg-white);
  box-shadow: 0 0 0 2px var(--text-muted);
}

.timeline-item.completed .timeline-dot {
  background: #4CAF50;
  box-shadow: 0 0 0 2px #4CAF50;
}

.timeline-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.timeline-title {
  font-size: 15px;
  color: var(--text-secondary);
}

.timeline-item.completed .timeline-title {
  color: var(--text-primary);
  font-weight: 500;
}

.timeline-time {
  font-size: 13px;
  color: var(--text-muted);
}

.offline-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 16px 20px 0;
  padding: 14px 16px;
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  border-left: 4px solid #0ea5e9;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.offline-card.cached {
  border-left-color: #16a34a;
}

.offline-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.offline-icon {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e0f2fe;
  color: #0369a1;
}

.offline-card.cached .offline-icon {
  background: #dcfce7;
  color: #15803d;
}

.offline-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.offline-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.offline-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.45;
}

.offline-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.action-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 16px 20px 24px;
  background: var(--bg-white);
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.08);
}

.path-hint {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 12px;
  color: #0369a1;
  background: #e0f2fe;
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 12px;
  line-height: 1.45;
}

.action-btn {
  height: 52px;
  border-radius: 14px;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: none;
}

.action-btn.primary {
  background: var(--primary-gradient);
  border: none;
  box-shadow: var(--shadow-primary);
}

.action-btn.success {
  background: linear-gradient(135deg, #4CAF50 0%, #66BB6A 100%);
  color: #fff;
  box-shadow: 0 4px 16px rgba(76, 175, 80, 0.4);
}

.action-btn.disabled {
  background: var(--bg-gray);
  color: var(--text-muted);
}

:deep(.van-dialog__confirm) {
  color: var(--primary-color);
}
</style>
