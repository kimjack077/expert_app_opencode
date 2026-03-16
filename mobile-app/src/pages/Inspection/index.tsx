import React, { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  NavBar,
  Steps,
  Button,
  Toast,
  Dialog,
  TextArea,
  ImageUploader,
  ActionSheet,
  Card,
  Tag,
  SpinLoading,
  FloatingPanel,
} from 'antd-mobile'
import {
  LeftOutline,
  CheckOutline,
  CloseOutline,
  MinusOutline,
  CameraOutline,
  AudioOutline,
  SetOutline,
  FileOutline,
  CheckCircleOutline,
} from 'antd-mobile-icons'
import { taskApi, recordApi, aiApi } from '../../services/api'
import './style.css'

const { Step } = Steps

interface CheckItem {
  id: string
  title: string
  description: string
  check_method: string
  legal_basis: string
  result?: string
  comment?: string
  photos?: string[]
}

interface TaskDetail {
  id: string
  title: string
  company_name: string
  status: string
  check_items: CheckItem[]
}

const Inspection: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [task, setTask] = useState<TaskDetail | null>(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [showAiResult, setShowAiResult] = useState(false)
  const [aiResult, setAiResult] = useState('')
  const commentRef = useRef('')

  useEffect(() => {
    fetchTaskDetail()
  }, [taskId])

  const fetchTaskDetail = async () => {
    if (!taskId) return
    setLoading(true)
    try {
      const res: any = await taskApi.getTaskDetail(taskId)
      if (res.code === 200) {
        setTask(res.data)
        if (res.data.status === 'pending') {
          await taskApi.startTask(taskId)
        }
      }
    } catch (error) {
      Toast.show({
        icon: 'fail',
        content: '获取任务详情失败',
      })
    } finally {
      setLoading(false)
    }
  }

  const handleResult = async (result: string) => {
    if (!task) return
    const currentItem = task.check_items[currentIndex]
    currentItem.result = result
    setTask({ ...task })

    // 自动保存
    await saveCurrentItem()
  }

  const saveCurrentItem = async () => {
    if (!task) return
    const currentItem = task.check_items[currentIndex]

    setSubmitting(true)
    try {
      await recordApi.updateRecord(currentItem.id, {
        result: currentItem.result,
        comment: commentRef.current,
      })
    } catch (error) {
      console.error('保存失败', error)
    } finally {
      setSubmitting(false)
    }
  }

  const handleNext = () => {
    if (!task) return
    if (currentIndex < task.check_items.length - 1) {
      setCurrentIndex(currentIndex + 1)
      commentRef.current = ''
    } else {
      // 完成检查
      Dialog.confirm({
        title: '完成检查',
        content: '确定要完成本次检查任务吗？',
        onConfirm: async () => {
          await taskApi.completeTask(task.id)
          Toast.show({
            icon: 'success',
            content: '检查完成',
          })
          navigate('/tasks')
        },
      })
    }
  }

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
      commentRef.current = ''
    }
  }

  const handleAiSuggestion = async () => {
    if (!task) return
    setAiLoading(true)
    setShowAiResult(true)
    try {
      const res: any = await aiApi.getSuggestion(task.check_items[currentIndex].id)
      if (res.code === 200) {
        setAiResult(res.data.suggestion)
      }
    } catch (error) {
      Toast.show({
        icon: 'fail',
        content: '获取AI建议失败',
      })
    } finally {
      setAiLoading(false)
    }
  }

  const handleLegalBasis = async () => {
    if (!task) return
    setAiLoading(true)
    setShowAiResult(true)
    try {
      const res: any = await aiApi.getLegalBasis(task.check_items[currentIndex].id)
      if (res.code === 200) {
        setAiResult(res.data.legal_basis)
      }
    } catch (error) {
      Toast.show({
        icon: 'fail',
        content: '获取法规依据失败',
      })
    } finally {
      setAiLoading(false)
    }
  }

  const handlePhotoUpload = async (file: File) => {
    if (!task) return
    try {
      const res: any = await recordApi.uploadPhoto(task.check_items[currentIndex].id, file)
      if (res.code === 200) {
        Toast.show({
          icon: 'success',
          content: '上传成功',
        })
        return { url: res.data.url }
      }
    } catch (error) {
      Toast.show({
        icon: 'fail',
        content: '上传失败',
      })
    }
    return null
  }

  if (loading) {
    return (
      <div className="inspection-page">
        <div className="loading-container">
          <SpinLoading color="primary" />
        </div>
      </div>
    )
  }

  if (!task || task.check_items.length === 0) {
    return (
      <div className="inspection-page">
        <NavBar
          onBack={() => navigate('/tasks')}
          className="inspection-nav"
        >
          现场检查
        </NavBar>
        <div className="empty-container">
          暂无检查项
        </div>
      </div>
    )
  }

  const currentItem = task.check_items[currentIndex]
  const progress = ((currentIndex + 1) / task.check_items.length) * 100

  return (
    <div className="inspection-page">
      <NavBar
        onBack={() => navigate('/tasks')}
        className="inspection-nav"
        right={
          <span className="progress-text">
            {currentIndex + 1}/{task.check_items.length}
          </span>
        }
      >
        现场检查
      </NavBar>

      {/* 进度条 */}
      <div className="progress-container">
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>

      {/* 检查项内容 */}
      <div className="inspection-content">
        <Card className="check-item-card">
          <div className="check-item-header">
            <Tag color="primary">检查项 {currentIndex + 1}</Tag>
            {currentItem.result && (
              <Tag
                color={
                  currentItem.result === 'pass'
                    ? 'success'
                    : currentItem.result === 'fail'
                    ? 'danger'
                    : 'default'
                }
              >
                {currentItem.result === 'pass'
                  ? '合规'
                  : currentItem.result === 'fail'
                  ? '不合规'
                  : '不适用'}
              </Tag>
            )}
          </div>

          <h3 className="check-item-title">{currentItem.title}</h3>
          <p className="check-item-desc">{currentItem.description}</p>

          <div className="check-item-info">
            <div className="info-row">
              <span className="info-label">检查方法：</span>
              <span className="info-value">{currentItem.check_method}</span>
            </div>
            <div className="info-row">
              <span className="info-label">法规依据：</span>
              <span className="info-value">{currentItem.legal_basis}</span>
            </div>
          </div>
        </Card>

        {/* 检查结果选择 */}
        <div className="result-section">
          <h4 className="section-title">检查结果</h4>
          <div className="result-buttons">
            <Button
              className={`result-btn ${currentItem.result === 'pass' ? 'active' : ''}`}
              onClick={() => handleResult('pass')}
              color={currentItem.result === 'pass' ? 'success' : 'default'}
              fill={currentItem.result === 'pass' ? 'solid' : 'outline'}
            >
              <CheckOutline />
              合规
            </Button>
            <Button
              className={`result-btn ${currentItem.result === 'fail' ? 'active' : ''}`}
              onClick={() => handleResult('fail')}
              color={currentItem.result === 'fail' ? 'danger' : 'default'}
              fill={currentItem.result === 'fail' ? 'solid' : 'outline'}
            >
              <CloseOutline />
              不合规
            </Button>
            <Button
              className={`result-btn ${currentItem.result === 'na' ? 'active' : ''}`}
              onClick={() => handleResult('na')}
              color={currentItem.result === 'na' ? 'default' : 'default'}
              fill={currentItem.result === 'na' ? 'solid' : 'outline'}
            >
              <MinusOutline />
              不适用
            </Button>
          </div>
        </div>

        {/* 检查说明 */}
        <div className="comment-section">
          <h4 className="section-title">检查说明</h4>
          <TextArea
            placeholder="请输入检查说明..."
            rows={3}
            maxLength={500}
            showCount
            onChange={(val) => {
              commentRef.current = val
            }}
          />
        </div>

        {/* 现场照片 */}
        <div className="photo-section">
          <h4 className="section-title">
            <CameraOutline /> 现场照片
          </h4>
          <ImageUploader
            upload={handlePhotoUpload}
            multiple
            maxCount={9}
            accept="image/*"
          />
        </div>

        {/* AI辅助按钮 */}
        <div className="ai-section">
          <Button
            className="ai-btn"
            onClick={handleAiSuggestion}
            loading={aiLoading}
          >
            <SetOutline /> AI监管建议
          </Button>
          <Button
            className="ai-btn"
            onClick={handleLegalBasis}
            loading={aiLoading}
          >
            <FileOutline /> 法规依据
          </Button>
        </div>
      </div>

      {/* 底部导航 */}
      <div className="inspection-footer">
        <Button
          className="nav-btn"
          onClick={handlePrev}
          disabled={currentIndex === 0}
        >
          上一条
        </Button>
        <Button
          className="nav-btn submit-btn"
          color="primary"
          onClick={handleNext}
          loading={submitting}
        >
          {currentIndex === task.check_items.length - 1 ? '完成检查' : '下一条'}
        </Button>
      </div>

      {/* AI结果浮层 */}
      <FloatingPanel
        anchors={[100, 400, 600]}
        visible={showAiResult}
        onClose={() => setShowAiResult(false)}
      >
        <div className="ai-result-panel">
          <h4>AI 分析结果</h4>
          {aiLoading ? (
            <div className="ai-loading">
              <SpinLoading color="primary" />
              <p>AI正在分析...</p>
            </div>
          ) : (
            <div className="ai-result-content">{aiResult}</div>
          )}
        </div>
      </FloatingPanel>
    </div>
  )
}

export default Inspection
