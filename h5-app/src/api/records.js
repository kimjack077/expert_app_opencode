import request from './request.js'

/**
 * 检查记录 API
 */

// 获取检查记录列表
export const getRecords = (params) => {
  // 将 page 参数转换为 skip (后端期望的参数)
  const { page, limit, ...rest } = params || {}
  const skip = page && limit ? (page - 1) * limit : 0
  return request.get('/records', {
    params: {
      skip,
      limit: limit || 20,
      ...rest
    }
  })
}

// 获取记录详情
export const getRecord = (id, config) => {
  return request.get(`/records/${id}`, config)
}

// 创建检查记录
export const createRecord = (data) => {
  return request.post('/records', data)
}

// 更新检查记录（用于保存最终判定等）
export const updateRecord = (id, data) => {
  return request.put(`/records/${id}`, data)
}

// 提交检查记录
export const submitRecord = (id) => {
  return request.post(`/records/${id}/submit`)
}

// 获取记录的检查项列表
export const getRecordItems = (recordId, config) => {
  return request.get(`/records/${recordId}/items`, config)
}

// 获取单个检查项详情
export const getRecordItem = (recordId, itemId, config) => {
  return request.get(`/records/${recordId}/items/${itemId}`, config)
}

// 创建/更新记录项（快速检查使用）
export const createOrUpdateRecordItem = (recordId, data) => {
  return request.post(`/records/${recordId}/items`, data)
}

// 创建/更新记录项
export const createRecordItem = (recordId, data) => {
  return request.post(`/records/${recordId}/items`, data)
}

// 更新记录项
export const updateRecordItem = (recordId, itemId, data) => {
  return request.put(`/records/${recordId}/items/${itemId}`, data)
}

// AI生成建议
export const generateAISuggestion = (recordId, itemId) => {
  return request.post(`/records/${recordId}/items/${itemId}/ai`)
}

// 采纳AI建议
export const acceptAISuggestion = (recordId, itemId) => {
  return request.post(`/records/${recordId}/items/${itemId}/accept-ai`)
}

// 获取模板列表（用于选择模板）
export const getTemplates = (params) => {
  const { page, limit, ...rest } = params || {}
  const skip = page && limit ? (page - 1) * limit : 0
  return request.get('/templates', {
    params: {
      skip,
      limit: limit || 20,
      ...rest
    }
  })
}

// 获取企业列表
export const getEnterprises = (params) => {
  // 将 page 参数转换为 skip (后端期望的参数)
  const { page, limit, ...rest } = params || {}
  const skip = page && limit ? (page - 1) * limit : 0
  return request.get('/enterprises', {
    params: {
      skip,
      limit: limit || 20,
      ...rest
    }
  })
}

// 获取企业详情
export const getEnterprise = (enterpriseId) => {
  return request.get(`/enterprises/${enterpriseId}`)
}

// 获取企业风险画像
export const getEnterpriseRiskProfile = (enterpriseId) => {
  return request.get(`/enterprises/${enterpriseId}/risk-profile`)
}