<template>
  <div class="records-page">
    <div class="page-header">
      <div class="header-bg"></div>
      <div class="header-content">
        <div class="header-top">
          <div class="header-info">
            <h1 class="page-title">检查记录</h1>
            <p class="page-subtitle">{{ filteredRecords.length }} 条记录</p>
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
            <span class="stat-value">{{ resultCounts.pass }}</span>
            <span class="stat-label">合格</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">{{ resultCounts.partial_pass }}</span>
            <span class="stat-label">基本合格</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">{{ resultCounts.fail }}</span>
            <span class="stat-label">不合格</span>
          </div>
        </div>
      </div>
    </div>

    <div class="search-section">
      <van-search
        v-model="searchText"
        placeholder="搜索企业名称、模板..."
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
        <div class="record-list">
          <div
            v-for="record in filteredRecords"
            :key="record.id"
            class="record-card"
            @click="goToDetail(record)"
          >
            <div class="card-header">
              <div class="result-badge" :class="record.overall_result || 'pending'">
                <svg v-if="record.overall_result === 'pass'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                <svg v-else-if="record.overall_result === 'partial_pass'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="12"/>
                  <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <svg v-else-if="record.overall_result === 'fail'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="15" y1="9" x2="9" y2="15"/>
                  <line x1="9" y1="9" x2="15" y2="15"/>
                </svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <polyline points="12 6 12 12 16 14"/>
                </svg>
                {{ getResultText(record.overall_result) }}
              </div>
              <span class="record-date">{{ formatDate(record.inspection_date) }}</span>
            </div>
            
            <h3 class="record-title">{{ record.template?.name || '未知模板' }}</h3>
            
            <div class="record-meta">
              <div v-if="record.template?.is_quantified" class="meta-item" style="color: #F59E0B; font-weight: 500;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                </svg>
                <span>总分：{{ record.total_score || 0 }}</span>
              </div>
              <div class="meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                  <polyline points="9 22 9 12 15 12 15 22"/>
                </svg>
                <span>{{ record.enterprise_name || record.enterprise?.name || '未指定企业' }}</span>
              </div>
              <div class="meta-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
                <span>{{ record.inspector?.real_name || record.inspector?.username }}</span>
              </div>
            </div>
            
            <div class="card-footer">
              <div class="status-badge" :class="record.status">
                <svg v-if="record.status === 'draft'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
                <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                {{ getStatusText(record.status) }}
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="arrow-icon">
                <path d="m9 18 6-6-6-6"/>
              </svg>
            </div>
          </div>
        </div>

        <div v-if="filteredRecords.length === 0 && !loading" class="empty-state">
          <div class="empty-icon-wrapper">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
          </div>
          <p class="empty-text">暂无记录</p>
          <p class="empty-hint">完成检查后记录将显示在这里</p>
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
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getRecords } from '../api/records'

const router = useRouter()
const activeTab = ref(2)
const searchText = ref('')
const activeFilter = ref('all')
const records = ref([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const page = ref(1)
const pageSize = 10

const filterTabs = [
  { label: '全部', value: 'all' },
  { label: '草稿', value: 'draft' },
  { label: '已提交', value: 'submitted' },
]

const resultCounts = computed(() => {
  return {
    pass: records.value.filter(r => r.overall_result === 'pass').length,
    partial_pass: records.value.filter(r => r.overall_result === 'partial_pass').length,
    fail: records.value.filter(r => r.overall_result === 'fail').length,
  }
})

const filteredRecords = computed(() => {
  let result = records.value
  if (activeFilter.value !== 'all') {
    result = result.filter(r => r.status === activeFilter.value)
  }
  if (searchText.value) {
    const keyword = searchText.value.toLowerCase()
    result = result.filter(r => 
      r.template?.name?.toLowerCase().includes(keyword) ||
      r.enterprise_name?.toLowerCase().includes(keyword) ||
      r.enterprise?.name?.toLowerCase().includes(keyword)
    )
  }
  return result
})

const getStatusText = (status) => {
  const texts = {
    'draft': '草稿',
    'submitted': '已提交',
  }
  return texts[status] || status
}

const getResultText = (result) => {
  const texts = {
    'pass': '合格',
    'partial_pass': '基本合格',
    'fail': '不合格',
  }
  return texts[result] || '待判定'
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

const fetchRecords = async (isRefresh = false) => {
  try {
    const res = await getRecords({
      page: page.value,
      limit: pageSize,
    })
    
    const items = res.data?.items || []
    if (isRefresh) {
      records.value = items
    } else {
      records.value.push(...items)
    }
    
    if (items.length < pageSize) {
      finished.value = true
    }
  } catch (error) {
    console.error('获取记录失败:', error)
  }
}

const onLoad = async () => {
  await fetchRecords()
  loading.value = false
  page.value++
}

const onRefresh = async () => {
  page.value = 1
  finished.value = false
  await fetchRecords(true)
  refreshing.value = false
}

const onSearch = () => {
  page.value = 1
  finished.value = false
  records.value = []
  onLoad()
}

const clearSearch = () => {
  searchText.value = ''
  onSearch()
}

const goToDetail = (record) => {
  if (record.status === 'draft') {
    router.push(`/inspection/${record.id}`)
  } else {
    router.push(`/record/${record.id}`)
  }
}
</script>

<style scoped>
.records-page {
  min-height: 100vh;
  padding-bottom: 80px;
  background: var(--bg-light);
}

.page-header {
  position: relative;
  padding: 0 0 16px;
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
  font-size: 23px;
  font-weight: 700;
  color: var(--bg-white);
  margin: 0;
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
  margin: 0 16px;
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

.search-section {
  margin: -8px 16px 12px;
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
  padding: 0 16px 12px;
  overflow-x: auto;
  scrollbar-width: none;
}

.filter-tabs::-webkit-scrollbar {
  display: none;
}

.filter-tab {
  flex-shrink: 0;
  min-height: 44px;
  padding: 0 18px;
  border-radius: 20px;
  font-size: 13px;
  background: var(--bg-white);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-base);
  box-shadow: var(--shadow-xs);
  font-weight: 500;
  border: 1px solid var(--border-color);
  display: inline-flex;
  align-items: center;
  justify-content: center;
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

.record-list {
  padding: 0 16px;
}

.record-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all var(--transition-base);
  border: 1px solid var(--border-light);
}

.record-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
  border-color: var(--primary-light);
}

.record-card:active {
  transform: translateY(0);
  box-shadow: var(--shadow-sm);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.result-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.result-badge.pass {
  background: var(--success-bg);
  color: var(--success-color);
}

.result-badge.partial_pass {
  background: var(--warning-bg);
  color: var(--warning-color);
}

.result-badge.fail {
  background: var(--error-bg);
  color: var(--error-color);
}

.result-badge.pending {
  background: var(--info-bg);
  color: var(--info-color);
}

.record-date {
  font-size: 12px;
  color: var(--text-muted);
}

.record-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  line-height: 1.4;
  font-family: var(--font-primary);
  letter-spacing: -0.3px;
}

.record-meta {
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

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 5px 12px;
  border-radius: 20px;
  font-weight: 500;
}

.status-badge.draft {
  background: var(--bg-light);
  color: var(--text-secondary);
}

.status-badge.submitted {
  background: var(--success-bg);
  color: var(--success-color);
}

.arrow-icon {
  color: var(--text-muted);
  transition: transform var(--transition-base);
}

.record-card:hover .arrow-icon {
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
  .record-card,
  .filter-tab,
  .header-actions,
  .arrow-icon {
    transition: none;
  }
}
</style>
