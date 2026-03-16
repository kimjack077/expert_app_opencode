<template>
  <div class="app-container">
    <router-view />
    <AgentFab @click="showChat = true" />
    <AgentChatPanel
      v-model:show="showChat"
      :context="chatContext"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import AgentFab from '@/components/agent/AgentFab.vue'
import AgentChatPanel from '@/components/agent/AgentChatPanel.vue'

const route = useRoute()
const showChat = ref(false)

const chatContext = computed(() => ({
  recordId: route.params.id || '',
  currentItemTitle: '',
  currentItemId: '',
  enterpriseId: route.query.enterprise_id || ''
}))
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: #f5f5f5;
  -webkit-font-smoothing: antialiased;
}

.app-container {
  min-height: 100vh;
  max-width: 430px;
  margin: 0 auto;
  background-color: #f5f5f5;
  position: relative;
}

/* 移动端适配 */
@media (max-width: 430px) {
  .app-container {
    max-width: 100%;
  }
}
</style>
