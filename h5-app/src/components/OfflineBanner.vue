<template>
  <div v-if="!online" class="offline-banner" role="status">
    <van-icon name="warning-o" />
    <span>网络已断开，未提交的文字草稿会保存在本机；照片上传和正式保存需恢复网络</span>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const online = ref(typeof navigator !== 'undefined' ? navigator.onLine : true)

const sync = () => {
  online.value = navigator.onLine
}

onMounted(() => {
  window.addEventListener('online', sync)
  window.addEventListener('offline', sync)
})

onUnmounted(() => {
  window.removeEventListener('online', sync)
  window.removeEventListener('offline', sync)
})
</script>

<style scoped>
.offline-banner {
  position: sticky;
  top: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #fff7ed;
  color: #c2410c;
  font-size: 13px;
  border-bottom: 1px solid #fed7aa;
}
</style>
