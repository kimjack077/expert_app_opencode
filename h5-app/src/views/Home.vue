<template>
  <div class="home-page">
    <div class="page-header">
      <div class="header-bg"></div>
      <div class="header-content">
        <div class="header-top">
          <div class="user-greeting">
            <span class="greeting-text">欢迎回来</span>
            <h1 class="user-name">{{ userName || '检查员' }}</h1>
          </div>
          <div class="header-actions" @click="goToProfile">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
          </div>
        </div>
        <div class="stats-row">
          <div class="stat-item">
            <span class="stat-value">{{ stats.pending }}</span>
            <span class="stat-label">待处理</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">{{ stats.inProgress }}</span>
            <span class="stat-label">进行中</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">{{ stats.completed }}</span>
            <span class="stat-label">已完成</span>
          </div>
        </div>
      </div>
    </div>

    <div class="content-section">
      <!-- 主路径：正式认证审核 -->
      <div class="quick-action-card primary-cta" @click="goToTodayAudit">
        <div class="action-icon-wrapper">
          <van-icon name="todo-list-o" size="26" color="#fff" />
        </div>
        <div class="action-content">
          <h3 class="action-title">继续今日审核</h3>
          <p class="action-desc">正式认证现场：证据采集 · AI 多条款 · 确认提交</p>
        </div>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="action-arrow">
          <path d="m9 18 6-6-6-6"/>
        </svg>
      </div>

      <!-- 次要：日常检查 -->
      <div class="quick-action-card secondary-cta" @click="startNewInspection">
        <div class="action-icon-wrapper muted">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 5v14"/>
            <path d="M5 12h14"/>
          </svg>
        </div>
        <div class="action-content">
          <h3 class="action-title">日常检查（可选）</h3>
          <p class="action-desc">非认证项目时：选企业 + 模板填表检查</p>
        </div>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="action-arrow">
          <path d="m9 18 6-6-6-6"/>
        </svg>
      </div>

      <div class="task-shortcuts">
        <div class="shortcut-card" @click="goToTasksWithStatus('pending')">
          <div class="shortcut-icon orange">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
          </div>
          <span class="shortcut-label">待处理</span>
          <span v-if="stats.pending > 0" class="shortcut-badge">{{ stats.pending }}</span>
        </div>
        <div class="shortcut-card" @click="goToTasksWithStatus('in_progress')">
          <div class="shortcut-icon blue">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <polygon points="10 8 16 12 10 16 10 8"/>
            </svg>
          </div>
          <span class="shortcut-label">进行中</span>
          <span v-if="stats.inProgress > 0" class="shortcut-badge blue">{{ stats.inProgress }}</span>
        </div>
        <div class="shortcut-card" @click="goToTasksWithStatus('completed')">
          <div class="shortcut-icon green">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
          </div>
          <span class="shortcut-label">已完成</span>
          <span v-if="stats.completed > 0" class="shortcut-badge green">{{ stats.completed }}</span>
        </div>
        <div class="shortcut-card" @click="goToTasks">
          <div class="shortcut-icon purple">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
              <rect x="9" y="3" width="6" height="4" rx="1"/>
            </svg>
          </div>
          <span class="shortcut-label">全部任务</span>
          <span v-if="totalTasks > 0" class="shortcut-badge purple">{{ totalTasks }}</span>
        </div>
      </div>

      <div class="menu-card">
        <div class="section-header">
          <h3 class="menu-title">最近检查记录</h3>
          <span class="view-more" @click="goToRecords">
            更多
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          </span>
        </div>
        <div v-if="recordsLoading" class="loading-wrapper">
          <van-loading size="24" />
        </div>
        <div v-else-if="recentRecords.length === 0" class="empty-wrapper">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="empty-icon">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
          <p class="empty-text">暂无检查记录</p>
          <van-button type="primary" size="small" @click="startNewInspection">
            发起检查
          </van-button>
        </div>
        <div v-else class="menu-list">
          <div
            v-for="record in recentRecords"
            :key="record.id"
            class="menu-item"
            @click="goToRecord(record.id)"
          >
            <div class="menu-icon" :class="getResultClass(record.overall_result)">
              <svg v-if="record.overall_result === 'pass'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
              <svg v-else-if="record.overall_result === 'fail'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="m15 9-6 6"/>
                <path d="m9 9 6 6"/>
              </svg>
              <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                <path d="M12 17h.01"/>
              </svg>
            </div>
            <div class="menu-content">
              <span class="menu-label">{{ record.template?.name || '检查记录' }}</span>
              <span class="menu-desc">{{ record.enterprise_name || '手动输入' }}</span>
            </div>
            <div class="menu-meta">
              <van-tag :type="getStatusType(record.status)" size="small">
                {{ getStatusText(record.status) }}
              </van-tag>
              <span class="menu-date">{{ formatDate(record.inspection_date) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <BottomNav />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getRecords } from '../api/records'
import { getTasks } from '../api/tasks'
import BottomNav from '../components/BottomNav.vue'

const router = useRouter()
const userName = ref(localStorage.getItem('userName') || '')

const tasksLoading = ref(false)
const recentTasks = ref([])
const recordsLoading = ref(false)
const recentRecords = ref([])

const stats = computed(() => {
  return {
    pending: recentTasks.value.filter(t => t.status === 'pending').length,
    inProgress: recentTasks.value.filter(t => t.status === 'in_progress').length,
    completed: recentTasks.value.filter(t => t.status === 'completed').length,
  }
})

const totalTasks = computed(() => {
  return recentTasks.value.length
})

const fetchTasks = async () => {
  tasksLoading.value = true
  try {
    const res = await getTasks({ limit: 5 })
    recentTasks.value = res.data?.items || res.data || []
  } catch (error) {
    console.error('获取任务失败:', error)
  } finally {
    tasksLoading.value = false
  }
}

const fetchRecords = async () => {
  recordsLoading.value = true
  try {
    const res = await getRecords({ limit: 5 })
    recentRecords.value = res.data?.items || []
  } catch (error) {
    console.error('获取记录失败:', error)
  } finally {
    recordsLoading.value = false
  }
}

const fetchAllData = async () => {
  try {
    await Promise.all([
      fetchTasks(),
      fetchRecords()
    ])
  } catch (error) {
    console.error('加载数据失败:', error)
  }
}

const goToTodayAudit = () => {
  router.push('/today-audit')
}

const startNewInspection = () => {
  router.push('/select-enterprise')
}

const goToTask = (id) => {
  router.push(`/task/${id}`)
}

const goToTasks = () => {
  router.push('/tasks')
}

const goToTasksWithStatus = (status) => {
  router.push({ path: '/tasks', query: { status } })
}

const goToRecord = (id) => {
  router.push(`/inspection/${id}`)
}

const goToRecords = () => {
  router.push('/records')
}

const goToProfile = () => {
  router.push('/profile')
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const day = date.getDate().toString().padStart(2, '0')
  return `${month}-${day}`
}

const getTaskStatusClass = (status) => {
  const classMap = {
    pending: 'orange',
    in_progress: 'blue',
    completed: 'green',
  }
  return classMap[status] || 'gray'
}

const getStatusType = (status) => {
  const typeMap = {
    draft: 'default',
    submitted: 'success',
  }
  return typeMap[status] || 'default'
}

const getStatusText = (status) => {
  const textMap = {
    draft: '草稿',
    submitted: '已提交',
  }
  return textMap[status] || status
}

const getResultClass = (result) => {
  const classMap = {
    pass: 'green',
    fail: 'red',
    pending: 'orange',
  }
  return classMap[result] || 'gray'
}

onMounted(() => {
  setTimeout(() => {
    fetchAllData()
  }, 100)
})
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  padding-bottom: 80px;
  background: var(--bg-light);
}

.page-header {
  position: relative;
  padding: calc(env(safe-area-inset-top) + 18px) 16px 16px;
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
  background: 
    radial-gradient(circle at 10% 20%, rgba(255, 255, 255, 0.1) 0%, transparent 40%),
    radial-gradient(circle at 90% 80%, rgba(56, 189, 248, 0.15) 0%, transparent 40%);
}

.header-content {
  position: relative;
  z-index: 1;
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.user-greeting {
  color: var(--bg-white);
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.greeting-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  display: inline;
  margin: 0;
  font-weight: 400;
  letter-spacing: 0.3px;
}

.user-name {
  margin: 0;
  font-size: 23px;
  font-weight: 700;
  color: var(--bg-white);
  font-family: var(--font-primary);
  letter-spacing: -0.5px;
  line-height: 1.25;
}

.header-actions {
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(10px);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-base);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.header-actions svg {
  color: var(--bg-white);
}

.header-actions:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: scale(1.02);
}

.stats-row {
  display: flex;
  justify-content: space-around;
  align-items: center;
  min-height: 44px;
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
  letter-spacing: 0.3px;
}

.stat-divider {
  width: 1px;
  height: 22px;
  background: rgba(255, 255, 255, 0.15);
}

.content-section {
  padding: 12px 20px 20px;
  margin-top: 0;
}

.quick-action-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
  cursor: pointer;
  transition: all var(--transition-base);
  box-shadow: var(--shadow-md);
  border: 1px solid var(--border-light);
}

.quick-action-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
  border-color: var(--primary-light);
}

.quick-action-card:active {
  transform: translateY(0);
}

.action-icon-wrapper {
  width: 56px;
  height: 56px;
  background: var(--primary-gradient);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: var(--shadow-primary);
}

.action-icon-wrapper.muted {
  background: linear-gradient(135deg, #94a3b8 0%, #64748b 100%);
  box-shadow: none;
}

.action-icon-wrapper svg {
  color: var(--bg-white);
}

.quick-action-card.secondary-cta {
  opacity: 0.95;
  margin-bottom: 12px;
}

.quick-action-card.primary-cta {
  border-color: rgba(3, 105, 161, 0.25);
}

.action-content {
  flex: 1;
}

.action-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
  font-family: var(--font-primary);
  letter-spacing: -0.3px;
}

.action-desc {
  font-size: 13px;
  color: var(--text-secondary);
}

.action-arrow {
  color: var(--text-muted);
  transition: transform var(--transition-base);
}

.quick-action-card:hover .action-arrow {
  transform: translateX(4px);
  color: var(--primary-color);
}

.task-shortcuts {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.shortcut-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all var(--transition-base);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
  position: relative;
}

.shortcut-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.shortcut-card:active {
  transform: translateY(0);
}

.shortcut-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.shortcut-icon.orange {
  background: var(--warning-bg);
  color: var(--warning-color);
}

.shortcut-icon.blue {
  background: var(--info-bg);
  color: var(--info-color);
}

.shortcut-icon.green {
  background: var(--success-bg);
  color: var(--success-color);
}

.shortcut-icon.purple {
  background: rgba(156, 39, 176, 0.1);
  color: #9C27B0;
}

.shortcut-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.shortcut-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  background: var(--warning-color);
  color: var(--bg-white);
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.shortcut-badge.blue {
  background: var(--info-color);
}

.shortcut-badge.green {
  background: var(--success-color);
}

.shortcut-badge.purple {
  background: #9C27B0;
}

.menu-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.menu-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-primary);
  letter-spacing: -0.2px;
}

.view-more {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--primary-color);
  cursor: pointer;
  font-weight: 500;
  transition: opacity var(--transition-base);
}

.view-more:hover {
  opacity: 0.8;
}

.loading-wrapper {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.empty-wrapper {
  text-align: center;
  padding: 32px 16px;
}

.empty-icon {
  color: var(--text-muted);
  margin-bottom: 12px;
}

.empty-text {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.menu-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-base);
}

.menu-item:hover {
  background: var(--bg-light);
}

.menu-item:active {
  background: var(--bg-gray);
}

.menu-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.menu-icon.blue {
  background: var(--info-bg);
  color: var(--info-color);
}

.menu-icon.green {
  background: var(--success-bg);
  color: var(--success-color);
}

.menu-icon.orange {
  background: var(--warning-bg);
  color: var(--warning-color);
}

.menu-icon.red {
  background: var(--error-bg);
  color: var(--error-color);
}

.menu-icon.gray {
  background: rgba(148, 163, 184, 0.1);
  color: var(--text-muted);
}

.menu-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.menu-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.menu-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

.menu-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.menu-date {
  font-size: 11px;
  color: var(--text-muted);
}

.menu-arrow {
  color: var(--text-muted);
}

.view-all-btn {
  margin-top: 12px;
}

.view-all-btn :deep(.van-button) {
  border-radius: var(--radius-md);
}

.custom-tabbar {
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.04);
  border-top: 1px solid var(--border-light);
}

:deep(.van-tabbar-item--active) {
  color: var(--primary-color);
}

:deep(.van-tabbar-item__icon) {
  font-size: 22px;
}

@media (prefers-reduced-motion: reduce) {
  .quick-action-card,
  .menu-item,
  .header-actions,
  .action-arrow {
    transition: none;
  }
}
</style>
