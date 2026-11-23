<template>
  <div class="not-found-page">
    <van-empty image="error" description="页面不存在或已被移动">
      <div class="actions">
        <van-button round plain type="primary" size="small" @click="goBack">返回上一页</van-button>
        <van-button round type="primary" size="small" @click="goHome">回到今日审核</van-button>
      </div>
    </van-empty>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const goBack = () => {
  if (window.history.length > 1) router.back()
  else goHome()
}

const goHome = () => {
  router.replace(localStorage.getItem('token') ? '/today-audit' : '/login')
}
</script>

<style scoped>
.not-found-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-light, #f5f7fa);
}
.actions {
  display: flex;
  gap: 12px;
}
</style>
