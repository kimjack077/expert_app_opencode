import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const API_BASE_URL = import.meta.env.VITE_API_URL !== undefined ? import.meta.env.VITE_API_URL : 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL ? `${API_BASE_URL}/api` : '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

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

export default api

/** 智审 Agent 主动提醒（复审到期 / NC 超期 / 草稿积压，由后端定时巡检生成） */
export const notificationApi = {
  list: (status: 'unread' | 'read' | 'all' = 'unread') =>
    api.get('/agent/notifications', { params: { status } }),
  update: (id: string, status: 'read' | 'dismissed' | 'unread') =>
    api.put(`/agent/notifications/${id}`, { status }),
}

export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  logout: () => api.post('/auth/logout'),
  getMe: () => api.get('/auth/me'),
  changePassword: (old_password: string, new_password: string) =>
    api.put('/auth/me/password', { old_password, new_password }),
}

export const templateApi = {
  // 模板管理
  getTemplates: (params?: any) => api.get('/templates', { params }),
  getTemplate: (id: string) => api.get(`/templates/${id}`),
  createTemplate: (data: any) => api.post('/templates', data),
  updateTemplate: (id: string, data: any) => api.put(`/templates/${id}`, data),
  deleteTemplate: (id: string) => api.delete(`/templates/${id}`),
  publishTemplate: (id: string) => api.post(`/templates/${id}/publish`),
  copyTemplate: (id: string, name?: string) => {
    const params = name ? { name } : {};
    return api.post(`/templates/${id}/copy`, null, { params });
  },

  // 检查项目管理
  createItem: (templateId: string, data: any) =>
    api.post(`/templates/${templateId}/items`, data),
  updateItem: (itemId: string, data: any) =>
    api.put(`/templates/items/${itemId}`, data),
  reorderItems: (templateId: string, data: { item_id: string; parent_id: string | null; position: number }) =>
    api.put(`/templates/${templateId}/items/reorder`, data),
  deleteItem: (itemId: string) =>
    api.delete(`/templates/items/${itemId}`),
}

export const taskApi = {
  getTasks: (params?: any) => api.get('/tasks', { params }),
  getTask: (id: string) => api.get(`/tasks/${id}`),
  createTask: (data: any) => api.post('/tasks', data),
  updateTask: (id: string, data: any) => api.put(`/tasks/${id}`, data),
  deleteTask: (id: string) => api.delete(`/tasks/${id}`),
  startTask: (id: string) => api.post(`/tasks/${id}/start`),
  completeTask: (id: string) => api.post(`/tasks/${id}/complete`),
  cancelTask: (id: string) => api.post(`/tasks/${id}/cancel`),

  getTaskRecords: (taskId: string) => api.get(`/tasks/${taskId}/records`),
  createRecord: (taskId: string, data: any) => api.post(`/tasks/${taskId}/records`, data),
  updateRecord: (recordId: string, data: any) => api.put(`/tasks/records/${recordId}`, data),
  getTaskSummary: (taskId: string) => api.get(`/tasks/${taskId}/summary`),
}

export const mediaApi = {
  upload: (file: File, options?: { task_id?: string; record_id?: string }) => {
    const formData = new FormData()
    formData.append('file', file)
    if (options?.task_id) formData.append('task_id', options.task_id)
    if (options?.record_id) formData.append('record_id', options.record_id)
    return api.post('/media/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteMedia: (id: string) => api.delete(`/media/${id}`),
}

export const llmApi = {
  getSuggestion: (data: { task_id: string; record_id: string; use_cache?: boolean }) =>
    api.post('/llm/suggestion', data),
  getBasis: (data: { task_id: string; record_id: string; use_cache?: boolean }) =>
    api.post('/llm/basis', data),
}

export const analyticsApi = {
  getDashboard: () => api.get('/analytics/dashboard'),
  getAuditLogs: (params?: any) => api.get('/analytics/audit-logs', { params }),
  getLLMLogs: (params?: any) => api.get('/analytics/llm-logs', { params }),
  getTrends: (params?: any) => api.get('/analytics/trends', { params }),
  getEnterpriseRisk: () => api.get('/analytics/enterprise-risk'),
  exportData: (params?: any) => api.get('/analytics/export', { params }),
}

export const enterpriseApi = {
  getEnterprises: (params?: any) => api.get('/enterprises', { params }),
  getEnterprise: (id: string) => api.get(`/enterprises/${id}`),
  /** 企业风险档案（真实统计：检查次数/不合格/待整改/NC） */
  getRiskProfile: (id: string) => api.get(`/enterprises/${id}/risk-profile`),
  createEnterprise: (data: any) => api.post('/enterprises', data),
  updateEnterprise: (id: string, data: any) => api.put(`/enterprises/${id}`, data),
  deleteEnterprise: (id: string) => api.delete(`/enterprises/${id}`),

  getQualifications: (enterpriseId: string) => api.get(`/enterprises/${enterpriseId}/qualifications`),
  createQualification: (enterpriseId: string, data: any) =>
    api.post(`/enterprises/${enterpriseId}/qualifications`, data),
  updateQualification: (qualId: string, data: any) =>
    api.put(`/enterprises/qualifications/${qualId}`, data),
  deleteQualification: (qualId: string) =>
    api.delete(`/enterprises/qualifications/${qualId}`),

  getProducts: (enterpriseId: string) => api.get(`/enterprises/${enterpriseId}/products`),
  createProduct: (enterpriseId: string, data: any) =>
    api.post(`/enterprises/${enterpriseId}/products`, data),
  updateProduct: (enterpriseId: string, productId: string, data: any) =>
    api.put(`/enterprises/${enterpriseId}/products/${productId}`, data),
  deleteProduct: (enterpriseId: string, productId: string) =>
    api.delete(`/enterprises/${enterpriseId}/products/${productId}`),


  getRectifications: (enterpriseId: string) =>
    api.get('/enterprises/rectifications/', { params: { enterprise_id: enterpriseId, limit: 100 } }),
  createRectification: (enterpriseId: string, data: any) =>
    api.post('/enterprises/rectifications/', { ...data, enterprise_id: enterpriseId }),
  updateRectification: (rectId: string, data: any) =>
    api.put(`/enterprises/rectifications/${rectId}`, data),
  reviewRectification: (rectId: string, data: { status: string; rectification_result?: string }) =>
    api.post(`/enterprises/rectifications/${rectId}/review`, data),
}

export const knowledgeApi = {
  getDocuments: (params?: any) => api.get('/knowledge/documents', { params }),
  getDocument: (id: string) => api.get(`/knowledge/documents/${id}`),
  createDocument: (data: any) => api.post('/knowledge/documents', data),
  updateDocument: (id: string, data: any) => api.put(`/knowledge/documents/${id}`, data),
  deleteDocument: (id: string) => api.delete(`/knowledge/documents/${id}`),

  /** 第一阶段：解析文件，返回 Markdown 预览（不写 DB） */
  parseDocument: (data: FormData) => api.post('/knowledge/documents/parse', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  }),

  /** 第二阶段：流式建立向量索引，返回 AsyncGenerator<SSE 事件> */
  indexDocumentStream: async function* (formData: FormData): AsyncGenerator<any> {
    const token = useAuthStore.getState().token
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 10 * 60 * 1000)

    try {
      const response = await fetch('/api/knowledge/documents/index', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('No reader available')

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
            } catch (e) {
              console.error('Failed to parse SSE data:', e)
            }
          }
        }
      }
    } finally {
      clearTimeout(timeoutId)
    }
  },

  getGuidelines: (params?: any) => api.get('/knowledge/guidelines', { params }),
  createGuideline: (data: any) => api.post('/knowledge/guidelines', data),
  updateGuideline: (id: string, data: any) => api.put(`/knowledge/guidelines/${id}`, data),
  deleteGuideline: (id: string) => api.delete(`/knowledge/guidelines/${id}`),
}


export const recordApi = {
  // 检查记录管理
  getRecords: (params?: any) => api.get('/records', { params }),
  getRecord: (id: string) => api.get(`/records/${id}`),
  createRecord: (data: any) => api.post('/records', data),
  updateRecord: (id: string, data: any) => api.put(`/records/${id}`, data),
  submitRecord: (id: string) => api.post(`/records/${id}/submit`),
  deleteRecord: (id: string) => api.delete(`/records/${id}`),

  // 记录检查项
  getRecordItems: (recordId: string) => api.get(`/records/${recordId}/items`),
  createRecordItem: (recordId: string, data: any) => api.post(`/records/${recordId}/items`, data),
  // 后端没有 PUT /items/{id}，POST /items 本身是按 id/template_item_id 匹配的 upsert
  updateRecordItem: (recordId: string, itemId: string, data: any) =>
    api.post(`/records/${recordId}/items`, { id: itemId, ...data }),
  correctSubmittedRecordItem: (recordId: string, itemId: string, data: any) =>
    api.patch(`/records/${recordId}/items/${itemId}/correction`, data),
  getItemHistoryStats: (recordId: string, itemId: string) =>
    api.get(`/records/${recordId}/items/${itemId}/history-stats`),

  // 报告相关
  getRecordReport: (recordId: string) => api.get(`/records/${recordId}/report`),
  downloadRecordReport: (recordId: string) =>
    api.get(`/records/${recordId}/report/pdf`, { responseType: 'blob' }),
}

export const aiExtractApi = {
  extractItemsStream: async function* (
    file: File,
    onStatus?: (status: string) => void
  ): AsyncGenerator<any> {
    const formData = new FormData()
    formData.append('file', file)

    const token = useAuthStore.getState().token
    // 总超时兜底：15 分钟（覆盖整个流式读取过程）
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 15 * 60 * 1000)

    try {
      const response = await fetch('/api/ai-extract/extract/stream', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('No reader available')
      }

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
              const data = JSON.parse(line.slice(6))
              if (data.type === 'status' && onStatus) {
                onStatus(data.message)
              }
              yield data
            } catch (e) {
              console.error('Failed to parse SSE data:', e)
            }
          }
        }
      }
    } finally {
      clearTimeout(timeoutId)
    }
  },
  applyItems: (templateId: string, items: any[]) =>
    api.post(`/ai-extract/apply/${templateId}`, items),
  refineItemsStream: async function* (
    items: any[],
    instruction: string
  ): AsyncGenerator<any> {
    const token = useAuthStore.getState().token
    // 总超时兜底：15 分钟（覆盖整个流式精修过程）
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 15 * 60 * 1000)

    try {
      const response = await fetch('/api/ai-extract/refine/stream', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ items, instruction }),
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('No reader available')
      }

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
            } catch (e) {
              console.error('Failed to parse SSE data:', e)
            }
          }
        }
      }
    } finally {
      clearTimeout(timeoutId)
    }
  },
}

export const industryApi = {
  getTree: (params?: any) => api.get('/industries/tree', { params }),
  getIndustries: (params?: any) => api.get('/industries', { params }),
  createIndustry: (data: any) => api.post('/industries', data),
  updateIndustry: (id: string, data: any) => api.put(`/industries/${id}`, data),
  deleteIndustry: (id: string) => api.delete(`/industries/${id}`),
}

export const userApi = {
  getUsers: (params?: any) => api.get('/users', { params }),
  // 轻量选员列表：所有登录用户可用（GET /users 仅管理员），返回 {id,username,full_name,role}
  getUserOptions: (params?: any) => api.get('/users/options', { params }),
  createUser: (data: any) => api.post('/users', data),
  updateUser: (id: string, data: any) => api.put(`/users/${id}`, data),
  deleteUser: (id: string) => api.delete(`/users/${id}`),
}

export const statisticsApi = {
  // 项目概览统计
  getOverview: () => api.get('/statistics/overview'),

  // 项目分布统计
  getProjectDistribution: (params?: { by?: 'status' | 'type' }) =>
    api.get('/statistics/projects/distribution', { params }),

  // 项目趋势统计
  getProjectTrend: (params?: { months?: number }) =>
    api.get('/statistics/projects/trend', { params }),

  // 不符合项严重程度分布
  getNCDistribution: (params?: { project_id?: string }) =>
    api.get('/statistics/nonconformities/distribution', { params }),

  // 不符合项按体系分布
  getNCBySystem: (params?: { project_id?: string }) =>
    api.get('/statistics/nonconformities/by-system', { params }),

  // 不符合项按条款TOP N
  getNCByClause: (params?: { project_id?: string; limit?: number }) =>
    api.get('/statistics/nonconformities/by-clause', { params }),

  // 不符合项趋势统计
  getNCTrend: (params?: { months?: number }) =>
    api.get('/statistics/nonconformities/trend', { params }),

  // 审核员工作量统计
  getAuditorWorkload: (params?: { project_id?: string }) =>
    api.get('/statistics/auditors/workload', { params }),

  // 审核员排名
  getAuditorRanking: (params?: { metric?: 'projects' | 'areas' | 'ncs'; limit?: number }) =>
    api.get('/statistics/auditors/ranking', { params }),
}