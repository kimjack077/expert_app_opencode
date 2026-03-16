<template>
  <div class="inspect-list-page">
    <!-- 导航栏 -->
    <van-nav-bar
      title="现场检查"
      left-arrow
      @click-left="goBack"
      fixed
      placeholder
    >
      <template #right>
        <van-icon name="passed" size="22" @click="completeInspection" />
      </template>
    </van-nav-bar>

    <div v-if="loading" class="loading-container">
      <van-skeleton title :row="10" />
    </div>

    <div v-else-if="record" class="page-content">
      <!-- 企业信息 -->
      <div class="enterprise-card">
        <div class="enterprise-icon">
          <van-icon name="shop-o" size="24" color="#4F46E5" />
        </div>
        <div class="enterprise-info">
          <h3 class="enterprise-name">{{ enterpriseName }}</h3>
          <p class="template-name">{{ record.template?.name }}</p>
        </div>
      </div>

      <!-- 进度条 -->
      <div class="progress-card">
        <div class="progress-header">
          <span class="progress-label">检查进度</span>
          <span class="progress-count">{{ completedCount }}/{{ totalCheckItems }}</span>
        </div>
        <van-progress
          :percentage="progressPercentage"
          :stroke-width="8"
          :show-pivot="false"
          :color="progressColor"
        />
        <div class="progress-hint">
          <span v-if="completedCount === 0">请开始填写检查项</span>
          <span v-else-if="completedCount < totalCheckItems">还有 {{ totalCheckItems - completedCount }} 项待检查</span>
          <span v-else class="complete">全部完成，可以提交</span>
        </div>
      </div>

      <!-- 检查项列表 -->
      <div class="items-container">
        <template v-for="item in flattenItems" :key="item.id">
          <!-- 分类节点 -->
          <div
            v-if="item.is_category"
            class="category-node"
            :style="{ paddingLeft: (item.level * 16 + 16) + 'px' }"
            @click="toggleCategory(item.id)"
          >
            <van-icon
              :name="expandedItems.includes(item.id) ? 'arrow-down' : 'arrow'"
              size="14"
              color="#64748B"
            />
            <span class="category-title">{{ item.title }}</span>
            <span class="category-count">{{ getCategoryProgress(item) }}</span>
          </div>

          <!-- 检查项节点 -->
          <div
            v-else
            class="check-item-node"
            :style="{ paddingLeft: (item.level * 16 + 16) + 'px' }"
            :class="{ completed: isItemCompleted(item) }"
            @click="goToItemDetail(item)"
          >
            <div class="item-status">
              <van-icon
                v-if="isItemCompleted(item)"
                name="passed"
                size="20"
                color="#34C759"
              />
              <van-icon
                v-else
                name="circle"
                size="20"
                color="#C7C7CC"
              />
            </div>
            <div class="item-content">
              <div class="item-title">{{ item.title }}</div>
              <div class="item-result" v-if="isItemCompleted(item)">
                <span class="result-text" :class="getResultClass(item)">
                  {{ getResultText(item) }}
                </span>
              </div>
              <div class="item-hint" v-else>
                点击进入检查
                <van-icon name="arrow" size="12" />
              </div>
            </div>
            <van-icon name="arrow" size="16" color="#C7C7CC" />
          </div>
        </template>
      </div>

      <van-empty v-if="flattenItems.length === 0" description="该模板暂无检查项目" />
    </div>

    <!-- 完成检查按钮 -->
    <div class="bottom-bar">
      <van-button
        type="primary"
        block
        :disabled="completedCount < totalCheckItems"
        @click="completeInspection"
      >
        完成检查
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import request from '../api/request.js'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const record = ref(null)
const expandedItems = ref([])
const itemResults = ref({})

// 计算属性
const enterpriseName = computed(() => {
  return record.value?.enterprise?.name || record.value?.enterprise_name || '未知企业'
})

const flattenItems = computed(() => {
  if (!record.value?.template?.items) return []

  const result = []
  const flatten = (items, level = 0, parentVisible = true) => {
    items.forEach(item => {
      let isVisible = parentVisible

      if (parentVisible && item.parent_id) {
        isVisible = expandedItems.value.includes(item.parent_id)
      }

      result.push({
        ...item,
        level,
        visible: isVisible,
      })

      if (item.children && item.children.length > 0) {
        flatten(item.children, level + 1, isVisible)
      }
    })
  }

  flatten(record.value.template.items)
  return result.filter(item => item.visible)
})

const totalCheckItems = computed(() => {
  if (!record.value?.template?.items) return 0

  let count = 0
  const countItems = (items) => {
    items.forEach(item => {
      if (!item.is_category) {
        count++
      }
      if (item.children && item.children.length > 0) {
        countItems(item.children)
      }
    })
  }
  countItems(record.value.template.items)
  return count
})

const completedCount = computed(() => {
  let count = 0
  for (const itemId in itemResults.value) {
    if (isResultFilled(itemResults.value[itemId])) {
      count++
    }
  }
  return count
})

const progressPercentage = computed(() => {
  if (totalCheckItems.value === 0) return 0
  return Math.round((completedCount.value / totalCheckItems.value) * 100)
})

const progressColor = computed(() => {
  const percentage = progressPercentage.value
  if (percentage >= 100) return '#34C759'
  if (percentage >= 50) return '#4F46E5'
  return '#FF9500'
})

// 方法
const isResultFilled = (result) => {
  return (
    result.radio_value ||
    result.score_value ||
    result.numeric_value ||
    result.text_value ||
    (result.multi_value && result.multi_value.length > 0)
  )
}

const isItemCompleted = (item) => {
  const result = itemResults.value[item.id]
  return isResultFilled(result)
}

const getResultText = (item) => {
  const result = itemResults.value[item.id]
  if (!result) return ''

  // 根据检查类型返回不同的结果文本
  if (result.radio_value) {
    const opt = item.result_options?.find(o => o.value === result.radio_value)
    return opt?.label || result.radio_value
  }
  if (result.score_value !== undefined && result.score_value !== null) {
    return `${result.score_value}分`
  }
  if (result.numeric_value) {
    return result.numeric_value + (item.unit || '')
  }
  
  // 没有结果
  return '待检查'
}

const getResultClass = (item) => {
  const result = itemResults.value[item.id]
  if (!result || Object.keys(result).length === 0) return 'pending'
  
  if (result.radio_value === 'fail') return 'fail'
  if (result.radio_value === 'pass') return 'pass'
  if (result.radio_value === 'na') return 'na'
  return 'completed'
}

const getCategoryProgress = (category) => {
  // 计算分类下的完成进度
  let completed = 0
  let total = 0

  const countChildren = (items) => {
    items.forEach(item => {
      if (item.is_category) {
        if (item.children) countChildren(item.children)
      } else {
        total++
        if (isItemCompleted(item)) completed++
      }
    })
  }

  if (category.children) {
    countChildren(category.children)
  }

  return total > 0 ? `${completed}/${total}` : ''
}

const toggleCategory = (itemId) => {
  const index = expandedItems.value.indexOf(itemId)
  if (index > -1) {
    expandedItems.value.splice(index, 1)
  } else {
    expandedItems.value.push(itemId)
  }
}

const goToItemDetail = (item) => {
  router.push(`/inspection/${route.params.id}/item/${item.id}`)
}

const completeInspection = async () => {
  if (completedCount.value < totalCheckItems.value) {
    showToast('请完成所有检查项')
    return
  }

  try {
    await showConfirmDialog({
      title: '确认提交',
      message: '确定要完成检查并提交吗？',
    })

    await request.post(`/records/${route.params.id}/submit`)

    showSuccessToast('检查已完成')
    router.push('/records')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('提交失败:', error)
      showToast('提交失败')
    }
  }
}

const goBack = () => {
  router.back()
}

// 初始化展开的分类
const initExpandedItems = (items) => {
  items.forEach(item => {
    if (item.is_category) {
      expandedItems.value.push(item.id)
    }
    if (item.children && item.children.length > 0) {
      initExpandedItems(item.children)
    }
  })
}

// 加载数据
const fetchRecord = async () => {
  loading.value = true
  try {
    const res = await request.get(`/records/${route.params.id}`)
    record.value = res.data.data

    // 初始化展开项
    if (record.value?.template?.items) {
      initExpandedItems(record.value.template.items)
    }

    // 加载已有的检查结果
    await loadItemResults()
  } catch (error) {
    console.error('获取记录失败:', error)
    showToast('获取记录失败')
  } finally {
    loading.value = false
  }
}

const loadItemResults = async () => {
  try {
    const res = await request.get(`/records/${route.params.id}/items`)
    const items = res.data.data || []

    items.forEach(item => {
      // 使用 item.is_category !== true 确保只处理真正的检查项
      if (item.is_category !== true) {
        itemResults.value[item.id] = {
          radio_value: item.radio_value,
          score_value: item.score_value,
          numeric_value: item.numeric_value,
          text_value: item.text_value,
          multi_value: item.multi_value || [],
        }
      }
    })
  } catch (error) {
    console.error('加载检查结果失败:', error)
  }
}

// 监听路由变化刷新数据
watch(
  () => route.params.id,
  async (newId, oldId) => {
    if (newId && newId !== oldId) {
      await fetchRecord()
    }
  }
)

onMounted(() => {
  fetchRecord()
})
</script>

<style scoped>
.inspect-list-page {
  min-height: 100vh;
  background: var(--bg-light);
  padding-bottom: 80px;
}

.loading-container {
  padding: 20px;
}

.page-content {
  padding: 12px;
}

.enterprise-card {
  background: var(--primary-gradient-dark);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.enterprise-icon {
  width: 48px;
  height: 48px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.enterprise-info {
  flex: 1;
}

.enterprise-name {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 4px;
}

.template-name {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  margin: 0;
}

.progress-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.progress-label {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

.progress-count {
  font-size: 18px;
  font-weight: 600;
  color: var(--primary-color);
}

.progress-hint {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 10px;
  text-align: center;
}

.progress-hint .complete {
  color: #34C759;
  font-weight: 500;
}

.items-container {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.category-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  background: var(--bg-light);
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
}

.category-title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.category-count {
  font-size: 13px;
  color: var(--text-secondary);
}

.check-item-node {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
  transition: background 0.2s;
}

.check-item-node:active {
  background: var(--bg-light);
}

.check-item-node.completed {
  background: rgba(52, 199, 89, 0.02);
}

.item-status {
  flex-shrink: 0;
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 15px;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.item-result {
  margin-top: 4px;
}

.result-text {
  font-size: 13px;
  padding: 2px 8px;
  border-radius: 4px;
}

.result-text.pass {
  background: rgba(52, 199, 89, 0.1);
  color: #34C759;
}

.result-text.fail {
  background: rgba(255, 59, 48, 0.1);
  color: #FF3B30;
}

.item-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--primary-color);
}

.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px;
  background: var(--bg-white);
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
}

:deep(.van-button--disabled) {
  opacity: 0.5;
}
</style>