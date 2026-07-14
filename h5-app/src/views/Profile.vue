<template>
  <div class="profile-page">
    <div class="page-header">
      <div class="header-bg"></div>
      <div class="header-content">
        <div class="avatar-section">
          <div class="avatar-ring">
            <div class="avatar">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
            </div>
          </div>
          <div class="user-info">
            <h1 class="username">{{ user?.username || '未登录' }}</h1>
            <div class="user-badges">
              <span class="user-badge">{{ user?.role || '普通用户' }}</span>
              <span class="user-badge verified">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                已认证
              </span>
            </div>
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
      <div class="menu-card">
        <h3 class="menu-title">功能菜单</h3>
        <div class="menu-list">
          <div class="menu-item" @click="goToTasks">
            <div class="menu-icon blue">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 11l3 3L22 4"/>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
              </svg>
            </div>
            <div class="menu-content">
              <span class="menu-label">我的任务</span>
              <span class="menu-desc">查看和管理检查任务</span>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="menu-arrow">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          </div>
          <div class="menu-item" @click="goToRecords">
            <div class="menu-icon green">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <div class="menu-content">
              <span class="menu-label">检查记录</span>
              <span class="menu-desc">历史检查数据</span>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="menu-arrow">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          </div>
          <div class="menu-item" @click="goToStatistics">
            <div class="menu-icon orange">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="20" x2="18" y2="10"/>
                <line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
            </div>
            <div class="menu-content">
              <span class="menu-label">数据统计</span>
              <span class="menu-desc">工作统计和分析</span>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="menu-arrow">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="menu-card">
        <h3 class="menu-title">系统设置</h3>
        <div class="menu-list">
          <div class="menu-item" @click="goToSettings">
            <div class="menu-icon purple">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </div>
            <div class="menu-content">
              <span class="menu-label">设置</span>
              <span class="menu-desc">应用偏好设置</span>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="menu-arrow">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          </div>
          <div class="menu-item" @click="goToAbout">
            <div class="menu-icon gray">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="16" x2="12" y2="12"/>
                <line x1="12" y1="8" x2="12.01" y2="8"/>
              </svg>
            </div>
            <div class="menu-content">
              <span class="menu-label">关于</span>
              <span class="menu-desc">版本信息和帮助</span>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="menu-arrow">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="logout-section">
        <van-button
          block
          class="logout-btn"
          @click="logout"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
          <span>退出登录</span>
        </van-button>
      </div>
    </div>

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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { getCurrentUser } from '../api/auth.js'
import { getTasks } from '../api/tasks.js'

const router = useRouter()
const activeTab = ref(3)
const user = ref(null)
const stats = ref({
  pending: 0,
  inProgress: 0,
  completed: 0
})

const fetchUser = async () => {
  try {
    const res = await getCurrentUser()
    user.value = res.data
  } catch (error) {
    console.error('获取用户信息失败:', error)
  }
}

const fetchStats = async () => {
  try {
    const res = await getTasks({ page: 1, page_size: 100 })
    const tasks = res.items || []
    stats.value = {
      pending: tasks.filter(t => t.status === 'pending').length,
      inProgress: tasks.filter(t => t.status === 'in_progress').length,
      completed: tasks.filter(t => t.status === 'completed').length
    }
  } catch (error) {
    console.error('获取统计数据失败:', error)
  }
}

const goToTasks = () => {
  router.push('/tasks')
}

const goToRecords = () => {
  router.push('/records')
}

const goToStatistics = () => {
  router.push('/statistics')
}

const goToSettings = () => {
  router.push('/settings')
}

const goToAbout = () => {
  router.push('/about')
}

const logout = async () => {
  try {
    await showConfirmDialog({
      title: '确认退出',
      message: '确定要退出登录吗？',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
    localStorage.removeItem('token')
    showToast({ type: 'success', message: '已退出登录' })
    router.push('/login')
  } catch (error) {
    if (error?.message !== 'cancel' && error !== 'cancel') {
      console.error('退出失败:', error)
    }
  }
}

onMounted(() => {
  fetchUser()
  fetchStats()
})
</script>

<style scoped>
.profile-page {
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

.avatar-section {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.avatar-ring {
  width: 44px;
  height: 44px;
  padding: 2px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 50%;
}

.avatar {
  width: 40px;
  height: 40px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(10px);
  color: var(--bg-white);
}

.avatar svg {
  width: 24px;
  height: 24px;
}

.user-info {
  flex: 1;
}

.username {
  font-size: 20px;
  font-weight: 700;
  color: var(--bg-white);
  margin: 0 0 4px;
  font-family: var(--font-primary);
  letter-spacing: -0.5px;
}

.user-badges {
  display: flex;
  gap: 6px;
}

.user-badge {
  min-height: 20px;
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.25);
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}

.user-badge.verified {
  background: rgba(16, 185, 129, 0.2);
  color: var(--bg-white);
  border-color: rgba(16, 185, 129, 0.3);
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

.menu-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

.menu-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
  font-family: var(--font-primary);
  letter-spacing: -0.3px;
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
  padding: 12px;
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

.menu-icon.purple {
  background: rgba(156, 39, 176, 0.1);
  color: #9C27B0;
}

.menu-icon.gray {
  background: var(--bg-light);
  color: var(--text-muted);
}

.menu-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.menu-label {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

.menu-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

.menu-arrow {
  color: var(--text-muted);
  transition: transform var(--transition-base);
}

.menu-item:hover .menu-arrow {
  transform: translateX(4px);
}

.logout-section {
  padding: 8px 0;
}

.logout-btn {
  height: 52px;
  border-radius: var(--radius-lg);
  background: var(--bg-white);
  border: 1px solid var(--border-color);
  color: var(--error-color);
  font-size: 16px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-base);
}

.logout-btn:hover {
  border-color: var(--error-color);
  box-shadow: var(--shadow-md);
}

.logout-btn:active {
  background: rgba(239, 68, 68, 0.05);
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

:deep(.van-dialog__confirm) {
  color: var(--error-color);
}

@media (prefers-reduced-motion: reduce) {
  .menu-item,
  .menu-arrow,
  .logout-btn {
    transition: none;
  }
}
</style>
