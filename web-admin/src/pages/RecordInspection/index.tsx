import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Button, Input, Space, Tag, Spin, message,
  Progress, Upload, Drawer, Radio, InputNumber, Select, Alert, Modal,
  Row, Col, Statistic, Divider
} from 'antd'
import {
  ArrowLeftOutlined, CheckCircleOutlined, CloseCircleOutlined,
  BulbOutlined, CameraOutlined,
  LoadingOutlined, SaveOutlined, SendOutlined, InfoCircleOutlined,
  SafetyCertificateOutlined, RobotOutlined
} from '@ant-design/icons'
import { recordApi, llmApi, mediaApi } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const { TextArea } = Input

export default function RecordInspection() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { token } = useAuthStore()
  const [record, setRecord] = useState<any>(null)
  const [items, setItems] = useState<any[]>([])
  const [flatItems, setFlatItems] = useState<any[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [llmLoading, setLlmLoading] = useState(false)
  const [llmContent, setLlmContent] = useState<string | null>(null)
  const [drawerVisible, setDrawerVisible] = useState(false)

  // 最终判定状态
  const [finalJudgment, setFinalJudgment] = useState({
    result: '',
    remarks: ''
  })
  const [aiJudgmentLoading, setAiJudgmentLoading] = useState(false)
  const [aiJudgmentThinking, setAiJudgmentThinking] = useState(false)
  const [aiJudgmentThinkingContent, setAiJudgmentThinkingContent] = useState('')
  const [aiJudgmentResult, setAiJudgmentResult] = useState('')
  const [aiJudgmentResultType, setAiJudgmentResultType] = useState('')

  useEffect(() => {
    fetchRecordData()
  }, [id])

  const fetchRecordData = async () => {
    if (!id) return
    setLoading(true)
    try {
      const res: any = await recordApi.getRecord(id)
      setRecord(res.data)
      const templateItems = res.data?.template?.items || []
      setItems(templateItems)
      const flat = flattenItems(templateItems)
      setFlatItems(flat)

      // 加载已有的最终判定
      if (res.data?.overall_result) {
        setFinalJudgment(prev => ({ ...prev, result: res.data.overall_result }))
      }
      if (res.data?.remarks) {
        setFinalJudgment(prev => ({ ...prev, remarks: res.data.remarks }))
      }
    } catch (error) {
      console.error('Failed to fetch record:', error)
      message.error('获取检查记录失败')
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

  const currentItem = flatItems[currentIndex]

  const handleResultChange = async (field: string, value: any) => {
    if (!currentItem || !id) return
    setSaving(true)
    try {
      const valueToSend = (field === 'numeric_value' || field === 'score_value') && typeof value === 'number'
        ? String(value)
        : value
      const res: any = await recordApi.createRecordItem(id, {
        template_item_id: currentItem.template_item_id,
        [field]: valueToSend,
      })
      const updatedItems = flatItems.map((item, idx) => {
        if (idx === currentIndex) {
          return { ...item, [field]: valueToSend, id: res.data?.id || item.id }
        }
        return item
      })
      setFlatItems(updatedItems)
      message.success('已保存')
    } catch (error) {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleLLMRequest = async () => {
    if (!currentItem || !id) return
    if (!currentItem.id || currentItem.id === currentItem.template_item_id) {
      setLlmContent('请先填写检查结果后再获取AI建议')
      setDrawerVisible(true)
      return
    }
    setLlmLoading(true)
    setDrawerVisible(true)
    try {
      const res: any = await llmApi.getSuggestion({ task_id: id, record_id: currentItem.id, use_cache: false })
      setLlmContent(res.data?.content || '暂无内容')
    } catch (error) {
      setLlmContent('获取失败，请稍后重试')
    } finally {
      setLlmLoading(false)
    }
  }

  // 保存最终判定
  const handleSaveFinalJudgment = async () => {
    if (!id) return
    try {
      await recordApi.updateRecord(id, {
        overall_result: finalJudgment.result,
        remarks: finalJudgment.remarks,
      })
      message.success('最终判定已保存')
    } catch (error) {
      message.error('保存失败')
    }
  }

  // AI生成最终判定
  const handleGenerateAIJudgment = async () => {
    if (!id || !token) return
    setAiJudgmentLoading(true)
    setAiJudgmentThinking(true)
    setAiJudgmentThinkingContent('')
    setAiJudgmentResult('')
    setAiJudgmentResultType('')

    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

      const response = await fetch(`${API_URL}/api/records/${id}/final-judgment-stream`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream',
        },
      })

      if (!response.ok) {
        throw new Error('请求失败')
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('无法读取响应')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              if (data.type === 'thinking') {
                setAiJudgmentThinkingContent(prev => prev + data.content)
              } else if (data.type === 'done') {
                setAiJudgmentResult(data.content)
                setAiJudgmentResultType(data.result || '')
                setAiJudgmentThinking(false)
                // 自动设置判定结果
                if (data.result) {
                  setFinalJudgment(prev => ({ ...prev, result: data.result }))
                }
              } else if (data.type === 'error') {
                message.error('AI 生成失败: ' + data.content)
                setAiJudgmentThinking(false)
              }
            } catch (e) {
              console.error('解析数据失败:', e)
            }
          }
        }
      }
    } catch (error) {
      console.error('AI生成失败:', error)
      message.error('AI生成失败，请稍后重试')
      setAiJudgmentThinking(false)
    } finally {
      setAiJudgmentLoading(false)
    }
  }

  // 采纳AI判定
  const handleAcceptAIJudgment = () => {
    if (aiJudgmentResultType) {
      setFinalJudgment(prev => ({ ...prev, result: aiJudgmentResultType }))
    }
    if (aiJudgmentResult) {
      setFinalJudgment(prev => ({ ...prev, remarks: aiJudgmentResult }))
    }
    message.success('已采纳AI建议')
  }

  // 清除AI判定
  const handleClearAIJudgment = () => {
    setAiJudgmentThinkingContent('')
    setAiJudgmentResult('')
    setAiJudgmentResultType('')
  }

  const handleSubmit = async () => {
    if (!id) return

    // 校验必填项和必传附件
    const incompleteItems: string[] = []
    const missingAttachments: string[] = []

    flatItems.forEach((item, index) => {
      if (item.is_required !== false) {
        const hasResult = item.radio_value ||
          item.numeric_value !== undefined ||
          item.text_value ||
          item.score_value !== undefined
        if (!hasResult) {
          incompleteItems.push(`第${index + 1}项: ${item.title || '未命名'}`)
        }
      }

      if (item.attachment_required) {
        const hasPhotos = item.photos && item.photos.length > 0
        if (!hasPhotos) {
          missingAttachments.push(`第${index + 1}项: ${item.title || '未命名'}`)
        }
      }
    })

    if (incompleteItems.length > 0 || missingAttachments.length > 0) {
      Modal.error({
        title: '提交失败',
        width: 520,
        content: (
          <div>
            {incompleteItems.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontWeight: 500, marginBottom: 4, color: '#ff4d4f' }}>
                  以下必填项未完成：
                </div>
                <ul style={{ margin: 0, paddingLeft: 20, color: '#666' }}>
                  {incompleteItems.slice(0, 10).map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                  {incompleteItems.length > 10 && <li>...还有 {incompleteItems.length - 10} 项</li>}
                </ul>
              </div>
            )}
            {missingAttachments.length > 0 && (
              <div>
                <div style={{ fontWeight: 500, marginBottom: 4, color: '#faad14' }}>
                  以下检查项需要上传照片：
                </div>
                <ul style={{ margin: 0, paddingLeft: 20, color: '#666' }}>
                  {missingAttachments.slice(0, 10).map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                  {missingAttachments.length > 10 && <li>...还有 {missingAttachments.length - 10} 项</li>}
                </ul>
              </div>
            )}
          </div>
        ),
      })
      return
    }

    // 校验最终判定
    if (!finalJudgment.result) {
      Modal.error({
        title: '提交失败',
        content: '请先选择最终判定结果（合格/基本合格/不合格）',
      })
      return
    }

    // 显示确认对话框
    Modal.confirm({
      title: '确认提交',
      width: 480,
      content: (
        <div>
          <div style={{ marginBottom: 12 }}>检查结果汇总：</div>
          <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
            <span>✅ 合格：{passCount} 项</span>
            {failCount > 0 && <span style={{ color: '#ff4d4f' }}>❌ 不合格：{failCount} 项</span>}
            {pendingRectificationCount > 0 && <span style={{ color: '#faad14' }}>⚠️ 待整改：{pendingRectificationCount} 项</span>}
            {notApplicableCount > 0 && <span style={{ color: '#999' }}>⚪ 不适用：{notApplicableCount} 项</span>}
          </div>
          <div style={{ marginBottom: 8 }}>
            <strong>最终判定：</strong>
            <Tag color={finalJudgment.result === 'pass' ? 'success' : finalJudgment.result === 'partial_pass' ? 'warning' : 'error'}>
              {finalJudgment.result === 'pass' ? '合格' : finalJudgment.result === 'partial_pass' ? '基本合格' : '不合格'}
            </Tag>
          </div>
          <div style={{ color: '#999', fontSize: 12 }}>提交后将无法修改，确定要提交吗？</div>
        </div>
      ),
      onOk: async () => {
        try {
          // 先保存最终判定
          await recordApi.updateRecord(id, {
            overall_result: finalJudgment.result,
            remarks: finalJudgment.remarks,
          })
          // 再提交
          await recordApi.submitRecord(id)
          message.success('检查记录已提交')
          navigate('/records')
        } catch (error) {
          message.error('提交失败')
        }
      },
    })
  }

  const handleUpload = async (uploadInfo: any) => {
    const file = uploadInfo.file as File
    if (!id || !currentItem) return
    try {
      // 传「检查记录项 ID」而非记录 ID，后端据此换算成任务检查项，保住照片与条目的关联
      const res: any = await mediaApi.upload(file, { record_id: currentItem.id || id })
      const photoUrl = res.data?.file_path
      if (photoUrl) {
        const currentPhotos = currentItem.photos || []
        const updatedPhotos = [...currentPhotos, photoUrl]
        const updatedItems = flatItems.map((item, idx) => {
          if (idx === currentIndex) {
            return { ...item, photos: updatedPhotos }
          }
          return item
        })
        setFlatItems(updatedItems)
        await recordApi.createRecordItem(id, {
          template_item_id: currentItem.template_item_id,
          photos: updatedPhotos,
        })
      }
      message.success('上传成功')
      if (uploadInfo.onSuccess) uploadInfo.onSuccess({}, uploadInfo.file)
    } catch (error) {
      message.error('上传失败')
      if (uploadInfo.onError) uploadInfo.onError(error)
    }
  }

  // 计算完成进度
  const completedCount = flatItems.filter(item => {
    const hasResult = item.radio_value || item.numeric_value || item.text_value || item.score_value
    const hasRequiredAttachment = !item.attachment_required || (item.photos && item.photos.length > 0)
    return hasResult && hasRequiredAttachment
  }).length
  const progress = flatItems.length > 0 ? Math.round((completedCount / flatItems.length) * 100) : 0

  // 统计各项数量
  const passCount = flatItems.filter(item => item.radio_value === 'pass').length
  const failCount = flatItems.filter(item => item.radio_value === 'fail').length
  const pendingRectificationCount = flatItems.filter(item => item.radio_value === 'pending_rectification').length
  const notApplicableCount = flatItems.filter(item => item.radio_value === 'not_applicable').length

  // 是否可以提交
  const canSubmit = progress === 100 && finalJudgment.result && record?.status === 'draft'

  const getResultTag = (item: any) => {
    if (item.radio_value) {
      const valueMap: Record<string, { color: string; text: string }> = {
        'pass': { color: 'success', text: '合格' },
        'fail': { color: 'error', text: '不合格' },
        'pending_rectification': { color: 'warning', text: '待整改' },
        'not_applicable': { color: 'default', text: '不适用' },
        'na': { color: 'default', text: '不适用' },
        'complete': { color: 'success', text: '全部整改完成' },
        'partial': { color: 'warning', text: '部分整改' },
        'none': { color: 'error', text: '未整改' },
        'valid': { color: 'success', text: '全部在有效期内' },
        'expired': { color: 'error', text: '存在超期未检' },
        'all_certified': { color: 'success', text: '全部持证' },
        'uncertified': { color: 'error', text: '存在无证上岗' },
      }
      const info = valueMap[item.radio_value] || { color: 'default', text: item.radio_value }
      return <Tag color={info.color}>{info.text}</Tag>
    }
    if (item.numeric_value !== undefined && item.numeric_value !== null) {
      return <Tag color="processing">{item.numeric_value} {item.unit || ''}</Tag>
    }
    if (item.score_value !== undefined && item.score_value !== null) {
      return <Tag color="processing">{item.score_value} 分</Tag>
    }
    if (item.text_value) {
      return <Tag color="default">已填写</Tag>
    }
    return <Tag>未填写</Tag>
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!record) {
    return (
      <div style={{ padding: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/records')}>返回</Button>
        <div style={{ marginTop: 24, textAlign: 'center' }}>检查记录不存在</div>
      </div>
    )
  }

  return (
    <div style={{ background: '#f0f2f5', minHeight: '100vh' }}>
      {/* 顶部导航栏 */}
      <div style={{ background: '#fff', padding: '16px 24px', marginBottom: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/records')}>
              返回
            </Button>
            <span style={{ fontSize: 18, fontWeight: 600 }}>{record.enterprise_name}</span>
            <Tag color="blue">{record.template?.name}</Tag>
            <Tag color={record.status === 'submitted' ? 'success' : 'warning'}>
              {record.status === 'submitted' ? '已提交' : '草稿'}
            </Tag>
          </Space>
          <Progress
            percent={progress}
            status={progress === 100 ? 'success' : 'active'}
            style={{ width: 200 }}
            format={() => `${completedCount}/${flatItems.length}`}
          />
        </div>
      </div>

      <div style={{ padding: '0 24px', maxWidth: 1200, margin: '0 auto' }}>
        {/* 检查项快捷导航 */}
        <Card style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {flatItems.map((item, idx) => (
              <Button
                key={item.id}
                size="small"
                type={idx === currentIndex ? 'primary' : 'default'}
                onClick={() => setCurrentIndex(idx)}
                style={{ marginBottom: 4 }}
              >
                {idx + 1}
                {(() => {
                  const hasResult = item.radio_value || item.numeric_value || item.text_value || item.score_value
                  const hasRequiredAttachment = !item.attachment_required || (item.photos && item.photos.length > 0)
                  return (hasResult && hasRequiredAttachment) ? ' ✓' : ''
                })()}
              </Button>
            ))}
          </div>
        </Card>

        {/* 当前检查项 */}
        {currentItem && (
          <Card
            title={
              <Space>
                <span>检查条目 {currentIndex + 1}/{flatItems.length}</span>
                {getResultTag(currentItem)}
              </Space>
            }
            extra={
              <Space>
                <Button
                  icon={<BulbOutlined />}
                  onClick={handleLLMRequest}
                  style={{ background: '#faad14', borderColor: '#faad14', color: '#fff' }}
                >
                  AI建议
                </Button>
              </Space>
            }
          >
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ fontSize: 18, marginBottom: 8 }}>
                {currentItem.title}
                {currentItem.is_required !== false && (
                  <span style={{ color: '#ff4d4f', marginLeft: 4 }}>*</span>
                )}
              </h3>
              {currentItem.description && (
                <p style={{ color: '#666', marginBottom: 8 }}>{currentItem.description}</p>
              )}
              {currentItem.check_method && (
                <p style={{ color: '#1890ff', fontSize: 13 }}>
                  <strong>检查方法：</strong>{currentItem.check_method}
                </p>
              )}
              {currentItem.legal_basis && (
                <p style={{ color: '#52c41a', fontSize: 13 }}>
                  <strong>法律依据：</strong>{currentItem.legal_basis}
                </p>
              )}
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>检查结果</div>

              {(currentItem.result_type === 'pass_fail' || (currentItem.result_type === null && currentItem.check_type === 'radio')) && (
                <Radio.Group
                  value={currentItem.radio_value}
                  onChange={(e) => handleResultChange('radio_value', e.target.value)}
                  buttonStyle="solid"
                  size="large"
                >
                  {(currentItem.result_options?.options || currentItem.result_options || [
                    { value: 'pass', label: '合格' },
                    { value: 'fail', label: '不合格' },
                    { value: 'not_applicable', label: '不适用' },
                  ]).map((opt: any) => (
                    <Radio.Button key={opt.value} value={opt.value}>
                      {opt.label === '未涉及' ? '不适用' : opt.label}
                    </Radio.Button>
                  ))}
                </Radio.Group>
              )}

              {(currentItem.result_type === 'score' || (currentItem.result_type === null && currentItem.check_type === 'score')) && (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Space>
                    <span>得分：</span>
                    <InputNumber
                      value={currentItem.score_value}
                      onChange={(value) => handleResultChange('score_value', value)}
                      min={0}
                      max={currentItem.max_score || 100}
                      step={currentItem.score_step || 1}
                      style={{ width: 120 }}
                    />
                    <span>/ {currentItem.max_score || 100} 分</span>
                  </Space>
                  {currentItem.pass_score && (
                    <div style={{ color: '#888', fontSize: 12 }}>合格线：{currentItem.pass_score} 分</div>
                  )}
                </Space>
              )}

              {(currentItem.result_type === 'numeric' || (currentItem.result_type === null && currentItem.check_type === 'numeric')) && (
                <Space>
                  <InputNumber
                    value={currentItem.numeric_value}
                    onChange={(value) => handleResultChange('numeric_value', value)}
                    min={currentItem.min_value}
                    max={currentItem.max_value}
                    placeholder={currentItem.min_value !== null && currentItem.max_value !== null
                      ? `范围: ${currentItem.min_value} ~ ${currentItem.max_value}`
                      : '请输入数值'}
                    style={{ width: 200 }}
                  />
                  {currentItem.unit && <span>{currentItem.unit}</span>}
                </Space>
              )}

              {(currentItem.result_type === 'text' || (currentItem.result_type === null && currentItem.check_type === 'text')) && (
                <TextArea
                  rows={4}
                  placeholder="请输入检查结果描述..."
                  value={currentItem.text_value || ''}
                  onChange={(e) => {
                    const updatedItems = flatItems.map((item, idx) => {
                      if (idx === currentIndex) return { ...item, text_value: e.target.value }
                      return item
                    })
                    setFlatItems(updatedItems)
                  }}
                  onBlur={() => handleResultChange('text_value', currentItem.text_value)}
                />
              )}

              {(currentItem.result_type === 'multi_check' || (currentItem.result_type === null && currentItem.check_type === 'multi_check')) && (
                <Select
                  mode="multiple"
                  style={{ width: '100%', maxWidth: 400 }}
                  value={currentItem.multi_value || []}
                  onChange={(value) => handleResultChange('multi_value', value)}
                  placeholder="请选择（可多选）"
                  options={(currentItem.result_options?.options || currentItem.result_options || []).map((opt: any) => ({
                    value: opt.value,
                    label: opt.label,
                  }))}
                />
              )}
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>审核记录</div>
              <TextArea
                rows={2}
                placeholder="请输入审核记录..."
                value={currentItem.inspector_note || ''}
                onChange={(e) => {
                  const updatedItems = flatItems.map((item, idx) => {
                    if (idx === currentIndex) return { ...item, inspector_note: e.target.value }
                    return item
                  })
                  setFlatItems(updatedItems)
                }}
                onBlur={() => handleResultChange('inspector_note', currentItem.inspector_note)}
              />
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>
                现场照片
                {currentItem.attachment_required && (
                  <span style={{ color: '#ff4d4f', marginLeft: 4 }}>*</span>
                )}
              </div>
              {currentItem.allow_attachment !== false ? (
                <>
                  {currentItem.attachment_required && (
                    <Alert type="warning" message="本检查项需要上传附件" style={{ marginBottom: 12, fontSize: 12 }} showIcon />
                  )}
                  <Upload customRequest={handleUpload} showUploadList={false} accept="image/*">
                    <Button icon={<CameraOutlined />}>上传照片</Button>
                  </Upload>
                  {currentItem.photos && currentItem.photos.length > 0 && (
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                      {currentItem.photos.map((url: string, idx: number) => {
                        const normalizedUrl = (!url || url.startsWith('/') || url.startsWith('http')) ? url : '/' + url
                        return (
                          <img
                            key={idx}
                            src={normalizedUrl}
                            alt={`附件图片 ${idx + 1}`}
                            style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 6, border: '1px solid #e2e8f0', cursor: 'pointer' }}
                            onClick={() => window.open(normalizedUrl, '_blank')}
                          />
                        )
                      })}
                    </div>
                  )}
                </>
              ) : (
                <div style={{ color: '#999', fontSize: 12 }}>本检查项不需要上传照片</div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 32 }}>
              <Button disabled={currentIndex === 0} onClick={() => setCurrentIndex(currentIndex - 1)}>
                上一条
              </Button>
              <Button type="primary" disabled={currentIndex === flatItems.length - 1} onClick={() => setCurrentIndex(currentIndex + 1)}>
                下一条
              </Button>
            </div>
          </Card>
        )}

        {/* 最终判定区域 - 当所有必填项完成后显示 */}
        {progress === 100 && record.status === 'draft' && (
          <Card
            style={{ marginTop: 16 }}
            title={
              <Space>
                <SafetyCertificateOutlined style={{ color: '#4F46E5' }} />
                <span>最终判定结论</span>
              </Space>
            }
          >
            {/* 统计汇总 */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontWeight: 500, marginBottom: 12 }}>检查结果汇总</div>
              <Row gutter={16}>
                <Col span={4}>
                  <Card size="small" style={{ background: '#f6ffed', borderColor: '#b7eb8f' }}>
                    <Statistic title="合格" value={passCount} valueStyle={{ color: '#52c41a' }} />
                  </Card>
                </Col>
                <Col span={4}>
                  <Card size="small" style={{ background: '#fff2f0', borderColor: '#ffccc7' }}>
                    <Statistic title="不合格" value={failCount} valueStyle={{ color: '#ff4d4f' }} />
                  </Card>
                </Col>
                <Col span={4}>
                  <Card size="small" style={{ background: '#fffbe6', borderColor: '#ffe58f' }}>
                    <Statistic title="待整改" value={pendingRectificationCount} valueStyle={{ color: '#faad14' }} />
                  </Card>
                </Col>
                <Col span={4}>
                  <Card size="small" style={{ background: '#fafafa', borderColor: '#d9d9d9' }}>
                    <Statistic title="不适用" value={notApplicableCount} valueStyle={{ color: '#999' }} />
                  </Card>
                </Col>
                <Col span={4}>
                  <Card size="small">
                    <Statistic title="总计" value={flatItems.length} />
                  </Card>
                </Col>
              </Row>
            </div>

            <Divider />

            {/* 判定结果选择 */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontWeight: 500, marginBottom: 12 }}>判定结果 <span style={{ color: '#ff4d4f' }}>*</span></div>
              <Radio.Group
                value={finalJudgment.result}
                onChange={(e) => setFinalJudgment(prev => ({ ...prev, result: e.target.value }))}
                buttonStyle="solid"
                size="large"
              >
                <Radio.Button value="pass">
                  <span style={{ color: '#52c41a' }}>✅ 合格</span>
                </Radio.Button>
                <Radio.Button value="partial_pass">
                  <span style={{ color: '#faad14' }}>⚠️ 基本合格</span>
                </Radio.Button>
                <Radio.Button value="fail">
                  <span style={{ color: '#ff4d4f' }}>❌ 不合格</span>
                </Radio.Button>
              </Radio.Group>
            </div>

            {/* 判定说明 */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontWeight: 500, marginBottom: 12 }}>判定说明</div>
              <TextArea
                rows={4}
                placeholder="请输入判定说明..."
                value={finalJudgment.remarks}
                onChange={(e) => setFinalJudgment(prev => ({ ...prev, remarks: e.target.value }))}
              />
            </div>

            {/* AI生成区域 */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontWeight: 500, marginBottom: 12 }}>AI 辅助判定</div>
              <Space style={{ marginBottom: 12 }}>
                <Button
                  type="primary"
                  icon={<RobotOutlined />}
                  loading={aiJudgmentLoading}
                  onClick={handleGenerateAIJudgment}
                  disabled={aiJudgmentLoading}
                >
                  {aiJudgmentLoading ? 'AI 分析中...' : 'AI 生成最终判定'}
                </Button>
                {aiJudgmentResult && (
                  <Button onClick={handleAcceptAIJudgment} type="default">
                    采纳 AI 建议
                  </Button>
                )}
                {(aiJudgmentThinkingContent || aiJudgmentResult) && (
                  <Button onClick={handleClearAIJudgment} danger ghost>
                    清除
                  </Button>
                )}
              </Space>

              {/* AI 思考过程 - 流式显示 */}
              {aiJudgmentThinking && aiJudgmentThinkingContent && (
                <Card
                  size="small"
                  style={{
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    borderColor: '#667eea',
                    marginBottom: 12
                  }}
                >
                  <div style={{ color: '#fff', fontWeight: 500, marginBottom: 8 }}>
                    <LoadingOutlined spin style={{ marginRight: 8 }} />
                    AI 正在分析检查结果...
                  </div>
                  <div
                    style={{
                      color: 'rgba(255,255,255,0.9)',
                      fontSize: 13,
                      lineHeight: 1.6,
                      maxHeight: 200,
                      overflow: 'auto',
                      whiteSpace: 'pre-wrap'
                    }}
                  >
                    {aiJudgmentThinkingContent}
                  </div>
                </Card>
              )}

              {/* AI 分析结果 */}
              {aiJudgmentResult && !aiJudgmentThinking && (
                <Alert
                  type="success"
                  message="AI 分析完成"
                  description={
                    <div>
                      {aiJudgmentResultType && (
                        <div style={{ marginBottom: 12, fontWeight: 500 }}>
                          建议判定：
                          {aiJudgmentResultType === 'pass' && (
                            <Tag color="success" style={{ marginLeft: 8 }}>合格</Tag>
                          )}
                          {aiJudgmentResultType === 'partial_pass' && (
                            <Tag color="warning" style={{ marginLeft: 8 }}>基本合格</Tag>
                          )}
                          {aiJudgmentResultType === 'fail' && (
                            <Tag color="error" style={{ marginLeft: 8 }}>不合格</Tag>
                          )}
                        </div>
                      )}
                      <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                        {aiJudgmentResult}
                      </div>
                    </div>
                  }
                  style={{ marginTop: 12 }}
                  showIcon
                  action={
                    <Button size="small" type="primary" onClick={handleAcceptAIJudgment}>
                      采纳
                    </Button>
                  }
                />
              )}
            </div>

            {/* 提交按钮 */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
              <Button onClick={handleSaveFinalJudgment}>保存判定</Button>
              <Button
                type="primary"
                icon={<SendOutlined />}
                disabled={!canSubmit}
                onClick={handleSubmit}
              >
                提交检查结果
              </Button>
            </div>

            {!finalJudgment.result && (
              <Alert
                type="info"
                message="请选择最终判定结果（合格/基本合格/不合格）后才能提交"
                style={{ marginTop: 16 }}
                showIcon
              />
            )}
          </Card>
        )}

        {/* 提交提示 */}
        {progress === 100 && !finalJudgment.result && record.status === 'draft' && (
          <Alert
            type="info"
            message="检查项已全部完成，请在上方填写【最终判定结论】后提交"
            style={{ marginTop: 16 }}
            showIcon
          />
        )}
      </div>

      <Drawer
        title="AI 监管建议"
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