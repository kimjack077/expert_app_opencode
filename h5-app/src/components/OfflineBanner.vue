<template>
  <div v-if="!online" class="offline-banner" role="status">
    <van-icon name="warning-o" />
    <div class="offline-banner-text">
      <span>网络已断开，未提交的文字草稿会保存在本机；照片上传和正式保存需恢复网络</span>
      <span class="offline-cache-line">
        <template v-if="summary.count > 0">
          已缓存 {{ summary.count }} 份检查资料 · 最近缓存 {{ formatCachedAt(summary.lastCachedAt) }}
        </template>
        <template v-else>
          本机暂无离线缓存，出发前可在任务详情点「缓存到本地」
        </template>
      </span>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { CACHE_EVENT, formatCachedAt, getCacheSummary, isOnline } from '@/utils/offlineCache.js'

const online = ref(isOnline())
const summary = ref(getCacheSummary())

const sync = () => {
  online.value = isOnline()
  summary.value = getCacheSummary()
}

const syncCache = () => {
  summary.value = getCacheSummary()
}

onMounted(() => {
  window.addEventListener('online', sync)
  window.addEventListener('offline', sync)
  window.addEventListener(CACHE_EVENT, syncCache)
})

onUnmounted(() => {
  window.removeEventListener('online', sync)
  window.removeEventListener('offline', sync)
  window.removeEventListener(CACHE_EVENT, syncCache)
})
</script>

<style scoped>
.offline-banner {
  position: sticky;
  top: 0;
  z-index: 1000;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  background: #fff7ed;
  color: #c2410c;
  font-size: 13px;
  border-bottom: 1px solid #fed7aa;
}

.offline-banner-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.45;
}

.offline-cache-line {
  font-size: 12px;
  color: #9a3412;
  opacity: 0.85;
}
</style>
