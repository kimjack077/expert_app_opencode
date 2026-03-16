<template>
  <div class="agent-citation">
    <div class="citation-header" @click="toggleExpand">
      <van-icon name="bookmark-o" size="14" color="#1677FF" />
      <span class="citation-title">引用来源 ({{ citations.length }})</span>
      <van-icon :name="expanded ? 'arrow-up' : 'arrow-down'" size="14" color="#999" />
    </div>

    <div v-if="expanded" class="citation-list">
      <div
        v-for="citation in citations"
        :key="citation.id"
        class="citation-item"
      >
        <div class="citation-source">
          <van-icon name="description" size="12" />
          <span>{{ citation.source }}</span>
          <span class="citation-relevance">相关度: {{ citation.relevance }}%</span>
        </div>
        <div class="citation-content" @click="showFullContent(citation)">
          {{ truncateContent(citation.content) }}
          <span v-if="citation.content.length > 100" class="expand-hint">展开全文</span>
        </div>
      </div>
    </div>

    <van-popup
      v-model:show="showDetail"
      position="bottom"
      :style="{ height: '50%', borderRadius: '16px 16px 0 0' }"
    >
      <div v-if="selectedCitation" class="citation-detail">
        <div class="detail-header">
          <span class="detail-title">{{ selectedCitation.source }}</span>
          <van-icon name="cross" size="20" color="#999" @click="showDetail = false" />
        </div>
        <div class="detail-content">
          {{ selectedCitation.content }}
        </div>
        <div class="detail-actions">
          <van-button type="primary" size="small" @click="copyCitation">
            <van-icon name="description" /> 复制引用
          </van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { showToast } from 'vant'

const props = defineProps({
  citations: {
    type: Array,
    default: () => []
  }
})

const expanded = ref(false)
const showDetail = ref(false)
const selectedCitation = ref(null)

const toggleExpand = () => {
  expanded.value = !expanded.value
}

const truncateContent = (content) => {
  if (content.length <= 100) return content
  return content.slice(0, 100) + '...'
}

const showFullContent = (citation) => {
  selectedCitation.value = citation
  showDetail.value = true
}

const copyCitation = () => {
  if (selectedCitation.value) {
    navigator.clipboard.writeText(selectedCitation.value.content)
    showToast('已复制到剪贴板')
  }
}
</script>

<style scoped>
.agent-citation {
  margin-top: 12px;
  border-top: 1px dashed #E8E8E8;
  padding-top: 12px;
}

.citation-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.citation-title {
  flex: 1;
  font-size: 12px;
  color: #666;
}

.citation-list {
  margin-top: 12px;
}

.citation-item {
  background: #FAFAFA;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 8px;
}

.citation-source {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  color: #1677FF;
  margin-bottom: 6px;
}

.citation-relevance {
  margin-left: auto;
  font-weight: 400;
  color: #999;
}

.citation-content {
  font-size: 12px;
  color: #666;
  line-height: 1.5;
}

.expand-hint {
  color: #1677FF;
  margin-left: 4px;
}

.citation-detail {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.detail-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.detail-content {
  flex: 1;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.8;
  color: #333;
  background: #FAFAFA;
  padding: 12px;
  border-radius: 8px;
}

.detail-actions {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}
</style>