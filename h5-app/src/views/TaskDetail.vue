<template>
  <div class="task-detail-page">
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
        <p class="task-desc">{{ task.description || '暂无描述' }}</p>

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

      <div class="action-bar">
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
          v-if="task.status === 'in_progress'"
          type="success"
          block
          class="action-btn success"
          @click="goToExecution"
        >
          <van-icon name="edit" size="20" />
          <span>执行检查</span>
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
          v-if="task.status === 'completed'"
          disabled
          block
          class="action-btn disabled"
        >
          <van-icon name="passed" size="20" />
          <span>任务已完成</span>
        </van-button>
      </div>
    </div>

    <van-empty v-else description="任务不存在" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import { getTask, updateTask } from '../api/tasks.js'

const router = useRouter()
const route = useRoute()
const task = ref(null)
const loading = ref(true)

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

const fetchTask = async () => {
  const taskId = route.params.id
  console.log('获取任务详情, ID:', taskId)
  
  if (!taskId || taskId === 'undefined' || taskId === 'null') {
    console.error('任务ID无效:', taskId)
    showToast({ type: 'fail', message: '任务ID无效' })
    loading.value = false
    return
  }
  
  try {
    const res = await getTask(taskId)
    console.log('任务详情响应:', res)
    if (res.code === 200) {
      task.value = res.data
    } else {
      showToast({ type: 'fail', message: res.message || '获取任务失败' })
    }
  } catch (error) {
    console.error('获取任务详情失败:', error)
    const errorMsg = error.response?.data?.detail || error.response?.data?.message || '获取任务详情失败'
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
    const res = await updateTask(task.value.id, { status: 'in_progress' })
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

const completeTask = async () => {
  try {
    await showConfirmDialog({
      title: '确认完成',
      message: '确定要完成这个任务吗？',
    })
    const res = await updateTask(task.value.id, { status: 'completed' })
    console.log('完成任务响应:', res)
    if (res.code === 200) {
      showToast({ type: 'success', message: '任务已完成' })
      fetchTask()
    } else {
      showToast({ type: 'fail', message: res.message || '操作失败' })
    }
  } catch (error) {
    if (error?.message !== 'cancel' && error !== 'cancel') {
      console.error('完成任务失败:', error)
      const errorMsg = error.response?.data?.detail || error.response?.data?.message || '完成任务失败'
      showToast({ type: 'fail', message: errorMsg })
    }
  }
}

const goToExecution = () => {
  router.push(`/task/${task.value.id}/execute`)
}

onMounted(() => {
  fetchTask()
})
</script>

<style scoped>
.task-detail-page {
  min-height: 100vh;
  background: var(--bg-light);
  padding-bottom: 100px;
}

.page-header {
  background: var(--primary-gradient-dark);
  padding: 50px 20px 30px;
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
  width: 40px;
  height: 40px;
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
  width: 40px;
  height: 40px;
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

.action-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 16px 20px 24px;
  background: var(--bg-white);
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.08);
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
