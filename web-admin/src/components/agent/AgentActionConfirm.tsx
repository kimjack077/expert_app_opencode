import { useState } from 'react'
import { Button, Card, Descriptions, Input, Space, Tag, Typography } from 'antd'
import {
  CheckOutlined,
  CloseOutlined,
  EditOutlined,
  FileTextOutlined,
  SafetyCertificateOutlined,
  WarningOutlined,
} from '@ant-design/icons'

const { Paragraph, Text } = Typography

export interface AgentAction {
  type: 'create_task' | 'judgment' | 'final_verdict' | 'operation'
  serverAction?: string
  title: string
  data: Record<string, unknown>
  status: 'pending' | 'confirmed' | 'cancelled' | 'failed'
  /**
   * 服务端持久化提案的定位坐标（来自 SSE 的 conversation / action_proposal 事件）。
   * 确认时只回传这两个值，执行内容完全由服务端动作注册表决定。
   */
  messageId?: string
  actionIndex?: number
}

interface Props {
  action: AgentAction
  applying?: boolean
  onConfirm: (modifiedData?: Record<string, unknown>) => void | Promise<void>
  onCancel: () => void
}

const resultConfig: Record<string, { text: string; color: string }> = {
  pass: { text: '符合', color: 'success' },
  partial_pass: { text: '基本符合', color: 'warning' },
  fail: { text: '不符合', color: 'error' },
  na: { text: '不适用', color: 'default' },
}

export default function AgentActionConfirm({ action, applying = false, onConfirm, onCancel }: Props) {
  const [editing, setEditing] = useState(false)
  const [editedData, setEditedData] = useState<Record<string, unknown>>(action.data)

  const icon = action.type === 'create_task'
    ? <FileTextOutlined />
    : action.type === 'final_verdict'
      ? <SafetyCertificateOutlined />
      : <WarningOutlined />

  const color = action.type === 'judgment' ? '#d46b08' : '#1677ff'

  const renderJudgment = () => {
    const result = String(action.data.result || '')
    const config = resultConfig[result] || { text: result || '待判断', color: 'default' }
    return (
      <Descriptions column={1} size="small">
        <Descriptions.Item label="检查项">{String(action.data.checkItem || action.data.item_title || '-')}</Descriptions.Item>
        <Descriptions.Item label="建议结果"><Tag color={config.color}>{config.text}</Tag></Descriptions.Item>
        <Descriptions.Item label="问题描述">
          <Paragraph style={{ marginBottom: 0 }}>{String(action.data.problemDescription || action.data.problem_description || '-')}</Paragraph>
        </Descriptions.Item>
        <Descriptions.Item label="整改建议">
          <Paragraph style={{ marginBottom: 0 }}>{String(action.data.rectificationSuggestion || action.data.rectification_suggestion || '-')}</Paragraph>
        </Descriptions.Item>
      </Descriptions>
    )
  }

  const renderFinalVerdict = () => {
    const verdict = String(action.data.verdict || '')
    const config = resultConfig[verdict] || { text: verdict || '待判断', color: 'default' }
    return (
      <Descriptions column={1} size="small">
        <Descriptions.Item label="最终结论"><Tag color={config.color}>{config.text}</Tag></Descriptions.Item>
        <Descriptions.Item label="结论说明">
          <Paragraph style={{ marginBottom: 0 }}>{String(action.data.comment || '-')}</Paragraph>
        </Descriptions.Item>
      </Descriptions>
    )
  }

  const renderTask = () => {
    if (editing) {
      return (
        <Space direction="vertical" style={{ width: '100%' }}>
          <label>
            <Text>企业</Text>
            <Input
              value={String(editedData.enterprise || '')}
              onChange={(event) => setEditedData({ ...editedData, enterprise: event.target.value })}
            />
          </label>
          <label>
            <Text>模板</Text>
            <Input
              value={String(editedData.template || '')}
              onChange={(event) => setEditedData({ ...editedData, template: event.target.value })}
            />
          </label>
          <label>
            <Text>日期</Text>
            <Input
              value={String(editedData.date || '')}
              onChange={(event) => setEditedData({ ...editedData, date: event.target.value })}
            />
          </label>
        </Space>
      )
    }

    return (
      <Descriptions column={1} size="small">
        <Descriptions.Item label="企业">{String(action.data.enterprise || '-')}</Descriptions.Item>
        <Descriptions.Item label="模板">{String(action.data.template || '-')}</Descriptions.Item>
        <Descriptions.Item label="日期">{String(action.data.date || '-')}</Descriptions.Item>
        <Descriptions.Item label="检查员">{String(action.data.inspector || '-')}</Descriptions.Item>
      </Descriptions>
    )
  }

  return (
    <Card
      className="agent-action-confirm"
      size="small"
      title={<Space style={{ color }}>{icon}<span>{action.title}</span></Space>}
      style={{ borderLeftColor: color, borderLeftWidth: 3 }}
    >
      {action.type === 'judgment' && renderJudgment()}
      {action.type === 'final_verdict' && renderFinalVerdict()}
      {action.type === 'create_task' && renderTask()}
      {action.type === 'operation' && (
        <Descriptions column={1} size="small">
          <Descriptions.Item label="项目ID">
            {String(action.data.project_id || '-')}
          </Descriptions.Item>
          {action.data.plan_item_id ? (
            <Descriptions.Item label="计划项ID">
              {String(action.data.plan_item_id)}
            </Descriptions.Item>
          ) : null}
          {action.data.evidence ? (
            <Descriptions.Item label="现场证据">
              <Paragraph style={{ marginBottom: 0 }}>
                {String(action.data.evidence)}
              </Paragraph>
            </Descriptions.Item>
          ) : null}
          {action.data.draft_count !== undefined ? (
            <Descriptions.Item label="草稿范围">
              {action.data.safe_only
                ? '仅证据充分的非异常草稿'
                : `${String(action.data.draft_count)} 条已选草稿`}
            </Descriptions.Item>
          ) : null}
          <Descriptions.Item label="写入方式">
            当前项目内受控写入，确认成功后刷新项目数据。
          </Descriptions.Item>
        </Descriptions>
      )}

      <Space wrap style={{ marginTop: 12 }}>
        <Button
          type="primary"
          icon={<CheckOutlined />}
          loading={applying}
          onClick={() => onConfirm(editing ? editedData : undefined)}
        >
          {editing ? '保存并确认' : '确认执行'}
        </Button>
        {action.type === 'create_task' && !editing && (
          <Button icon={<EditOutlined />} disabled={applying} onClick={() => setEditing(true)}>修改</Button>
        )}
        {editing && (
          <Button disabled={applying} onClick={() => { setEditedData(action.data); setEditing(false) }}>取消修改</Button>
        )}
        <Button icon={<CloseOutlined />} disabled={applying} onClick={onCancel}>拒绝</Button>
      </Space>
    </Card>
  )
}
