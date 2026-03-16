<template>
  <div class="record-detail-page">
    <div class="page-header">
      <div class="header-bg"></div>
      <div class="header-content">
        <div class="header-nav">
          <div class="back-btn" @click="$router.back()">
            <van-icon name="arrow-left" size="24" color="#fff" />
          </div>
          <h1 class="header-title">检查记录详情</h1>
        </div>
      </div>
    </div>

    <van-loading v-if="loading" type="spinner" size="24px" class="loading-container">加载中...</van-loading>

    <div v-else-if="record" class="detail-content">
      <div class="compact-info">
        <div class="info-row">
          <div class="info-badge">
            <van-icon name="shop-o" size="14" />
          </div>
          <div class="info-content">
            <div class="info-label">企业</div>
            <div class="info-value">{{ record.enterprise_name || record.enterprise?.name || '手动输入' }}</div>
          </div>
        </div>
        <div class="info-row">
          <div class="info-badge">
            <van-icon name="description" size="14" />
          </div>
          <div class="info-content">
            <div class="info-label">模板</div>
            <div class="info-value">{{ record.template?.name || '未知模板' }}</div>
          </div>
        </div>
        <div class="info-row">
          <div class="info-badge">
            <van-icon name="clock-o" size="14" />
          </div>
          <div class="info-content">
            <div class="info-label">时间</div>
            <div class="info-value">{{ formatDate(record.inspection_date) }}</div>
          </div>
        </div>
        <div v-if="record.template?.is_quantified" class="info-row">
          <div class="info-badge" style="background: rgba(245, 158, 11, 0.1); color: #F59E0B;">
            <van-icon name="points" size="14" />
          </div>
          <div class="info-content">
            <div class="info-label">总分</div>
            <div class="info-value" style="color: #F59E0B; font-weight: bold;">{{ record.total_score || 0 }}</div>
          </div>
        </div>
        <div class="status-indicator" :class="record.overall_result">
          <van-icon v-if="record.overall_result === 'pass'" name="success" size="20" />
          <van-icon v-else-if="record.overall_result === 'fail'" name="cross" size="20" />
          <van-icon v-else name="info-o" size="20" />
          <span>{{ getOverallResultText(record.overall_result) }}</span>
        </div>
      </div>

      <div v-if="record.template?.items && record.template.items.length > 0" class="inspection-items">
        <div class="section-header">
          <div class="section-icon">
            <van-icon name="todo-list-o" size="20" />
          </div>
          <h3 class="section-title">检查项目</h3>
          <div class="item-count">{{ record.template.items.length }} 项</div>
        </div>
        <div class="tree-container">
          <tree-item
            v-for="(item, index) in record.template.items"
            :key="item.id"
            :item="item"
            :index="index"
            :get-check-type-text="getCheckTypeText"
            :get-radio-text="getRadioText"
            :format-range="formatRange"
            :preview-image="previewImage"
            :get-item-score="getItemScore"
          />
        </div>
      </div>

      <van-empty v-else description="暂无检查项目" class="empty-container" />

      <div v-if="record.remarks" class="remarks-card">
        <div class="remarks-header">
          <van-icon name="comment-o" size="16" />
          <span>判定说明</span>
        </div>
        <div class="remarks-text">{{ record.remarks }}</div>
      </div>

      <div style="height: 80px;"></div>
    </div>

    <van-empty v-else description="记录不存在或已被删除" class="empty-container" />

    <div v-if="record && record.status === 'submitted'" class="bottom-bar">
      <van-button type="primary" block @click="viewReport" icon="description">
        查看检查报告
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, ImagePreview } from 'vant'
import { getRecord } from '../api/records'
import TreeItem from '../components/TreeItem.vue'

const route = useRoute()
const router = useRouter()
const recordId = route.params.id

const record = ref(null)
const loading = ref(true)

const getStatusText = (status) => {
  const texts = {
    'draft': '草稿',
    'submitted': '已提交',
  }
  return texts[status] || status
}

const getCheckTypeText = (item) => {
  if (item.check_type) {
    const types = {
      'score': '打分',
      'radio': '单选',
      'numeric': '数值',
      'text': '文本',
      'multi_check': '多选',
    }
    return types[item.check_type] || '未知'
  }
  if (item.result_type) {
    const types = {
      'pass_fail': '通过/不通过',
      'numeric': '数值判定',
      'text': '文字描述',
    }
    return types[item.result_type] || '未知'
  }
  return '未知'
}

const getRadioText = (value) => {
  const texts = {
    'pass': '合格',
    'fail': '不合格',
    'na': '不适用',
  }
  return texts[value] || value
}

const getOverallResultText = (result) => {
  if (!result) return '待判定'
  const texts = {
    'pass': '合格',
    'partial_pass': '基本合格',
    'fail': '不合格',
  }
  return texts[result] || result
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const formatRange = (min, max) => {
  if (min !== null && min !== undefined && max !== null && max !== undefined) {
    return `${min} ~ ${max}`
  }
  if (min !== null && min !== undefined) {
    return `≥ ${min}`
  }
  if (max !== null && max !== undefined) {
    return `≤ ${max}`
  }
  return '-'
}

const flattenItems = (items) => {
  // 后端返回的 items 已经是扁平数组，直接返回
  // 但需要处理可能的嵌套结构（如果后端返回树形结构）
  const result = []
  const traverse = (list) => {
    for (const item of list) {
      if (!item.is_category) {
        result.push(item)
      }
      if (item.children && item.children.length > 0) {
        traverse(item.children)
      }
    }
  }
  traverse(items)
  return result
}

const previewImage = (src, list) => {
  ImagePreview.show({
    images: list,
    startPosition: list.findIndex(img => img === src),
  })
}

const getItemScore = (item) => {
  if (!record.value?.template?.is_quantified) return null
  if (item.score_value !== null && item.score_value !== undefined && item.score_value !== '') {
    return Number(item.score_value)
  }
  const radio = item.radio_value
  if (radio === 'pass') {
    return Number(item.score_weight || item.default_score || 0)
  } else if (radio === 'fail') {
    return 0
  } else if (radio === 'na') {
    return Number(item.default_score || 0)
  }
  return null
}

const fetchRecordDetail = async () => {
  try {
    loading.value = true
    const res = await getRecord(recordId)
    record.value = res.data
    console.log('Record detail:', record.value)
  } catch (error) {
    console.error('获取记录详情失败:', error)
    showToast('获取记录详情失败')
  } finally {
    loading.value = false
  }
}

const viewReport = () => {
  router.push(`/record/${recordId}/report`)
}

onMounted(() => {
  fetchRecordDetail()
})
</script>

<style scoped>
.record-detail-page {
  min-height: 100vh;
  background: var(--bg-light);
  padding-bottom: 20px;
}

.page-header {
  position: relative;
  padding: 0 0 20px;
  overflow: hidden;
}

.header-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--primary-gradient);
}

.header-bg::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: 
    radial-gradient(circle at 20% 30%, rgba(255, 255, 255, 0.1) 0%, transparent 40%),
    radial-gradient(circle at 80% 70%, rgba(255, 255, 255, 0.08) 0%, transparent 40%);
}

.header-content {
  position: relative;
  z-index: 1;
}

.header-nav {
  display: flex;
  align-items: center;
  padding: 50px 20px 20px;
  gap: 16px;
}

.back-btn {
  width: 40px;
  height: 40px;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-base);
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.25);
  transform: scale(1.05);
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--bg-white);
  font-family: var(--font-primary);
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 100px 0;
}

.detail-content {
  padding: 16px;
  margin-top: -10px;
}

.compact-info {
  background: var(--bg-white);
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.info-badge {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, rgba(79, 70, 229, 0.1) 0%, rgba(129, 140, 248, 0.1) 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-color);
  flex-shrink: 0;
}

.info-content {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-label {
  font-size: 13px;
  color: var(--text-muted);
  flex-shrink: 0;
  min-width: 40px;
}

.info-value {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-indicator {
  position: absolute;
  top: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
}

.status-indicator.pass {
  background: rgba(16, 185, 129, 0.1);
  color: var(--success-color);
}

.status-indicator.fail {
  background: rgba(239, 68, 68, 0.1);
  color: var(--danger-color);
}

.status-indicator.partial_pass {
  background: rgba(245, 158, 11, 0.1);
  color: var(--warning-color);
}

.inspection-items {
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 16px 20px;
  background: var(--bg-white);
  border-radius: 16px;
  box-shadow: var(--shadow-sm);
}

.section-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, rgba(79, 70, 229, 0.1) 0%, rgba(129, 140, 248, 0.1) 100%);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-color);
}

.section-title {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-primary);
}

.item-count {
  font-size: 14px;
  color: var(--text-secondary);
  background: var(--bg-light);
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 500;
}

.tree-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.remarks-card {
  background: var(--bg-white);
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
}

.remarks-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-primary);
}

.remarks-header .van-icon {
  color: var(--primary-color);
}

.remarks-text {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
  white-space: pre-wrap;
}

.empty-container {
  padding: 60px 20px;
}

.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px;
  background: #fff;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
  z-index: 100;
}

@media (prefers-reduced-motion: reduce) {
  .back-btn {
    transition: none;
  }
}
</style>
