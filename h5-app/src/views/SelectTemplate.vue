<template>
  <div class="template-select-page">
    <div class="page-header">
      <div class="header-bg"></div>
      <div class="header-content">
        <div class="header-nav">
          <div class="back-btn" @click="goBack">
            <van-icon name="arrow-left" size="24" color="#fff" />
          </div>
          <h1 class="header-title">选择模板</h1>
        </div>
        <div class="enterprise-banner" v-if="enterpriseName">
          <div class="banner-icon">
            <van-icon name="shop-o" size="20" />
          </div>
          <div class="banner-info">
            <span class="banner-label">被检查企业</span>
            <h3 class="banner-title">{{ enterpriseName }}</h3>
          </div>
          <div class="banner-edit" @click="goBack">
            <van-icon name="edit" size="14" />
            <span>修改</span>
          </div>
        </div>
        <div class="banner-detail" v-if="enterpriseAddress">
          <van-icon name="location-o" size="12" />
          {{ enterpriseAddress }}
        </div>
      </div>
    </div>

    <div class="search-section">
      <van-search
        v-model="searchText"
        placeholder="搜索模板..."
        shape="round"
        background="transparent"
        @search="onSearch"
        @clear="onCancel"
      />
    </div>

    <div class="filter-tabs">
      <div
        v-for="tab in filterTabs"
        :key="tab.value"
        class="filter-tab"
        :class="{ active: activeFilter === tab.value }"
        @click="activeFilter = tab.value"
      >
        {{ tab.label }}
      </div>
    </div>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh" class="refresh-container">
      <van-list
        v-model:loading="loading"
        :finished="finished"
        finished-text=""
        @load="onLoad"
      >
        <div class="template-list">
          <div
            v-for="template in filteredTemplates"
            :key="template.id"
            class="template-card"
            @click="selectTemplate(template)"
          >
            <div class="card-header">
              <div class="template-icon">
                <van-icon name="file-text-o" size="24" />
              </div>
              <div class="template-info">
                <h3 class="template-name">{{ template.name }}</h3>
                <div class="template-meta">
                  <span class="version-tag">v{{ template.version || '1.0' }}</span>
                  <span v-if="template.category" class="category-tag">{{ template.category }}</span>
                </div>
              </div>
              <van-icon name="arrow" class="card-arrow" />
            </div>
            
            <div v-if="template.description" class="template-desc">
              {{ template.description }}
            </div>
            
            <div class="template-footer">
              <div class="stat-item">
                <van-icon name="checked" size="14" />
                <span>{{ template.stats?.check_items || template.items_count || template.items?.length || 0 }} 检查项</span>
              </div>
              <div class="start-hint">
                点击开始检查
                <van-icon name="arrow" size="12" />
              </div>
            </div>
          </div>
        </div>

        <div v-if="filteredTemplates.length === 0 && !loading" class="empty-state">
          <div class="empty-icon-wrapper">
            <van-icon name="file-text-o" size="64" />
          </div>
          <p class="empty-text">暂无可用模板</p>
          <p class="empty-hint">请联系管理员添加检查模板</p>
        </div>
      </van-list>
    </van-pull-refresh>

    <van-dialog
      v-model:show="showConfirmDialog"
      title="确认开始检查"
      show-cancel-button
      confirm-button-color="#4F46E5"
      class="confirm-dialog"
      @confirm="confirmStartInspection"
    >
      <div class="confirm-content">
        <div class="confirm-item">
          <span class="confirm-label">被检查企业</span>
          <span class="confirm-value">{{ enterpriseName }}</span>
        </div>
        <div class="confirm-item">
          <span class="confirm-label">检查模板</span>
          <span class="confirm-value">{{ selectedTemplate?.name }}</span>
        </div>
        <div class="confirm-tip">
          <van-icon name="info-o" size="14" />
          确认后将创建检查记录并开始检查
        </div>
      </div>
    </van-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast } from 'vant'
import { getTemplates, createRecord } from '../api/records'

const router = useRouter()
const route = useRoute()

const searchText = ref('')
const activeFilter = ref('all')
const templates = ref([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const page = ref(1)
const pageSize = 20

const showConfirmDialog = ref(false)
const selectedTemplate = ref(null)

const enterpriseId = ref('')
const enterpriseName = ref('')
const enterpriseAddress = ref('')
const contactPerson = ref('')
const contactPhone = ref('')

const resetState = () => {
  templates.value = []
  page.value = 1
  finished.value = false
  selectedTemplate.value = null
}

const initFromQuery = () => {
  enterpriseId.value = route.query.enterprise_id || ''
  enterpriseName.value = route.query.enterprise_name || ''
  enterpriseAddress.value = route.query.enterprise_address || ''
  contactPerson.value = route.query.contact_person || ''
  contactPhone.value = route.query.contact_phone || ''
}

watch(
  () => route.query,
  () => {
    initFromQuery()
    resetState()
    fetchTemplates(true)
  }
)

const filterTabs = [
  { label: '全部', value: 'all' },
  { label: '食品安全', value: '食品安全' },
  { label: '安全生产', value: '安全生产' },
  { label: '质量管理', value: '质量管理' },
]

const filteredTemplates = computed(() => {
  let result = templates.value
  if (activeFilter.value !== 'all') {
    result = result.filter(t => t.category === activeFilter.value)
  }
  if (searchText.value) {
    const keyword = searchText.value.toLowerCase()
    result = result.filter(t =>
      t.name?.toLowerCase().includes(keyword) ||
      t.description?.toLowerCase().includes(keyword)
    )
  }
  return result
})

const fetchTemplates = async (isRefresh = false) => {
  try {
    const res = await getTemplates({
      is_published: true,
      page: page.value,
      limit: pageSize,
    })
    const items = res.data || []
    if (isRefresh) {
      templates.value = items
    } else {
      templates.value.push(...items)
    }
    if (items.length < pageSize) {
      finished.value = true
    }
  } catch (error) {
    console.error('获取模板失败:', error)
    showToast('获取模板失败')
  }
}

const onLoad = async () => {
  await fetchTemplates()
  loading.value = false
  page.value++
}

const onRefresh = async () => {
  page.value = 1
  finished.value = false
  await fetchTemplates(true)
  refreshing.value = false
}

const onSearch = () => {
  page.value = 1
  finished.value = false
  templates.value = []
  onLoad()
}

const onCancel = () => {
  searchText.value = ''
  onSearch()
}

const selectTemplate = (template) => {
  selectedTemplate.value = template
  showConfirmDialog.value = true
}

const confirmStartInspection = async () => {
  try {
    const data = {
      template_id: selectedTemplate.value.id,
      enterprise_id: enterpriseId.value || null,
      enterprise_name: enterpriseName.value,
      enterprise_address: enterpriseAddress.value,
      contact_person: contactPerson.value,
      contact_phone: contactPhone.value,
    }

    const res = await createRecord(data)

    // 根据是否是草稿显示不同提示
    if (res.data?.is_draft) {
      showToast({
        type: 'success',
        message: '继续当天草稿',
      })
    } else {
      showToast({
        type: 'success',
        message: '创建成功',
      })
    }

    setTimeout(() => {
      router.replace(`/inspection/${res.data.id}`)
    }, 500)
  } catch (error) {
    console.error('创建检查记录失败:', error)
    showToast({
      type: 'fail',
      message: error?.response?.data?.message || '创建失败',
    })
  }
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  initFromQuery()
  if (!enterpriseName.value) {
    showToast('请先选择企业')
    router.replace('/select-enterprise')
    return
  }
  // 不在这里调用 fetchTemplates，让 van-list 的 @load 自动触发
})
</script>

<style scoped>
.template-select-page {
  min-height: 100vh;
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
  background: radial-gradient(circle at 30% 20%, rgba(14, 165, 233, 0.25) 0%, transparent 50%),
              radial-gradient(circle at 70% 80%, rgba(56, 189, 248, 0.2) 0%, transparent 50%);
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
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
}

.enterprise-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px 8px;
}

.banner-icon {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  background: var(--primary-gradient);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.banner-info {
  flex: 1;
}

.banner-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  display: block;
  margin-bottom: 2px;
}

.banner-title {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.banner-edit {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 44px;
  padding: 0 12px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  color: #fff;
  font-size: 12px;
  cursor: pointer;
}

.banner-detail {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 16px 0 62px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
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
}

.filter-tabs {
  display: flex;
  gap: 8px;
  padding: 0 16px 16px;
  overflow-x: auto;
  scrollbar-width: none;
}

.filter-tabs::-webkit-scrollbar {
  display: none;
}

.filter-tab {
  flex-shrink: 0;
  padding: 8px 18px;
  border-radius: 20px;
  font-size: 13px;
  background: var(--bg-white);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.25s ease;
  box-shadow: var(--shadow-sm);
}

.filter-tab.active {
  background: var(--primary-gradient);
  color: var(--bg-white);
  box-shadow: var(--shadow-primary);
}

.refresh-container {
  min-height: 200px;
}

.template-list {
  padding: 0 16px 20px;
}

.template-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all 0.25s ease;
}

.template-card:active {
  transform: scale(0.98);
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.08);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.template-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: var(--info-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-color);
  flex-shrink: 0;
}

.template-info {
  flex: 1;
  min-width: 0;
}

.template-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.template-meta {
  display: flex;
  gap: 8px;
}

.version-tag {
  padding: 2px 8px;
  background: var(--info-bg);
  color: var(--primary-color);
  border-radius: 10px;
  font-size: 11px;
}

.category-tag {
  padding: 2px 8px;
  background: rgba(76, 175, 80, 0.1);
  color: #4CAF50;
  border-radius: 10px;
  font-size: 11px;
}

.card-arrow {
  color: #ccc;
  font-size: 18px;
}

.template-desc {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.template-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.start-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--primary-color);
  font-weight: 500;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-icon-wrapper {
  width: 100px;
  height: 100px;
  background: var(--info-bg);
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
}

.empty-hint {
  font-size: 14px;
  color: var(--text-secondary);
}

.confirm-dialog :deep(.van-dialog__header) {
  font-weight: 600;
  color: var(--text-primary);
}

.confirm-content {
  padding: 20px;
}

.confirm-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-light);
}

.confirm-item:last-of-type {
  border-bottom: none;
}

.confirm-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.confirm-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.confirm-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 16px;
  padding: 12px;
  background: #FFFBEB;
  border-radius: 10px;
  font-size: 12px;
  color: #B45309;
}
</style>
