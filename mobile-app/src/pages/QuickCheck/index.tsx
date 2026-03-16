import React, { useState } from 'react'
import {
  NavBar,
  Card,
  Button,
  TextArea,
  ImageUploader,
  Toast,
  List,
  Dialog,
} from 'antd-mobile'
import {
  CameraOutline,
  LocationOutline,
  ClockCircleOutline,
} from 'antd-mobile-icons'
import './style.css'

// 快速检查模板（简化版）
const quickCheckItems = [
  { id: '1', title: '安全通道畅通', category: '消防' },
  { id: '2', title: '消防器材完好', category: '消防' },
  { id: '3', title: '用电安全规范', category: '用电' },
  { id: '4', title: '设备防护到位', category: '设备' },
  { id: '5', title: '劳保用品佩戴', category: '防护' },
  { id: '6', title: '警示标识清晰', category: '标识' },
]

const QuickCheck: React.FC = () => {
  const [selectedItems, setSelectedItems] = useState<string[]>([])
  const [location, setLocation] = useState('')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const toggleItem = (id: string) => {
    if (selectedItems.includes(id)) {
      setSelectedItems(selectedItems.filter(item => item !== id))
    } else {
      setSelectedItems([...selectedItems, id])
    }
  }

  const handleSubmit = async () => {
    if (selectedItems.length === 0) {
      Toast.show({
        icon: 'fail',
        content: '请至少选择一项检查内容',
      })
      return
    }

    Dialog.confirm({
      title: '提交快速检查',
      content: `已选择 ${selectedItems.length} 项检查内容，确定提交吗？`,
      onConfirm: async () => {
        setSubmitting(true)
        // 模拟提交
        setTimeout(() => {
          setSubmitting(false)
          Toast.show({
            icon: 'success',
            content: '提交成功',
          })
          // 重置
          setSelectedItems([])
          setComment('')
        }, 1500)
      },
    })
  }

  const handlePhotoUpload = async (file: File) => {
    // 模拟上传
    return { url: URL.createObjectURL(file) }
  }

  return (
    <div className="quick-check-page">
      <NavBar back={null} className="quick-nav">
        快速检查
      </NavBar>

      <div className="quick-content">
        {/* 位置信息 */}
        <Card className="location-card">
          <div className="location-header">
            <LocationOutline className="location-icon" />
            <span className="location-label">检查位置</span>
          </div>
          <TextArea
            placeholder="请输入检查位置（自动定位）"
            value={location}
            onChange={setLocation}
            rows={2}
          />
          <Button
            size="small"
            className="location-btn"
            onClick={() => {
              // 模拟定位
              setLocation('北京市朝阳区XX工厂A区')
              Toast.show({
                icon: 'success',
                content: '定位成功',
              })
            }}
          >
            自动定位
          </Button>
        </Card>

        {/* 快速检查项 */}
        <Card className="check-list-card">
          <div className="card-header">
            <ClockCircleOutline />
            <span>快速检查项（点击选择）</span>
          </div>
          <div className="quick-check-grid">
            {quickCheckItems.map((item) => (
              <div
                key={item.id}
                className={`quick-check-item ${
                  selectedItems.includes(item.id) ? 'selected' : ''
                }`}
                onClick={() => toggleItem(item.id)}
              >
                <span className="item-category">{item.category}</span>
                <span className="item-title">{item.title}</span>
                {selectedItems.includes(item.id) && (
                  <div className="selected-mark">✓</div>
                )}
              </div>
            ))}
          </div>
        </Card>

        {/* 问题描述 */}
        <Card className="comment-card">
          <div className="card-header">
            <span>问题描述</span>
          </div>
          <TextArea
            placeholder="请描述发现的问题..."
            value={comment}
            onChange={setComment}
            rows={4}
            maxLength={500}
            showCount
          />
        </Card>

        {/* 现场照片 */}
        <Card className="photo-card">
          <div className="card-header">
            <CameraOutline />
            <span>现场照片</span>
          </div>
          <ImageUploader
            upload={handlePhotoUpload}
            multiple
            maxCount={6}
            accept="image/*"
          />
        </Card>

        {/* 统计信息 */}
        <div className="summary-bar">
          <span>已选择: {selectedItems.length} 项</span>
          <span className="summary-time">
            {new Date().toLocaleString('zh-CN', {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </div>
      </div>

      {/* 提交按钮 */}
      <div className="quick-footer">
        <Button
          block
          color="primary"
          size="large"
          onClick={handleSubmit}
          loading={submitting}
          className="submit-btn"
        >
          提交快速检查
        </Button>
      </div>
    </div>
  )
}

export default QuickCheck
