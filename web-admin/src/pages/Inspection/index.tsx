import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Steps, Button, Radio, Input, Space, Tag, Modal, Spin, message,
  Progress, Descriptions, Upload, Image, Drawer
} from 'antd'
import {
  ArrowLeftOutlined, CheckCircleOutlined, CloseCircleOutlined,
  MinusCircleOutlined, BulbOutlined, BookOutlined, CameraOutlined,
  LoadingOutlined
} from '@ant-design/icons'
import { taskApi, llmApi, mediaApi } from '@/services/api'

const { TextArea } = Input

export default function Inspection() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [task, setTask] = useState<any>(null)
  const [records, setRecords] = useState<any[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [llmLoading, setLlmLoading] = useState(false)
  const [llmContent, setLlmContent] = useState<string | null>(null)
  const [llmType, setLlmType] = useState<'suggestion' | 'basis'>('suggestion')
  const [drawerVisible, setDrawerVisible] = useState(false)

  const currentRecord = records[currentIndex]

  useEffect(() => {
    fetchTaskData()
  }, [id])

  const fetchTaskData = async () => {
    if (!id) return
    setLoading(true)
    try {
      const [taskRes, recordsRes]: any[] = await Promise.all([
        taskApi.getTask(id),
        taskApi.getTaskRecords(id),
      ])
      setTask(taskRes.data)
      setRecords(recordsRes.data || [])

      if (taskRes.data.status === 'pending') {
        await taskApi.startTask(id)
      }
    } catch (error) {
      console.error('Failed to fetch task:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleResultChange = async (result: string) => {
    if (!currentRecord) return
    setSaving(true)
    try {
      await taskApi.updateRecord(currentRecord.id, { result })
      const updatedRecords = [...records]
      updatedRecords[currentIndex] = { ...currentRecord, result }
      setRecords(updatedRecords)
    } catch (error) {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleNoteChange = async (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (!currentRecord) return
    const note = e.target.value
    const updatedRecords = [...records]
    updatedRecords[currentIndex] = { ...currentRecord, inspector_note: note }
    setRecords(updatedRecords)
  }

  const saveNote = async () => {
    if (!currentRecord?.inspector_note) return
    setSaving(true)
    try {
      await taskApi.updateRecord(currentRecord.id, { inspector_note: currentRecord.inspector_note })
      message.success('备注已保存')
    } catch (error) {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleLLMRequest = async (type: 'suggestion' | 'basis') => {
    if (!currentRecord || !id) return
    setLlmLoading(true)
    setLlmType(type)
    setDrawerVisible(true)
    try {
      const res: any = type === 'suggestion'
        ? await llmApi.getSuggestion({ task_id: id, record_id: currentRecord.id })
        : await llmApi.getBasis({ task_id: id, record_id: currentRecord.id })
      setLlmContent(res.data?.content || '暂无内容')
    } catch (error) {
      setLlmContent('获取失败，请稍后重试')
    } finally {
      setLlmLoading(false)
    }
  }

  const handleUpload = async (uploadInfo: any) => {
    const file = uploadInfo.file as File
    if (!id) return
    try {
      await mediaApi.upload(file, { task_id: id, record_id: currentRecord?.id })
      message.success('上传成功')
      if (uploadInfo.onSuccess) uploadInfo.onSuccess({}, uploadInfo.file)
    } catch (error) {
      message.error('上传失败')
      if (uploadInfo.onError) uploadInfo.onError(error)
    }
  }

  const handleComplete = async () => {
    if (!id) return
    try {
      await taskApi.completeTask(id)
      message.success('检查任务已完成')
      navigate(`/tasks/${id}`)
    } catch (error) {
      message.error('操作失败')
    }
  }

  const getResultTag = (result: string) => {
    const resultMap: Record<string, { color: string; icon: any; text: string }> = {
      compliant: { color: 'success', icon: <CheckCircleOutlined />, text: '合规' },
      non_compliant: { color: 'error', icon: <CloseCircleOutlined />, text: '不合规' },
      not_applicable: { color: 'default', icon: <MinusCircleOutlined />, text: '不适用' },
    }
    const item = resultMap[result] || { color: 'default', icon: null, text: '未填写' }
    return <Tag color={item.color} icon={item.icon}>{item.text}</Tag>
  }

  const completedCount = records.filter(r => r.result).length
  const progress = records.length > 0 ? Math.round((completedCount / records.length) * 100) : 0

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ background: '#f0f2f5', minHeight: '100vh' }}>
      <div style={{ background: '#fff', padding: '16px 24px', marginBottom: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
              返回
            </Button>
            <span style={{ fontSize: 18, fontWeight: 600 }}>{task?.title}</span>
            <Tag color="blue">{task?.task_no}</Tag>
          </Space>
          <Progress
            percent={progress}
            status={progress === 100 ? 'success' : 'active'}
            style={{ width: 200 }}
            format={() => `${completedCount}/${records.length}`}
          />
        </div>
      </div>

      <div style={{ padding: '0 24px', maxWidth: 1200, margin: '0 auto' }}>
        <Card style={{ marginBottom: 16 }}>
          <Steps
            current={currentIndex}
            onChange={(current) => setCurrentIndex(current)}
            items={records.map((r, idx) => ({
              title: `条目 ${idx + 1}`,
              status: r.result ? 'finish' : 'wait',
            }))}
            size="small"
          />
        </Card>

        {currentRecord && (
          <Card
            title={
              <Space>
                <span>检查条目 {currentIndex + 1}/{records.length}</span>
                {getResultTag(currentRecord.result)}
              </Space>
            }
            extra={
              <Space>
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
              </Space>
            }
          >
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ fontSize: 18, marginBottom: 8 }}>
                {currentRecord.check_item?.title}
              </h3>
              {currentRecord.check_item?.description && (
                <p style={{ color: '#666', marginBottom: 8 }}>
                  {currentRecord.check_item.description}
                </p>
              )}
              {currentRecord.check_item?.check_method && (
                <p style={{ color: '#1890ff', fontSize: 13 }}>
                  <strong>检查方法：</strong>{currentRecord.check_item.check_method}
                </p>
              )}
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>检查结果</div>
              <Radio.Group
                value={currentRecord.result}
                onChange={(e) => handleResultChange(e.target.value)}
                buttonStyle="solid"
                size="large"
              >
                <Radio.Button value="compliant">
                  <CheckCircleOutlined /> 合规
                </Radio.Button>
                <Radio.Button value="non_compliant">
                  <CloseCircleOutlined /> 不合规
                </Radio.Button>
                <Radio.Button value="not_applicable">
                  <MinusCircleOutlined /> 不适用
                </Radio.Button>
              </Radio.Group>
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>检查说明</div>
              <TextArea
                rows={4}
                placeholder="请输入检查说明..."
                value={currentRecord.result_text || ''}
                onChange={handleNoteChange}
                onBlur={saveNote}
              />
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>专家备注</div>
              <TextArea
                rows={3}
                placeholder="请输入备注信息..."
                value={currentRecord.inspector_note || ''}
                onChange={(e) => {
                  const updatedRecords = [...records]
                  updatedRecords[currentIndex] = { ...currentRecord, inspector_note: e.target.value }
                  setRecords(updatedRecords)
                }}
                onBlur={() => {
                  if (currentRecord.inspector_note !== records[currentIndex]?.inspector_note) {
                    taskApi.updateRecord(currentRecord.id, { inspector_note: currentRecord.inspector_note })
                  }
                }}
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
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 32 }}>
              <Button
                disabled={currentIndex === 0}
                onClick={() => setCurrentIndex(currentIndex - 1)}
              >
                上一条
              </Button>
              <Space>
                {currentIndex === records.length - 1 && progress === 100 && (
                  <Button type="primary" onClick={handleComplete}>
                    完成检查
                  </Button>
                )}
              </Space>
              <Button
                type="primary"
                disabled={currentIndex === records.length - 1}
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
