<template>
  <div class="about-page">
    <van-nav-bar
      title="关于"
      left-arrow
      @click-left="goBack"
      class="custom-nav"
    />

    <div class="content-section">
      <div class="app-info-card">
        <div style="display: flex; justify-content: center; margin-bottom: 12px;">
          <EasyAuditLogo :size="52" :show-text="false" />
        </div>
        <h1 class="app-name">易审通 EasyAudit</h1>
        <p class="app-version">版本 {{ appVersion }}</p>
        <p class="app-desc">新一代认证审核与现场评审智能云平台，提供项目策划、智能排期、智审 Agent 现场辅助与一键报告交付全流程支持。</p>
      </div>

      <div class="info-card">
        <h3 class="card-title">功能特性</h3>
        <div class="feature-list">
          <div class="feature-item">
            <div class="feature-icon blue">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <div class="feature-content">
              <span class="feature-label">模板管理</span>
              <span class="feature-desc">创建和管理检查模板</span>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon green">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 11l3 3L22 4"/>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
              </svg>
            </div>
            <div class="feature-content">
              <span class="feature-label">任务分配</span>
              <span class="feature-desc">灵活的任务派发机制</span>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon orange">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <path d="m21 21-4.35-4.35"/>
              </svg>
            </div>
            <div class="feature-content">
              <span class="feature-label">现场检查</span>
              <span class="feature-desc">移动端检查执行</span>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon purple">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="20" x2="18" y2="10"/>
                <line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
            </div>
            <div class="feature-content">
              <span class="feature-label">数据统计</span>
              <span class="feature-desc">工作数据可视化分析</span>
            </div>
          </div>
        </div>
      </div>

      <div class="info-card">
        <h3 class="card-title">帮助与支持</h3>
        <div class="contact-list">
          <div class="contact-item" @click="openManual">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
              <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
            </svg>
            <span>在线使用文档与操作指南</span>
          </div>
          <div v-if="supportContact" class="contact-item">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
            </svg>
            <span>{{ supportContact }}</span>
          </div>
          <p v-else class="contact-tip">账号、权限或密码问题，请联系所在机构的系统管理员。</p>
        </div>
      </div>

      <div class="info-card">
        <h3 class="card-title">法律信息</h3>
        <div class="legal-list">
          <div class="legal-item" @click="showTerms">
            <span>用户协议</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          </div>
          <div class="legal-item" @click="showPrivacy">
            <span>隐私政策</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="m9 18 6-6-6-6"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="copyright">
        <p>© 2026 易审通 (EasyAudit) · 认证审核与现场评审智能云平台</p>
        <p>All Rights Reserved</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { showDialog } from 'vant'
import EasyAuditLogo from '../components/brand/EasyAuditLogo.vue'

const router = useRouter()

// 版本号与支持联系方式通过构建环境变量配置（.env.production），未配置时不展示占位假信息
const appVersion = import.meta.env.VITE_APP_VERSION || '2.4.0'
const supportContact = import.meta.env.VITE_SUPPORT_CONTACT || ''

const goBack = () => {
  if (window.history.length > 1) router.back()
  else router.replace('/profile')
}

// 文档中心部署在 Web 管理端 /docs；H5 与 Web 不同端口时通过 VITE_DOCS_URL 配置完整地址
const openManual = () => {
  const fallback = `${window.location.protocol}//${window.location.hostname}:3000/docs`
  window.open(import.meta.env.VITE_DOCS_URL || fallback, '_blank')
}

const TERMS = [
  '1. 本系统仅供经授权的审核机构人员用于认证审核、现场检查及相关管理工作。',
  '2. 账号仅限本人使用，不得转借；因账号保管不当造成的后果由账号持有人承担。',
  '3. 用户应保证录入的检查记录、证据照片真实、准确，并对提交内容负责。',
  '4. 智审 Agent 生成的条款判断、不符合项草稿仅作辅助参考，正式结论以审核员人工确认为准。',
  '5. 不得利用本系统上传违法违规内容，或进行与审核业务无关的操作。',
  '6. 平台可根据业务需要对功能进行调整，重大变更将通过系统内提示告知。',
]

const PRIVACY = [
  '1. 收集范围：账号信息、检查与审核记录、现场照片/语音、操作日志，以及拍照时您授权获取的位置信息。',
  '2. 使用目的：仅用于完成审核业务、生成报告、追溯审核过程及改进系统服务。',
  '3. AI 处理：调用智审 Agent 时，相关文字、照片会发送至机构配置的模型服务用于分析，不用于其他用途。',
  '4. 存储与共享：数据存储于机构部署的服务器，除法律法规要求或机构授权外，不向第三方提供。',
  '5. 本地缓存：离线缓存数据仅保存在本机浏览器，可在「设置 → 清除缓存」中随时删除。',
  '6. 如需查询、更正或删除个人信息，请联系所在机构的系统管理员。',
]

const showTerms = () => {
  showDialog({
    title: '用户协议',
    message: TERMS.join('\n'),
    messageAlign: 'left',
    confirmButtonText: '我知道了',
  })
}

const showPrivacy = () => {
  showDialog({
    title: '隐私政策',
    message: PRIVACY.join('\n'),
    messageAlign: 'left',
    confirmButtonText: '我知道了',
  })
}
</script>

<style scoped>
.about-page {
  min-height: 100vh;
  background: var(--bg-light);
  padding-bottom: 20px;
}

.custom-nav {
  background: var(--bg-white);
  border-bottom: 1px solid var(--border-light);
}

.custom-nav :deep(.van-nav-bar__title) {
  font-weight: 600;
  color: var(--text-primary);
}

.content-section {
  padding: 16px;
}

.app-info-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 32px 20px;
  text-align: center;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

.app-logo {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  background: var(--primary-gradient);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--bg-white);
  box-shadow: var(--shadow-primary);
}

.app-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.app-version {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.app-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.info-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-light);
}

.card-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-light);
  border-radius: var(--radius-md);
}

.feature-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.feature-icon.blue {
  background: var(--info-bg);
  color: var(--info-color);
}

.feature-icon.green {
  background: var(--success-bg);
  color: var(--success-color);
}

.feature-icon.orange {
  background: var(--warning-bg);
  color: var(--warning-color);
}

.feature-icon.purple {
  background: rgba(156, 39, 176, 0.1);
  color: #9C27B0;
}

.feature-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.feature-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.feature-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

.contact-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.contact-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: var(--bg-light);
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--text-primary);
}

.contact-item svg {
  color: var(--text-muted);
}

.legal-list {
  display: flex;
  flex-direction: column;
}

.legal-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
  font-size: 14px;
  color: var(--text-primary);
}

.legal-item:last-child {
  border-bottom: none;
}

.legal-item svg {
  color: var(--text-muted);
}

.copyright {
  text-align: center;
  padding: 20px;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.8;
}

.contact-item {
  cursor: pointer;
}

.contact-tip {
  font-size: 12px;
  color: var(--text-muted);
  margin: 8px 0 0;
}
</style>
