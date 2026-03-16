<template>
  <div class="agent-fab" @click="$emit('click')">
    <van-icon name="chat-o" size="24" color="#fff" />
  </div>
</template>

<script setup>
defineEmits(['click'])
</script>

<style scoped>
.agent-fab {
  position: fixed;
  right: 16px;
  bottom: 116px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #1677FF;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(22, 119, 255, 0.4);
  z-index: 999;
  cursor: pointer;
  transition: all 0.3s ease;
}

.agent-fab:active {
  transform: scale(0.95);
  box-shadow: 0 2px 8px rgba(22, 119, 255, 0.3);
}
</style>
