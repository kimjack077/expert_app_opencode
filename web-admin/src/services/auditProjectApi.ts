import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
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
  create: (data: any) => api.post('/api/v1/audit-projects', data),
  
  // 获取审核项目列表
  list: (params?: any) => api.get('/api/v1/audit-projects', { params }),
  
  // 获取审核项目详情
  get: (id: string) => api.get(`/api/v1/audit-projects/${id}`),
  
  // 更新审核项目
  update: (id: string, data: any) => api.put(`/api/v1/audit-projects/${id}`, data),
  
  // 删除审核项目
  delete: (id: string) => api.delete(`/api/v1/audit-projects/${id}`),
  
  // 获取项目进度
  getProgress: (id: string) => api.get(`/api/v1/audit-projects/${id}/progress`),
}

// ==================== 审核组成员 API ====================

export const auditTeamApi = {
  // 添加审核组成员
  add: (projectId: string, data: any) => 
    api.post(`/api/v1/audit-projects/${projectId}/team`, data),
  
  // 获取审核组成员列表
  list: (projectId: string) => 
    api.get(`/api/v1/audit-projects/${projectId}/team`),
  
  // 更新审核组成员
  update: (memberId: string, data: any) => 
    api.put(`/api/v1/audit-projects/team/${memberId}`, data),
  
  // 移除审核组成员
  remove: (memberId: string) => 
    api.delete(`/api/v1/audit-projects/team/${memberId}`),
}

// ==================== 审核计划 API ====================

export const auditPlanApi = {
  // 创建审核计划项
  create: (projectId: string, data: any) => 
    api.post(`/api/v1/audit-projects/${projectId}/plan`, data),
  
  // 获取审核计划项列表
  list: (projectId: string, params?: any) => 
    api.get(`/api/v1/audit-projects/${projectId}/plan`, { params }),
  
  // 获取审核计划项详情
  get: (planItemId: string) => 
    api.get(`/api/v1/audit-projects/plan/${planItemId}`),
  
  // 更新审核计划项
  update: (planItemId: string, data: any) => 
    api.put(`/api/v1/audit-projects/plan/${planItemId}`, data),
  
  // 删除审核计划项
  delete: (planItemId: string) => 
    api.delete(`/api/v1/audit-projects/plan/${planItemId}`),
}

// ==================== 审核记录 API ====================

export const auditRecordApi = {
  // 创建审核区域记录
  create: (projectId: string, data: any) => 
    api.post(`/api/v1/audit-projects/${projectId}/records`, data),
  
  // 获取审核区域记录列表
  list: (projectId: string, params?: any) => 
    api.get(`/api/v1/audit-projects/${projectId}/records`, { params }),
  
  // 获取审核区域记录详情
  get: (recordId: string) => 
    api.get(`/api/v1/audit-projects/records/${recordId}`),
  
  // 更新审核区域记录
  update: (recordId: string, data: any) => 
    api.put(`/api/v1/audit-projects/records/${recordId}`, data),
}

// ==================== 不符合项 API ====================

export const nonconformityApi = {
  // 创建不符合项
  create: (projectId: string, data: any) => 
    api.post(`/api/v1/audit-projects/${projectId}/nonconformities`, data),
  
  // 获取不符合项列表
  list: (projectId: string, params?: any) => 
    api.get(`/api/v1/audit-projects/${projectId}/nonconformities`, { params }),
  
  // 更新不符合项
  update: (ncId: string, data: any) => 
    api.put(`/api/v1/audit-projects/nonconformities/${ncId}`, data),
}

// ==================== 审核报告 API ====================

export const auditReportApi = {
  // 创建审核报告
  create: (projectId: string, data: any) => 
    api.post(`/api/v1/audit-projects/${projectId}/report`, data),
  
  // 获取审核报告列表
  list: (projectId: string) => 
    api.get(`/api/v1/audit-projects/${projectId}/report`),
  
  // 更新审核报告
  update: (reportId: string, data: any) => 
    api.put(`/api/v1/audit-projects/report/${reportId}`, data),
  
  // 导出 Word 格式报告
  exportWord: (projectId: string) => {
    const token = useAuthStore.getState().token
    window.open(
      `${API_BASE_URL}/api/v1/audit-projects/${projectId}/export/word?token=${token}`,
      '_blank'
    )
  },

  // 导出 PDF 格式报告
  exportPdf: (projectId: string) => {
    const token = useAuthStore.getState().token
    window.open(
      `${API_BASE_URL}/api/v1/audit-projects/${projectId}/export/pdf?token=${token}`,
      '_blank'
    )
  },
}

// ==================== 沟通会议 API ====================

export const meetingApi = {
  // 创建沟通会议记录
  create: (projectId: string, data: any) => 
    api.post(`/api/v1/audit-projects/${projectId}/meetings`, data),
  
  // 获取沟通会议记录列表
  list: (projectId: string, params?: any) => 
    api.get(`/api/v1/audit-projects/${projectId}/meetings`, { params }),
  
  // 更新沟通会议记录
  update: (meetingId: string, data: any) => 
    api.put(`/api/v1/audit-projects/meetings/${meetingId}`, data),
}

// ==================== 我的任务 API ====================

export const myTasksApi = {
  // 获取我的审核任务列表
  list: (params?: any) => 
    api.get('/api/v1/audit-projects/my-tasks', { params }),
}


// ==================== AI Agent API ====================

export const auditAIApi = {
  // AI 审核准备建议
  prepareAudit: (projectId: string) => 
    api.post(`/api/v1/audit-projects/${projectId}/ai/prepare`),
  
  // AI 证据充分性评估
  evaluateEvidence: (projectId: string, data: {
    evidence: string
    clause_no: string
    certification_system: string
  }) => 
    api.post(`/api/v1/audit-projects/${projectId}/ai/evaluate-evidence`, null, {
      params: data
    }),
  
  // AI 生成审核报告
  generateReport: (projectId: string) => 
    api.post(`/api/v1/audit-projects/${projectId}/ai/generate-report`),
  
  // AI 建议不符合项
  suggestNC: (projectId: string, data: {
    evidence: string
    clause_no: string
    certification_system: string
  }) => 
    api.post(`/api/v1/audit-projects/${projectId}/ai/suggest-nc`, null, {
      params: data
    }),
}
