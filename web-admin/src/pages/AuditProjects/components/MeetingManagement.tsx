import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Checkbox,
  DatePicker,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'

import { auditTeamApi, meetingApi } from '@/services/auditProjectApi'

const { Paragraph, Text } = Typography
const { TextArea } = Input

interface Props {
  projectId: string
}

interface MeetingItem {
  id: string
  meeting_type: string
  meeting_time: string
  participants_enterprise?: string
  participants_audit_team?: string[]
  key_points?: string
  meeting_minutes?: string
  sign_in_sheet?: {
    confirmed?: boolean
    note?: string
  }
}

const meetingTypeText: Record<string, string> = {
  opening: '首次会议',
  interim: '阶段沟通',
  closing: '末次会议',
  internal: '审核组内部会议',
}

const unwrapList = <T,>(response: any): T[] => {
  const payload = response?.data ?? response
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  return []
}

export default function MeetingManagement({ projectId }: Props) {
  const [form] = Form.useForm()
  const [meetings, setMeetings] = useState<MeetingItem[]>([])
  const [teamMembers, setTeamMembers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<MeetingItem>()

  const fetchData = async () => {
    setLoading(true)
    try {
      const [meetingResponse, teamResponse] = await Promise.all([
        meetingApi.list(projectId),
        auditTeamApi.list(projectId),
      ])
      setMeetings(unwrapList<MeetingItem>(meetingResponse))
      setTeamMembers(unwrapList<any>(teamResponse))
    } catch (error: any) {
      message.error(error.response?.data?.detail || error.response?.data?.message || '获取会议记录失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [projectId])

  // BUG-25：智审 Agent 确认写入会议记录后，广播全局事件；面板监听并刷新，
  // 避免用户需要手动刷新页面才能看到新会议。
  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ serverAction?: string }>).detail || {}
      if (String(detail.serverAction || '') === 'create_meeting_record') {
        fetchData()
      }
    }
    window.addEventListener('efis:action-confirmed', handler)
    return () => window.removeEventListener('efis:action-confirmed', handler)
  }, [projectId])

  const showCreate = () => {
    setEditing(undefined)
    form.resetFields()
    form.setFieldsValue({ meeting_type: 'opening', meeting_time: dayjs(), sign_in_confirmed: false })
    setOpen(true)
  }

  const showEdit = (item: MeetingItem) => {
    setEditing(item)
    form.setFieldsValue({
      ...item,
      meeting_time: dayjs(item.meeting_time),
      sign_in_confirmed: Boolean(item.sign_in_sheet?.confirmed),
      sign_in_note: item.sign_in_sheet?.note,
    })
    setOpen(true)
  }

  const handleSubmit = async (values: any) => {
    setSaving(true)
    try {
      const data = {
        project_id: projectId,
        meeting_type: values.meeting_type,
        meeting_time: values.meeting_time.toISOString(),
        participants_enterprise: values.participants_enterprise,
        participants_audit_team: values.participants_audit_team || [],
        key_points: values.key_points,
        meeting_minutes: values.meeting_minutes,
        sign_in_sheet: values.sign_in_confirmed || values.sign_in_note
          ? { confirmed: Boolean(values.sign_in_confirmed), note: values.sign_in_note || '' }
          : null,
      }
      if (editing) {
        await meetingApi.update(editing.id, data)
        message.success('会议记录已更新')
      } else {
        await meetingApi.create(projectId, data)
        message.success('会议记录已创建')
      }
      setOpen(false)
      form.resetFields()
      await fetchData()
    } catch (error: any) {
      message.error(error.response?.data?.detail || error.response?.data?.message || '保存会议记录失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (item: MeetingItem) => {
    try {
      await meetingApi.delete(item.id)
      message.success('会议记录已删除')
      await fetchData()
    } catch (error: any) {
      message.error(error.response?.data?.detail || error.response?.data?.message || '删除会议记录失败')
    }
  }

  const hasOpening = meetings.some((item) => item.meeting_type === 'opening')
  const hasClosing = meetings.some((item) => item.meeting_type === 'closing')

  const columns: TableColumnsType<MeetingItem> = [
    {
      title: '会议',
      dataIndex: 'meeting_type',
      width: 150,
      render: (value: string) => meetingTypeText[value] || value,
    },
    {
      title: '时间',
      dataIndex: 'meeting_time',
      width: 190,
      render: (value: string) => new Date(value).toLocaleString('zh-CN', { hour12: false }),
    },
    {
      title: '企业参会人员',
      dataIndex: 'participants_enterprise',
      ellipsis: true,
      render: (value?: string) => value || '-',
    },
    {
      title: '签到',
      key: 'signIn',
      width: 110,
      render: (_, item) => item.sign_in_sheet?.confirmed
        ? <Tag color="success">已确认</Tag>
        : <Tag color="warning">待补充</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_, item) => (
        <Space size={0}>
          <Button type="link" icon={<EditOutlined />} onClick={() => showEdit(item)}>
            编辑
          </Button>
          <Popconfirm
            title="删除会议记录"
            description="删除后案卷中将缺少该会议记录，确定删除？"
            okText="删除"
            okButtonProps={{ danger: true }}
            cancelText="取消"
            onConfirm={() => handleDelete(item)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {(!hasOpening || !hasClosing) && (
        <Alert
          type="warning"
          showIcon
          message="案卷会议记录尚不完整"
          description={`还需补充：${[
            !hasOpening ? '首次会议' : '',
            !hasClosing ? '末次会议' : '',
          ].filter(Boolean).join('、')}。会议纪要和签到状态会进入资料完整性检查及归档包。`}
        />
      )}

      <div>
        <Button type="primary" icon={<PlusOutlined />} onClick={showCreate}>
          新增会议记录
        </Button>
      </div>

      <Table<MeetingItem>
        rowKey="id"
        columns={columns}
        dataSource={meetings}
        loading={loading}
        pagination={false}
        locale={{ emptyText: <Empty description="暂无首次、末次或沟通会议记录" /> }}
        expandable={{
          expandedRowRender: (item) => (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text strong>会议要点</Text>
              <Paragraph>{item.key_points || '-'}</Paragraph>
              <Text strong>会议纪要</Text>
              <Paragraph>{item.meeting_minutes || '-'}</Paragraph>
              {item.sign_in_sheet?.note && <Text type="secondary">签到说明：{item.sign_in_sheet.note}</Text>}
            </Space>
          ),
          rowExpandable: (item) => Boolean(item.key_points || item.meeting_minutes || item.sign_in_sheet?.note),
        }}
      />

      <Modal
        title={editing ? '编辑会议记录' : '新增会议记录'}
        open={open}
        width={720}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
        onOk={() => form.submit()}
        onCancel={() => setOpen(false)}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Space size="large" style={{ width: '100%' }} align="start">
            <Form.Item
              label="会议类型"
              name="meeting_type"
              rules={[{ required: true, message: '请选择会议类型' }]}
              style={{ minWidth: 220 }}
            >
              <Select
                options={Object.entries(meetingTypeText).map(([value, label]) => ({ value, label }))}
              />
            </Form.Item>
            <Form.Item
              label="会议时间"
              name="meeting_time"
              rules={[{ required: true, message: '请选择会议时间' }]}
            >
              <DatePicker showTime format="YYYY-MM-DD HH:mm" />
            </Form.Item>
          </Space>

          <Form.Item label="企业参会人员" name="participants_enterprise">
            <TextArea rows={2} placeholder="填写姓名、部门或职务，可一行一人" />
          </Form.Item>
          <Form.Item label="审核组参会人员" name="participants_audit_team">
            <Select
              mode="multiple"
              placeholder="选择审核组成员"
              options={teamMembers.map((member) => ({
                value: member.member_id,
                label: member.member_name || member.member_username || member.member_id,
              }))}
            />
          </Form.Item>
          <Form.Item label="会议要点" name="key_points">
            <TextArea rows={3} placeholder="议程、需确认事项和沟通结论" />
          </Form.Item>
          <Form.Item label="会议纪要" name="meeting_minutes">
            <TextArea rows={5} placeholder="记录双方确认的主要内容、异议和后续行动" />
          </Form.Item>
          <Space align="start" size="large">
            <Form.Item name="sign_in_confirmed" valuePropName="checked">
              <Checkbox>签到表已收集并核对</Checkbox>
            </Form.Item>
            <Form.Item name="sign_in_note">
              <Input placeholder="签到表文件名或补充说明" style={{ width: 320 }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </Space>
  )
}
