<template>
  <div class="statistics-page">
    <van-nav-bar
      title="数据统计"
      left-arrow
      @click-left="goBack"
      class="custom-nav"
    />

    <div class="content-section">
      <div class="stats-overview">
        <div class="stats-card primary">
          <div class="stats-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 11l3 3L22 4"/>
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
            </svg>
          </div>
          <div class="stats-info">
            <span class="stats-value">{{ stats.totalTasks }}</span>
            <span class="stats-label">总任务数</span>
          </div>
        </div>
        
        <div class="stats-row">
          <div class="stats-card">
            <div class="stats-icon orange">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
              </svg>
            </div>
            <div class="stats-info">
              <span class="stats-value">{{ stats.pending }}</span>
              <span class="stats-label">待处理</span>
            </div>
          </div>
          
          <div class="stats-card">
            <div class="stats-icon blue">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <polygon points="10 8 16 12 10 16 10 8"/>
              </svg>
            </div>
            <div class="stats-info">
              <span class="stats-value">{{ stats.inProgress }}</span>
              <span class="stats-label">进行中</span>
            </div>
          </div>
        </div>
        
        <div class="stats-row">
          <div class="stats-card">
            <div class="stats-icon green">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
            </div>
            <div class="stats-info">
              <span class="stats-value">{{ stats.completed }}</span>
              <span class="stats-label">已完成</span>
            </div>
          </div>
          
          <div class="stats-card">
            <div class="stats-icon purple">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <div class="stats-info">
              <span class="stats-value">{{ stats.totalRecords }}</span>
              <span class="stats-label">检查记录</span>
            </div>
          </div>
        </div>
      </div>

      <div class="chart-section">
        <div class="chart-card">
          <h3 class="chart-title">任务完成率</h3>
          <div class="progress-wrapper">
            <van-progress 
              :percentage="completionRate" 
              stroke-width="12"
              color="linear-gradient(to right, #F97316, #EA580C)"
              track-color="#F3F4F6"
            />
            <span class="progress-text">{{ completionRate }}%</span>
          </div>
        </div>
      </div>

      <div class="chart-section">
        <div class="chart-card">
          <h3 class="chart-title">检查结果分布</h3>
          <div class="result-distribution">
            <div class="result-item">
              <div class="result-bar">
                <div class="result-fill pass" :style="{ width: passRate + '%' }"></div>
              </div>
              <div class="result-info">
                <span class="result-label">合格</span>
                <span class="result-value">{{ resultStats.pass }} ({{ passRate }}%)</span>
              </div>
            </div>
            <div class="result-item">
              <div class="result-bar">
                <div class="result-fill partial_pass" :style="{ width: partialPassRate + '%' }"></div>
              </div>
              <div class="result-info">
                <span class="result-label">基本合格</span>
                <span class="result-value">{{ resultStats.partial_pass }} ({{ partialPassRate }}%)</span>
              </div>
            </div>
            <div class="result-item">
              <div class="result-bar">
                <div class="result-fill fail" :style="{ width: failRate + '%' }"></div>
              </div>
              <div class="result-info">
                <span class="result-label">不合格</span>
                <span class="result-value">{{ resultStats.fail }} ({{ failRate }}%)</span>
              </div>
            </div>
            <div class="result-item">
              <div class="result-bar">
                <div class="result-fill pending" :style="{ width: pendingRate + '%' }"></div>
              </div>
              <div class="result-info">
                <span class="result-label">待判定</span>
                <span class="result-value">{{ resultStats.pending }} ({{ pendingRate }}%)</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="chart-section">
        <div class="chart-card">
          <h3 class="chart-title">最近7天活动</h3>
          <div v-if="recentActivity.length === 0" class="empty-activity">
            <span>暂无活动数据</span>
          </div>
          <div v-else class="activity-list">
            <div v-for="(activity, index) in recentActivity" :key="index" class="activity-item">
              <div class="activity-date">{{ activity.date }}</div>
              <div class="activity-counts">
                <span class="count-item">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  </svg>
                  {{ activity.records }} 条记录
                </span>
                <span class="count-item">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                  </svg>
                  {{ activity.completed }} 个完成
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getTaskStatistics } from '../api/tasks'
import { getRecordStatistics } from '../api/records'

const router = useRouter()

const stats = ref({
  totalTasks: 0,
  pending: 0,
  inProgress: 0,
  completed: 0,
  totalRecords: 0
})

const resultStats = ref({
  pass: 0,
  partial_pass: 0,
  fail: 0,
  pending: 0
})

const recentActivity = ref([])

const completionRate = computed(() => {
  if (stats.value.totalTasks === 0) return 0
  return Math.round((stats.value.completed / stats.value.totalTasks) * 100)
})

// 记录总体结论只有 pass / partial_pass / fail / 待判定（null）四种，
// 分母必须含 partial_pass，否则「基本合格」记录被漏算、百分比之和不足 100%。
const resultTotal = computed(() => {
  const r = resultStats.value
  return r.pass + r.partial_pass + r.fail + r.pending
})

const passRate = computed(() => {
  if (resultTotal.value === 0) return 0
  return Math.round((resultStats.value.pass / resultTotal.value) * 100)
})

const partialPassRate = computed(() => {
  if (resultTotal.value === 0) return 0
  return Math.round((resultStats.value.partial_pass / resultTotal.value) * 100)
})

const failRate = computed(() => {
  if (resultTotal.value === 0) return 0
  return Math.round((resultStats.value.fail / resultTotal.value) * 100)
})

const pendingRate = computed(() => {
  if (resultTotal.value === 0) return 0
  return Math.round((resultStats.value.pending / resultTotal.value) * 100)
})

const fetchData = async () => {
  try {
    const [statsRes, recordsRes] = await Promise.all([
      getTaskStatistics(),
      getRecordStatistics()
    ])

    const td = statsRes?.data || {}
    const rd = recordsRes?.data || {}

    // 任务汇总走后端全量口径；记录总数取后端 total，避免被分页截断
    stats.value = {
      totalTasks: td.total ?? 0,
      pending: td.pending ?? 0,
      inProgress: td.in_progress ?? 0,
      completed: td.completed ?? 0,
      totalRecords: rd.total ?? 0
    }

    resultStats.value = rd.results || { pass: 0, partial_pass: 0, fail: 0, pending: 0 }
    const activity = new Map()
    for (const entry of [...(rd.recent_activity || []), ...(td.recent_activity || [])]) {
      activity.set(entry.date, { ...activity.get(entry.date), ...entry })
    }
    recentActivity.value = [...activity.entries()].sort(([a], [b]) => a.localeCompare(b))
      .map(([date, entry]) => ({
        date: `${Number(date.slice(5, 7))}/${Number(date.slice(8, 10))}`,
        records: entry.records || 0,
        completed: entry.completed || 0
      }))
  } catch (error) {
    console.error('获取统计数据失败:', error)
  }
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.statistics-page {
  min-height: 100vh;
  background: var(--bg-light);
  padding-bottom: 20px;
}

.custom-nav {
  background: var(--bg-white);
  border-bottom: 1px solid var(--border-light);
}

.custom-nav :deep(.van-nav-bar__title) {
  font-weight: 600;
  color: var(--text-primary);
}

.content-section {
  padding: 16px;
}

.stats-overview {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.stats-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

.stats-card.primary {
  background: var(--primary-gradient-dark);
}

.stats-card.primary .stats-icon {
  background: rgba(255, 255, 255, 0.2);
  color: var(--bg-white);
}

.stats-card.primary .stats-value {
  color: var(--bg-white);
}

.stats-card.primary .stats-label {
  color: rgba(255, 255, 255, 0.8);
}

.stats-row {
  display: flex;
  gap: 12px;
}

.stats-row .stats-card {
  flex: 1;
  padding: 16px;
}

.stats-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stats-icon.orange {
  background: var(--warning-bg);
  color: var(--warning-color);
}

.stats-icon.blue {
  background: var(--info-bg);
  color: var(--info-color);
}

.stats-icon.green {
  background: var(--success-bg);
  color: var(--success-color);
}

.stats-icon.purple {
  background: rgba(156, 39, 176, 0.1);
  color: #9C27B0;
}

.stats-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stats-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  font-family: var(--font-primary);
}

.stats-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.chart-section {
  margin-bottom: 16px;
}

.chart-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

.chart-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
}

.progress-wrapper {
  display: flex;
  align-items: center;
  gap: 16px;
}

.progress-wrapper :deep(.van-progress) {
  flex: 1;
}

.progress-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--accent-color);
  min-width: 50px;
  text-align: right;
}

.result-distribution {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-bar {
  height: 8px;
  background: var(--bg-light);
  border-radius: 4px;
  overflow: hidden;
}

.result-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.result-fill.pass {
  background: var(--success-color);
}

.result-fill.partial_pass {
  background: var(--info-color);
}

.result-fill.fail {
  background: var(--error-color);
}

.result-fill.pending {
  background: var(--warning-color);
}

.result-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.result-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.empty-activity {
  text-align: center;
  padding: 24px;
  color: var(--text-muted);
  font-size: 14px;
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.activity-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--bg-light);
  border-radius: var(--radius-md);
}

.activity-date {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.activity-counts {
  display: flex;
  gap: 16px;
}

.count-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.count-item svg {
  color: var(--text-muted);
}
</style>
