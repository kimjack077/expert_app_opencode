import { useState, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Button, Space, message, Radio, InputNumber, Input,
  Upload, Progress, Alert, Spin, Modal, Drawer, Badge, Tooltip, Divider, Image, Checkbox, ConfigProvider
} from 'antd'
import {
  ArrowLeftOutlined, CheckCircleOutlined, CloseCircleOutlined,
  BulbOutlined, CameraOutlined, LoadingOutlined, SaveOutlined,
  WarningOutlined, ClockCircleOutlined, HistoryOutlined, InfoCircleOutlined,
} from '@ant-design/icons'
import { recordApi, llmApi, mediaApi } from '@/services/api'
import EnterpriseRiskProfile from '@/components/EnterpriseRiskProfile'
import { normalizeVerdictFields, resolveCheckType } from '@/utils/completion'
import { normalizeResultOptions } from '@/utils/resultOptions'
import type { UploadProps } from 'antd'

const { TextArea } = Input

interface ItemData {
  id: string
  title: string
  description?: string
  check_method?: string
  legal_basis?: string
  risk_level?: 'high' | 'medium' | 'low'
  result_type: 'pass_fail' | 'score' | 'numeric' | 'text' | 'multi_check'
  result_options?: Array<{ value: string; label: string } | string> | { options: Array<{ value: string; label: string } | string> }
  min_value?: number
  max_value?: number
  unit?: string
  max_score?: number
  pass_score?: number
  score_step?: number
  use_ai?: boolean
  is_required?: boolean
  allow_attachment?: boolean
  attachment_required?: boolean
  check_type?: string
}

interface HistoryStats {
  has_history: boolean
  total_checks: number
  pass_count: number
  fail_count: number
  na_count: number
  fail_rate: number
  last_check_date?: string
  last_result?: string
}

interface ItemResult {
  radio_value?: string
  score_value?: number
  numeric_value?: number
  text_value?: string
  multi_value?: string[]
  inspector_note?: string
  photos?: string[]
}

export default function AuditItemDetail() {
  const { recordId, itemId } = useParams<{ recordId: string; itemId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [llmLoading, setLlmLoading] = useState(false)
  const [llmContent, setLlmContent] = useState<string | null>(null)
  const [llmType, setLlmType] = useState<'suggestion' | 'basis'>('suggestion')
  const [drawerVisible, setDrawerVisible] = useState(false)

  const [record, setRecord] = useState<any>(null)
  const [itemData, setItemData] = useState<ItemData | null>(null)
  const [historyStats, setHistoryStats] = useState<HistoryStats | null>(null)
  const [result, setResult] = useState<ItemResult>({})
  const [recordItemId, setRecordItemId] = useState<string | null>(null)
  const readOnly = record?.status === 'submitted' || searchParams.get('mode') === 'view'
  const resultType = resolveCheckType(itemData)
  const resultOptions = normalizeResultOptions(itemData?.result_options)

  useEffect(() => {
    if (recordId && itemId) {
      fetchData()
    }
  }, [recordId, itemId])

  const fetchData = async () => {
    setLoading(true)
    try {
      // 获取记录详情
      const recordRes: any = await recordApi.getRecord(recordId!)
      setRecord(recordRes.data)

      const itemsRes: any = await recordApi.getRecordItems(recordId!)
      const recordItems = Array.isArray(itemsRes.data) ? itemsRes.data : []
      const existingResult = recordItems.find((i: any) => i.id === itemId)
        || recordItems.find((i: any) => i.template_item_id === itemId)
      const templateItemId = existingResult?.template_item_id || itemId
      const flatItems = flattenItems(recordRes.data?.template?.items || [])
      const item = flatItems.find((i: any) => (i.template_item_id || i.id) === templateItemId)
      // 模板节点被删除/调整时仍使用落库快照查看及填写历史明细。
      const snapshot = existingResult ? {
        ...existingResult,
        id: templateItemId,
        title: existingResult.item_title || existingResult.title || '历史检查项',
        check_type: existingResult.check_type,
        result_type: existingResult.result_type || 'pass_fail',
      } : null
      setItemData(item ? { ...item, id: templateItemId } : snapshot)
      setRecordItemId(existingResult?.id || null)
      setHistoryStats(null)
      setResult(existingResult ? {
        radio_value: normalizeVerdictFields(existingResult).radio_value,
        score_value: existingResult.score_value,
        numeric_value: existingResult.numeric_value,
        text_value: existingResult.text_value,
        multi_value: existingResult.multi_value || [],
        inspector_note: existingResult.inspector_note,
        photos: existingResult.photos || [],
      } : {})
      if (existingResult?.id) fetchHistoryStats(existingResult.id)
    } catch (error) {
      console.error('Failed to fetch data:', error)
      message.error('获取检查项数据失败')
    } finally {
      setLoading(false)
    }
  }

  const flattenItems = (items: any[], result: any[] = []): any[] => {
    for (const item of items) {
      if (!item.is_category) {
        result.push(item)
      }
      if (item.children && item.children.length > 0) {
        flattenItems(item.children, result)
      }
    }
    return result
  }

  const fetchHistoryStats = async (savedItemId: string) => {
    try {
      const res: any = await recordApi.getItemHistoryStats(recordId!, savedItemId)
      const data = res.data || {}
      setHistoryStats({
        has_history: !!data.has_history,
        total_checks: data.total_inspections || 0,
        pass_count: data.pass_count || 0,
        fail_count: data.fail_count || 0,
        na_count: data.na_count || 0,
        fail_rate: data.fail_rate || 0,
        last_check_date: data.last_inspection_date || undefined,
        last_result: data.last_result || undefined,
      })
    } catch {
      // 检查项尚未落库（新记录）或记录未关联企业时没有历史可查
      setHistoryStats(null)
    }
  }

  const handleSaveResult = async (field: string, value: any) => {
    if (readOnly || !recordId || !itemData?.id) return
    setSaving(true)
    try {
      // Convert numeric values to string for backend compatibility
      const valueToSave = (field === 'numeric_value' || field === 'score_value') && typeof value === 'number'
        ? String(value)
        : value

      const data = {
        template_item_id: itemData.id,
        [field]: valueToSave,
      }

      let res: any
      if (recordItemId) {
        // 更新已有记录
        res = await recordApi.updateRecordItem(recordId!, recordItemId, data)
      } else {
        // 创建新记录
        res = await recordApi.createRecordItem(recordId!, data)
        setRecordItemId(res.data?.id)
        if (res.data?.id) fetchHistoryStats(res.data.id)
      }

      setResult(prev => ({ ...prev, [field]: value }))
      message.success('已保存')
    } catch (error: any) {
      console.error('保存失败:', error)
      const errorMsg = error.response?.data?.message || error.message || '保存失败'
      message.error(errorMsg)
    } finally {
      setSaving(false)
    }
  }

  const handleLLMRequest = async (type: 'suggestion' | 'basis') => {
    if (readOnly) return
    if (!recordItemId) {
      message.warning('请先填写检查结果后再获取AI建议')
      return
    }
    setLlmLoading(true)
    setLlmType(type)
    setDrawerVisible(true)
    try {
      const res: any = type === 'suggestion'
        ? await llmApi.getSuggestion({ task_id: recordId!, record_id: recordItemId!, use_cache: false })
        : await llmApi.getBasis({ task_id: recordId!, record_id: recordItemId!, use_cache: false })
      setLlmContent(res.data?.content || '暂无内容')
    } catch (error) {
      setLlmContent('获取失败，请稍后重试')
    } finally {
      setLlmLoading(false)
    }
  }

  const handleUpload = async (uploadInfo: any) => {
    if (readOnly) {
      uploadInfo.onError?.(new Error('已提交记录不能上传照片'))
      return
    }
    const file = uploadInfo.file as File
    if (!recordId) return
    try {
      // 优先用检查记录项 ID，后端据此换算为任务检查项，保住照片与条目的关联
      let savedItemId = recordItemId
      if (!savedItemId) {
        const saved: any = await recordApi.createRecordItem(recordId, { template_item_id: itemData!.id })
        savedItemId = saved.data?.id
        if (!savedItemId) throw new Error('检查项尚未保存')
        setRecordItemId(savedItemId)
      }
      const res: any = await mediaApi.upload(file, { record_id: savedItemId })
      const photoUrl = res.data?.file_path
      if (photoUrl) {
        const updatedPhotos = [...(result.photos || []), photoUrl]
        try {
          await recordApi.updateRecordItem(recordId, savedItemId, { photos: updatedPhotos })
        } catch (error) {
          if (res.data?.id) await mediaApi.deleteMedia(res.data.id).catch(() => {})
          throw error
        }
        setResult(prev => ({ ...prev, photos: updatedPhotos }))
      }
      if (uploadInfo.onSuccess) uploadInfo.onSuccess({}, uploadInfo.file)
    } catch (error) {
      message.error('上传失败')
      if (uploadInfo.onError) uploadInfo.onError(error)
    }
  }

  const uploadProps: UploadProps = {
    accept: 'image/*',
    showUploadList: false,
    customRequest: handleUpload,
  }

  // 风险等级颜色
  const riskLevelConfig: Record<string, { color: string; text: string }> = {
    high: { color: '#EF4444', text: '高风险' },
    medium: { color: '#F59E0B', text: '中风险' },
    low: { color: '#10B981', text: '低风险' },
  }

  // 结果标签
  const getResultTag = () => {
    if (result.radio_value) {
      const valueMap: Record<string, { color: string; text: string }> = {
        'pass': { color: 'success', text: '合格' },
        'fail': { color: 'error', text: '不合格' },
        'na': { color: 'default', text: '不适用' },
      }
      const info = valueMap[result.radio_value] || { color: 'default', text: result.radio_value }
      return <Tag color={info.color}>{info.text}</Tag>
    }
    if (result.score_value !== undefined && result.score_value !== null) {
      const isPass = itemData?.pass_score && result.score_value >= itemData.pass_score
      return <Tag color={isPass ? 'success' : 'error'}>{result.score_value} 分</Tag>
    }
    if (result.numeric_value !== undefined && result.numeric_value !== null) {
      return <Tag color="processing">{result.numeric_value} {itemData?.unit || ''}</Tag>
    }
    if (result.text_value) {
      return <Tag color="default">已填写</Tag>
    }
    if (result.multi_value?.length) return <Tag color="processing">已选 {result.multi_value.length} 项</Tag>
    return <Tag>未填写</Tag>
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!itemData) {
    return (
      <div style={{ padding: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>返回</Button>
        <div style={{ marginTop: 24, textAlign: 'center' }}>检查项不存在</div>
      </div>
    )
  }

  return (
    <div style={{ background: '#f0f2f5', minHeight: '100vh', padding: 24 }}>
      {/* 页面头部 */}
      <div style={{ background: '#fff', padding: '16px 24px', marginBottom: 16, borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
              返回
            </Button>
            <Divider type="vertical" />
            <span style={{ fontSize: 18, fontWeight: 600 }}>{itemData.title}</span>
            {getResultTag()}
            {itemData.risk_level && (
              <Tag color={riskLevelConfig[itemData.risk_level]?.color}>
                {riskLevelConfig[itemData.risk_level]?.text}
              </Tag>
            )}
          </Space>
          <Space>
            <Button
              icon={<BulbOutlined />}
              disabled={readOnly}
              onClick={() => handleLLMRequest('suggestion')}
              style={{ background: '#faad14', borderColor: '#faad14', color: '#fff' }}
            >
              AI建议
            </Button>
            <Button
              icon={<InfoCircleOutlined />}
              disabled={readOnly}
              onClick={() => handleLLMRequest('basis')}
              style={{ background: '#722ed1', borderColor: '#722ed1', color: '#fff' }}
            >
              法规依据
            </Button>
          </Space>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16 }}>
        {/* 左侧主内容 */}
        <div style={{ flex: 1 }}>
          {/* 历史检查统计 */}
          {historyStats?.has_history && (
            <Card
              title={
                <Space>
                  <HistoryOutlined style={{ color: 'var(--primary-color)' }} />
                  <span>历史检查记录</span>
                </Space>
              }
              style={{ marginBottom: 16 }}
              styles={{ header: { borderBottom: '1px solid var(--border-color)' } }}
            >
              <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--primary-color)' }}>
                      {historyStats.total_checks}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>总检查次数</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 24, fontWeight: 700, color: '#10B981' }}>
                      {historyStats.pass_count}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>合格</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 24, fontWeight: 700, color: '#EF4444' }}>
                      {historyStats.fail_count}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>不合格</div>
                  </div>
                </div>

                {historyStats.fail_rate >= 50 && (
                  <Alert
                    type="error"
                    icon={<WarningOutlined />}
                    message="高频不合格预警"
                    description={`该检查项历史不合格率 ${historyStats.fail_rate.toFixed(1)}%，请重点关注`}
                    showIcon
                    style={{ flex: 1 }}
                  />
                )}
              </div>
            </Card>
          )}

          {/* 检查项详情 */}
          <Card
            title="检查项详情"
            style={{ marginBottom: 16 }}
            styles={{ header: { borderBottom: '1px solid var(--border-color)' } }}
          >
            <Descriptions column={1} labelStyle={{ width: 120 }}>
              <Descriptions.Item label="检查项目">{itemData.title}</Descriptions.Item>
              {itemData.description && (
                <Descriptions.Item label="检查内容">{itemData.description}</Descriptions.Item>
              )}
              {itemData.check_method && (
                <Descriptions.Item label="检查方法">
                  <span style={{ color: '#1890ff' }}>{itemData.check_method}</span>
                </Descriptions.Item>
              )}
              {itemData.legal_basis && (
                <Descriptions.Item label="法律依据">
                  <span style={{ color: '#52c41a' }}>{itemData.legal_basis}</span>
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>

          {/* 检查结果填写 */}
          <ConfigProvider componentDisabled={readOnly}>
          <Card
            title="检查结果"
            extra={saving ? <Spin size="small" /> : null}
            style={{ marginBottom: 16 }}
            styles={{ header: { borderBottom: '1px solid var(--border-color)' } }}
          >
            {/* 必填项提示 */}
            {itemData.is_required !== false && (
              <Alert
                type="info"
                message="本检查项为必填项，请完成检查结果填写"
                style={{ marginBottom: 16, fontSize: 12 }}
                showIcon
              />
            )}

            {/* 合格/不合格选择 */}
            {(resultType === 'radio' || resultType === 'audit_3level') && (
              <div style={{ marginBottom: 24 }}>
                <div style={{ marginBottom: 8, fontWeight: 500 }}>
                  {itemData.is_required !== false && <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>}
                  检查结论
                </div>
                <Radio.Group
                  value={result.radio_value}
                  onChange={(e) => handleSaveResult('radio_value', e.target.value)}
                  buttonStyle="solid"
                  size="large"
                >
                  {(resultOptions.length ? resultOptions : [
                    { value: 'pass', label: '合格' },
                    { value: 'fail', label: '不合格' },
                    { value: 'na', label: '不适用' },
                  ]).map((opt) => (
                    <Radio.Button key={opt.value} value={opt.value}>
                      {opt.label}
                    </Radio.Button>
                  ))}
                </Radio.Group>
              </div>
            )}

            {/* 得分输入 */}
            {resultType === 'multi' && (
              <div style={{ marginBottom: 24 }}>
                <div id="multi-result-label" style={{ marginBottom: 8, fontWeight: 500 }}>多选结果</div>
                <Checkbox.Group
                  aria-labelledby="multi-result-label"
                  disabled={readOnly || saving}
                  options={resultOptions || []}
                  value={result.multi_value || []}
                  onChange={(values) => handleSaveResult('multi_value', values)}
                />
              </div>
            )}
            {resultType === 'score' && (
              <div style={{ marginBottom: 24 }}>
                <div style={{ marginBottom: 8, fontWeight: 500 }}>
                  {itemData.is_required !== false && <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>}
                  得分
                </div>
                <Space>
                  <InputNumber
                    value={result.score_value}
                    onChange={(value) => setResult(prev => ({ ...prev, score_value: value as number }))}
                    onBlur={() => result.score_value !== undefined && handleSaveResult('score_value', result.score_value)}
                    min={0}
                    max={itemData.max_score || 100}
                    step={itemData.score_step || 1}
                    style={{ width: 120 }}
                  />
                  <span>/ {itemData.max_score || 100} 分</span>
                </Space>
                {itemData.pass_score && (
                  <div style={{ color: '#888', fontSize: 12, marginTop: 8 }}>
                    合格线：{itemData.pass_score} 分
                  </div>
                )}
              </div>
            )}

            {/* 数值输入 */}
            {resultType === 'numeric' && (
              <div style={{ marginBottom: 24 }}>
                <div style={{ marginBottom: 8, fontWeight: 500 }}>
                  {itemData.is_required !== false && <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>}
                  测量值
                </div>
                <Space>
                  <InputNumber
                    value={result.numeric_value}
                    onChange={(value) => setResult(prev => ({ ...prev, numeric_value: value as number }))}
                    onBlur={() => result.numeric_value !== undefined && handleSaveResult('numeric_value', result.numeric_value)}
                    min={itemData.min_value}
                    max={itemData.max_value}
                    placeholder={itemData.min_value !== undefined && itemData.max_value !== undefined
                      ? `范围: ${itemData.min_value} ~ ${itemData.max_value}`
                      : '请输入数值'}
                    style={{ width: 200 }}
                  />
                  {itemData.unit && <span>{itemData.unit}</span>}
                </Space>
              </div>
            )}

            {/* 文本输入 */}
            {resultType === 'text' && (
              <div style={{ marginBottom: 24 }}>
                <div style={{ marginBottom: 8, fontWeight: 500 }}>
                  {itemData.is_required !== false && <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>}
                  检查结果描述
                </div>
                <TextArea
                  rows={4}
                  placeholder="请输入检查结果描述..."
                  value={result.text_value || ''}
                  onChange={(e) => setResult(prev => ({ ...prev, text_value: e.target.value }))}
                  onBlur={() => handleSaveResult('text_value', result.text_value)}
                />
              </div>
            )}

            {/* 审核记录 */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>审核记录</div>
              <TextArea
                rows={3}
                placeholder="请输入审核记录..."
                value={result.inspector_note || ''}
                onChange={(e) => setResult(prev => ({ ...prev, inspector_note: e.target.value }))}
                onBlur={() => handleSaveResult('inspector_note', result.inspector_note)}
              />
            </div>

            {/* 照片上传 */}
            {(itemData.allow_attachment || itemData.attachment_required) && (
              <div>
                <div style={{ marginBottom: 8, fontWeight: 500 }}>
                  {itemData.attachment_required && <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>}
                  现场照片
                  {itemData.attachment_required && (
                    <span style={{ color: '#ff4d4f', fontSize: 12, marginLeft: 8 }}>（必填）</span>
                  )}
                </div>
                <Upload {...uploadProps}>
                  <Button icon={<CameraOutlined />}>上传照片</Button>
                </Upload>
                {result.photos && result.photos.length > 0 && (
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                    <Image.PreviewGroup>
                      {result.photos.map((url, idx) => {
                        const normalizedUrl = (!url || url.startsWith('/') || url.startsWith('http')) ? url : '/' + url
                        return (
                          <Image
                            key={idx}
                            src={normalizedUrl}
                            alt={`附件图片 ${idx + 1}`}
                            width={80}
                            height={80}
                            style={{ borderRadius: 6, objectFit: 'cover', border: '1px solid #e2e8f0', cursor: 'pointer' }}
                          />
                        )
                      })}
                    </Image.PreviewGroup>
                  </div>
                )}
              </div>
            )}
          </Card>
          </ConfigProvider>
        </div>

        {/* 右侧企业信息（如果需要） */}
        <div style={{ width: 300 }}>
          {/* 企业风险档案 */}
          {record?.enterprise_id && (
            <EnterpriseRiskProfile enterpriseId={record.enterprise_id} compact />
          )}

          <Card
            title="企业信息"
            size="small"
            style={{ marginBottom: 16 }}
          >
            <Descriptions column={1} size="small">
              <Descriptions.Item label="企业名称">
                {record?.enterprise_name || record?.enterprise?.name || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="检查模板">
                {record?.template?.name || '-'}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 操作提示 */}
          <Card title="操作提示" size="small">
            <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.8 }}>
              <p>1. 选择检查结论或填写检查结果</p>
              <p>2. 填写审核记录（可选）</p>
              <p>3. 上传现场照片（如需要）</p>
              <p>4. 点击AI建议获取智能分析</p>
            </div>
          </Card>
        </div>
      </div>

      {/* AI内容抽屉 */}
      <Drawer
        title={llmType === 'suggestion' ? 'AI 监管建议' : '法规标准依据'}
        placement="right"
        width={480}
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
      >
        {llmLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
            <p style={{ marginTop: 16, color: '#666' }}>AI 正在分析...</p>
          </div>
        ) : (
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
            {llmContent}
          </div>
        )}
      </Drawer>
    </div>
  )
}
