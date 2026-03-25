import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Steps, Button, Radio, Input, Space, Tag, Modal, Spin, message,
  Progress, Descriptions, Upload, Image, Drawer
} from 'antd'
import {
  ArrowLeftOutlined, CheckCircleOutlined, CloseCircleOutlined,
  MinusCircleOutlined, BulbOutlined, CameraOutlined,
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

  const handleLLMRequest = async () => {
    if (!currentRecord || !id) return
    setLlmLoading(true)
    setDrawerVisible(true)
    try {
      const res: any = await llmApi.getSuggestion({ task_id: id, record_id: currentRecord.id })
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
      pass: { color: 'success', icon: <CheckCircleOutlined />, text: '合格' },
      fail: { color: 'error', icon: <CloseCircleOutlined />, text: '不合格' },
      pending_rectification: { color: 'warning', icon: <MinusCircleOutlined />, text: '待整改' },
      not_applicable: { color: 'default', icon: <MinusCircleOutlined />, text: '未涉及' },
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

      <div style={{ padding: '0 24px', maxWidth: 1400, margin: '0 auto', display: 'flex', gap: 24 }}>
        {/* 左侧：条目列表导航 */}
        <Card 
          title={
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 600 }}>检查条目列表</span>
              <span style={{ fontSize: 13, color: '#666', fontWeight: 400 }}>
                已完成 {completedCount} / 共 {records.length} 项
              </span>
            </div>
          }
          style={{ width: 380, flexShrink: 0, maxHeight: 'calc(100vh - 140px)', display: 'flex', flexDirection: 'column' }}
          bodyStyle={{ padding: 0, overflow: 'hidden', flex: 1, display: 'flex', flexDirection: 'column' }}
        >
          {/* 进度条 */}
          <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid #f0f0f0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 13, color: '#666' }}>总体进度</span>
              <span style={{ fontSize: 14, color: '#1890ff', fontWeight: 600 }}>{progress}%</span>
            </div>
            <Progress
              percent={progress}
              status={progress === 100 ? 'success' : 'active'}
              showInfo={false}
              strokeColor={{ from: '#108ee9', to: '#87d068' }}
            />
          </div>
          
          {/* 条目列表 */}
          <div style={{ 
            flex: 1, 
            overflowY: 'auto',
            padding: '8px 0'
          }}>
            {records.map((r, idx) => (
              <div
                key={idx}
                onClick={() => setCurrentIndex(idx)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '12px 16px',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  background: idx === currentIndex ? '#e6f7ff' : 'transparent',
                  borderLeft: `3px solid ${idx === currentIndex ? '#1890ff' : 'transparent'}`,
                  borderBottom: '1px solid #f5f5f5'
                }}
              >
                {/* 序号 */}
                <div style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 12,
                  fontWeight: 600,
                  flexShrink: 0,
                  background: idx === currentIndex ? '#1890ff' : r.result ? '#52c41a' : '#f0f0f0',
                  color: idx === currentIndex || r.result ? '#fff' : '#999'
                }}>
                  {idx + 1}
                </div>
                
                {/* 条目内容 */}
                <div style={{ 
                  flex: 1, 
                  marginLeft: 12, 
                  overflow: 'hidden',
                  opacity: idx === currentIndex ? 1 : 0.85
                }}>
                  <div style={{ 
                    fontSize: 14, 
                    fontWeight: idx === currentIndex ? 500 : 400,
                    color: idx === currentIndex ? '#1890ff' : '#333',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    marginBottom: 4
                  }}>
                    {r.check_item?.title || `检查条目 ${idx + 1}`}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {getResultTag(r.result)}
                    {r.inspector_note && (
                      <span style={{ fontSize: 12, color: '#999' }}>
                        <BookOutlined style={{ fontSize: 10, marginRight: 2 }} />
                        有备注
                      </span>
                    )}
                  </div>
                </div>
                
                {/* 当前指示器 */}
                {idx === currentIndex && (
                  <div style={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: '#1890ff',
                    marginLeft: 8
                  }} />
                )}
              </div>
            ))}
          </div>
          
          {/* 底部图例 */}
          <div style={{ 
            padding: '12px 16px', 
            borderTop: '1px solid #f0f0f0',
            display: 'flex', 
            gap: 16, 
            fontSize: 12, 
            color: '#666',
            background: '#fafafa'
          }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 10, height: 10, background: '#1890ff', borderRadius: '50%' }}></span>
              当前
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 10, height: 10, background: '#52c41a', borderRadius: '50%' }}></span>
              已完成
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 10, height: 10, background: '#f0f0f0', borderRadius: '50%' }}></span>
              未完成
            </span>
          </div>
        </Card>
        
        {/* 右侧：检查详情 */}
        <div style={{ flex: 1, minWidth: 0 }}>

        {currentRecord && (
          <Card>
            {/* 卡片头部：条目信息和AI按钮 */}
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'flex-start',
              marginBottom: 20,
              paddingBottom: 16,
              borderBottom: '1px solid #f0f0f0'
            }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
                  检查条目 {currentIndex + 1}/{records.length}
                  <span style={{ marginLeft: 12 }}>{getResultTag(currentRecord.result)}</span>
                </div>
                <div style={{ fontSize: 13, color: '#999' }}>
                  点击左侧列表可快速切换条目
                </div>
              </div>
              <Space>
                <Button
                  icon={<BulbOutlined />}
                  onClick={handleLLMRequest}
                  style={{ background: '#faad14', borderColor: '#faad14', color: '#fff' }}
                >
                  AI建议
                </Button>
              </Space>
            </div>
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
                {(currentRecord.check_item?.result_options || currentRecord.result_options || [
                  { value: 'pass', label: '合格' },
                  { value: 'fail', label: '不合格' },
                  { value: 'pending_rectification', label: '待整改' },
                  { value: 'not_applicable', label: '未涉及' },
                ]).map((opt: any) => (
                  <Radio.Button key={opt.value} value={opt.value}>
                    {opt.label}
                  </Radio.Button>
                ))}
              </Radio.Group>
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>审核记录</div>
              <TextArea
                rows={4}
                placeholder="请输入审核记录..."
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

            {/* 底部导航区域 */}
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              marginTop: 32,
              paddingTop: 20,
              borderTop: '1px solid #f0f0f0'
            }}>
              <Button
                size="large"
                disabled={currentIndex === 0}
                onClick={() => setCurrentIndex(currentIndex - 1)}
                style={{ minWidth: 100 }}
              >
                ← 上一条
              </Button>
              
              <Space size="middle">
                {currentIndex > 0 && (
                  <Button 
                    onClick={() => setCurrentIndex(0)}
                    style={{ color: '#666' }}
                  >
                    回到首条
                  </Button>
                )}
                {currentIndex === records.length - 1 && progress === 100 && (
                  <Button 
                    type="primary" 
                    size="large"
                    onClick={handleComplete}
                    style={{ background: '#52c41a', borderColor: '#52c41a' }}
                  >
                    ✓ 完成检查
                  </Button>
                )}
              </Space>
              
              <Button
                type="primary"
                size="large"
                disabled={currentIndex === records.length - 1}
                onClick={() => setCurrentIndex(currentIndex + 1)}
                style={{ minWidth: 100 }}
              >
                下一条 →
              </Button>
            </div>
          </Card>
        )}
        </div>
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
