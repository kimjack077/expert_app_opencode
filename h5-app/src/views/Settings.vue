<template>
  <div class="settings-page">
    <van-nav-bar
      title="设置"
      left-arrow
      @click-left="goBack"
      class="custom-nav"
    />

    <div class="content-section">
      <div class="settings-card">
        <h3 class="card-title">应用设置</h3>
        <div class="settings-list">
          <div class="settings-item" @click="toggleNotification">
            <div class="item-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
            </div>
            <div class="item-content">
              <span class="item-label">消息通知</span>
              <span class="item-desc">接收任务提醒和系统通知</span>
            </div>
            <van-switch v-model="settings.notification" size="22" />
          </div>
          
          <div class="settings-item" @click="toggleSound">
            <div class="item-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
                <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
              </svg>
            </div>
            <div class="item-content">
              <span class="item-label">提示音</span>
              <span class="item-desc">操作反馈声音</span>
            </div>
            <van-switch v-model="settings.sound" size="22" />
          </div>
          
          <div class="settings-item" @click="toggleVibration">
            <div class="item-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M2 12h2"/>
                <path d="M20 12h2"/>
                <path d="M6 12a6 6 0 0 0 12 0"/>
                <rect x="8" y="4" width="8" height="16" rx="4"/>
              </svg>
            </div>
            <div class="item-content">
              <span class="item-label">震动反馈</span>
              <span class="item-desc">操作时震动提示</span>
            </div>
            <van-switch v-model="settings.vibration" size="22" />
          </div>
        </div>
      </div>

      <div class="settings-card">
        <h3 class="card-title">数据管理</h3>
        <div class="settings-list">
          <div class="settings-item" @click="clearCache">
            <div class="item-icon orange">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 6h18"/>
                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
              </svg>
            </div>
            <div class="item-content">
              <span class="item-label">清除缓存</span>
              <span class="item-desc">清除本地缓存数据</span>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="item-arrow">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          </div>
          
          <div class="settings-item" @click="exportData">
            <div class="item-icon blue">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
            </div>
            <div class="item-content">
              <span class="item-label">导出数据</span>
              <span class="item-desc">导出检查记录数据</span>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="item-arrow">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="settings-card">
        <h3 class="card-title">账户安全</h3>
        <div class="settings-list">
          <div class="settings-item" @click="changePassword">
            <div class="item-icon purple">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </div>
            <div class="item-content">
              <span class="item-label">修改密码</span>
              <span class="item-desc">更新登录密码</span>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="item-arrow">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="version-info">
        <span>当前版本: v1.0.0</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'

const router = useRouter()

const settings = ref({
  notification: true,
  sound: true,
  vibration: true
})

const loadSettings = () => {
  const saved = localStorage.getItem('app_settings')
  if (saved) {
    settings.value = { ...settings.value, ...JSON.parse(saved) }
  }
}

const saveSettings = () => {
  localStorage.setItem('app_settings', JSON.stringify(settings.value))
}

const toggleNotification = () => {
  settings.value.notification = !settings.value.notification
  saveSettings()
  showToast(settings.value.notification ? '已开启消息通知' : '已关闭消息通知')
}

const toggleSound = () => {
  settings.value.sound = !settings.value.sound
  saveSettings()
  showToast(settings.value.sound ? '已开启提示音' : '已关闭提示音')
}

const toggleVibration = () => {
  settings.value.vibration = !settings.value.vibration
  saveSettings()
  showToast(settings.value.vibration ? '已开启震动反馈' : '已关闭震动反馈')
}

const clearCache = async () => {
  try {
    await showConfirmDialog({
      title: '清除缓存',
      message: '确定要清除本地缓存数据吗？这不会影响您的账户数据。',
      confirmButtonText: '清除',
      cancelButtonText: '取消',
    })
    localStorage.removeItem('cached_enterprises')
    localStorage.removeItem('cached_templates')
    showToast({ type: 'success', message: '缓存已清除' })
  } catch (error) {
    if (error?.message !== 'cancel' && error !== 'cancel') {
      console.error('清除缓存失败:', error)
    }
  }
}

const exportData = () => {
  showToast('数据导出功能开发中')
}

const changePassword = () => {
  showToast('修改密码功能开发中')
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  loadSettings()
})
</script>

<style scoped>
.settings-page {
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

.settings-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

.card-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.settings-list {
  display: flex;
  flex-direction: column;
}

.settings-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
  transition: background var(--transition-base);
}

.settings-item:last-child {
  border-bottom: none;
}

.settings-item:active {
  background: var(--bg-light);
  margin: 0 -16px;
  padding: 14px 16px;
}

.item-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-light);
  color: var(--text-primary);
  flex-shrink: 0;
}

.item-icon.orange {
  background: var(--warning-bg);
  color: var(--warning-color);
}

.item-icon.blue {
  background: var(--info-bg);
  color: var(--info-color);
}

.item-icon.purple {
  background: rgba(156, 39, 176, 0.1);
  color: #9C27B0;
}

.item-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item-label {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

.item-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

.item-arrow {
  color: var(--text-muted);
}

.version-info {
  text-align: center;
  padding: 20px;
  color: var(--text-muted);
  font-size: 13px;
}
</style>
