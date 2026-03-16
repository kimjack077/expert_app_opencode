import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.reload()
    }
    return Promise.reject(error)
  }
)

// 认证相关
export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
}

// 任务相关
export const taskApi = {
  getMyTasks: (params?: { status?: string }) =>
    api.get('/tasks', { params }),
  getTaskDetail: (id: string) =>
    api.get(`/tasks/${id}`),
  startTask: (id: string) =>
    api.post(`/tasks/${id}/start`),
  completeTask: (id: string) =>
    api.post(`/tasks/${id}/complete`),
}

// 检查记录相关
export const recordApi = {
  getRecords: (taskId: string) =>
    api.get(`/tasks/${taskId}/records`),
  updateRecord: (recordId: string, data: any) =>
    api.put(`/tasks/records/${recordId}`, data),
  uploadPhoto: (recordId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/tasks/records/${recordId}/photos`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

// AI相关
export const aiApi = {
  getSuggestion: (recordId: string) =>
    api.post('/llm/suggestion', { record_id: recordId }),
  getLegalBasis: (recordId: string) =>
    api.post('/llm/legal-basis', { record_id: recordId }),
}

export default api
