<template>
  <van-tabbar v-model="active" route class="efis-tabbar" safe-area-inset-bottom>
    <!-- 「今日审核」= 按审核计划指派的区域任务；「检查任务」= 按检查表逐项填报的任务（含审核计划生成的检查表），
         与该页标题一致。此前叫「任务」，审核员常误以为两者是同一份列表 -->
    <van-tabbar-item to="/today-audit" icon="todo-list-o">今日审核</van-tabbar-item>
    <van-tabbar-item to="/tasks" icon="orders-o">检查任务</van-tabbar-item>
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
