import request from './request.js'

export const getTasks = (params) => {
  return request.get('/tasks', { params })
}

export const getTask = (id) => {
  return request.get(`/tasks/${id}`)
}

export const createTask = (data) => {
  return request.post('/tasks', data)
}

export const updateTask = (id, data) => {
  return request.put(`/tasks/${id}`, data)
}

export const deleteTask = (id) => {
  return request.delete(`/tasks/${id}`)
}

// 获取模板的检查项目
export const getTemplateItems = (templateId) => {
  return request.get(`/templates/${templateId}`)
}

// 提交检查记录
export const submitCheckRecord = (taskId, data) => {
  return request.post(`/tasks/${taskId}/records`, data)
}

// 获取检查记录
export const getTaskRecords = (taskId) => {
  return request.get(`/tasks/${taskId}/records`)
}
