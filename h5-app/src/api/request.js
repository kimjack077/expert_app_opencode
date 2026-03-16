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
      } else {
        try {
          showToast({ type: 'fail', message: data.detail || '请求失败' })
        } catch (e) {
          console.error('Toast error:', e)
        }
      }
    } else {
      console.error('网络错误:', error.message)
      try {
        showToast({ type: 'fail', message: '网络错误' })
      } catch (e) {
        console.error('Toast error:', e)
      }
    }
    return Promise.reject(error)
  }
)

export default request
