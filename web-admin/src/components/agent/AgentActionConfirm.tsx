import { useState } from 'react'
import { Card, Button, Descriptions, Input, Tag, Modal } from 'antd'
import {
  CheckOutlined,
  CloseOutlined,
  EditOutlined,
  WarningOutlined,
  FileTextOutlined,
} from '@ant-design/icons'

interface ActionConfirm {
  type: 'create_task' | 'judgment' | 'operation'
  title: string
  data: Record<string, unknown>
  status: 'pending' | 'confirmed' | 'cancelled'
}

interface AgentActionConfirmProps {
  action: ActionConfirm
  onConfirm: (modifiedData?: Record<string, unknown>) => void
  onCancel: () => void
}

export default function AgentActionConfirm({
  action,
  onConfirm,
  onCancel,
}: AgentActionConfirmProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editedData, setEditedData] = useState<Record<string, unknown>>(action.data)
  const [showDetailModal, setShowDetailModal] = useState(false)

  const getActionIcon = () => {
    switch (action.type) {
      case 'create_task':
        return <FileTextOutlined />
      case 'judgment':
        return <WarningOutlined />
      default:
        return <WarningOutlined />
    }
  }

  const getActionColor = () => {
    switch (action.type) {
      case 'create_task':
        return '#1677FF'
      case 'judgment':
        return '#FAAD14'
      default:
        return '#FAAD14'
    }
  }

  const handleEdit = () => {
    setIsEditing(true)
  }

  const handleSaveEdit = () => {
    setIsEditing(false)
    onConfirm(editedData)
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    setEditedData(action.data)
  }

  const renderJudgmentContent = () => {
    const data = action.data as {
      checkItem?: string
      result?: string
      problemDescription?: string
      rectificationSuggestion?: string
    }

    return (
      <div className="judgment-content">
        <div className="judgment-item">
          <span className="label">检查项：</span>
          <span className="value">{data.checkItem}</span>
        </div>
        <div className="judgment-item">
          <span className="label">建议结果：</span>
          <Tag
            color={
              data.result === 'pass'
                ? 'success'
                : data.result === 'fail'
                ? 'error'
                : 'warning'
            }
          >
            {data.result === 'pass'
              ? '合格'
              : data.result === 'fail'
              ? '不合格'
              : '基本合格'}
          </Tag>
        </div>
        {data.problemDescription && (
          <div className="judgment-item">
            <span className="label">问题描述：</span>
            <div className="description-box">{data.problemDescription}</div>
          </div>
        )}
        {data.rectificationSuggestion && (
          <div className="judgment-item">
            <span className="label">整改建议：</span>
            <div className="description-box">{data.rectificationSuggestion}</div>
          </div>
        )}
      </div>
    )
  }

  const renderTaskContent = () => {
    const data = action.data as {
      enterprise?: string
      template?: string
      date?: string
      inspector?: string
    }

    if (isEditing) {
      return (
        <div className="edit-form">
          <div className="edit-item">
            <label>企业：</label>
            <Input
              value={editedData.enterprise as string}
              onChange={(e) =>
                setEditedData({ ...editedData, enterprise: e.target.value })
              }
            />
          </div>
          <div className="edit-item">
            <label>模板：</label>
            <Input
              value={editedData.template as string}
              onChange={(e) =>
                setEditedData({ ...editedData, template: e.target.value })
              }
            />
          </div>
          <div className="edit-item">
            <label>日期：</label>
            <Input
              value={editedData.date as string}
              onChange={(e) =>
                setEditedData({ ...editedData, date: e.target.value })
              }
            />
          </div>
          <div className="edit-actions">
            <Button size="small" onClick={handleCancelEdit}>
              取消
            </Button>
            <Button type="primary" size="small" onClick={handleSaveEdit}>
              保存
            </Button>
          </div>
        </div>
      )
    }

    return (
      <Descriptions column={1} size="small">
        <Descriptions.Item label="企业">{data.enterprise}</Descriptions.Item>
        <Descriptions.Item label="模板">{data.template}</Descriptions.Item>
        <Descriptions.Item label="日期">{data.date}</Descriptions.Item>
        <Descriptions.Item label="检查员">{data.inspector}</Descriptions.Item>
      </Descriptions>
    )
  }

  return (
    <Card
      className="agent-action-confirm"
      size="small"
      title={
        <div className="action-title" style={{ color: getActionColor() }}>
          {getActionIcon()}
          <span>{action.title}</span>
        </div>
      }
      style={{ borderLeftColor: getActionColor(), borderLeftWidth: 3 }}
    >
      {action.type === 'judgment' && renderJudgmentContent()}
      {action.type === 'create_task' && renderTaskContent()}
      {action.type === 'operation' && (
        <div className="operation-content">
          <pre>{JSON.stringify(action.data, null, 2)}</pre>
        </div>
      )}

      {!isEditing && (
        <div className="action-buttons">
          <Button
            type="primary"
            icon={<CheckOutlined />}
            onClick={() => onConfirm()}
          >
            确认
          </Button>
          {action.type === 'create_task' && (
            <Button icon={<EditOutlined />} onClick={handleEdit}>
              修改
            </Button>
          )}
          <Button icon={<CloseOutlined />} onClick={onCancel}>
            取消
          </Button>
        </div>
      )}
    </Card>
  )
}