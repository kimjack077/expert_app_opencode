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
              <span class="item-label">智审提醒角标</span>
              <span class="item-desc">在「我的」页显示复审到期、NC 超期等未读提醒数</span>
            </div>
            <van-switch v-model="settings.notification" size="22" @click.stop @change="onSettingToggle('notification')" />
          </div>
          <!-- 提示音 / 震动反馈开关此前只保存设置、从未生效，已移除，避免误导 -->
          <div class="settings-item" @click="router.push('/messages')">
            <div class="item-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 6h16M4 12h16M4 18h10"/>
              </svg>
            </div>
            <div class="item-content">
              <span class="item-label">查看全部提醒</span>
              <span class="item-desc">已读、未读的智审提醒记录</span>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="item-arrow">
              <path d="m9 18 6-6-6-6"/>
            </svg>
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
              <span class="item-desc">{{ cacheDesc }}</span>
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
        <span>当前版本：v{{ appVersion }}</span>
      </div>
    </div>

    <van-dialog
      v-model:show="pwdDialogShow"
      title="修改密码"
      show-cancel-button
      :before-close="onPwdBeforeClose"
      confirm-button-text="确认修改"
    >
      <div class="pwd-form">
        <van-field
          v-model="pwdForm.old_password"
          type="password"
          label="当前密码"
          placeholder="请输入当前密码"
          autocomplete="current-password"
        />
        <van-field
          v-model="pwdForm.new_password"
          type="password"
          label="新密码"
          placeholder="至少 6 位"
          autocomplete="new-password"
        />
        <van-field
          v-model="pwdForm.confirm_password"
          type="password"
          label="确认新密码"
          placeholder="再次输入新密码"
          autocomplete="new-password"
        />
      </div>
    </van-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, closeToast, showConfirmDialog } from 'vant'
import { changePassword as changePasswordApi, getCurrentUser } from '../api/auth.js'
import { getRecords } from '../api/records.js'
import { clearCache as clearOfflineCache, getCacheSummary } from '@/utils/offlineCache.js'

const router = useRouter()
// 与「关于」页同源，避免两处显示不同版本号
const appVersion = import.meta.env.VITE_APP_VERSION || '2.4.0'

const settings = ref({
  notification: true,
  sound: true,
  vibration: true
})

const pwdDialogShow = ref(false)
const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const cacheDesc = ref('清除本地离线任务与临时缓存')
const exporting = ref(false)

const refreshCacheSummary = () => {
  try {
    const summary = getCacheSummary()
    if (summary && summary.count > 0) {
      const kb = Math.max(1, Math.round((summary.bytes || 0) / 1024))
      cacheDesc.value = `已缓存 ${summary.count} 项离线数据（约 ${kb} KB）`
    } else {
      cacheDesc.value = '当前无本地离线缓存'
    }
  } catch {
    cacheDesc.value = '清除本地离线任务与临时缓存'
  }
}

const loadSettings = () => {
  const saved = localStorage.getItem('app_settings')
  if (saved) {
    try {
      settings.value = { ...settings.value, ...JSON.parse(saved) }
    } catch {
      // ignore corrupted settings
    }
  }
  refreshCacheSummary()
}

const saveSettings = () => {
  localStorage.setItem('app_settings', JSON.stringify(settings.value))
}

const settingLabels = {
  notification: '消息通知',
  sound: '提示音',
  vibration: '震动反馈',
}

const onSettingToggle = (key) => {
  saveSettings()
  const label = settingLabels[key] || ''
  showToast(settings.value[key] ? `已开启${label}` : `已关闭${label}`)
}

const toggleNotification = () => {
  settings.value.notification = !settings.value.notification
  onSettingToggle('notification')
}

const toggleSound = () => {
  settings.value.sound = !settings.value.sound
  onSettingToggle('sound')
}

const toggleVibration = () => {
  settings.value.vibration = !settings.value.vibration
  onSettingToggle('vibration')
}

const clearCache = async () => {
  try {
    await showConfirmDialog({
      title: '清除缓存',
      message: '确定要清除本地离线缓存数据吗？这不会影响已提交到云端的记录。',
      confirmButtonText: '清除',
      cancelButtonText: '取消',
    })
    clearOfflineCache()
    localStorage.removeItem('cached_enterprises')
    localStorage.removeItem('cached_templates')
    refreshCacheSummary()
    showToast({ type: 'success', message: '本地缓存已清除' })
  } catch (error) {
    if (error?.message !== 'cancel' && error !== 'cancel') {
      console.error('清除缓存失败:', error)
    }
  }
}

const exportData = async () => {
  if (exporting.value) return
  exporting.value = true
  let resultMessage = ''
  let resultType = 'text'
  try {
    showToast({ type: 'loading', message: '正在准备导出数据...', forbidClick: true, duration: 0 })
    const userRes = await getCurrentUser()
    if (!userRes.data?.id) throw new Error('无法获取当前检查员信息')
    const items = []
    const pageSize = 100
    for (let page = 1; ; page++) {
      const res = await getRecords({ page, limit: pageSize, inspector_id: userRes.data.id })
      const batch = res.data?.items || []
      items.push(...batch)
      const total = res.data?.total
      if (batch.length < pageSize || (total != null && items.length >= Number(total))) break
    }
    if (items.length === 0) {
      resultMessage = '暂无可导出的检查记录'
      return
    }
    const statusMap = { draft: '草稿', submitted: '已提交' }
    const resultMap = { pass: '合格', partial_pass: '基本合格', fail: '不合格' }
    const escapeCell = (v) => {
      const s = v === null || v === undefined ? '' : String(v)
      return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
    }
    const headers = ['企业名称', '检查模板', '状态', '总体结论', '总分', '检查日期']
    const rows = items.map((r) => [
      r.enterprise_name || r.enterprise?.name || '未指定企业',
      r.template?.name || '未知模板',
      statusMap[r.status] || r.status || '',
      resultMap[r.overall_result] || '待判定',
      r.total_score ?? '',
      r.inspection_date ? String(r.inspection_date).slice(0, 10) : '',
    ])
    const csv = '\uFEFF' + [headers, ...rows].map((row) => row.map(escapeCell).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const today = new Date().toISOString().slice(0, 10)
    link.href = url
    link.download = `易审通_检查记录_${today}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    resultType = 'success'
    resultMessage = `已导出 ${items.length} 条记录`
  } catch (error) {
    console.error('导出失败:', error)
    resultMessage = '导出失败，请稍后重试'
  } finally {
    closeToast()
    exporting.value = false
    if (resultMessage) showToast({ type: resultType, message: resultMessage })
  }
}

const changePassword = () => {
  pwdForm.old_password = ''
  pwdForm.new_password = ''
  pwdForm.confirm_password = ''
  pwdDialogShow.value = true
}

// van-dialog 的 before-close：确认时校验并提交，失败返回 false 保持弹窗打开
const onPwdBeforeClose = async (action) => {
  if (action !== 'confirm') return true
  if (!pwdForm.old_password) {
    showToast('请输入当前密码')
    return false
  }
  if (!pwdForm.new_password || pwdForm.new_password.length < 6) {
    showToast('新密码至少 6 位')
    return false
  }
  if (pwdForm.new_password !== pwdForm.confirm_password) {
    showToast('两次输入的新密码不一致')
    return false
  }
  try {
    await changePasswordApi({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password
    })
    showToast({ type: 'success', message: '密码修改成功' })
    return true
  } catch {
    // 请求拦截器统一显示接口失败信息，保留对话框供用户修正。
    return false
  }
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

.pwd-form {
  padding: 8px 0 16px;
}
</style>
