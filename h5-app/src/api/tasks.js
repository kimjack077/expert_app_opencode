import request from './request.js'

export const getTasks = (params) => {
  // 将 page/page_size 参数转换为 skip/limit (后端期望的参数)
  const { page, page_size, limit, ...rest } = params || {}
  const effectiveLimit = limit || page_size || 20
  const skip = page ? (page - 1) * effectiveLimit : 0
  return request.get('/tasks', {
    params: {
      skip,
      limit: effectiveLimit,
      ...rest
    }
  })
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

export const startTask = (id) => {
  return request.post(`/tasks/${id}/start`)
}

export const completeTask = (id) => {
  return request.post(`/tasks/${id}/complete`)
}

// 获取模板的检查项目
export const getTemplateItems = (templateId) => {
  return request.get(`/templates/${templateId}`)
}

// 提交/更新任务检查项结果（与 Web 端同一条任务数据链）
export const submitCheckRecord = (taskId, data) => {
  return request.post(`/tasks/${taskId}/records`, data)
}

// 获取任务检查项记录
export const getTaskRecords = (taskId) => {
  return request.get(`/tasks/${taskId}/records`)
}
