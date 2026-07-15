<template>
  <main class="legacy-audit-redirect">
    <van-nav-bar title="进入 AI 现场审核" left-arrow @click-left="router.push('/today-audit')" />
    <van-loading size="28px" vertical>正在打开正式审核会话</van-loading>
  </main>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'

import {
  createAuditSession,
  getAuditPlanItem,
  listAuditSessions
} from '../api/auditProjects'

const route = useRoute()
const router = useRouter()

const unwrap = (response) => response?.data || response || {}

onMounted(async () => {
  const planItemId = String(route.params.id || '')
  try {
    const planItem = unwrap(await getAuditPlanItem(planItemId))
    const projectId = String(route.query.projectId || planItem.project_id || '')
    if (!projectId) throw new Error('审核计划项缺少项目归属')

    const sessions = unwrap(await listAuditSessions(projectId))
    const existing = (Array.isArray(sessions) ? sessions : []).find(
      (item) => item.context_snapshot?.plan_item_id === planItemId && item.status === 'active'
    )
    const session = existing || unwrap(await createAuditSession(projectId, {
      plan_item_id: planItemId,
      title: `${planItem.area_name || '现场'}审核`
    }))

    await router.replace({
      name: 'AiAuditSession',
      params: { sessionId: session.id },
      query: { projectId, planItemId }
    })
  } catch (error) {
    showToast(error?.message || '无法打开审核会话')
    await router.replace('/today-audit')
  }
})
</script>

<style scoped>
.legacy-audit-redirect {
  min-height: 100dvh;
  background: var(--bg-light);
}

.legacy-audit-redirect :deep(.van-loading) {
  padding-top: 30vh;
}
</style>
