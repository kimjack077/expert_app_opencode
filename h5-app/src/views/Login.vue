<template>
  <div class="efis-h5-login">
    <!-- 顶部科技流光 Header -->
    <div class="h5-login-hero">
      <div class="hero-mesh"></div>
      <div class="hero-ambient-glow"></div>

      <!-- 品牌 EasyAudit Logo -->
      <div class="hero-brand">
        <EasyAuditLogo
          :size="44"
          text-color="#ffffff"
          sub-text-color="rgba(255, 255, 255, 0.75)"
          :show-slogan="true"
          slogan-text="让每一次审核都简单高效"
        />
      </div>

      <!-- 业务能力亮点标签 -->
      <div class="hero-features">
        <div class="feature-chip">
          <span class="chip-dot"></span>
          <span>智审 Agent</span>
        </div>
        <div class="feature-chip">
          <span class="chip-dot dot-green"></span>
          <span>现场智能采证</span>
        </div>
        <div class="feature-chip">
          <span class="chip-dot dot-amber"></span>
          <span>移动合规研判</span>
        </div>
      </div>
    </div>

    <!-- 登录主体卡片 -->
    <div class="h5-form-wrapper">
      <div class="h5-login-card">
        <!-- 身份快捷切换 Tabs -->
        <div class="role-selector-header">
          <div class="role-selector-label">快速选择登录身份</div>
          <div class="role-pills">
            <button
              type="button"
              class="role-pill"
              :class="{ active: currentRole === 'expert' }"
              @click="selectRole('expert')"
            >
              <div class="role-pill-icon icon-expert">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
                  <circle cx="9" cy="7" r="4"/>
                  <path d="M22 21v-2a4 4 0 0 0-3-3.87"/>
                  <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                </svg>
              </div>
              <div class="role-pill-text">
                <span class="pill-title">审核专家</span>
                <span class="pill-sub">expert</span>
              </div>
              <div v-if="currentRole === 'expert'" class="role-check">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </div>
            </button>

            <button
              type="button"
              class="role-pill"
              :class="{ active: currentRole === 'admin' }"
              @click="selectRole('admin')"
            >
              <div class="role-pill-icon icon-admin">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
              </div>
              <div class="role-pill-text">
                <span class="pill-title">管理员</span>
                <span class="pill-sub">admin</span>
              </div>
              <div v-if="currentRole === 'admin'" class="role-check">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </div>
            </button>
          </div>
        </div>

        <!-- 登录表单 -->
        <van-form class="h5-actual-form" @submit.prevent="onSubmit">
          <div class="form-item-group">
            <label class="field-label">账号 / 用户名</label>
            <div class="input-box">
              <span class="field-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
              </span>
              <input
                v-model="form.username"
                type="text"
                class="native-input"
                placeholder="请输入用户名"
                autocomplete="username"
              />
            </div>
          </div>

          <div class="form-item-group">
            <label class="field-label">登录密码</label>
            <div class="input-box">
              <span class="field-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
              </span>
              <input
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                class="native-input"
                placeholder="请输入密码"
                autocomplete="current-password"
                @keyup.enter="onSubmit"
              />
              <button
                type="button"
                class="pwd-toggle"
                @click="showPassword = !showPassword"
              >
                <svg v-if="showPassword" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- 选项栏 -->
          <div class="form-sub-options">
            <van-checkbox v-model="rememberMe" shape="square" icon-size="15px">
              <span class="checkbox-text">记住我的账号</span>
            </van-checkbox>
            <span class="help-text" @click="onHelpClick">需要帮助?</span>
          </div>

          <!-- 登录按钮 -->
          <van-button
            block
            type="primary"
            :loading="loading"
            loading-text="正在进入工作台..."
            class="h5-submit-button"
            @click="onSubmit"
          >
            <span class="btn-title">登录工作台</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="arrow-icon">
              <line x1="5" y1="12" x2="19" y2="12"/>
              <polyline points="12 5 19 12 12 19"/>
            </svg>
          </van-button>
        </van-form>
      </div>
    </div>

    <!-- 底部安全与合规标识 -->
    <div class="h5-login-footer">
      <div class="footer-security">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          <polyline points="9 12 11 14 15 10"/>
        </svg>
        <span>SSL 256-bit 加密传输 · 现场数据安全保障</span>
      </div>
      <div class="footer-copy">
        易审通 EasyAudit · 移动现场端 v2.4
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showDialog } from 'vant'
import { login } from '../api/auth.js'
import EasyAuditLogo from '../components/brand/EasyAuditLogo.vue'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const rememberMe = ref(true)
const showPassword = ref(false)
const currentRole = ref('expert')

const form = reactive({
  username: 'expert',
  password: 'expert123',
})

onMounted(() => {
  const savedUser = localStorage.getItem('rememberedUsername')
  if (savedUser) {
    form.username = savedUser
    if (savedUser === 'admin') {
      currentRole.value = 'admin'
      form.password = 'admin123'
    } else if (savedUser === 'expert') {
      currentRole.value = 'expert'
      form.password = 'expert123'
    }
  }
})

const selectRole = (role) => {
  currentRole.value = role
  if (role === 'expert') {
    form.username = 'expert'
    form.password = 'expert123'
  } else if (role === 'admin') {
    form.username = 'admin'
    form.password = 'admin123'
  }
}

const onHelpClick = () => {
  showDialog({
    title: '系统登录提示',
    message: '现场专家请使用分配的专家账号登录。如忘记密码，请联系机构管理中心或管理员 (admin) 重置。',
    theme: 'round-button',
    confirmButtonColor: '#0284c7',
  })
}

const onSubmit = async () => {
  if (!form.username || !form.password) {
    showToast({ type: 'fail', message: '请填写用户名和密码' })
    return
  }

  loading.value = true
  try {
    const res = await login(form)
    const token = res.data?.access_token
    const refreshToken = res.data?.refresh_token

    if (token) {
      localStorage.setItem('token', token)
      if (refreshToken) {
        localStorage.setItem('refresh_token', refreshToken)
      }
      // 持久化显示名，供首页问候与检查记录署名使用（此前从未写入，恒为「检查员」）
      const userInfo = res.data?.user
      if (userInfo) {
        localStorage.setItem('userName', userInfo.full_name || userInfo.username || '')
      }
      if (rememberMe.value) {
        localStorage.setItem('rememberedUsername', form.username)
      } else {
        localStorage.removeItem('rememberedUsername')
      }

      showToast({ type: 'success', message: '登录成功', duration: 1000 })
      setTimeout(() => {
        // 登录前被拦截的页面（如分享的审核任务链接），登录后直接回到该页
        const redirect = route.query.redirect
        const target = typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('/login')
          ? redirect : '/today-audit'
        router.replace(target)
      }, 400)
    } else {
      throw new Error('未获取到有效认证凭据')
    }
  } catch (error) {
    console.error('登录失败:', error)
    let errorMsg = '登录失败，请检查账号密码'
    if (error.response?.data?.detail) {
      errorMsg = error.response.data.detail
    } else if (error.response?.data?.message) {
      errorMsg = error.response.data.message
    } else if (error.message) {
      errorMsg = error.message
    }
    showToast({ type: 'fail', message: errorMsg, duration: 2000 })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.efis-h5-login {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f1f5f9;
  position: relative;
  overflow-x: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}

/* 顶部科技 Hero 区域 */
.h5-login-hero {
  position: relative;
  background: linear-gradient(155deg, #09172a 0%, #0d2547 55%, #0369a1 100%);
  padding: calc(env(safe-area-inset-top) + 24px) 20px 48px;
  color: #ffffff;
  overflow: hidden;
  border-bottom-left-radius: 28px;
  border-bottom-right-radius: 28px;
}

.hero-mesh {
  position: absolute;
  inset: 0;
  background-image: 
    linear-gradient(to right, rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 24px 24px;
  pointer-events: none;
  opacity: 0.8;
}

.hero-ambient-glow {
  position: absolute;
  top: -20%;
  right: -10%;
  width: 220px;
  height: 220px;
  background: radial-gradient(circle, rgba(56, 189, 248, 0.3) 0%, transparent 70%);
  border-radius: 50%;
  filter: blur(40px);
  pointer-events: none;
}

.hero-brand {
  display: flex;
  align-items: center;
  gap: 16px;
  position: relative;
  z-index: 2;
  margin-bottom: 20px;
}

.brand-shield-wrapper {
  position: relative;
  flex-shrink: 0;
}

.shield-pulse {
  position: absolute;
  inset: -6px;
  background: radial-gradient(circle, rgba(56, 189, 248, 0.4) 0%, transparent 70%);
  border-radius: 50%;
  animation: pulseLogo 3s infinite ease-in-out;
}

@keyframes pulseLogo {
  0%, 100% { transform: scale(0.95); opacity: 0.5; }
  50% { transform: scale(1.15); opacity: 0.9; }
}

.brand-shield {
  width: 54px;
  height: 54px;
  background: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%);
  border: 2px solid rgba(255, 255, 255, 0.25);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  box-shadow: 0 8px 20px rgba(2, 132, 199, 0.4);
  position: relative;
  z-index: 1;
}

.brand-text {
  flex: 1;
}

.brand-tag {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #38bdf8;
  margin-bottom: 2px;
}

.brand-title {
  font-size: 21px;
  font-weight: 800;
  margin: 0 0 3px 0;
  letter-spacing: -0.02em;
  color: #ffffff;
}

.brand-desc {
  font-size: 12px;
  color: #cbd5e1;
  margin: 0;
  line-height: 1.3;
}

/* 亮点标签 */
.hero-features {
  display: flex;
  gap: 8px;
  position: relative;
  z-index: 2;
}

.feature-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 20px;
  font-size: 11px;
  color: #e2e8f0;
  backdrop-filter: blur(10px);
}

.chip-dot {
  width: 6px;
  height: 6px;
  background: #38bdf8;
  border-radius: 50%;
}

.dot-green {
  background: #4ade80;
}

.dot-amber {
  background: #fbbf24;
}

/* 表单主体卡片 */
.h5-form-wrapper {
  padding: 0 16px;
  margin-top: -24px;
  position: relative;
  z-index: 10;
  flex: 1;
}

.h5-login-card {
  background: #ffffff;
  border-radius: 20px;
  padding: 22px 18px 24px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
  border: 1px solid rgba(226, 232, 240, 0.8);
}

/* 角色快速选择 Pill */
.role-selector-header {
  margin-bottom: 20px;
}

.role-selector-label {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}

.role-pills {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.role-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  background: #f8fafc;
  border: 1.5px solid #e2e8f0;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
}

.role-pill.active {
  background: #f0f9ff;
  border-color: #0284c7;
  box-shadow: 0 4px 12px rgba(2, 132, 199, 0.12);
}

.role-pill-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-expert {
  background: #dcfce7;
  color: #16a34a;
}

.icon-admin {
  background: #e0f2fe;
  color: #0284c7;
}

.role-pill-text {
  flex: 1;
  text-align: left;
  display: flex;
  flex-direction: column;
}

.pill-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}

.pill-sub {
  font-size: 11px;
  color: #64748b;
}

.role-check {
  color: #0284c7;
  display: flex;
  align-items: center;
}

/* 输入框 */
.form-item-group {
  margin-bottom: 16px;
}

.field-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 6px;
}

.input-box {
  display: flex;
  align-items: center;
  background: #f8fafc;
  border: 1.5px solid #e2e8f0;
  border-radius: 12px;
  padding: 0 12px;
  height: 48px;
  transition: all 0.2s ease;
}

.input-box:focus-within {
  border-color: #0284c7;
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.15);
}

.field-icon {
  color: #94a3b8;
  display: flex;
  align-items: center;
  margin-right: 10px;
}

.input-box:focus-within .field-icon {
  color: #0284c7;
}

.native-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 15px;
  color: #0f172a;
  height: 100%;
}

.native-input::placeholder {
  color: #94a3b8;
}

.pwd-toggle {
  background: none;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
}

/* 选项栏 */
.form-sub-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 16px 0 20px;
}

.checkbox-text {
  font-size: 13px;
  color: #64748b;
}

.help-text {
  font-size: 13px;
  color: #0284c7;
  font-weight: 500;
  cursor: pointer;
}

/* 提交按钮 */
.h5-submit-button {
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
  border: none !important;
  font-size: 16px;
  font-weight: 700;
  box-shadow: 0 8px 20px rgba(2, 132, 199, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: transform 0.15s ease;
}

.h5-submit-button:active {
  transform: scale(0.98);
}

.arrow-icon {
  transition: transform 0.2s ease;
}

.h5-submit-button:active .arrow-icon {
  transform: translateX(3px);
}

/* 底部声明 */
.h5-login-footer {
  padding: 24px 16px;
  text-align: center;
}

.footer-security {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #64748b;
  margin-bottom: 6px;
}

.footer-copy {
  font-size: 11px;
  color: #94a3b8;
}
</style>
