<template>
  <div class="tree-node">
    <div class="node-header" :class="{ 'is-category': isCategory }" @click="toggleExpand">
      <div class="node-header-main">
        <span class="node-index">{{ index + 1 }}</span>
        <span class="node-title">{{ item.title }}</span>
      </div>
      
      <!-- 检查结论放在右侧 -->
      <div v-if="!isCategory" class="node-result">
        <span v-if="getItemScore && getItemScore(item) !== null" class="item-quantified-score" style="color: #D97706; font-size: 13px; margin-right: 8px; font-weight: 500;">
          {{ getItemScore(item) }}分
        </span>

        <!-- 通过/不通过类型 -->
        <van-tag
          v-if="item.radio_value"
          :type="getRadioTagType(item.radio_value)"
          size="medium"
        >
          {{ getRadioText(item.radio_value) }}
        </van-tag>

        <!-- 打分类型 -->
        <van-tag
          v-else-if="item.score_value !== null && item.score_value !== undefined && item.score_value !== ''"
          type="primary"
          size="medium"
        >
          {{ item.score_value }}分
        </van-tag>

        <!-- 数值类型 -->
        <van-tag
          v-else-if="item.numeric_value !== null && item.numeric_value !== undefined && item.numeric_value !== ''"
          type="primary"
          size="medium"
        >
          {{ item.numeric_value }}{{ item.unit || '' }}
        </van-tag>

        <!-- 文字描述类型 -->
        <van-tag
          v-else-if="item.text_value"
          type="purple"
          size="medium"
        >
          {{ item.text_value.length > 6 ? item.text_value.substring(0, 6) + '...' : item.text_value }}
        </van-tag>

        <!-- 多选类型 -->
        <van-tag
          v-else-if="item.multi_value && item.multi_value.length > 0"
          type="cyan"
          size="medium"
        >
          已选{{ item.multi_value.length }}项
        </van-tag>

        <!-- 未填写 -->
        <van-tag v-else type="default" size="medium">未填写</van-tag>
        
        <van-icon :name="isExpanded ? 'arrow-up' : 'arrow-down'" class="expand-icon" />
      </div>
    </div>

    <!-- 展开的内容：详细信息 -->
    <div v-if="!isCategory && isExpanded" class="node-details">
      <!-- 检查项详细信息 -->
      <div class="detail-section">
        <div class="detail-title">检查项说明</div>
        <div v-if="item.description" class="detail-item">
          <b>检查要求：</b><span>{{ item.description }}</span>
        </div>
        <div v-if="item.check_method" class="detail-item">
          <b>检查方法：</b><span>{{ item.check_method }}</span>
        </div>
        <div v-if="item.legal_basis" class="detail-item">
          <b>法律依据：</b><span>{{ item.legal_basis }}</span>
        </div>
        <div v-if="item.ai_prompt_template" class="detail-item">
          <b>知识库指引：</b><span>{{ item.ai_prompt_template }}</span>
        </div>
        <div v-if="item.numeric_value !== null && item.numeric_value !== undefined && item.numeric_value !== '' && (item.min_value !== null || item.max_value !== null)" class="detail-item">
          <b>数值参考：</b><span style="color: var(--primary-color);">{{ formatRange(item.min_value, item.max_value) }}{{ item.unit || '' }}</span>
        </div>
      </div>

      <!-- 结果详情 -->
      <div class="detail-section results-section" style="margin-top: 12px;">
        <div class="detail-title">检查结论与说明</div>
        
        <div v-if="item.problem_description" class="detail-item">
          <var style="color: var(--danger-color); font-style: normal; font-weight: 500;">问题描述：</var>
          <span style="color: var(--danger-color);">{{ item.problem_description }}</span>
        </div>
        
        <div v-if="item.rectification_suggestion" class="detail-item">
          <var style="color: var(--warning-color); font-style: normal; font-weight: 500;">整改建议：</var>
          <span>{{ item.rectification_suggestion }}</span>
        </div>
        
        <div v-if="item.inspector_note" class="detail-item">
          <b>审核记录：</b>
          <span>{{ item.inspector_note }}</span>
        </div>
        
        <div v-if="item.ai_suggestion && item.ai_suggestion !== '0'" class="detail-item ai-suggestion-card">
          <div class="ai-header">
            <van-icon name="bulb-o" />
            <span>AI智能裁定与建议</span>
          </div>
          <div class="ai-content">{{ item.ai_suggestion }}</div>
        </div>
      </div>

      <!-- 照片 (附件) -->
      <div v-if="item.photos && item.photos.length > 0" class="result-photos" style="margin-left: 0;">
        <van-image
          v-for="(photo, idx) in item.photos"
          :key="idx"
          :src="normalizePhotoUrl(photo)"
          width="60"
          height="60"
          fit="cover"
          class="photo-item"
          @click.stop="() => previewImage(normalizePhotoUrl(photo), item.photos.map(normalizePhotoUrl))"
        />
      </div>
    </div>

    <!-- 递归渲染子节点 -->
    <div v-if="hasChildren" class="node-children">
      <TreeItem
        v-for="(child, childIndex) in item.children"
        :key="child.id"
        :item="child"
        :index="childIndex"
        :get-check-type-text="getCheckTypeText"
        :get-radio-text="getRadioText"
        :get-radio-tag-type="getRadioTagType"
        :format-range="formatRange"
        :preview-image="previewImage"
        :get-item-score="getItemScore"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
  index: {
    type: Number,
    required: true,
  },
  getCheckTypeText: {
    type: Function,
    required: true,
  },
  getRadioText: {
    type: Function,
    required: true,
  },
  getRadioTagType: {
    type: Function,
    required: true,
  },
  formatRange: {
    type: Function,
    required: true,
  },
  previewImage: {
    type: Function,
    required: true,
  },
  getItemScore: {
    type: Function,
    default: null,
  },
})

// Ensure photo URLs are valid: use forward slashes and ensure leading /
const normalizePhotoUrl = (url) => {
  if (!url) return url
  // Replace Windows backslashes with forward slashes
  url = url.replace(/\\/g, '/')
  if (url.startsWith('http')) return url
  if (!url.startsWith('/')) url = '/' + url
  return url
}

const hasChildren = props.item.children && props.item.children.length > 0
const isCategory = props.item.is_category

const isExpanded = ref(false)
const toggleExpand = () => {
  if (!isCategory) {
    isExpanded.value = !isExpanded.value
  }
}
</script>

<style scoped>
.tree-node {
  margin-bottom: 8px;
}

.node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-white);
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-base);
  cursor: pointer;
}

.node-header-main {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.node-header:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.node-header.is-category {
  background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
  box-shadow: var(--shadow-md);
  cursor: default;
}

.node-header.is-category:hover {
  box-shadow: var(--shadow-lg);
  transform: none;
}

.node-header.is-category .node-title,
.node-header.is-category .node-index {
  color: var(--bg-white);
}

.node-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: var(--primary-color);
  color: var(--bg-white);
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  margin-right: 12px;
  flex-shrink: 0;
  font-family: var(--font-primary);
}

.node-header.is-category .node-index {
  background: rgba(255, 255, 255, 0.25);
  backdrop-filter: blur(10px);
}

.node-title {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-primary);
}

.node-result {
  flex-shrink: 0;
  margin-left: 8px;
  display: flex;
  align-items: center;
}

.expand-icon {
  margin-left: 8px;
  color: var(--text-muted);
  font-size: 14px;
  transition: transform 0.2s;
}

.node-details {
  background: #f8fafc;
  padding: 16px;
  margin: 0;
  border-radius: 0 0 12px 12px;
  border: 1px solid #e2e8f0;
  border-top: none;
  font-size: 13px;
  color: var(--text-secondary);
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-item {
  display: flex;
  align-items: flex-start;
  line-height: 1.5;
}

.detail-item b {
  font-weight: 500;
  color: var(--text-primary);
  flex-shrink: 0;
}

.detail-item span {
  flex: 1;
  word-break: break-all;
}

.ai-suggestion-card {
  margin-top: 8px;
  background: linear-gradient(135deg, rgba(79, 70, 229, 0.05) 0%, rgba(129, 140, 248, 0.05) 100%);
  border: 1px solid rgba(79, 70, 229, 0.2);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
}

.ai-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--primary-color);
  font-weight: 600;
  margin-bottom: 6px;
}

.ai-content {
  color: var(--text-primary);
  line-height: 1.5;
  white-space: pre-wrap;
}

.node-children {
  margin-left: 24px;
  margin-top: 6px;
  padding-left: 12px;
  border-left: 2px solid var(--border-light);
}

.result-photos {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.photo-item {
  border-radius: 8px;
  cursor: pointer;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-base);
}

.photo-item:hover {
  box-shadow: var(--shadow-md);
  transform: scale(1.05);
}

@media (prefers-reduced-motion: reduce) {
  .node-header,
  .photo-item {
    transition: none;
  }
}
</style>
