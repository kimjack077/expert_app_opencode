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
        <p class="app-version">版本 2.4.0 SaaS Pro</p>
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
        <h3 class="card-title">联系我们</h3>
        <div class="contact-list">
          <div class="contact-item">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
              <polyline points="22,6 12,13 2,6"/>
            </svg>
            <span>support@example.com</span>
          </div>
          <div class="contact-item">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
            </svg>
            <span>400-123-4567</span>
          </div>
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
import { showToast } from 'vant'
import EasyAuditLogo from '../components/brand/EasyAuditLogo.vue'

const router = useRouter()

const goBack = () => {
  router.back()
}

const showTerms = () => {
  showToast('用户协议页面开发中')
}

const showPrivacy = () => {
  showToast('隐私政策页面开发中')
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
</style>
