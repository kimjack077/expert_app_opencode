<template>
  <div class="messages-page">
    <van-nav-bar title="智审提醒" left-arrow fixed placeholder @click-left="goBack">
      <template #right>
        <span v-if="unreadItems.length" class="nav-action" @click="markAllRead">全部已读</span>
      </template>
    </van-nav-bar>

    <div class="filter-bar">
      <button
        v-for="opt in filters"
        :key="opt.value"
        type="button"
        class="filter-chip"
        :class="{ active: filter === opt.value }"
        @click="switchFilter(opt.value)"
      >
        {{ opt.label }}<span v-if="opt.value === 'unread' && unreadCount"> {{ unreadCount }}</span>
      </button>
    </div>

    <van-pull-refresh v-model="refreshing" @refresh="load">
      <div class="list">
        <div v-if="loading && !items.length" class="loading-box">
          <van-loading size="24px">加载中…</van-loading>
        </div>
        <van-empty
          v-else-if="!items.length"
          image="search"
          :description="filter === 'unread' ? '没有未读提醒' : '暂无提醒'"
        />
        <van-swipe-cell v-for="item in items" :key="item.id">
          <div class="msg-card" :class="{ unread: item.status === 'unread' }" @click="openItem(item)">
            <div class="msg-head">
              <van-tag :type="kindOf(item).type" plain>{{ kindOf(item).text }}</van-tag>
              <span class="msg-time">{{ formatTime(item.created_at) }}</span>
            </div>
            <div class="msg-title">
              <span v-if="item.status === 'unread'" class="dot" aria-hidden="true"></span>
              {{ pretty(item.title) }}
            </div>
            <div v-if="item.body" class="msg-body">{{ pretty(item.body) }}</div>
          </div>
          <template #right>
            <van-button
              v-if="item.status === 'unread'"
              square
              type="primary"
              class="swipe-btn"
              text="已读"
              @click="mark(item, 'read')"
            />
            <van-button square type="danger" class="swipe-btn" text="忽略" @click="mark(item, 'dismissed')" />
          </template>
        </van-swipe-cell>
        <p v-if="items.length" class="hint">左滑可标为已读或忽略</p>
      </div>
    </van-pull-refresh>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { getNotifications, updateNotification } from '../api/agent.js'

const router = useRouter()
const items = ref([])
const loading = ref(false)
const refreshing = ref(false)
const filter = ref('unread')
const unreadCount = ref(0)

const filters = [
  { value: 'unread', label: '未读' },
  { value: 'all', label: '全部' },
]

const KIND = {
  reaudit_due: { text: '复审到期', type: 'warning' },
  open_nonconformity: { text: 'NC 超期', type: 'danger' },
  stale_draft: { text: '草稿待确认', type: 'primary' },
}
const kindOf = (item) => KIND[item.kind] || { text: '提醒', type: 'default' }

// 历史提醒里残留英文状态码 / 空条款，展示前转中文（新提醒已在后端修正）
const NC_STATUS_TEXT = {
  open: '待整改',
  pending_rectification: '待整改',
  corrected: '已整改·待验证',
  pending_verification: '待验证',
  draft: 'AI 草稿',
}
const pretty = (text) =>
  String(text || '')
    .replace(/当前状态[:：]\s*([a-z_]+)/g, (_, s) => `当前状态：${NC_STATUS_TEXT[s] || s}`)
    .replace(/[:：]\s*$/, '')

const unreadItems = computed(() => items.value.filter((i) => i.status === 'unread'))

const formatTime = (value) => {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const load = async () => {
  loading.value = true
  try {
    const res = await getNotifications(filter.value)
    items.value = res?.data?.items || []
    if (filter.value === 'unread') unreadCount.value = items.value.length
  } catch {
    // 拦截器已按需提示，这里保持空列表
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const switchFilter = (value) => {
  if (filter.value === value) return
  filter.value = value
  load()
}

const mark = async (item, status) => {
  try {
    await updateNotification(item.id, status)
    if (item.status === 'unread') unreadCount.value = Math.max(0, unreadCount.value - 1)
    if (filter.value === 'unread') {
      items.value = items.value.filter((i) => i.id !== item.id)
    } else {
      item.status = status
    }
  } catch {
    showToast('操作失败，请稍后重试')
  }
}

const markAllRead = async () => {
  const targets = unreadItems.value.slice()
  await Promise.allSettled(targets.map((i) => updateNotification(i.id, 'read')))
  showToast({ type: 'success', message: '已全部标为已读' })
  unreadCount.value = 0
  load()
}

const openItem = (item) => {
  if (item.status === 'unread') mark(item, 'read')
  // 草稿待确认 / NC 超期都和审核项目相关：带去审核任务列表处理
  if (item.project_id) router.push('/audit-tasks')
}

const goBack = () => {
  if (window.history.length > 1) router.back()
  else router.replace('/profile')
}

onMounted(load)
</script>

<style scoped>
.messages-page {
  min-height: 100vh;
  background: var(--bg-light, #f5f7fa);
}
.nav-action {
  font-size: 13px;
  color: var(--primary-color, #0284c7);
}
.filter-bar {
  display: flex;
  gap: 8px;
  padding: 12px 16px 4px;
}
.filter-chip {
  border: 1px solid var(--border-light, #e5e7eb);
  background: #fff;
  color: var(--text-secondary, #64748b);
  border-radius: 999px;
  padding: 4px 14px;
  font-size: 13px;
}
.filter-chip.active {
  border-color: var(--primary-color, #0284c7);
  color: var(--primary-color, #0284c7);
  background: rgba(2, 132, 199, 0.06);
  font-weight: 600;
}
.list {
  padding: 8px 16px 24px;
  min-height: 60vh;
}
.loading-box {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.msg-card {
  background: #fff;
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 10px;
  border: 1px solid var(--border-light, #eef0f3);
  opacity: 0.7;
}
.msg-card.unread {
  opacity: 1;
  border-color: rgba(2, 132, 199, 0.25);
}
.msg-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.msg-time {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}
.msg-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #0f172a);
  display: flex;
  align-items: center;
  gap: 6px;
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #ef4444;
  flex-shrink: 0;
}
.msg-body {
  margin-top: 4px;
  font-size: 13px;
  color: var(--text-secondary, #64748b);
  line-height: 1.5;
}
.swipe-btn {
  height: 100%;
}
.hint {
  text-align: center;
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
  margin-top: 8px;
}
</style>
