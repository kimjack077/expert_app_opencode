<template>
  <div class="enterprise-select-page">
    <div class="page-header">
      <div class="header-bg"></div>
      <div class="header-content">
        <div class="header-nav">
          <div class="back-btn" @click="goBack">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="m15 18-6-6 6-6"/>
            </svg>
          </div>
          <h1 class="header-title">选择企业</h1>
        </div>
        <div class="hero-section">
          <div class="hero-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
          </div>
          <div class="hero-text">
            <h2 class="hero-title">选择被检查企业</h2>
            <p class="hero-subtitle">从企业库选择或手动输入</p>
          </div>
        </div>
      </div>
    </div>

    <div class="search-section">
      <van-search
        v-model="searchText"
        placeholder="搜索企业名称或地址..."
        shape="round"
        background="transparent"
        @update:model-value="onInputDebounced"
        @search="onSearch"
        @clear="onCancel"
      />
    </div>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh" class="refresh-container">
      <van-list
        v-model:loading="loading"
        :finished="finished"
        finished-text=""
        @load="onLoad"
      >
        <div class="enterprise-list">
          <div
            v-for="enterprise in filteredEnterprises"
            :key="enterprise.id"
            class="enterprise-card"
            @click="selectEnterprise(enterprise)"
          >
            <div class="card-main">
              <div class="enterprise-avatar">
                <span class="avatar-text">{{ getInitial(enterprise.name) }}</span>
              </div>
              <div class="enterprise-info">
                <h3 class="enterprise-name">{{ enterprise.name }}</h3>
                <div class="enterprise-meta">
                  <span class="meta-item" v-if="enterprise.address">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                      <circle cx="12" cy="10" r="3"/>
                    </svg>
                    {{ enterprise.address }}
                  </span>
                </div>
              </div>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="card-arrow">
                <path d="m9 18 6-6-6-6"/>
              </svg>
            </div>

            <div v-if="enterprise.contact_person || enterprise.contact_phone" class="enterprise-contact">
              <div class="contact-tag" v-if="enterprise.contact_person">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
                {{ enterprise.contact_person }}
              </div>
              <div class="contact-tag" v-if="enterprise.contact_phone">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
                </svg>
                {{ enterprise.contact_phone }}
              </div>
            </div>

            <div class="ai-briefing-entry" @click.stop="openBriefing(enterprise)">
              <van-icon name="star-o" size="14" />
              <span>AI 检查准备简报</span>
            </div>
          </div>
        </div>

        <div v-if="filteredEnterprises.length === 0 && !loading" class="empty-state">
          <div class="empty-icon-wrapper">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
          </div>
          <p class="empty-text">暂无企业数据</p>
          <p class="empty-hint">可以手动输入企业信息开始检查</p>
        </div>
      </van-list>
    </van-pull-refresh>

    <div class="manual-input-btn">
      <van-button type="primary" block round @click="showManualInput = true" class="manual-btn">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="btn-icon">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
        手动输入企业信息
      </van-button>
    </div>

    <van-popup
      v-model:show="showManualInput"
      position="bottom"
      round
      :style="{ height: '65%' }"
      class="manual-popup"
    >
      <div class="popup-header">
        <h3>手动输入企业信息</h3>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" @click="showManualInput = false" class="close-icon">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </div>
      <van-form @submit="onManualSubmit" class="popup-form">
        <van-field
          v-model="manualForm.enterprise_name"
          name="enterprise_name"
          label="企业名称"
          placeholder="请输入企业名称"
          :rules="[{ required: true, message: '请输入企业名称' }]"
          clearable
        />
        <van-field
          v-model="manualForm.enterprise_address"
          name="enterprise_address"
          label="企业地址"
          placeholder="请输入企业地址"
          clearable
        />
        <van-field
          v-model="manualForm.contact_person"
          name="contact_person"
          label="联系人"
          placeholder="请输入联系人"
          clearable
        />
        <van-field
          v-model="manualForm.contact_phone"
          name="contact_phone"
          label="联系电话"
          type="tel"
          placeholder="请输入联系电话"
          clearable
        />
        <div class="popup-footer">
          <van-button type="primary" block round native-type="submit" class="submit-btn">
            确认并选择模板
          </van-button>
        </div>
      </van-form>
    </van-popup>

    <!-- AI 检查准备简报 -->
    <van-popup
      v-model:show="showBriefing"
      position="bottom"
      round
      :style="{ height: '70%' }"
      class="briefing-popup"
    >
      <div class="popup-header">
        <h3>AI 检查准备简报</h3>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" @click="showBriefing = false" class="close-icon">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </div>
      <button
        type="button"
        class="model-selector"
        :aria-expanded="showModelSheet"
        aria-haspopup="listbox"
        @click="showModelSheet = true"
      >
        <span class="model-selector-label">生成模型</span>
        <span class="model-selector-value">
          {{ selectedModelName }}
          <van-icon name="arrow-down" size="14" />
        </span>
      </button>
      <div class="briefing-body">
        <div v-if="briefingLoading && !briefingData" class="briefing-loading">
          <van-loading size="24" color="#0EA5E9" />
          <p>正在整理企业资料...</p>
        </div>
        <div v-else-if="briefingData" class="briefing-content">
          <div class="briefing-markdown" v-html="renderedBriefing"></div>
          <div v-if="briefingLoading" class="briefing-streaming">
            <van-loading size="14" color="#0369A1" />
            <span>正在生成</span>
          </div>
          <div v-if="briefingData.outstanding_issues?.length" class="briefing-issues">
            <div class="issues-title">历史遗留问题（{{ briefingData.outstanding_issues.length }}）</div>
            <div v-for="(issue, idx) in briefingData.outstanding_issues" :key="idx" class="issue-item">
              <span class="issue-date">{{ issue.date }}</span>
              <span class="issue-title">{{ issue.title }}</span>
            </div>
          </div>
        </div>
        <div v-else-if="briefingError" class="briefing-error">
          <van-icon name="warning-o" size="28" />
          <p>{{ briefingError }}</p>
          <van-button
            type="primary"
            plain
            size="small"
            :disabled="briefingLoading"
            @click="loadBriefing"
          >
            重新生成
          </van-button>
        </div>
      </div>
    </van-popup>

    <van-action-sheet
      v-model:show="showModelSheet"
      title="选择生成模型"
      :actions="modelActions"
      cancel-text="取消"
      close-on-click-action
      @select="selectModel"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import DOMPurify from 'dompurify'
import { marked } from 'marked'

import { getEnterprises } from '../api/records'
import { getAgentModels, streamInspectionBriefing } from '../api/agent'

// Simple debounce utility
const debounce = (fn, delay) => {
  let timer = null
  return (...args) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}

const router = useRouter()
const searchText = ref('')
const enterprises = ref([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const showManualInput = ref(false)
const page = ref(1)
const pageSize = 20

const showBriefing = ref(false)
const briefingLoading = ref(false)
const briefingData = ref(null)
const briefingError = ref('')
const briefingEnterprise = ref(null)
const showModelSheet = ref(false)
const modelOptions = ref([
  {
    id: 'deepseek-v4-flash',
    name: 'DeepSeek V4 Flash',
    recommended_for: '文字问答和检查准备简报',
  },
  {
    id: 'sensenova-6.7-flash-lite',
    name: 'SenseNova 6.7 Flash Lite',
    recommended_for: '图片识别和多模态分析',
  },
])
const selectedModel = ref(localStorage.getItem('ai_text_model') || 'deepseek-v4-flash')

const selectedModelName = computed(() =>
  modelOptions.value.find(model => model.id === selectedModel.value)?.name || selectedModel.value
)

const renderedBriefing = computed(() => {
  const markdown = briefingData.value?.briefing_text || ''
  return DOMPurify.sanitize(marked.parse(markdown, { breaks: true, gfm: true }))
})

const modelActions = computed(() =>
  modelOptions.value.map(model => ({
    id: model.id,
    name: model.name,
    subname: model.recommended_for,
    color: model.id === selectedModel.value ? '#0369A1' : undefined,
  }))
)

const loadModels = async () => {
  try {
    const res = await getAgentModels()
    if (res.code === 200 && res.data?.models?.length) {
      modelOptions.value = res.data.models
      const isAvailable = modelOptions.value.some(model => model.id === selectedModel.value)
      if (!isAvailable) {
        selectedModel.value = res.data.default_model
      }
    }
  } catch (error) {
    console.error('加载 AI 模型列表失败:', error)
  }
}

const loadBriefing = async () => {
  if (!briefingEnterprise.value) return

  briefingLoading.value = true
  briefingData.value = null
  briefingError.value = ''
  try {
    await streamInspectionBriefing(
      briefingEnterprise.value.id,
      selectedModel.value,
      {
        onMetadata: (metadata) => {
          briefingData.value = {
            ...metadata,
            briefing_text: '',
          }
        },
        onContent: (content) => {
          briefingData.value = {
            ...briefingData.value,
            briefing_text: (briefingData.value?.briefing_text || '') + content,
          }
        },
      },
    )
  } catch (error) {
    briefingData.value = null
    briefingError.value = error.message || '简报生成失败，请切换模型或重试'
  } finally {
    briefingLoading.value = false
  }
}

const openBriefing = async (enterprise) => {
  showBriefing.value = true
  briefingEnterprise.value = enterprise
  await loadModels()
  await loadBriefing()
}

const selectModel = async (action) => {
  selectedModel.value = action.id
  localStorage.setItem('ai_text_model', action.id)
  showModelSheet.value = false
  await loadBriefing()
}

const manualForm = ref({
  enterprise_name: '',
  enterprise_address: '',
  contact_person: '',
  contact_phone: '',
})

const filteredEnterprises = computed(() => {
  if (!searchText.value) return enterprises.value
  const keyword = searchText.value.toLowerCase()
  return enterprises.value.filter(e =>
    e.name?.toLowerCase().includes(keyword) ||
    e.address?.toLowerCase().includes(keyword)
  )
})

const getInitial = (name) => {
  if (!name) return '企'
  return name.charAt(0)
}

const fetchEnterprises = async (isRefresh = false) => {
  try {
    const params = {
      page: page.value,
      limit: pageSize,
    }
    if (searchText.value) {
      params.name = searchText.value
    }
    const res = await getEnterprises(params)
    const items = res.data?.items || res.data || []
    if (isRefresh) {
      enterprises.value = items
    } else {
      enterprises.value.push(...items)
    }
    if (items.length < pageSize) {
      finished.value = true
    }
  } catch (error) {
    console.error('获取企业列表失败:', error)
    showToast('获取企业列表失败')
    finished.value = true
  }
}

const onLoad = async () => {
  await fetchEnterprises()
  loading.value = false
  page.value++
}

const onRefresh = async () => {
  page.value = 1
  finished.value = false
  await fetchEnterprises(true)
  refreshing.value = false
}

const onSearch = () => {
  page.value = 1
  finished.value = false
  enterprises.value = []
  onLoad()
}

// Debounced handler for real-time input search (300ms)
const onInputDebounced = debounce((value) => {
  // Client-side filter already handles UI; trigger API reload for thoroughness
  page.value = 1
  finished.value = false
  enterprises.value = []
  fetchEnterprises(true)
}, 300)

const onCancel = () => {
  searchText.value = ''
  onSearch()
}

const selectEnterprise = (enterprise) => {
  router.push({
    path: '/select-template',
    query: {
      enterprise_id: enterprise.id,
      enterprise_name: enterprise.name,
      enterprise_address: enterprise.address,
      contact_person: enterprise.contact_person,
      contact_phone: enterprise.contact_phone,
    }
  })
}

const onManualSubmit = () => {
  if (!manualForm.value.enterprise_name) {
    showToast('请输入企业名称')
    return
  }
  router.push({
    path: '/select-template',
    query: {
      enterprise_name: manualForm.value.enterprise_name,
      enterprise_address: manualForm.value.enterprise_address,
      contact_person: manualForm.value.contact_person,
      contact_phone: manualForm.value.contact_phone,
    }
  })
}

const goBack = () => {
  router.back()
}
</script>

<style scoped>
.enterprise-select-page {
  min-height: 100vh;
  padding-bottom: 90px;
  background: var(--bg-light);
}

.page-header {
  position: relative;
  padding: 0 0 16px;
  overflow: hidden;
}

.header-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--primary-gradient-dark);
}

.header-bg::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: 
    radial-gradient(circle at 10% 20%, rgba(255, 255, 255, 0.08) 0%, transparent 40%),
    radial-gradient(circle at 90% 80%, rgba(14, 165, 233, 0.15) 0%, transparent 40%);
}

.header-content {
  position: relative;
  z-index: 1;
}

.header-nav {
  display: flex;
  align-items: center;
  padding: calc(env(safe-area-inset-top) + 18px) 16px 8px;
  gap: 12px;
}

.back-btn {
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(10px);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-base);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--bg-white);
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: scale(1.05);
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--bg-white);
  font-family: var(--font-primary);
  letter-spacing: -0.3px;
}

.hero-section {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px 8px;
}

.hero-icon {
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--bg-white);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.hero-icon svg {
  width: 24px;
  height: 24px;
}

.hero-text {
  flex: 1;
}

.hero-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--bg-white);
  margin-bottom: 4px;
  font-family: var(--font-primary);
  letter-spacing: -0.5px;
}

.hero-subtitle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 400;
}

.search-section {
  margin: -8px 16px 12px;
  position: relative;
  z-index: 10;
}

.search-section :deep(.van-search) {
  padding: 0;
  background: transparent;
}

.search-section :deep(.van-search__content) {
  background: var(--bg-white);
  box-shadow: var(--shadow-md);
  padding-left: 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
}

.refresh-container {
  min-height: 200px;
}

.enterprise-list {
  padding: 0 16px;
}

.enterprise-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all var(--transition-base);
  border: 1px solid var(--border-light);
}

.enterprise-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
  border-color: var(--primary-light);
}

.enterprise-card:active {
  transform: translateY(0);
  box-shadow: var(--shadow-sm);
}

.card-main {
  display: flex;
  align-items: center;
  gap: 14px;
}

.enterprise-avatar {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-md);
  background: var(--primary-gradient);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-text {
  color: var(--bg-white);
  font-size: 20px;
  font-weight: 600;
  font-family: var(--font-primary);
}

.enterprise-info {
  flex: 1;
  min-width: 0;
}

.enterprise-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: var(--font-primary);
  letter-spacing: -0.3px;
}

.enterprise-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.meta-item {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.card-arrow {
  color: var(--text-muted);
  transition: transform var(--transition-base);
}

.enterprise-card:hover .card-arrow {
  transform: translateX(4px);
}

.enterprise-contact {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.ai-briefing-entry {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 10px;
  padding: 5px 12px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.12) 0%, rgba(99, 102, 241, 0.12) 100%);
  color: #0EA5E9;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.ai-briefing-entry:active {
  opacity: 0.7;
}

.briefing-popup {
  border-radius: 24px 24px 0 0;
}

.briefing-body {
  padding: 16px 20px 30px;
  overflow-y: auto;
  height: calc(100% - 60px);
}

.briefing-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.briefing-text {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
  white-space: pre-wrap;
}

.briefing-issues {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--border-light);
}

.issues-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.issue-item {
  display: flex;
  gap: 8px;
  font-size: 13px;
  padding: 6px 0;
  color: var(--text-primary);
}

.issue-date {
  color: var(--text-muted);
  flex-shrink: 0;
}

.briefing-error {
  text-align: center;
  color: var(--text-secondary);
  padding: 40px 0;
  font-size: 14px;
}

.contact-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  background: var(--info-bg);
  color: var(--info-color);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-icon-wrapper {
  width: 90px;
  height: 90px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.1) 0%, rgba(56, 189, 248, 0.1) 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  color: var(--primary-color);
}

.empty-text {
  font-size: 16px;
  color: var(--text-primary);
  font-weight: 500;
  margin-bottom: 8px;
  font-family: var(--font-primary);
}

.empty-hint {
  font-size: 14px;
  color: var(--text-secondary);
}

.manual-input-btn {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px;
  background: linear-gradient(180deg, transparent 0%, var(--bg-light) 30%);
  z-index: 100;
}

.manual-btn {
  background: var(--primary-gradient);
  border: none;
  font-weight: 500;
  letter-spacing: 0.5px;
  height: 48px;
  font-size: 15px;
}

.manual-btn :deep(.van-button__text) {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-icon {
  margin-right: 4px;
}

.manual-popup {
  border-radius: 24px 24px 0 0;
}

.popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 20px 16px;
  border-bottom: 1px solid var(--border-light);
}

.popup-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-primary);
  letter-spacing: -0.3px;
}

.close-icon {
  color: var(--text-muted);
  cursor: pointer;
  transition: color var(--transition-base);
}

.close-icon:hover {
  color: var(--text-primary);
}

.popup-form {
  padding: 16px 20px;
}

.popup-footer {
  margin-top: 24px;
  padding: 0 0 20px;
}

.submit-btn {
  background: var(--primary-gradient);
  border: none;
  font-weight: 500;
  letter-spacing: 0.5px;
  height: 48px;
}

.briefing-popup {
  border-radius: 24px 24px 0 0;
}

.model-selector {
  width: calc(100% - 40px);
  min-height: 44px;
  margin: 8px 20px 0;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: var(--text-primary);
  font: inherit;
  cursor: pointer;
}

.model-selector:focus-visible {
  outline: 2px solid #0369a1;
  outline-offset: 2px;
}

.model-selector-label {
  color: var(--text-secondary);
  font-size: 13px;
}

.model-selector-value {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  color: #0369a1;
  font-size: 13px;
  font-weight: 600;
  text-align: right;
}

.briefing-body {
  padding: 16px 20px 24px;
  overflow-y: auto;
  height: calc(100% - 112px);
}

.briefing-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.briefing-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
}

.briefing-markdown {
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.75;
  overflow-wrap: anywhere;
}

.briefing-markdown :deep(h1) {
  margin: 0 0 16px;
  color: #0f172a;
  font-size: 20px;
  line-height: 1.35;
  font-weight: 700;
}

.briefing-markdown :deep(h2) {
  margin: 22px 0 10px;
  padding-bottom: 7px;
  border-bottom: 1px solid #e2e8f0;
  color: #0f172a;
  font-size: 17px;
  line-height: 1.4;
  font-weight: 650;
}

.briefing-markdown :deep(h3) {
  margin: 18px 0 8px;
  color: #1e293b;
  font-size: 16px;
  line-height: 1.45;
}

.briefing-markdown :deep(p) {
  margin: 8px 0;
}

.briefing-markdown :deep(ul),
.briefing-markdown :deep(ol) {
  margin: 8px 0 12px;
  padding-left: 22px;
}

.briefing-markdown :deep(li) {
  margin: 7px 0;
  padding-left: 2px;
}

.briefing-markdown :deep(strong) {
  color: #0f172a;
  font-weight: 650;
}

.briefing-markdown :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 12px;
  border-left: 3px solid #0369a1;
  background: #f8fafc;
  color: #475569;
}

.briefing-streaming {
  min-height: 32px;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  color: #0369a1;
  font-size: 13px;
}

.briefing-issues {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--border-light);
}

.issues-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.issue-item {
  display: flex;
  gap: 8px;
  padding: 8px 0;
  font-size: 13px;
  border-bottom: 1px dashed var(--border-light);
}

.issue-date {
  color: var(--text-muted);
  flex-shrink: 0;
}

.issue-title {
  color: var(--text-primary);
}

.briefing-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  text-align: center;
  padding: 40px 0;
  color: var(--text-muted);
  font-size: 14px;
}

.briefing-error p {
  margin: 0;
  line-height: 1.6;
}

@media (prefers-reduced-motion: reduce) {
  .enterprise-card,
  .back-btn,
  .card-arrow {
    transition: none;
  }
}
</style>
