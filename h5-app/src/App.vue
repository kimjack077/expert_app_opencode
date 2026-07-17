<template>
  <div class="app-container">
    <OfflineBanner />
    <router-view />
    <template v-if="showGlobalAgent">
      <AgentFab @click="showChat = true" />
      <AgentChatPanel
        v-model:show="showChat"
        :context="chatContext"
      />
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import AgentFab from '@/components/agent/AgentFab.vue'
import AgentChatPanel from '@/components/agent/AgentChatPanel.vue'
import OfflineBanner from '@/components/OfflineBanner.vue'

const route = useRoute()
const showChat = ref(false)

const hasEmbeddedAgent = computed(() =>
  route.path.startsWith('/inspection/') ||
  /^\/task\/[^/]+\/execute$/.test(route.path) ||
  route.path.startsWith('/audit-session/')
)

const showGlobalAgent = computed(() =>
  route.path !== '/login' && !hasEmbeddedAgent.value
)

const chatContext = computed(() => ({
  recordId: route.path.startsWith('/record/') || route.path.startsWith('/inspection/')
    ? route.params.id || ''
    : '',
  currentItemTitle: '',
  currentItemId: '',
  enterpriseId: route.query.enterprise_id || '',
  projectId: route.query.projectId || route.params.projectId || '',
  planItemId: route.path.startsWith('/audit-task/') ? route.params.id || '' : '',
  sessionId: route.params.sessionId || ''
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
