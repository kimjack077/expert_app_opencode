<template>
  <div class="audit-task-detail">
    <van-nav-bar
      title="审核记录填写"
      left-arrow
      @click-left="onBack"
      fixed
      placeholder
    />

    <div v-if="planItem" class="task-info-card">
      <div class="info-header">
        <h3>{{ planItem.area_name }}</h3>
        <van-tag :type="getStatusType(planItem.status)">
          {{ getStatusText(planItem.status) }}
        </van-tag>
      </div>
      <div class="info-content">
        <div class="info-item">
          <span class="label">审核日期：</span>
          <span>{{ planItem.plan_date }}</span>
        </div>
        <div class="info-item">
          <span class="label">审核时间：</span>
          <span>{{ planItem.time_start }} - {{ planItem.time_end }}</span>
        </div>
        <div class="info-item">
          <span class="label">认证体系：</span>
          <div class="tags">
            <van-tag
              v-for="sys in planItem.certification_systems"
              :key="sys"
              size="small"
            >
              {{ sys }}
            </van-tag>
          </div>
        </div>
      </div>
    </div>

    <van-form @submit="onSubmit">
      <van-cell-group title="审核记录" inset>
        <van-field
          v-model="formData.audit_date"
          label="审核日期"
          placeholder="请选择日期"
          readonly
          required
          :rules="[{ required: true, message: '请选择审核日期' }]"
          @click="showDatePicker = true"
        />
        <van-popup v-model:show="showDatePicker" position="bottom">
          <van-date-picker
            v-model="currentDate"
            @confirm="onDateConfirm"
            @cancel="showDatePicker = false"
          />
        </van-popup>

        <van-field
          v-model="formData.audit_time_start"
          label="开始时间"
          placeholder="如：09:00"
          required
          :rules="[
            { required: true, message: '请输入开始时间' },
            { pattern: /^([01]\d|2[0-3]):([0-5]\d)$/, message: '请输入正确的时间格式，如：09:00' }
          ]"
        />
        <van-field
          v-model="formData.audit_time_end"
          label="结束时间"
          placeholder="如：12:00"
          required
          :rules="[
            { required: true, message: '请输入结束时间' },
            { pattern: /^([01]\d|2[0-3]):([0-5]\d)$/, message: '请输入正确的时间格式，如：12:00' },
            { validator: validateTimeRange, message: '结束时间必须晚于开始时间' }
          ]"
        />

        <van-field
          v-model="formData.conclusion"
          label="审核结论"
          type="textarea"
          rows="3"
          placeholder="请输入审核结论，描述审核发现的主要情况"
          :rules="[
            { required: true, message: '请输入审核结论' },
            { validator: (val) => val.length >= 10, message: '审核结论至少10个字符' }
          ]"
        />
      </van-cell-group>

      <div class="form-actions">
        <van-button
          round
          block
          type="primary"
          native-type="submit"
          :loading="submitting"
        >
          {{ record ? '更新记录' : '创建记录' }}
        </van-button>
      </div>
    </van-form>

    <div v-if="record" class="record-items-section">
      <van-cell-group title="检查项记录" inset>
        <van-button
          type="primary"
          size="small"
          @click="showItemForm = true"
        >
          添加检查项
        </van-button>
      </van-cell-group>
    </div>

    <!-- 检查项表单弹窗 -->
    <van-popup
      v-model:show="showItemForm"
      position="bottom"
      :style="{ height: '80%' }"
    >
      <div class="item-form-container">
        <van-nav-bar
          title="填写检查项"
          left-text="取消"
          right-text="保存"
          @click-left="showItemForm = false"
          @click-right="saveItem"
        />
        <van-form>
          <van-field
            v-model="itemForm.audit_evidence"
            label="审核证据"
            type="textarea"
            rows="3"
            placeholder="请输入审核证据，如：查阅了工艺操作规程SP-03"
            :rules="[
              { required: true, message: '请输入审核证据' },
              { validator: (val) => val.length >= 5, message: '审核证据至少5个字符' }
            ]"
          />
          <van-cell center>
            <template #title>
              <van-button
                type="primary"
                size="small"
                plain
                @click="handleAIEvaluate"
                :loading="aiLoading"
              >
                🤖 AI 智能评估
              </van-button>
            </template>
          </van-cell>
          <van-field name="evaluation" label="评估结果" required>
            <template #input>
              <van-radio-group v-model="itemForm.evaluation_3level" direction="horizontal">
                <van-radio name="1">1-符合</van-radio>
                <van-radio name="2">2-基本符合</van-radio>
                <van-radio name="3">3-不符合</van-radio>
              </van-radio-group>
            </template>
          </van-field>
          <van-field
            v-if="itemForm.evaluation_3level === '3'"
            v-model="itemForm.audit_findings"
            label="审核发现"
            type="textarea"
            rows="3"
            placeholder="请描述发现的问题"
            :rules="[
              { required: true, message: '不符合项必须填写审核发现' },
              { validator: (val) => val.length >= 10, message: '审核发现至少10个字符' }
            ]"
          />
          <van-field name="photos" label="照片">
            <template #input>
              <van-uploader v-model="itemForm.photos" multiple :max-count="5" />
            </template>
          </van-field>
        </van-form>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showConfirmDialog, showDialog } from 'vant'
import {
  getAuditPlanItem,
  createAuditRecord,
  updateAuditRecord,
  evaluateEvidenceWithAI
} from '../api/auditProjects'

const route = useRoute()
const router = useRouter()

const planItem = ref(null)
const record = ref(null)
const submitting = ref(false)
const showDatePicker = ref(false)
const showItemForm = ref(false)
const currentDate = ref(new Date())
const aiLoading = ref(false)

const formData = reactive({
  audit_date: '',
  audit_time_start: '',
  audit_time_end: '',
  conclusion: ''
})

const itemForm = reactive({
  audit_evidence: '',
  evaluation_3level: '1',
  audit_findings: '',
  photos: []
})

const getStatusType = (status) => {
  const typeMap = {
    pending: 'default',
    in_progress: 'primary',
    completed: 'success'
  }
  return typeMap[status] || 'default'
}

const getStatusText = (status) => {
  const textMap = {
    pending: '待开始',
    in_progress: '进行中',
    completed: '已完成'
  }
  return textMap[status] || status
}

const validateTimeRange = () => {
  if (formData.audit_time_start && formData.audit_time_end) {
    const [startH, startM] = formData.audit_time_start.split(':').map(Number)
    const [endH, endM] = formData.audit_time_end.split(':').map(Number)
    const startMinutes = startH * 60 + startM
    const endMinutes = endH * 60 + endM
    return endMinutes > startMinutes
  }
  return true
}

const fetchPlanItem = async () => {
  try {
    const response = await getAuditPlanItem(route.params.id)
    planItem.value = response.data
    
    // 初始化表单数据
    formData.audit_date = planItem.value.plan_date
    formData.audit_time_start = planItem.value.time_start
    formData.audit_time_end = planItem.value.time_end
  } catch (error) {
    showToast(error.message || '获取任务详情失败')
  }
}

const onDateConfirm = ({ selectedValues }) => {
  formData.audit_date = selectedValues.join('-')
  showDatePicker.value = false
}

const onSubmit = async () => {
  submitting.value = true
  try {
    const data = {
      plan_item_id: route.params.id,
      template_id: planItem.value.template_id,
      certification_systems: planItem.value.certification_systems,
      ...formData
    }

    if (record.value) {
      await updateAuditRecord(record.value.id, data)
      showToast('更新成功')
    } else {
      const response = await createAuditRecord(route.query.projectId, data)
      record.value = response.data
      showToast('创建成功')
    }
  } catch (error) {
    showToast(error.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

const saveItem = () => {
  // TODO: 保存检查项记录
  showToast('检查项保存成功')
  showItemForm.value = false
  
  // 重置表单
  itemForm.audit_evidence = ''
  itemForm.evaluation_3level = '1'
  itemForm.audit_findings = ''
  itemForm.photos = []
}

const handleAIEvaluate = async () => {
  if (!itemForm.audit_evidence || itemForm.audit_evidence.length < 5) {
    showToast('请先输入审核证据')
    return
  }

  aiLoading.value = true
  try {
    const response = await evaluateEvidenceWithAI(route.query.projectId, {
      evidence: itemForm.audit_evidence,
      clause_no: '7.1', // TODO: 从模板项获取
      certification_system: planItem.value.certification_systems[0]
    })
    
    const result = response.data
    
    // 应用 AI 建议
    itemForm.evaluation_3level = result.suggested_evaluation
    
    // 显示评估结果
    showDialog({
      title: 'AI 评估结果',
      message: `
        <div style="text-align: left;">
          <p><strong>证据充分性：</strong>${result.is_sufficient ? '充分' : '不充分'}</p>
          <p><strong>建议评级：</strong>${result.suggested_evaluation === '1' ? '符合' : result.suggested_evaluation === '2' ? '基本符合' : '不符合'}</p>
          <p><strong>评估理由：</strong>${result.reasoning}</p>
          ${result.additional_evidence_needed ? `<p><strong>建议补充：</strong>${result.additional_evidence_needed}</p>` : ''}
        </div>
      `,
      allowHtml: true,
      confirmButtonText: '知道了'
    })
  } catch (error) {
    showToast(error.message || 'AI 评估失败')
  } finally {
    aiLoading.value = false
  }
}

const onBack = () => {
  if (record.value) {
    showConfirmDialog({
      title: '提示',
      message: '确定要离开吗？未保存的内容将丢失',
    }).then(() => {
      router.back()
    }).catch(() => {
      // 取消
    })
  } else {
    router.back()
  }
}

onMounted(() => {
  fetchPlanItem()
})
</script>

<style scoped>
.audit-task-detail {
  min-height: 100vh;
  background-color: var(--bg-gray);
  padding-bottom: 20px;
}

.task-info-card {
  margin: 12px;
  padding: 16px;
  background: var(--bg-white);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.info-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.info-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.info-content {
  font-size: 14px;
}

.info-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.label {
  color: var(--text-secondary);
  min-width: 80px;
}

.tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.form-actions {
  padding: 16px;
}

.record-items-section {
  margin-top: 12px;
}

.item-form-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}
</style>
