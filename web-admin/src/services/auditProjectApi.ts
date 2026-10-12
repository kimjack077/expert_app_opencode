import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const API_BASE_URL = import.meta.env.VITE_API_URL !== undefined ? import.meta.env.VITE_API_URL : 'http://localhost:8000'
const PROJECT_AGENT_BASE = '/api/audit-projects'

const api = axios.create({
  baseURL: API_BASE_URL || undefined,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器：添加 token
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：处理错误
api.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    if (error.response?.status === 401) {
      const refreshToken = useAuthStore.getState().refreshToken
      if (refreshToken) {
        try {
          const res = await axios.post(`${API_BASE_URL}/api/auth/refresh`, null, {
            params: { refresh_token: refreshToken },
          })
          const { access_token, refresh_token } = res.data.data
          useAuthStore.getState().setTokens(access_token, refresh_token)
          error.config.headers.Authorization = `Bearer ${access_token}`
          return api(error.config)
        } catch {
          useAuthStore.getState().logout()
        }
      }
    }
    return Promise.reject(error)
  }
)

// ==================== 审核项目 API ====================

export const auditProjectApi = {
  // 创建审核项目
  create: (data: any) => api.post('/api/audit-projects', data),
  
  // 获取审核项目列表
  list: (params?: any) => api.get('/api/audit-projects', { params }),
  
  // 获取审核项目详情
  get: (id: string) => api.get(`/api/audit-projects/${id}`),
  
  // 更新审核项目
  update: (id: string, data: any) => api.put(`/api/audit-projects/${id}`, data),
  
  // 删除审核项目
  delete: (id: string) => api.delete(`/api/audit-projects/${id}`),
  
  // 获取项目进度
  getProgress: (id: string) => api.get(`/api/audit-projects/${id}/progress`),
}

// ==================== 审核组成员 API ====================

export const auditTeamApi = {
  // 添加审核组成员
  add: (projectId: string, data: any) => 
    api.post(`/api/audit-projects/${projectId}/team`, data),
  
  // 获取审核组成员列表
  list: (projectId: string) => 
    api.get(`/api/audit-projects/${projectId}/team`),
  
  // 更新审核组成员
  update: (memberId: string, data: any) => 
    api.put(`/api/audit-projects/team/${memberId}`, data),
  
  // 移除审核组成员
  remove: (memberId: string) => 
    api.delete(`/api/audit-projects/team/${memberId}`),
}

// ==================== 审核计划 API ====================

export const auditPlanApi = {
  // 创建审核计划项
  create: (projectId: string, data: any) => 
    api.post(`/api/audit-projects/${projectId}/plan`, data),
  
  // 获取审核计划项列表
  list: (projectId: string, params?: any) => 
    api.get(`/api/audit-projects/${projectId}/plan`, { params }),
  
  // 获取审核计划项详情
  get: (planItemId: string) => 
    api.get(`/api/audit-projects/plan/${planItemId}`),
  
  // 更新审核计划项
  update: (planItemId: string, data: any) => 
    api.put(`/api/audit-projects/plan/${planItemId}`, data),
  
  // 删除审核计划项
  delete: (planItemId: string) => 
    api.delete(`/api/audit-projects/plan/${planItemId}`),

  // 绑定检查模板
  bindTemplate: (planItemId: string, templateId: string) =>
    api.post(`/api/audit-projects/plan/${planItemId}/bind-template`, { template_id: templateId }),
}

// ==================== 审核记录 API ====================

export const auditRecordApi = {
  // 创建审核区域记录
  create: (projectId: string, data: any) => 
    api.post(`/api/audit-projects/${projectId}/records`, data),
  
  // 获取审核区域记录列表
  list: (projectId: string, params?: any) => 
    api.get(`/api/audit-projects/${projectId}/records`, { params }),
  
  // 获取审核区域记录详情
  get: (recordId: string) => 
    api.get(`/api/audit-projects/records/${recordId}`),
  
  // 更新审核区域记录
  update: (recordId: string, data: any) => 
    api.put(`/api/audit-projects/records/${recordId}`, data),
}

// ==================== 不符合项 API ====================

export const nonconformityApi = {
  // 创建不符合项
  create: (projectId: string, data: any) => 
    api.post(`/api/audit-projects/${projectId}/nonconformities`, data),
  
  // 获取不符合项列表
  list: (projectId: string, params?: any) => 
    api.get(`/api/audit-projects/${projectId}/nonconformities`, { params }),
  
  // 更新不符合项
  update: (ncId: string, data: any) => 
    api.put(`/api/audit-projects/nonconformities/${ncId}`, data),

  // 确认 AI 生成的不符合项草稿。新 Agent 接口按项目隔离，避免跨项目写入。
  confirm: (projectId: string, ncId: string, data?: Record<string, unknown>) =>
    api.post(
      `${PROJECT_AGENT_BASE}/${projectId}/nonconformities/${ncId}/confirm`,
      data || {}
    ),
}

// ==================== 审核报告 API ====================

/** 带鉴权的文件下载（避免把 token 放进 URL） */
async function downloadWithAuth(url: string, filename: string) {
  const token = useAuthStore.getState().token
  const resp = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    throw new Error(`导出失败: HTTP ${resp.status} ${text}`)
  }
  const blob = await resp.blob()
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(link.href)
}

export const auditReportApi = {
  // 创建审核报告
  create: (projectId: string, data: any) => 
    api.post(`/api/audit-projects/${projectId}/report`, data),
  
  // 获取审核报告列表
  list: (projectId: string) => 
    api.get(`/api/audit-projects/${projectId}/report`),
  
  // 更新审核报告
  update: (reportId: string, data: any) => 
    api.put(`/api/audit-projects/report/${reportId}`, data),
  
  // 导出 Word 格式报告
  exportWord: (projectId: string) =>
    downloadWithAuth(
      `${API_BASE_URL}/api/audit-projects/${projectId}/export/word`,
      `audit_report_${projectId}.docx`
    ),

  // 导出 PDF 格式报告
  exportPdf: (projectId: string) =>
    downloadWithAuth(
      `${API_BASE_URL}/api/audit-projects/${projectId}/export/pdf`,
      `audit_report_${projectId}.pdf`
    ),
}

// ==================== 沟通会议 API ====================

export const meetingApi = {
  // 创建沟通会议记录
  create: (projectId: string, data: any) => 
    api.post(`/api/audit-projects/${projectId}/meetings`, data),
  
  // 获取沟通会议记录列表
  list: (projectId: string, params?: any) => 
    api.get(`/api/audit-projects/${projectId}/meetings`, { params }),
  
  // 更新沟通会议记录
  update: (meetingId: string, data: any) => 
    api.put(`/api/audit-projects/meetings/${meetingId}`, data),
}

// ==================== 我的任务 API ====================

export const myTasksApi = {
  // 获取我的审核任务列表
  list: (params?: any) => 
    api.get('/api/audit-projects/my-tasks', { params }),
}

// ==================== 项目 Agent 资料与成果 API ====================

export interface ProjectDocument {
  id: string
  title?: string
  document_type?: string
  original_filename?: string
  file_name?: string
  filename?: string
  name?: string
  category?: string
  status?: string
  parse_status?: string
  chunk_count?: number
  size?: number
  file_size?: number
  created_at?: string
  uploaded_at?: string
  summary?: string
  parse_error?: string
  parsed_at?: string
  metadata?: Record<string, unknown>
}

export interface ProjectKnowledgeHit {
  id?: string
  chunk_id?: string
  document_id?: string
  source?: string
  file_name?: string
  document_title?: string
  source_scope?: 'project' | 'global_regulation'
  content?: string
  text?: string
  score?: number
  relevance?: number
  similarity?: number
}

export interface ProjectAuditSession {
  id: string
  title?: string
  area_name?: string
  status?: string
  progress?: number
  exception_count?: number
  created_at?: string
  updated_at?: string
}

export interface ProjectArtifact {
  id?: string
  type?: string
  artifact_type?: string
  name?: string
  file_name?: string
  filename?: string
  status?: string
  generated_at?: string
  updated_at?: string
  size?: number
  file_size?: number
  available?: boolean
  version?: number
  progress?: number
  error_message?: string
  metadata?: Record<string, unknown>
}

export interface ProjectQualityCheck {
  score?: number
  overall_score?: number
  completeness_score?: number
  consistency_score?: number
  passed?: boolean
  blocking_count?: number
  warning_count?: number
  issues?: Array<{
    id?: string
    level?: string
    type?: string
    title?: string
    message?: string
    suggestion?: string
  }>
  blockers?: Array<string | Record<string, unknown>>
  warnings?: Array<string | Record<string, unknown>>
  reminders?: Array<string | Record<string, unknown>>
  completeness?: Record<string, unknown>
  consistency?: Record<string, unknown>
  checked_at?: string
}

export const projectDocumentApi = {
  list: (projectId: string) =>
    api.get(`${PROJECT_AGENT_BASE}/${projectId}/documents`),

  upload: (projectId: string, file: File, category?: string, forceIndex?: boolean) => {
    const formData = new FormData()
    formData.append('file', file)
    if (category) {
      formData.append('document_type', category)
      formData.append('category', category)
    }
    if (forceIndex) {
      formData.append('force_index', 'true')
    }
    return api.post(`${PROJECT_AGENT_BASE}/${projectId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 180000,
    })
  },

  confirmIndex: (
    projectId: string,
    documentId: string,
    action: 'index' | 'archive_only' = 'index'
  ) =>
    api.post(
      `${PROJECT_AGENT_BASE}/${projectId}/documents/${documentId}/confirm_index`,
      { action }
    ),

  remove: (projectId: string, documentId: string) =>
    api.delete(`${PROJECT_AGENT_BASE}/${projectId}/documents/${documentId}`),

  reindex: (projectId: string, documentId: string) =>
    api.post(
      `${PROJECT_AGENT_BASE}/${projectId}/documents/${documentId}/reindex`
    ),

  search: (projectId: string, query: string, limit = 8) =>
    api.post(
      `${PROJECT_AGENT_BASE}/${projectId}/knowledge/search`,
      {
        query,
        top_k: limit,
      },
      // Embedding + dual-scope retrieval can take tens of seconds
      { timeout: 120000 },
    ),
}

export const projectSessionApi = {
  list: (projectId: string) =>
    api.get(`${PROJECT_AGENT_BASE}/${projectId}/sessions`),
}

export const projectArtifactApi = {
  list: (projectId: string) =>
    api.get(`${PROJECT_AGENT_BASE}/${projectId}/artifacts`),

  generate: (projectId: string, data?: Record<string, unknown>) =>
    api.post(
      `${PROJECT_AGENT_BASE}/${projectId}/artifacts/generate`,
      data || {}
    ),

  retry: (projectId: string, artifactId: string) =>
    api.post(
      `${PROJECT_AGENT_BASE}/${projectId}/artifacts/${artifactId}/retry`
    ),

  qualityCheck: (projectId: string) =>
    api.post(`${PROJECT_AGENT_BASE}/${projectId}/quality-check`),

  download: (projectId: string, artifactId: string) =>
    api.get(
      `${PROJECT_AGENT_BASE}/${projectId}/artifacts/${artifactId}/download`,
      { responseType: 'blob', timeout: 120000 }
    ),

  downloadPackage: (projectId: string) =>
    api.get(`${PROJECT_AGENT_BASE}/${projectId}/package`, {
      responseType: 'blob',
      timeout: 180000,
    }),
}

export const saveDownloadedBlob = (
  response: unknown,
  fallbackName: string
) => {
  const candidate = response as { data?: Blob } | Blob
  const blob = candidate instanceof Blob ? candidate : candidate?.data
  if (!(blob instanceof Blob)) {
    throw new Error('下载响应不是有效文件')
  }

  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fallbackName
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}


// ==================== AI Agent API ====================

export const auditAIApi = {
  // AI 审核准备建议（普通）
  prepareAudit: (projectId: string) => 
    api.post(`/api/audit-projects/${projectId}/ai/prepare`),

  // AI 审核准备建议（流式 SSE）
  prepareAuditStream: async function* (
    projectId: string,
    signal?: AbortSignal
  ): AsyncGenerator<{ type: string; content?: string; full_content?: string }> {
    const token = useAuthStore.getState().token
    const response = await fetch(
      `${API_BASE_URL}/api/audit-projects/${projectId}/ai/prepare/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        signal,
      }
    )
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            yield JSON.parse(line.slice(6))
          } catch {
            // ignore JSON parse error
          }
        }
      }
    }
  },
  
  // AI 证据充分性评估
  evaluateEvidence: (projectId: string, data: {
    evidence: string
    clause_no: string
    certification_system: string
  }) => 
    api.post(`/api/audit-projects/${projectId}/ai/evaluate-evidence`, null, {
      params: data
    }),
  
  // AI 生成审核报告（普通）
  generateReport: (projectId: string) => 
    api.post(`/api/audit-projects/${projectId}/ai/generate-report`),

  // AI 生成审核报告（流式 SSE）
  generateReportStream: async function* (
    projectId: string,
    signal?: AbortSignal
  ): AsyncGenerator<{ type: string; content?: string; full_content?: string }> {
    const token = useAuthStore.getState().token
    const response = await fetch(
      `${API_BASE_URL}/api/audit-projects/${projectId}/ai/generate-report/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        signal,
      }
    )
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            yield JSON.parse(line.slice(6))
          } catch {
            // ignore JSON parse error
          }
        }
      }
    }
  },
  
  // AI 建议不符合项
  suggestNC: (projectId: string, data: {
    evidence: string
    clause_no: string
    certification_system: string
  }) => 
    api.post(`/api/audit-projects/${projectId}/ai/suggest-nc`, null, {
      params: data
    }),
}

