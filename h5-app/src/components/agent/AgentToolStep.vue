<template>
  <div class="agent-tool-step">
    <div class="tool-header" @click="toggleExpand">
      <div class="tool-icon">
        <van-icon :name="getToolIcon" size="14" />
      </div>
      <div class="tool-info">
        <span class="tool-name">{{ getToolLabel }}</span>
        <van-tag v-if="tool.status === 'calling'" type="primary" size="mini">执行中</van-tag>
        <van-tag v-else-if="tool.status === 'done'" type="success" size="mini">完成</van-tag>
        <van-tag v-else-if="tool.status === 'error'" type="danger" size="mini">失败</van-tag>
      </div>
      <van-icon :name="expanded ? 'arrow-up' : 'arrow-down'" size="14" color="#999" />
    </div>

    <div v-if="expanded && tool.result" class="tool-result">
      <pre>{{ tool.result }}</pre>
    </div>

    <div v-if="tool.status === 'calling'" class="tool-progress">
      <van-loading size="16" color="#1677FF" />
      <span>正在执行...</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  tool: {
    type: Object,
    required: true
  }
})

const expanded = ref(false)

const toggleExpand = () => {
  expanded.value = !expanded.value
}

const toolLabels = {
  get_check_item_details: '获取检查项详情',
  get_inspection_summary: '汇总检查结果',
  generate_final_verdict: '生成最终判定',
  search_knowledge: '检索知识库',
  get_enterprise_info: '查询企业信息',
  analyze_photo: '分析照片'
}

const toolIcons = {
  get_check_item_details: 'description',
  get_inspection_summary: 'chart-trending-o',
  generate_final_verdict: 'certificate',
  search_knowledge: 'search',
  get_enterprise_info: 'shop-o',
  analyze_photo: 'photo-o'
}

const getToolLabel = computed(() => {
  return toolLabels[props.tool.name] || props.tool.name
})

const getToolIcon = computed(() => {
  return toolIcons[props.tool.name] || 'setting-o'
})
</script>

<style scoped>
.agent-tool-step {
  background: #FAFAFA;
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
}

.tool-icon {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  background: #E6F4FF;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #1677FF;
}

.tool-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-name {
  font-size: 13px;
  color: #333;
}

.tool-result {
  padding: 0 12px 12px;
}

.tool-result pre {
  margin: 0;
  font-size: 11px;
  background: #F5F5F5;
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.tool-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #E6F4FF;
  font-size: 12px;
  color: #1677FF;
}
</style>