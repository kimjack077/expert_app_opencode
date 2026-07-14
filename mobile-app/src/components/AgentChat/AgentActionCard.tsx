import React from 'react'
import { Button, Tag, Toast } from 'antd-mobile'
import {
  CheckOutline,
  CloseOutline,
  ExclamationCircleOutline,
  CheckShieldOutline,
} from 'antd-mobile-icons'
import type { ActionProposalState } from './types'
import './AgentActionCard.css'

interface AgentActionCardProps {
  action: ActionProposalState
  /**
   * 任务流页面（如 Inspection/QuickCheck）走 /api/tasks/* 的 TaskItemRecord，
   * 与本卡片对应的 /api/records/* 写入接口是不同的表。这类页面必须传
   * advisoryOnly，此时卡片只展示建议内容 + 复制按钮，不提供"采纳并填写"。
   */
  advisoryOnly?: boolean
  onConfirm?: () => void
  onCancel?: () => void
}

const resultText = (result?: string) => {
  const map: Record<string, string> = {
    pass: '合格',
    fail: '不合格',
    na: '不适用',
    partial_pass: '基本合格',
  }
  return (result && map[result]) || result || ''
}

const resultTagColor = (result?: string): 'success' | 'danger' | 'warning' | 'default' => {
  const map: Record<string, 'success' | 'danger' | 'warning' | 'default'> = {
    pass: 'success',
    fail: 'danger',
    na: 'default',
    partial_pass: 'warning',
  }
  return (result && map[result]) || 'default'
}

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    Toast.show({ icon: 'success', content: '已复制到剪贴板' })
  } catch {
    Toast.show({ icon: 'fail', content: '复制失败' })
  }
}

const buildCopyText = (action: ActionProposalState) => {
  if (action.type === 'judgment') {
    const lines = [`建议结果：${resultText(action.data.result)}`]
    if (action.data.problemDescription) lines.push(`问题描述：${action.data.problemDescription}`)
    if (action.data.rectificationSuggestion) lines.push(`整改建议：${action.data.rectificationSuggestion}`)
    return lines.join('\n')
  }
  if (action.type === 'final_verdict') {
    const lines = [`最终判定：${resultText(action.data.verdict)}`]
    if (action.data.comment) lines.push(`总体评价：${action.data.comment}`)
    return lines.join('\n')
  }
  return JSON.stringify(action.data, null, 2)
}

const AgentActionCard: React.FC<AgentActionCardProps> = ({
  action,
  advisoryOnly = false,
  onConfirm,
  onCancel,
}) => {
  const icon =
    action.type === 'judgment' ? (
      <ExclamationCircleOutline fontSize={16} color="#faad14" />
    ) : (
      <CheckShieldOutline fontSize={16} color="#1677ff" />
    )

  return (
    <div className={`agent-action-card ${action.type} ${action.status}`}>
      <div className="card-header">
        {icon}
        <span className="card-title">{action.title}</span>
      </div>

      <div className="card-content">
        {action.type === 'judgment' && (
          <>
            {action.data.checkItem && (
              <div className="info-row">
                <span className="label">检查项：</span>
                <span className="value">{action.data.checkItem}</span>
              </div>
            )}
            <div className="info-row">
              <span className="label">建议结果：</span>
              <Tag color={resultTagColor(action.data.result)}>{resultText(action.data.result)}</Tag>
            </div>
            {action.data.problemDescription && (
              <div className="info-block">
                <span className="label">问题描述：</span>
                <div className="description-box">{action.data.problemDescription}</div>
              </div>
            )}
            {action.data.rectificationSuggestion && (
              <div className="info-block">
                <span className="label">整改建议：</span>
                <div className="description-box">{action.data.rectificationSuggestion}</div>
              </div>
            )}
          </>
        )}

        {action.type === 'final_verdict' && (
          <>
            <div className="info-row">
              <span className="label">最终判定：</span>
              <Tag color={resultTagColor(action.data.verdict)}>{resultText(action.data.verdict)}</Tag>
            </div>
            {action.data.comment && (
              <div className="info-block">
                <span className="label">总体评价：</span>
                <div className="description-box">{action.data.comment}</div>
              </div>
            )}
          </>
        )}

        {action.type === 'operation' && (
          <pre className="operation-data">{JSON.stringify(action.data, null, 2)}</pre>
        )}
      </div>

      {advisoryOnly && action.status === 'pending' && (
        <>
          <div className="advisory-hint">
            <ExclamationCircleOutline fontSize={12} /> 当前页面暂不支持一键写入，请复制后手动填写
          </div>
          <div className="card-actions">
            <Button size="small" color="primary" fill="outline" onClick={() => copyToClipboard(buildCopyText(action))}>
              复制
            </Button>
            <Button size="small" onClick={onCancel}>
              <CloseOutline /> 忽略
            </Button>
          </div>
        </>
      )}

      {!advisoryOnly && action.status === 'pending' && (
        <div className="card-actions">
          <Button size="small" color="primary" onClick={onConfirm}>
            <CheckOutline /> 采纳并填写
          </Button>
          <Button size="small" onClick={onCancel}>
            <CloseOutline /> 忽略
          </Button>
        </div>
      )}

      {action.status !== 'pending' && (
        <div className="card-status">
          {action.status === 'confirmed' && (
            <>
              <CheckOutline color="#52c41a" /> 已填写
            </>
          )}
          {action.status === 'cancelled' && (
            <>
              <CloseOutline color="#ff4d4f" /> 已忽略
            </>
          )}
          {action.status === 'failed' && (
            <>
              <ExclamationCircleOutline color="#ff4d4f" /> 填写失败，请重试或手动填写
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default AgentActionCard
