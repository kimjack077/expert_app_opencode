<template>
  <van-tabbar v-model="active" route class="efis-tabbar" safe-area-inset-bottom>
    <van-tabbar-item to="/today-audit" icon="todo-list-o">今日</van-tabbar-item>
    <van-tabbar-item to="/tasks" icon="orders-o">任务</van-tabbar-item>
    <van-tabbar-item to="/records" icon="notes-o">记录</van-tabbar-item>
    <van-tabbar-item to="/profile" icon="user-o">我的</van-tabbar-item>
  </van-tabbar>
</template>

<script setup>
import { ref } from 'vue'
const active = ref(0)
</script>

<style scoped>
.efis-tabbar {
  max-width: 430px;
  left: 50%;
  transform: translateX(-50%);
}
</style>
