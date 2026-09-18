<template>
  <div class="report-page">
    <van-nav-bar
      title="检查报告"
      left-arrow
      @click-left="goBack"
      fixed
      placeholder
    >
      <template #right>
        <van-icon name="down" size="20" @click="downloadPdf" />
      </template>
    </van-nav-bar>

    <div v-if="loading" class="loading-container">
      <van-skeleton title :row="10" />
    </div>

    <div v-else-if="reportData" class="report-content" ref="reportRef">
      <div class="report-cover">
        <h1 class="cover-title">现场检查报告</h1>
        <div class="cover-info">
          <div class="cover-row">
            <span class="cover-label">报告编号</span>
            <span class="cover-value">{{ reportData.report_number }}</span>
          </div>
          <div class="cover-row">
            <span class="cover-label">企业名称</span>
            <span class="cover-value">{{ reportData.enterprise.name }}</span>
          </div>
          <div class="cover-row">
            <span class="cover-label">检查日期</span>
            <span class="cover-value">{{ formatDate(reportData.inspection.date) }}</span>
          </div>
          <div class="cover-row">
            <span class="cover-label">检查员</span>
            <span class="cover-value">{{ reportData.inspection.inspector }}</span>
          </div>
          <div class="cover-row">
            <span class="cover-label">检查类型</span>
            <span class="cover-value">定期检查</span>
          </div>
          <div class="cover-row">
            <span class="cover-label">总体结论</span>
            <span class="cover-value result-tag" :class="reportData.inspection.overall_result">
              {{ reportData.inspection.overall_result_text }}
            </span>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">
          <van-icon name="description" color="#1e40af" />
          一、检查概况
        </div>
        <div class="overview-cards" :class="{ 'has-extra': extraStatCount > 0 }">
          <div class="stat-card total">
            <div class="stat-value">{{ reportData.statistics.total }}</div>
            <div class="stat-label">检查项</div>
          </div>
          <div class="stat-card pass">
            <div class="stat-value">{{ reportData.statistics.pass }}</div>
            <div class="stat-label">合格</div>
          </div>
          <div class="stat-card fail">
            <div class="stat-value">{{ reportData.statistics.fail }}</div>
            <div class="stat-label">不合格</div>
          </div>
          <div class="stat-card na">
            <div class="stat-value">{{ reportData.statistics.na }}</div>
            <div class="stat-label">不适用</div>
          </div>
          <!-- 观察项 / 未填写：让「合格+不合格+不适用+观察项+未填写 = 检查项」闭合 -->
          <div v-if="reportData.statistics.observe > 0" class="stat-card observe">
            <div class="stat-value">{{ reportData.statistics.observe }}</div>
            <div class="stat-label">观察项</div>
          </div>
          <div v-if="unfilledCount > 0" class="stat-card unfilled">
            <div class="stat-value">{{ unfilledCount }}</div>
            <div class="stat-label">未填写</div>
          </div>
        </div>
        <div class="pass-rate">
          <span>合格率</span>
          <van-progress :percentage="reportData.statistics.pass_rate" :show-pivot="false" :color="getProgressColor" />
          <span class="rate-value">{{ reportData.statistics.pass_rate }}%</span>
        </div>
        <div v-if="reportData.inspection.total_score" class="total-score">
          得分：<span class="score-value">{{ reportData.inspection.total_score }}</span> 分
        </div>
      </div>

      <div class="section">
        <div class="section-title">
          <van-icon name="shop-o" color="#1e40af" />
          二、企业基本情况
        </div>
        <div class="info-table">
          <div class="info-row">
            <span class="info-label">企业名称</span>
            <span class="info-value">{{ reportData.enterprise.name }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">企业地址</span>
            <span class="info-value">{{ reportData.enterprise.address || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">联系人</span>
            <span class="info-value">{{ reportData.enterprise.contact_person || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">联系电话</span>
            <span class="info-value">{{ reportData.enterprise.contact_phone || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">统一社会信用代码</span>
            <span class="info-value">{{ reportData.enterprise.credit_code || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">法定代表人</span>
            <span class="info-value">{{ reportData.enterprise.legal_person || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">风险等级</span>
            <span class="info-value">{{ reportData.enterprise.risk_level || '-' }}</span>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">
          <van-icon name="todo-list-o" color="#1e40af" />
          三、检查内容及结果
        </div>
        <div class="items-table">
          <div class="table-header">
            <span class="col-index">序号</span>
            <span class="col-title">检查项目</span>
            <span class="col-result">结果</span>
          </div>
          <div 
            v-for="(item, idx) in reportData.items" 
            :key="item.id" 
            class="table-row"
            :class="{ 'fail-row': item.radio_value === 'fail' }"
          >
            <span class="col-index">{{ idx + 1 }}</span>
            <span class="col-title">{{ item.title }}</span>
            <span class="col-result" :class="item.radio_value">
              {{ getItemResultText(item) }}
            </span>
          </div>
        </div>
      </div>

      <div v-if="reportData.fail_items && reportData.fail_items.length > 0" class="section">
        <div class="section-title fail-title">
          <van-icon name="warning-o" color="#dc2626" />
          四、不符合项描述
        </div>
        <div v-for="(item, idx) in reportData.fail_items" :key="item.id" class="fail-item">
          <div class="fail-item-title">{{ idx + 1 }}. {{ item.title }}</div>
          <div v-if="item.description" class="fail-item-content">
            <span class="fail-label">检查内容：</span>{{ item.description }}
          </div>
          <div v-if="item.problem_description" class="fail-item-problem">
            <span class="fail-label">问题描述：</span>{{ item.problem_description }}
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">
          <van-icon name="edit" color="#1e40af" />
          {{ reportData.fail_items && reportData.fail_items.length > 0 ? '五' : '四' }}、整改建议
        </div>
        <div v-if="reportData.fail_items && reportData.fail_items.length > 0" class="remarks-content">
          <template v-if="hasRectificationSuggestions">
            <div v-for="(item, idx) in reportData.fail_items" :key="item.id">
              <div v-if="item.rectification_suggestion" class="rectification-item">
                {{ idx + 1 }}. {{ item.title }}：{{ item.rectification_suggestion }}
              </div>
            </div>
          </template>
          <span v-else>请依据检查发现的不合格项，制定相应整改措施并按期完成整改复查。</span>
        </div>
        <div v-else class="no-remarks">
          本次检查未发现需要整改的问题。
        </div>
      </div>

      <div class="section">
        <div class="section-title">
          <van-icon name="passed" color="#1e40af" />
          {{ reportData.fail_items && reportData.fail_items.length > 0 ? '六' : '五' }}、总体判定
        </div>
        <div class="conclusion-box">
          <div class="conclusion-row">
            <span class="conclusion-label">总体结论</span>
            <span class="conclusion-value result-tag" :class="reportData.inspection.overall_result">
              {{ reportData.inspection.overall_result_text }}
            </span>
          </div>
          <div v-if="reportData.inspection.judgment_note" class="conclusion-row">
            <span class="conclusion-label">判定说明</span>
            <span class="conclusion-value">{{ reportData.inspection.judgment_note }}</span>
          </div>
          <div v-if="reportData.inspection.remarks" class="conclusion-row">
            <span class="conclusion-label">检查备注</span>
            <span class="conclusion-value">{{ reportData.inspection.remarks }}</span>
          </div>
          <div class="conclusion-row">
            <span class="conclusion-label">检查员</span>
            <span class="conclusion-value">{{ reportData.inspection.inspector }}</span>
          </div>
          <div class="conclusion-row">
            <span class="conclusion-label">签名</span>
            <span class="conclusion-value signature-line"></span>
          </div>
        </div>
      </div>

      <div class="report-footer">
        本报告由 易审通 (EasyAudit) 智能审核云平台自动生成 · 生成时间：{{ formatDateTime(reportData.generated_at) }}
      </div>
    </div>

    <van-empty v-else description="报告数据加载失败" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showSuccessToast } from 'vant'
import request from '../api/request.js'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const reportData = ref(null)

const getProgressColor = computed(() => {
  if (!reportData.value) return '#22c55e'
  const rate = reportData.value.statistics.pass_rate
  if (rate >= 80) return '#22c55e'
  if (rate >= 60) return '#f59e0b'
  return '#ef4444'
})

// 观察项之外还剩多少项没填 —— 保证概况卡片各项相加等于「检查项」总数
const unfilledCount = computed(() => {
  const s = reportData.value?.statistics
  if (!s) return 0
  return Math.max(
    (s.total || 0) - (s.pass || 0) - (s.fail || 0) - (s.na || 0) - (s.observe || 0),
    0
  )
})

// 需要额外占位的卡片数（有观察项 / 有未填写时才显示，用于调整网格列数）
const extraStatCount = computed(() => {
  const s = reportData.value?.statistics
  if (!s) return 0
  return (s.observe > 0 ? 1 : 0) + (unfilledCount.value > 0 ? 1 : 0)
})

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${d} ${hh}:${mm}`
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

const hasRectificationSuggestions = computed(() =>
  (reportData.value?.fail_items || []).some(item => !!item.rectification_suggestion)
)

const getRadioText = (value) => {
  // 与 PC 端 InspectionReport 的映射保持一致，补齐历史/集成写入的同义值。
  // 注意：库里实际存在 observe（观察项），原映射表漏了它，会直接回显英文。
  const map = {
    'pass': '合格',
    'compliant': '合格',
    'qualified': '合格',
    'fail': '不合格',
    'non_compliant': '不合格',
    'unqualified': '不合格',
    'partial_pass': '基本合格',
    'pending_rectification': '待整改',
    'observe': '观察项',
    'not_applicable': '不适用',
    'na': '不适用',
    'not-applicable': '不适用',
    'n/a': '不适用',
  }
  return map[value] || value || '-'
}

/**
 * 检查项结论的展示文本。
 *
 * 优先判定值 → 数值（带单位）→ 真实文本内容。
 */
const getItemResultText = (item) => {
  if (item.radio_value) {
    return getRadioText(item.radio_value)
  }
  const numeric = item.numeric_value
  if (numeric !== null && numeric !== undefined && numeric !== '') {
    return `${numeric}${item.unit ? ' ' + item.unit : ''}`
  }
  if (item.text_value) {
    return item.text_value
  }
  return '—'
}

const fetchReportData = async () => {
  loading.value = true
  try {
    const recordId = route.params.id
    const res = await request.get(`/records/${recordId}/report`)
    reportData.value = res.data
  } catch (error) {
    console.error('获取报告数据失败:', error)
    showToast('获取报告数据失败')
  } finally {
    loading.value = false
  }
}

const downloadPdf = async () => {
  const recordId = route.params.id
  const token = localStorage.getItem('token')
  
  try {
    showToast('正在生成PDF...')
    const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const response = await fetch(`${API_BASE_URL}/api/records/${recordId}/report/pdf`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })
    
    if (!response.ok) {
      throw new Error('下载失败')
    }
    
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `检查报告_${reportData.value?.enterprise?.name || '未知'}_${new Date().toISOString().slice(0, 10)}.pdf`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    
    showSuccessToast('PDF下载成功')
  } catch (error) {
    console.error('下载PDF失败:', error)
    showToast('下载PDF失败')
  }
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  fetchReportData()
})
</script>

<style scoped>
.report-page {
  min-height: 100vh;
  background: var(--bg-light);
  padding-bottom: 20px;
}

.loading-container {
  padding: 20px;
}

.report-content {
  padding: 12px;
}

.report-cover {
  background: var(--primary-gradient-dark);
  border-radius: var(--radius-lg);
  padding: 30px 20px;
  margin-bottom: 12px;
  color: var(--bg-white);
  text-align: center;
}

.cover-title {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 24px;
  letter-spacing: 4px;
}

.cover-info {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  padding: 16px;
}

.cover-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.cover-row:last-child {
  border-bottom: none;
}

.cover-label {
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
}

.cover-value {
  font-size: 14px;
  font-weight: 500;
}

.result-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.result-tag.pass {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.result-tag.partial_pass {
  background: rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.result-tag.fail {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.section {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--primary-color);
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-light);
}

.fail-title {
  color: #dc2626;
}

.overview-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 12px 8px;
  border-radius: var(--radius-md);
  background: var(--bg-light);
}

.stat-card.total {
  background: var(--info-bg);
}

.stat-card.pass {
  background: rgba(34, 197, 94, 0.1);
}

.stat-card.fail {
  background: rgba(239, 68, 68, 0.1);
}

.stat-card.na {
  background: rgba(156, 163, 175, 0.1);
}

/* 观察项：已填写但不属三级判定的中间态 */
.stat-card.observe {
  background: rgba(8, 145, 178, 0.1);
}

.stat-card.unfilled {
  background: rgba(148, 163, 184, 0.12);
}

/* 多出观察项/未填写卡片时改为三列，避免 390px 宽度下挤压 */
.overview-cards.has-extra {
  grid-template-columns: repeat(3, 1fr);
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-card.pass .stat-value {
  color: #22c55e;
}

.stat-card.fail .stat-value {
  color: #ef4444;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.pass-rate {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-light);
  border-radius: var(--radius-md);
  margin-bottom: 12px;
}

.pass-rate span {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.pass-rate .van-progress {
  flex: 1;
  min-width: 80px;
}

.rate-value {
  font-weight: 600;
  color: var(--primary-color) !important;
}

.total-score {
  text-align: center;
  font-size: 16px;
  color: var(--text-primary);
}

.score-value {
  font-size: 28px;
  font-weight: 700;
  color: #f59e0b;
}

.info-table {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.info-row {
  display: flex;
  border-bottom: 1px solid var(--border-light);
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  width: 120px;
  padding: 12px;
  background: var(--info-bg);
  font-size: 13px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.info-value {
  flex: 1;
  padding: 12px;
  font-size: 13px;
  color: var(--text-primary);
}

.items-table {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.table-header {
  display: flex;
  background: var(--primary-color);
  color: var(--bg-white);
  font-size: 13px;
  font-weight: 600;
}

.table-header span {
  padding: 10px 8px;
}

.table-row {
  display: flex;
  border-bottom: 1px solid var(--border-light);
  font-size: 13px;
}

.table-row:last-child {
  border-bottom: none;
}

.table-row.fail-row {
  background: #fef2f2;
}

.table-row span {
  padding: 10px 8px;
}

.col-index {
  width: 40px;
  text-align: center;
  flex-shrink: 0;
}

.col-title {
  flex: 1;
}

.col-result {
  width: 60px;
  text-align: center;
  flex-shrink: 0;
}

.col-result.pass {
  color: #22c55e;
  font-weight: 600;
}

.col-result.fail {
  color: #ef4444;
  font-weight: 600;
}

.col-result.na {
  color: #9ca3af;
}

.fail-item {
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
}

.fail-item:last-child {
  margin-bottom: 0;
}

.fail-item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--danger-color);
  margin-bottom: 8px;
}

.fail-item-content {
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 6px;
  line-height: 1.5;
}

.fail-item-problem {
  font-size: 13px;
  color: #b91c1c;
  line-height: 1.5;
}

.fail-label {
  font-weight: 500;
  color: var(--text-secondary);
}

.remarks-content {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.8;
  background: var(--warning-bg);
  border: 1px solid var(--warning-color);
  border-radius: var(--radius-md);
  padding: 12px;
}

.rectification-item {
  margin-bottom: 8px;
}

.rectification-item:last-child {
  margin-bottom: 0;
}

.no-remarks {
  font-size: 14px;
  color: #9ca3af;
  font-style: italic;
}

.conclusion-box {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.conclusion-row {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--border-light);
}

.conclusion-row:last-child {
  border-bottom: none;
}

.conclusion-label {
  width: 100px;
  padding: 14px 12px;
  background: var(--info-bg);
  font-size: 13px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.conclusion-value {
  flex: 1;
  padding: 14px 12px;
  font-size: 14px;
  color: var(--text-primary);
}

.signature-line {
  border-bottom: 1px solid #374151;
  min-width: 150px;
  height: 20px;
}

.report-footer {
  text-align: center;
  font-size: 11px;
  color: #9ca3af;
  padding: 20px 0;
}
</style>
