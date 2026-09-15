import axios from 'axios'
import { showToast } from 'vant'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const request = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: false,
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type']
    }
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 后端部分接口直接抛出英文技术文案（如 "Enterprise not found"、"Task not found"），
// 直接透传给审核员既看不懂也不专业。这里做一层收敛：
// 后端返回的中文提示（业务校验信息，如「请先填写最终判定结论」）原样展示，
// 英文/缺失/结构异常的 detail 一律降级为按状态码的通用中文文案。
const CN_TEXT_RE = /[\u4e00-\u9fa5]/

const FALLBACK_BY_STATUS = {
  400: '请求参数有误，请检查后重试',
  403: '没有权限执行该操作',
  404: '请求的数据不存在或已被删除',
  409: '数据状态已变化，请刷新后重试',
  422: '提交内容不完整，请检查后重试',
  500: '服务异常，请稍后重试',
  502: '服务暂时不可用，请稍后重试',
  503: '服务暂时不可用，请稍后重试',
}

const toFriendlyMessage = (status, detail) => {
  if (typeof detail === 'string' && CN_TEXT_RE.test(detail)) {
    return detail
  }
  // FastAPI 的参数校验错误：detail 是数组，原实现会显示成 [object Object]
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0]
    if (first && typeof first.msg === 'string' && CN_TEXT_RE.test(first.msg)) {
      return first.msg
    }
  }
  return FALLBACK_BY_STATUS[status] || '请求失败，请稍后重试'
}

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        localStorage.removeItem('token')
        // 延迟跳转，避免在拦截器中直接操作DOM
        setTimeout(() => {
          window.location.href = '/h5/login'
        }, 100)
        try {
          showToast({ type: 'fail', message: '登录已过期，请重新登录' })
        } catch (e) {
          console.error('Toast error:', e)
        }
      } else if (!error.config?.skipErrorToast) {
        try {
          showToast({ type: 'fail', message: toFriendlyMessage(status, data?.detail) })
        } catch (e) {
          console.error('Toast error:', e)
        }
      }
    } else {
      console.error('网络错误:', error.message)
      try {
        if (!error.config?.skipErrorToast) {
          showToast({ type: 'fail', message: '网络连接失败，请检查网络' })
        }
      } catch (e) {
        console.error('Toast error:', e)
      }
    }
    return Promise.reject(error)
  }
)

export default request
