<template>
  <div class="login-page">
    <div class="login-header">
      <div class="header-bg"></div>
      <div class="logo-container">
        <div class="logo-glow"></div>
        <div class="logo">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            <path d="m9 12 2 2 4-4"/>
          </svg>
        </div>
      </div>
      <h1 class="title">专家检查系统</h1>
      <p class="subtitle">Expert Field Inspection System</p>
      <div class="badges">
        <span class="badge">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
          专业认证
        </span>
        <span class="badge accent">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          安全可靠
        </span>
      </div>
    </div>

    <div class="login-form-container">
      <div class="form-card">
        <div class="form-header">
          <h2 class="form-title">欢迎登录</h2>
          <p class="form-subtitle">请使用您的账号密码登录系统</p>
        </div>
        
        <van-form class="login-form">
          <div class="input-group">
            <van-field
              v-model="form.username"
              name="username"
              placeholder="请输入用户名"
              :rules="[{ required: true, message: '请填写用户名' }]"
              class="custom-field"
            >
              <template #left-icon>
                <div class="input-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                  </svg>
                </div>
              </template>
            </van-field>
          </div>
          
          <div class="input-group">
            <van-field
              v-model="form.password"
              type="password"
              name="password"
              placeholder="请输入密码"
              :rules="[{ required: true, message: '请填写密码' }]"
              class="custom-field"
              @keyup.enter="onSubmit"
            >
              <template #left-icon>
                <div class="input-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                  </svg>
                </div>
              </template>
            </van-field>
          </div>

          <div class="form-options">
            <van-checkbox v-model="rememberMe" shape="round" icon-size="16">
              记住我
            </van-checkbox>
            <a href="#" class="forgot-link">忘记密码?</a>
          </div>

          <van-button
            block
            type="primary"
            :loading="loading"
            loading-text="登录中..."
            class="submit-btn"
            @click="onSubmit"
          >
            <span class="btn-text">登录</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="btn-icon">
              <path d="M5 12h14"/>
              <path d="m12 5 7 7-7 7"/>
            </svg>
          </van-button>
        </van-form>
      </div>
    </div>

    <div class="login-footer">
      <div class="security-info">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
        <span>SSL 安全加密传输</span>
      </div>
      <p class="copyright">© 2024 专家检查系统 · 专业现场工作辅助平台</p>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { login } from '../api/auth.js'

const router = useRouter()
const loading = ref(false)
const rememberMe = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const onSubmit = async () => {
  if (!form.username || !form.password) {
    showToast({ type: 'fail', message: '请填写用户名和密码' })
    return
  }
  
  loading.value = true
  try {
    console.log('开始登录，用户名:', form.username)
    console.log('请求数据:', JSON.stringify({ username: form.username, password: '***' }))
    
    const res = await login(form)
    
    console.log('登录响应完整数据:', JSON.stringify(res))
    console.log('响应状态码:', res.code)
    console.log('响应消息:', res.message)
    
    const token = res.data?.access_token
    const refreshToken = res.data?.refresh_token
    console.log('获取到的 token:', token ? token.substring(0, 50) + '...' : 'null')
    
    if (token) {
      localStorage.setItem('token', token)
      if (refreshToken) {
        localStorage.setItem('refresh_token', refreshToken)
      }
      if (rememberMe.value) {
        localStorage.setItem('rememberedUsername', form.username)
      }
      showToast({ type: 'success', message: '登录成功', duration: 1000 })
      console.log('页面跳转开始')
      setTimeout(() => {
        router.push('/home')
        console.log('页面跳转完成')
      }, 500)
    } else {
      console.error('未获取到 token，响应数据:', res)
      throw new Error('登录失败：未获取到 token')
    }
  } catch (error) {
    console.error('登录失败:', error)
    console.error('错误详情:', error.response?.data || error.message)
    
    let errorMsg = '登录失败'
    if (error.response) {
      errorMsg = error.response.data?.detail || error.response.data?.message || errorMsg
      console.error('后端错误:', error.response.data)
    } else if (error.request) {
      console.error('网络错误：请求已发送但未收到响应')
      console.error('请求配置:', error.config)
      errorMsg = '网络连接失败，请检查后端服务是否启动'
    } else {
      errorMsg = error.message || errorMsg
    }
    
    showToast({ type: 'fail', message: errorMsg, duration: 2000 })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto 1fr auto;
  background: var(--bg-white);
  position: relative;
  overflow: hidden;
}

.login-page::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 156px;
  background: var(--primary-gradient-dark);
  pointer-events: none;
}

.login-page::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 156px;
  background: 
    radial-gradient(circle at 10% 20%, rgba(255, 255, 255, 0.08) 0%, transparent 40%),
    radial-gradient(circle at 90% 70%, rgba(56, 189, 248, 0.15) 0%, transparent 40%);
  pointer-events: none;
}

.login-header {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  grid-template-rows: auto auto auto;
  align-items: center;
  column-gap: 12px;
  padding: calc(env(safe-area-inset-top) + 18px) 20px 28px;
  color: var(--bg-white);
  position: relative;
  z-index: 1;
}

.header-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: 
    radial-gradient(circle at 30% 40%, rgba(56, 189, 248, 0.1) 0%, transparent 50%);
  pointer-events: none;
}

.logo-container {
  position: relative;
  grid-column: 1;
  grid-row: 1 / 3;
  margin: 0;
}

.logo-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 76px;
  height: 76px;
  background: radial-gradient(circle, rgba(14, 165, 233, 0.25) 0%, transparent 70%);
  border-radius: 50%;
  animation: pulse 3s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { 
    transform: translate(-50%, -50%) scale(1); 
    opacity: 0.5; 
  }
  50% { 
    transform: translate(-50%, -50%) scale(1.12); 
    opacity: 0.25; 
  }
}

.logo {
  width: 52px;
  height: 52px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  position: relative;
  z-index: 1;
  backdrop-filter: blur(10px);
}

.logo svg {
  color: var(--primary-color);
  width: 30px;
  height: 30px;
}

.title {
  grid-column: 2;
  grid-row: 1;
  align-self: end;
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 2px;
  letter-spacing: 1px;
  font-family: var(--font-primary);
}

.subtitle {
  grid-column: 2;
  grid-row: 2;
  align-self: start;
  font-size: 11px;
  opacity: 0.75;
  margin: 0;
  letter-spacing: 0.5px;
  font-weight: 400;
}

.badges {
  grid-column: 1 / 3;
  grid-row: 3;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 10px;
}

.badge {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 28px;
  padding: 0 10px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.badge.accent {
  background: rgba(14, 165, 233, 0.18);
  border-color: rgba(14, 165, 233, 0.3);
}

.login-form-container {
  position: relative;
  z-index: 2;
  padding: 0 20px;
  margin-top: -18px;
}

.form-card {
  background: var(--bg-white);
  border-radius: 24px;
  padding: 32px 24px;
  box-shadow: var(--shadow-xl);
  border: 1px solid var(--border-light);
}

.form-header {
  text-align: center;
  margin-bottom: 28px;
}

.form-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 6px;
  font-family: var(--font-primary);
  letter-spacing: -0.5px;
}

.form-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
}

.input-group {
  margin-bottom: 14px;
}

.custom-field {
  background: var(--bg-light);
  border-radius: 14px;
  overflow: hidden;
  border: 2px solid transparent;
  transition: all var(--transition-base);
}

.custom-field:focus-within {
  border-color: var(--primary-color);
  background: var(--bg-white);
}

.custom-field :deep(.van-field__body) {
  padding: 6px 0;
}

.custom-field :deep(.van-field__control) {
  font-size: 15px;
  color: var(--text-primary);
}

.input-icon {
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-color);
  background: rgba(100, 116, 139, 0.08);
  border-radius: 12px;
  margin-right: 10px;
  transition: all var(--transition-base);
}

.custom-field:focus-within .input-icon {
  background: rgba(100, 116, 139, 0.12);
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 20px 0;
  font-size: 14px;
}

.forgot-link {
  color: var(--primary-color);
  text-decoration: none;
  font-weight: 500;
  transition: opacity var(--transition-base);
}

.forgot-link:hover {
  opacity: 0.8;
}

.submit-btn {
  height: 54px;
  border-radius: 14px;
  background: var(--primary-gradient);
  border: none;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: var(--shadow-primary);
  transition: all var(--transition-base);
  font-family: var(--font-primary);
}

.submit-btn:active {
  transform: translateY(1px);
  box-shadow: 0 2px 8px rgba(14, 165, 233, 0.25);
}

.btn-text {
  font-size: 16px;
}

.btn-icon {
  transition: transform var(--transition-base);
}

.submit-btn:active .btn-icon {
  transform: translateX(4px);
}

.login-footer {
  padding: 28px 20px;
  text-align: center;
  position: relative;
  z-index: 1;
}

.security-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  margin-bottom: 8px;
}

.copyright {
  color: var(--text-muted);
  font-size: 11px;
}

:deep(.van-checkbox__label) {
  color: var(--text-secondary);
  font-size: 14px;
}

:deep(.van-checkbox__icon--checked .van-icon) {
  background-color: var(--primary-color);
  border-color: var(--primary-color);
}

@media (prefers-reduced-motion: reduce) {
  .logo-glow {
    animation: none;
  }
}
</style>
