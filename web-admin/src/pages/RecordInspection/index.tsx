import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Button, Input, Space, Tag, Spin, message,
  Progress, Upload, Drawer, Radio, InputNumber, Select
} from 'antd'
import {
  ArrowLeftOutlined, CheckCircleOutlined, CloseCircleOutlined,
  BulbOutlined, BookOutlined, CameraOutlined,
  LoadingOutlined, SaveOutlined, SendOutlined
} from '@ant-design/icons'
import { recordApi, llmApi, mediaApi } from '@/services/api'

const { TextArea } = Input

export default function RecordInspection() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [record, setRecord] = useState<any>(null)
  const [items, setItems] = useState<any[]>([])
  const [flatItems, setFlatItems] = useState<any[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [llmLoading, setLlmLoading] = useState(false)
  const [llmContent, setLlmContent] = useState<string | null>(null)
  const [llmType, setLlmType] = useState<'suggestion' | 'basis'>('suggestion')
  const [drawerVisible, setDrawerVisible] = useState(false)

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
      const res: any = await recordApi.createRecordItem(id, {
        template_item_id: currentItem.template_item_id,
        [field]: value,
      })
      const updatedItems = flatItems.map((item, idx) => {
        if (idx === currentIndex) {
          return { ...item, [field]: value, id: res.data?.id || item.id }
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

  const handleLLMRequest = async (type: 'suggestion' | 'basis') => {
    if (!currentItem || !id) return
    if (!currentItem.id || currentItem.id === currentItem.template_item_id) {
      setLlmContent('请先填写检查结果后再获取AI建议')
      setDrawerVisible(true)
      return
    }
    setLlmLoading(true)
    setLlmType(type)
    setDrawerVisible(true)
    try {
      const res: any = type === 'suggestion'
        ? await llmApi.getSuggestion({ task_id: id, record_id: currentItem.id, use_cache: false })
        : await llmApi.getBasis({ task_id: id, record_id: currentItem.id, use_cache: false })
      setLlmContent(res.data?.content || '暂无内容')
    } catch (error) {
      setLlmContent('获取失败，请稍后重试')
    } finally {
      setLlmLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!id) return
    try {
      await recordApi.submitRecord(id)
      message.success('检查记录已提交')
      navigate('/records')
    } catch (error) {
      message.error('提交失败')
    }
  }

  const handleUpload = async (uploadInfo: any) => {
    const file = uploadInfo.file as File
    if (!id || !currentItem) return
    try {
      const res: any = await mediaApi.upload(file, { record_id: id })
      const photoUrl = res.data?.file_path
      if (photoUrl) {
        // Update local state to show photo
        const currentPhotos = currentItem.photos || []
        const updatedPhotos = [...currentPhotos, photoUrl]
        const updatedItems = flatItems.map((item, idx) => {
          if (idx === currentIndex) {
            return { ...item, photos: updatedPhotos }
          }
          return item
        })
        setFlatItems(updatedItems)
        // Save photos to the record item
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

  const completedCount = flatItems.filter(item =>
    item.radio_value || item.numeric_value || item.text_value || item.score_value
  ).length
  const progress = flatItems.length > 0 ? Math.round((completedCount / flatItems.length) * 100) : 0

  const getResultTag = (item: any) => {
    if (item.radio_value) {
      const valueMap: Record<string, { color: string; text: string }> = {
        'pass': { color: 'success', text: '合格' },
        'fail': { color: 'error', text: '不合格' },
        'na': { color: 'default', text: '不适用' },
        'complete': { color: 'success', text: '全部整改完成' },
        'partial': { color: 'warning', text: '部分整改' },
        'none': { color: 'error', text: '未整改' },
        'valid': { color: 'success', text: '全部在有效期内' },
        'expired': { color: 'error', text: '存在超期未检' },
        'all_certified': { color: 'success', text: '全部持证' },
        'uncertified': { color: 'error', text: '存在无证上岗' },
        'normal': { color: 'success', text: '正常运行' },
        'abnormal': { color: 'warning', text: '运行异常' },
        'stopped': { color: 'error', text: '停运/损坏' },
        'implemented': { color: 'success', text: '落实到位' },
        'not_implemented': { color: 'error', text: '未落实' },
        'reliable': { color: 'success', text: '真实可靠' },
        'doubtful': { color: 'warning', text: '存在疑点' },
        'fake': { color: 'error', text: '明显造假' },
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
                {(item.radio_value || item.numeric_value || item.text_value || item.score_value) && ' ✓'}
              </Button>
            ))}
          </div>
        </Card>

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
                {currentItem.use_ai && (
                  <>
                    <Button
                      icon={<BulbOutlined />}
                      onClick={() => handleLLMRequest('suggestion')}
                      style={{ background: '#faad14', borderColor: '#faad14', color: '#fff' }}
                    >
                      AI建议
                    </Button>
                    <Button
                      icon={<BookOutlined />}
                      onClick={() => handleLLMRequest('basis')}
                      style={{ background: '#722ed1', borderColor: '#722ed1', color: '#fff' }}
                    >
                      法规依据
                    </Button>
                  </>
                )}
              </Space>
            }
          >
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ fontSize: 18, marginBottom: 8 }}>
                {currentItem.title}
              </h3>
              {currentItem.description && (
                <p style={{ color: '#666', marginBottom: 8 }}>
                  {currentItem.description}
                </p>
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

              {currentItem.result_type === 'pass_fail' && currentItem.result_options && (
                <Select
                  style={{ width: '100%', maxWidth: 400 }}
                  value={currentItem.radio_value}
                  onChange={(value) => handleResultChange('radio_value', value)}
                  placeholder="请选择检查结果"
                  options={currentItem.result_options.map((opt: any) => ({
                    value: opt.value,
                    label: opt.label,
                  }))}
                />
              )}

              {currentItem.result_type === 'numeric' && (
                <Space>
                  <InputNumber
                    value={currentItem.numeric_value}
                    onChange={(value) => handleResultChange('numeric_value', value)}
                    min={currentItem.min_value}
                    max={currentItem.max_value}
                    placeholder={`范围: ${currentItem.min_value} ~ ${currentItem.max_value}`}
                    style={{ width: 200 }}
                  />
                  <span>{currentItem.unit}</span>
                </Space>
              )}

              {currentItem.result_type === 'text' && (
                <TextArea
                  rows={4}
                  placeholder="请输入检查结果描述..."
                  value={currentItem.text_value || ''}
                  onChange={(e) => {
                    const updatedItems = flatItems.map((item, idx) => {
                      if (idx === currentIndex) {
                        return { ...item, text_value: e.target.value }
                      }
                      return item
                    })
                    setFlatItems(updatedItems)
                  }}
                  onBlur={() => handleResultChange('text_value', currentItem.text_value)}
                />
              )}
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>检查说明</div>
              <TextArea
                rows={3}
                placeholder="请输入检查说明..."
                value={currentItem.inspector_note || ''}
                onChange={(e) => {
                  const updatedItems = flatItems.map((item, idx) => {
                    if (idx === currentIndex) {
                      return { ...item, inspector_note: e.target.value }
                    }
                    return item
                  })
                  setFlatItems(updatedItems)
                }}
                onBlur={() => handleResultChange('inspector_note', currentItem.inspector_note)}
              />
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>现场照片</div>
              <Upload
                customRequest={handleUpload}
                showUploadList={false}
                accept="image/*"
              >
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
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 32 }}>
              <Button
                disabled={currentIndex === 0}
                onClick={() => setCurrentIndex(currentIndex - 1)}
              >
                上一条
              </Button>
              <Space>
                {progress === 100 && record.status === 'draft' && (
                  <Button
                    type="primary"
                    icon={<SendOutlined />}
                    onClick={handleSubmit}
                  >
                    提交检查
                  </Button>
                )}
              </Space>
              <Button
                type="primary"
                disabled={currentIndex === flatItems.length - 1}
                onClick={() => setCurrentIndex(currentIndex + 1)}
              >
                下一条
              </Button>
            </div>
          </Card>
        )}
      </div>

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
