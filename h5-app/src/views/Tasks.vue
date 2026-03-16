<template>
  <div class="tasks-page">
    <div class="page-header">
      <div class="header-bg"></div>
      <div class="header-content">
        <div class="header-top">
          <div class="header-info">
            <h1 class="page-title">检查任务</h1>
            <p class="page-subtitle">{{ tasks.length }} 个任务</p>
          </div>
          <div class="header-actions">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 6h18"/>
              <path d="M7 12h10"/>
              <path d="M10 18h4"/>
            </svg>
          </div>
        </div>
        <div class="stats-row">
          <div class="stat-item">
            <span class="stat-value">{{ statusCounts.pending }}</span>
            <span class="stat-label">待处理</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">{{ statusCounts.in_progress }}</span>
            <span class="stat-label">进行中</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">{{ statusCounts.completed }}</span>
            <span class="stat-label">已完成</span>
          </div>
        </div>
      </div>
    </div>

    <div class="search-section">
      <van-search
        v-model="searchText"
        placeholder="搜索任务名称、地点..."
        shape="round"
        background="transparent"
        @search="onSearch"
        @clear="clearSearch"
      />
    </div>

    <div class="filter-tabs">
      <div
        v-for="tab in filterTabs"
        :key="tab.value"
        class="filter-tab"
        :class="{ active: activeFilter === tab.value }"
        @click="activeFilter = tab.value"
      >
        {{ tab.label }}
      </div>
    </div>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh" class="refresh-container">
      <van-list
        v-model:loading="loading"
        :finished="finished"
        finished-text=""
        @load="onLoad"
      >
        <div class="task-list">
          <div
            v-for="task in filteredTasks"
            :key="task.id"
            class="task-card"
            @click="goToDetail(task.id)"
          >
            <div class="card-header">
              <div class="task-status" :class="task.status">
                <svg v-if="task.status === 'pending'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <polyline points="12 6 12 12 16 14"/>
                </svg>
                <svg v-else-if="task.status === 'in_progress'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <polygon points="10 8 16 12 10 16 10 8"/>
                </svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                {{ getStatusText(task.status) }}
              </div>
              <span class="task-date">{{ formatDate(task.created_at) }}</span>
            </div>
            
            <h3 class="task-title">{{ task.title }}</h3>
            <p class="task-desc">{{ task.description || '暂无描述' }}</p>
            
            <div class="task-meta">
              <div class="meta-item" v-if="task.location">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                  <circle cx="12" cy="10" r="3"/>
                </svg>
                <span>{{ task.location }}</span>
              </div>
              <div class="meta-item" v-if="task.assignee">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
                <span>{{ task.assignee }}</span>
              </div>
            </div>
            
            <div class="card-footer">
              <div class="task-priority" :class="task.priority || 'normal'">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/>
                  <line x1="4" y1="22" x2="4" y2="15"/>
                </svg>
                {{ getPriorityText(task.priority) }}
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="arrow-icon">
                <path d="m9 18 6-6-6-6"/>
              </svg>
            </div>
          </div>
        </div>

        <div v-if="filteredTasks.length === 0 && !loading" class="empty-state">
          <div class="empty-icon-wrapper">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
              <rect x="9" y="3" width="6" height="4" rx="1"/>
              <path d="M9 12h6"/>
              <path d="M9 16h6"/>
            </svg>
          </div>
          <p class="empty-text">暂无任务</p>
          <p class="empty-hint">下拉刷新获取最新任务</p>
        </div>
      </van-list>
    </van-pull-refresh>

    <van-tabbar v-model="activeTab" route class="custom-tabbar">
      <van-tabbar-item to="/home">
        <span>首页</span>
        <template #icon="props">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
            <polyline points="9 22 9 12 15 12 15 22"/>
          </svg>
        </template>
      </van-tabbar-item>
      <van-tabbar-item to="/select-enterprise">
        <span>检查</span>
        <template #icon="props">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/>
            <path d="m21 21-4.35-4.35"/>
          </svg>
        </template>
      </van-tabbar-item>
      <van-tabbar-item to="/records">
        <span>记录</span>
        <template #icon="props">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </template>
      </van-tabbar-item>
      <van-tabbar-item to="/profile">
        <span>我的</span>
        <template #icon="props">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        </template>
      </van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getTasks } from '../api/tasks.js'

const router = useRouter()
const route = useRoute()
const activeTab = ref(0)
const searchText = ref('')
const activeFilter = ref('all')
const tasks = ref([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const page = ref(1)
const pageSize = 10

const filterTabs = [
  { label: '全部', value: 'all' },
  { label: '待处理', value: 'pending' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'completed' },
]

const statusCounts = computed(() => {
  return {
    pending: tasks.value.filter(t => t.status === 'pending').length,
    in_progress: tasks.value.filter(t => t.status === 'in_progress').length,
    completed: tasks.value.filter(t => t.status === 'completed').length,
  }
})

const filteredTasks = computed(() => {
  let result = tasks.value
  if (activeFilter.value !== 'all') {
    result = result.filter(t => t.status === activeFilter.value)
  }
  if (searchText.value) {
    const keyword = searchText.value.toLowerCase()
    result = result.filter(t => 
      t.title?.toLowerCase().includes(keyword) ||
      t.location?.toLowerCase().includes(keyword)
    )
  }
  return result
})

const getStatusText = (status) => {
  const texts = {
    'pending': '待处理',
    'in_progress': '进行中',
    'completed': '已完成',
    'cancelled': '已取消',
  }
  return texts[status] || status
}

const getPriorityText = (priority) => {
  const texts = {
    'high': '高优先级',
    'normal': '普通',
    'low': '低优先级',
  }
  return texts[priority] || '普通'
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

const fetchTasks = async (isRefresh = false) => {
  try {
    const res = await getTasks({
      page: page.value,
      page_size: pageSize,
      search: searchText.value,
    })
    
    const items = res.data?.items || []
    if (isRefresh) {
      tasks.value = items
    } else {
      tasks.value.push(...items)
    }
    
    if (items.length < pageSize) {
      finished.value = true
    }
  } catch (error) {
    console.error('获取任务失败:', error)
  }
}

const onLoad = async () => {
  await fetchTasks()
  loading.value = false
  page.value++
}

const onRefresh = async () => {
  page.value = 1
  finished.value = false
  await fetchTasks(true)
  refreshing.value = false
}

const onSearch = () => {
  page.value = 1
  finished.value = false
  tasks.value = []
  onLoad()
}

const clearSearch = () => {
  searchText.value = ''
  onSearch()
}

const goToDetail = (id) => {
  router.push(`/task/${id}`)
}

onMounted(() => {
  if (route.query.status && ['pending', 'in_progress', 'completed'].includes(route.query.status)) {
    activeFilter.value = route.query.status
  }
  fetchTasks()
})
</script>

<style scoped>
.tasks-page {
  min-height: 100vh;
  padding-bottom: 80px;
  background: var(--bg-light);
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
  align-items: flex-start;
  padding: 48px 20px 20px;
}

.header-info {
  flex: 1;
}

.page-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--bg-white);
  margin-bottom: 4px;
  font-family: var(--font-primary);
  letter-spacing: -0.5px;
}

.page-subtitle {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 400;
  letter-spacing: 0.3px;
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
  padding: 18px 16px;
  margin: 0 20px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(10px);
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--bg-white);
  font-family: var(--font-primary);
  letter-spacing: -1px;
}

.stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
  letter-spacing: 0.3px;
}

.stat-divider {
  width: 1px;
  height: 36px;
  background: rgba(255, 255, 255, 0.15);
}

.search-section {
  margin: -10px 16px 16px;
  position: relative;
  z-index: 10;
}

.search-section :deep(.van-search) {
  padding: 0;
  background: transparent;
}

.search-section :deep(.van-search__content) {
  background: var(--bg-white);
  box-shadow: var(--shadow-md);
  padding-left: 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
}

.filter-tabs {
  display: flex;
  gap: 8px;
  padding: 0 16px 16px;
  overflow-x: auto;
  scrollbar-width: none;
}

.filter-tabs::-webkit-scrollbar {
  display: none;
}

.filter-tab {
  flex-shrink: 0;
  padding: 8px 18px;
  border-radius: 20px;
  font-size: 13px;
  background: var(--bg-white);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-base);
  box-shadow: var(--shadow-xs);
  font-weight: 500;
  border: 1px solid var(--border-color);
}

.filter-tab.active {
  background: var(--primary-gradient);
  color: var(--bg-white);
  box-shadow: var(--shadow-md);
  border-color: transparent;
}

.filter-tab:hover:not(.active) {
  background: var(--bg-gray);
  border-color: var(--primary-light);
}

.refresh-container {
  min-height: 300px;
}

.task-list {
  padding: 0 16px;
}

.task-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all var(--transition-base);
  border: 1px solid var(--border-light);
}

.task-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
  border-color: var(--primary-light);
}

.task-card:active {
  transform: translateY(0);
  box-shadow: var(--shadow-sm);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-status {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.task-status.pending {
  background: var(--warning-bg);
  color: var(--warning-color);
}

.task-status.in_progress {
  background: var(--info-bg);
  color: var(--info-color);
}

.task-status.completed {
  background: var(--success-bg);
  color: var(--success-color);
}

.task-status.cancelled {
  background: var(--error-bg);
  color: var(--error-color);
}

.task-date {
  font-size: 12px;
  color: var(--text-muted);
}

.task-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  line-height: 1.4;
  font-family: var(--font-primary);
  letter-spacing: -0.3px;
}

.task-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.task-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.task-priority {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 5px 12px;
  border-radius: 20px;
  font-weight: 500;
}

.task-priority.high {
  background: var(--error-bg);
  color: var(--error-color);
}

.task-priority.normal {
  background: var(--bg-light);
  color: var(--text-secondary);
}

.task-priority.low {
  background: var(--success-bg);
  color: var(--success-color);
}

.arrow-icon {
  color: var(--text-muted);
  transition: transform var(--transition-base);
}

.task-card:hover .arrow-icon {
  transform: translateX(4px);
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-icon-wrapper {
  width: 90px;
  height: 90px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.1) 0%, rgba(56, 189, 248, 0.1) 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  color: var(--primary-color);
}

.empty-text {
  font-size: 16px;
  color: var(--text-primary);
  font-weight: 500;
  margin-bottom: 8px;
  font-family: var(--font-primary);
}

.empty-hint {
  font-size: 14px;
  color: var(--text-secondary);
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
  .task-card,
  .filter-tab,
  .header-actions,
  .arrow-icon {
    transition: none;
  }
}
</style>
