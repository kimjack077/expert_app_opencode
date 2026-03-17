# 多模态与嵌入模型使用说明

## 概述

本系统已集成以下 AI 模型：
- **多模态模型**：阿里云通义千问（Qwen3.5 Plus），支持对检查照片进行智能分析
- **嵌入模型**：BAAI/bge-m3，用于知识库向量检索（RAG）

---

## 一、多模态图片分析

### 模型配置

配置文件位置：`backend/app/config.py`

```python
# Vision/Multimodal LLM for image analysis (Qwen3.5 Plus)
VISION_LLM_BASE_URL: str = "https://coding.dashscope.aliyuncs.com/v1"
VISION_LLM_MODEL: str = "qwen3.5-plus"
VISION_LLM_API_KEY: str = "sk-sp-473938c68b6d4027b4c0f7754c8028db"
```

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/ai-enhanced/photo/analyze` | POST | 单张照片分析 |
| `/api/ai-enhanced/photo/analyze/stream` | POST | 流式照片分析 |
| `/api/ai-enhanced/photo/batch-analyze` | POST | 批量照片分析 |

## API 使用方法

### 1. 单张照片分析

**请求示例：**

```bash
curl -X POST "http://localhost:8000/api/ai-enhanced/photo/analyze" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{
    "media_file_id": "<媒体文件ID>",
    "analysis_type": "compliance",
    "check_item_title": "消防设施检查"
  }'
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `media_file_id` | string | 是 | 媒体文件ID（需先上传图片） |
| `analysis_type` | string | 否 | 分析类型：`compliance`（合规）、`safety`（安全）、`quality`（质量）、`general`（通用），默认 `compliance` |
| `task_item_id` | string | 否 | 关联的检查项记录ID |
| `check_item_title` | string | 否 | 检查项标题，用于提供上下文 |
| `custom_prompt` | string | 否 | 自定义分析提示词 |

**响应示例：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "分析记录ID",
    "media_file_id": "媒体文件ID",
    "analysis_type": "compliance",
    "description": "照片内容描述",
    "issues": [
      {
        "type": "safety",
        "severity": "high",
        "description": "灭火器过期",
        "location": "走廊入口"
      }
    ],
    "compliance_status": "non_compliant",
    "confidence": 0.85,
    "recommendations": [
      "立即更换过期的灭火器",
      "建立消防设施定期检查制度"
    ],
    "model_used": "qwen3.5-plus",
    "duration_ms": 2500
  }
}
```

### 2. 流式照片分析

适用于需要实时显示分析进度的场景。

**请求示例：**

```javascript
const response = await fetch('/api/ai-enhanced/photo/analyze/stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    media_file_id: '<媒体文件ID>',
    analysis_type: 'compliance'
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      console.log(data.type, data.content);
    }
  }
}
```

**流式事件类型：**

| 类型 | 说明 |
|------|------|
| `thinking` | 分析过程中的思考内容 |
| `done` | 分析完成，包含最终结果 |
| `error` | 发生错误 |

### 3. 批量照片分析

**请求示例：**

```bash
curl -X POST "http://localhost:8000/api/ai-enhanced/photo/batch-analyze" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{
    "media_file_ids": ["id1", "id2", "id3"],
    "analysis_type": "safety"
  }'
```

## 分析结果说明

### 合规状态 (compliance_status)

| 状态 | 说明 |
|------|------|
| `compliant` | 合规，未发现问题 |
| `non_compliant` | 不合规，存在违规问题 |
| `warning` | 警告，存在潜在风险 |
| `unknown` | 无法判断 |

### 问题类型 (issues.type)

| 类型 | 说明 |
|------|------|
| `safety` | 安全问题 |
| `quality` | 质量问题 |
| `compliance` | 合规问题 |
| `other` | 其他问题 |

### 严重程度 (issues.severity)

| 级别 | 说明 |
|------|------|
| `high` | 高危，需立即处理 |
| `medium` | 中等，需尽快处理 |
| `low` | 低危，可延后处理 |

## 代码集成示例

### Python 后端调用

```python
from app.services.multimodal_service import multimodal_service

# 分析照片
result = await multimodal_service.analyze_photo(
    media_file_id="媒体文件ID",
    db=db_session,
    analysis_type="compliance",
    check_item_title="消防设施检查"
)

print(f"合规状态: {result['compliance_status']}")
print(f"发现问题: {len(result['issues'])}个")
```

### 前端 Vue 组件示例

```vue
<template>
  <div class="photo-analysis">
    <van-uploader :after-read="onPhotoUpload" />
    <div v-if="analyzing">分析中...</div>
    <div v-if="result">
      <p>合规状态: {{ result.compliance_status }}</p>
      <div v-for="issue in result.issues" :key="issue.description">
        <van-tag :type="issue.severity === 'high' ? 'danger' : 'warning'">
          {{ issue.type }}
        </van-tag>
        {{ issue.description }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { uploadFile, analyzePhoto } from '@/api/media';

const analyzing = ref(false);
const result = ref(null);

const onPhotoUpload = async (file) => {
  analyzing.value = true;

  // 1. 上传图片
  const uploadResult = await uploadFile(file.file);

  // 2. 分析图片
  result.value = await analyzePhoto(uploadResult.data.id, {
    analysis_type: 'compliance',
    check_item_title: '现场检查'
  });

  analyzing.value = false;
};
</script>
```

## 注意事项

1. **图片要求**
   - 支持格式：JPEG、PNG
   - 最小尺寸：宽度和高度均需大于 10 像素
   - 建议尺寸：800x600 以上，以获得更好的分析效果

2. **性能考虑**
   - 单张图片分析时间约 2-5 秒
   - 批量分析时建议每次不超过 10 张
   - 大图片会自动压缩处理

3. **错误处理**
   - API 调用失败时会返回错误信息
   - 建议实现重试机制（最多 3 次）
   - 网络超时默认为 180 秒

4. **费用说明**
   - 使用阿里云 DashScope API
   - 按 token 计费，具体价格请参考阿里云官网

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/app/config.py` | 模型配置 |
| `backend/app/services/multimodal_service.py` | 多模态服务实现 |
| `backend/app/routers/ai_enhanced.py` | API 路由定义 |
| `backend/app/models/rag.py` | PhotoAnalysis 数据模型 |

## 更新日志

- **2026-03-17**: 初始版本，集成 Qwen3.5 Plus 多模态模型
- **2026-03-17**: 新增 BAAI/bge-m3 嵌入模型，用于知识库向量检索

---

## 二、嵌入模型（RAG 知识库检索）

### 模型配置

配置文件位置：`backend/app/config.py`

```python
# Primary Embedding model for RAG (BGE-M3 via OpenAI-compatible API)
EMBEDDING_BASE_URL: str = "https://api.edgefn.net/v1"
EMBEDDING_MODEL: str = "BAAI/bge-m3"
EMBEDDING_API_KEY: str = "sk-PJHqVIOVEgya3CAu12682eFb2cBe4aBcB2396625E1Bc7cA3"
```

### 模型特点

- **BAAI/bge-m3** 是北京智源人工智能研究院开发的多语言嵌入模型
- 支持中英文等多语言文本
- 嵌入维度：1024
- 通过 OpenAI 兼容 API 调用

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/knowledge/embeddings/create` | POST | 为知识库文档创建嵌入 |
| `/api/knowledge/search` | POST | 语义搜索知识库 |
| `/api/ai-enhanced/link-regulations` | POST | 自动关联检查项与法规 |

### 使用示例

#### 1. 创建文档嵌入

```bash
curl -X POST "http://localhost:8000/api/knowledge/embeddings/create" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{
    "document_id": "<文档ID>"
  }'
```

#### 2. 语义搜索知识库

```bash
curl -X POST "http://localhost:8000/api/knowledge/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{
    "query": "消防安全管理规定",
    "top_k": 5
  }'
```

#### 3. Python 代码调用

```python
from app.services.rag_service import rag_service

# 搜索知识库
results = await rag_service.search_knowledge(
    query="消防安全管理规定",
    db=db_session,
    top_k=5
)

for result in results:
    print(f"文档: {result['document_title']}")
    print(f"相关度: {result['similarity']:.2f}")
    print(f"内容: {result['content'][:100]}...")
```

#### 4. 自动关联检查项与法规

```python
# 将检查项自动关联到相关法规
links = await rag_service.link_check_item_to_regulations(
    template_item_id="检查项ID",
    db=db_session,
    top_k=3,
    min_similarity=0.5
)
```

### 嵌入向量说明

| 属性 | 值 |
|------|-----|
| 维度 | 1024 |
| 输入长度限制 | 8000 字符 |
| 支持语言 | 中文、英文等多语言 |
| 相似度计算 | 余弦相似度 |

### 相关文件

| 文件 | 说明 |
|------|------|
| `backend/app/config.py` | 模型配置 |
| `backend/app/services/rag_service.py` | RAG 服务实现 |
| `backend/app/models/rag.py` | KnowledgeEmbedding 数据模型 |
| `backend/app/routers/knowledge.py` | 知识库 API 路由 |