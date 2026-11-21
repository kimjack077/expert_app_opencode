import request from './request'

// 获取我的审核任务列表
export function getMyAuditTasks(params) {
  return request({
    url: '/audit-projects/my-tasks',
    method: 'get',
    params
  })
}

// 获取审核计划项详情
export function getAuditPlanItem(id) {
  return request({
    url: `/audit-projects/plan/${id}`,
    method: 'get'
  })
}

// 创建审核区域记录
export function createAuditRecord(projectId, data) {
  return request({
    url: `/audit-projects/${projectId}/records`,
    method: 'post',
    data
  })
}

// 获取审核区域记录详情
export function getAuditRecord(recordId) {
  return request({
    url: `/audit-projects/records/${recordId}`,
    method: 'get'
  })
}

// 更新审核区域记录
export function updateAuditRecord(recordId, data) {
  return request({
    url: `/audit-projects/records/${recordId}`,
    method: 'put',
    data
  })
}

// 创建不符合项
export function createNonconformity(projectId, data) {
  return request({
    url: `/audit-projects/${projectId}/nonconformities`,
    method: 'post',
    data
  })
}

// 获取审核项目进度
export function getAuditProgress(projectId) {
  return request({
    url: `/audit-projects/${projectId}/progress`,
    method: 'get'
  })
}

// ==================== AI Agent API ====================

// AI 证据充分性评估
export function evaluateEvidenceWithAI(projectId, params) {
  return request({
    url: `/audit-projects/${projectId}/ai/evaluate-evidence`,
    method: 'post',
    params
  })
}

// AI 建议不符合项
export function suggestNCWithAI(projectId, params) {
  return request({
    url: `/audit-projects/${projectId}/ai/suggest-nc`,
    method: 'post',
    params
  })
}

// ==================== Project-scoped Audit Agent API ====================

export function listAuditSessions(projectId) {
  return request({
    url: `/audit-projects/${projectId}/sessions`,
    method: 'get'
  })
}

export function createAuditSession(projectId, data) {
  return request({
    url: `/audit-projects/${projectId}/sessions`,
    method: 'post',
    data
  })
}

export function getAuditSession(projectId, sessionId) {
  return request({
    url: `/audit-projects/${projectId}/sessions/${sessionId}`,
    method: 'get'
  })
}

export function uploadAuditSessionMedia(projectId, sessionId, file) {
  const data = new FormData()
  data.append('file', file)
  return request({
    url: `/audit-projects/${projectId}/sessions/${sessionId}/media`,
    method: 'post',
    data,
    timeout: 120000
  })
}

export function submitSessionEvidence(projectId, sessionId, data) {
  return request({
    url: `/audit-projects/${projectId}/sessions/${sessionId}/evidence`,
    method: 'post',
    data,
    timeout: 120000
  })
}

// 保存审核员手工填写的正式现场记录
export function createManualSessionRecord(projectId, sessionId, data) {
  return request({
    url: `/audit-projects/${projectId}/sessions/${sessionId}/records/manual`,
    method: 'post',
    data
  })
}

export function confirmAuditDrafts(projectId, sessionId, data) {
  return request({
    url: `/audit-projects/${projectId}/sessions/${sessionId}/drafts/confirm`,
    method: 'post',
    data
  })
}

export function checkAuditQuality(projectId, sessionId) {
  return request({
    url: `/audit-projects/${projectId}/sessions/${sessionId}/quality-check`,
    method: 'post'
  })
}

export function submitAuditSession(projectId, sessionId, data) {
  return request({
    url: `/audit-projects/${projectId}/sessions/${sessionId}/submit`,
    method: 'post',
    data
  })
}

// ==================== 会话上下文持久化 ====================
// sessionId → { projectId, planItemId } 的 sessionStorage 映射。
// 会话页刷新/直达时 URL query 可能丢失 projectId，按 sessionId 恢复，
// 避免发出 /audit-projects//sessions/… 这类空参请求变成死页。

const SESSION_CONTEXT_KEY = 'efis:audit-session-context'

// 进入会话时写入（跳转来源与会话页自身都会调用）
export function rememberAuditSessionContext(sessionId, projectId, planItemId = '') {
  if (!sessionId || !projectId) return
  try {
    const raw = window.sessionStorage.getItem(SESSION_CONTEXT_KEY)
    const map = raw ? JSON.parse(raw) : {}
    map[sessionId] = { projectId: String(projectId), planItemId: String(planItemId || '') }
    window.sessionStorage.setItem(SESSION_CONTEXT_KEY, JSON.stringify(map))
  } catch {
    // 存储不可用时静默降级，URL 参数仍可用
  }
}

export function recallAuditSessionContext(sessionId) {
  if (!sessionId) return null
  try {
    const raw = window.sessionStorage.getItem(SESSION_CONTEXT_KEY)
    const map = raw ? JSON.parse(raw) : {}
    const entry = map[sessionId]
    return entry && entry.projectId ? entry : null
  } catch {
    return null
  }
}
