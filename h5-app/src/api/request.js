import axios from 'axios'
import { showToast } from 'vant'

// 生产构建留空 = 同源（nginx 反代 /api）；开发环境 .env.development 指向 8000。
// 注意不能用 `|| 'http://localhost:8000'`：空串会被兜底成本机地址，
// 手机端访问时就发到手机自己身上了。
const API_BASE_URL =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : 'http://localhost:8000'

const request = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: false,
})

// 刷新失败后的统一退场：清 token、跳登录页（axios 拦截器与 fetch 流式共用）
const forceRelogin = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
  setTimeout(() => {
    window.location.href = '/h5/login'
  }, 100)
  try {
    showToast({ type: 'fail', message: '登录已过期，请重新登录' })
  } catch (e) {
    console.error('Toast error:', e)
  }
}

/**
 * 单飞刷新 access token：axios 拦截器与原生 fetch 流式调用共享同一刷新请求，
 * 并发 401 只会触发一次 /auth/refresh。
 */
export const refreshAccessToken = () => {
  refreshingPromise = refreshingPromise || tryRefreshToken()
  return refreshingPromise.finally(() => {
    refreshingPromise = null
  })
}

/**
 * 原生 fetch（SSE 流式）调用的 401 自动续期。
 * buildRequest(token) 负责构造并发起请求；收到 401 时刷新 token 并用新 token
 * 重试一次；刷新失败按拦截器同样方式清登录态并跳登录页，返回 null。
 */
export const fetchWithTokenRetry = async (buildRequest) => {
  const response = await buildRequest(localStorage.getItem('token'))
  if (response.status !== 401) return response
  const newToken = await refreshAccessToken()
  if (!newToken) {
    forceRelogin()
    return null
  }
  return buildRequest(newToken)
}

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
// BUG-38：新增 401 自动刷新机制。此前 access_token 过期只会清 token 跳登录，
// 现场审核员会被强制退出。现在先用 refresh_token 续期并重试原请求，失败才登出。
let refreshingPromise = null

async function tryRefreshToken() {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return null
  try {
    // 用原生 axios 避免递归经过本拦截器；后端同时支持 body 与 query 传参
    const res = await axios.post(`${API_BASE_URL}/api/auth/refresh`, null, {
      params: { refresh_token: refreshToken },
      timeout: 15000,
    })
    const data = res.data?.data || {}
    if (!data.access_token) return null
    localStorage.setItem('token', data.access_token)
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token)
    }
    return data.access_token
  } catch (e) {
    return null
  }
}

request.interceptors.response.use(
  (response) => {
    return response.data
  },
  async (error) => {
    if (error.response) {
      const { status, data, config } = error.response
      if (status === 401) {
        // 单飞刷新：并发 401 只触发一次刷新请求
        if (!config?._retried) {
          const newToken = await refreshAccessToken()
          if (newToken) {
            config._retried = true
            config.headers = config.headers || {}
            config.headers.Authorization = `Bearer ${newToken}`
            return request(config)
          }
        }
        forceRelogin()
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
