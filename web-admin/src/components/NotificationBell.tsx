/**
 * 顶栏通知铃铛：展示智审 Agent 主动提醒（企业复审到期、不符合项超期、AI 草稿积压）。
 * 后端定时巡检写入 agent_notifications，此前前端没有任何入口可以看到。
 */
import { useEffect, useState } from 'react'
import { Badge, Button, Empty, List, Popover, Segmented, Space, Tag, Tooltip, Typography, message } from 'antd'
import { BellOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { notificationApi } from '@/services/api'

interface NotificationItem {
  id: string
  kind: string
  severity?: string
  title: string
  body?: string
  status: string
  enterprise_id?: string | null
  project_id?: string | null
  created_at?: string | null
}

const kindLabel: Record<string, { text: string; color: string }> = {
  reaudit_due: { text: '复审到期', color: 'orange' },
  open_nonconformity: { text: 'NC 超期', color: 'red' },
  stale_draft: { text: '草稿待确认', color: 'blue' },
}

const POLL_MS = 2 * 60 * 1000

/** 历史提醒中残留的英文状态码 / 空条款，展示前转成中文（新提醒已在后端修正） */
const NC_STATUS_TEXT: Record<string, string> = {
  open: '待整改',
  pending_rectification: '待整改',
  corrected: '已整改·待验证',
  pending_verification: '待验证',
  draft: 'AI 草稿',
}
const prettifyNotificationText = (text?: string) =>
  (text || '')
    .replace(/当前状态[:：]\s*([a-z_]+)/g, (_, s) => `当前状态：${NC_STATUS_TEXT[s] || s}`)
    .replace(/[:：]\s*$/, '')

/** 每类提醒点开后直接到能处理它的位置 */
const targetOf = (item: NotificationItem): string | null => {
  if (item.project_id) {
    if (item.kind === 'open_nonconformity') return `/audit-projects/${item.project_id}?tab=nonconformities`
    if (item.kind === 'stale_draft') return `/audit-projects/${item.project_id}?tab=records`
    return `/audit-projects/${item.project_id}`
  }
  if (item.enterprise_id) return '/enterprises'
  return null
}

export default function NotificationBell() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<'unread' | 'all'>('unread')
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)

  const load = async (status: 'unread' | 'all' = tab) => {
    setLoading(true)
    try {
      const res: any = await notificationApi.list(status)
      const list: NotificationItem[] = res?.data?.items || []
      setItems(list)
      if (status === 'unread') setUnreadCount(list.length)
    } catch {
      // 通知是辅助信息，加载失败不打断用户
    } finally {
      setLoading(false)
    }
  }

  const refreshCount = async () => {
    try {
      const res: any = await notificationApi.list('unread')
      setUnreadCount((res?.data?.items || []).length)
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    refreshCount()
    const timer = window.setInterval(refreshCount, POLL_MS)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (open) load(tab)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, tab])

  const mark = async (item: NotificationItem, status: 'read' | 'dismissed') => {
    try {
      await notificationApi.update(item.id, status)
      if (tab === 'unread') {
        setItems((prev) => prev.filter((i) => i.id !== item.id))
      } else {
        setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, status } : i)))
      }
      if (item.status === 'unread') setUnreadCount((c) => Math.max(0, c - 1))
    } catch {
      message.error('操作失败，请稍后重试')
    }
  }

  const markAllRead = async () => {
    const unread = items.filter((i) => i.status === 'unread')
    await Promise.allSettled(unread.map((i) => notificationApi.update(i.id, 'read')))
    message.success('已全部标为已读')
    load(tab)
    refreshCount()
  }

  const openTarget = (item: NotificationItem) => {
    const target = targetOf(item)
    if (item.status === 'unread') mark(item, 'read')
    setOpen(false)
    if (target) navigate(target)
  }

  const content = (
    <div style={{ width: 380 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <Segmented
          size="small"
          value={tab}
          onChange={(v) => setTab(v as 'unread' | 'all')}
          options={[
            { label: `未读${unreadCount ? ` ${unreadCount}` : ''}`, value: 'unread' },
            { label: '全部', value: 'all' },
          ]}
        />
        {items.some((i) => i.status === 'unread') && (
          <Button type="link" size="small" onClick={markAllRead}>
            全部已读
          </Button>
        )}
      </div>
      <List
        loading={loading}
        dataSource={items}
        style={{ maxHeight: 420, overflowY: 'auto' }}
        locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={tab === 'unread' ? '没有未读提醒' : '暂无提醒'} /> }}
        renderItem={(item) => {
          const k = kindLabel[item.kind] || { text: '提醒', color: 'default' }
          return (
            <List.Item
              style={{ cursor: item.project_id || item.enterprise_id ? 'pointer' : 'default', opacity: item.status === 'unread' ? 1 : 0.6 }}
              onClick={() => openTarget(item)}
              actions={
                item.status === 'unread'
                  ? [
                      <Tooltip title="标为已读" key="read">
                        <Button
                          type="text"
                          size="small"
                          icon={<CheckOutlined />}
                          onClick={(e) => {
                            e.stopPropagation()
                            mark(item, 'read')
                          }}
                        />
                      </Tooltip>,
                      <Tooltip title="忽略" key="dismiss">
                        <Button
                          type="text"
                          size="small"
                          icon={<CloseOutlined />}
                          onClick={(e) => {
                            e.stopPropagation()
                            mark(item, 'dismissed')
                          }}
                        />
                      </Tooltip>,
                    ]
                  : undefined
              }
            >
              <List.Item.Meta
                title={
                  <Space size={6}>
                    <Tag color={k.color} style={{ marginInlineEnd: 0 }}>{k.text}</Tag>
                    <Typography.Text strong={item.status === 'unread'} ellipsis style={{ maxWidth: 210 }}>
                      {prettifyNotificationText(item.title)}
                    </Typography.Text>
                  </Space>
                }
                description={
                  <div style={{ fontSize: 12 }}>
                    {item.body && <div style={{ marginBottom: 2 }}>{prettifyNotificationText(item.body)}</div>}
                    {item.created_at && <span style={{ color: '#94a3b8' }}>{dayjs(item.created_at).format('MM-DD HH:mm')}</span>}
                  </div>
                }
              />
            </List.Item>
          )
        }}
      />
    </div>
  )

  return (
    <Popover
      content={content}
      title="智审提醒"
      trigger="click"
      placement="bottomRight"
      open={open}
      onOpenChange={setOpen}
    >
      <Tooltip title={open ? '' : '智审提醒'}>
        <Badge count={unreadCount} size="small" offset={[-4, 4]}>
          <Button type="text" className="header-icon-btn" icon={<BellOutlined style={{ fontSize: 15 }} />} aria-label="通知" />
        </Badge>
      </Tooltip>
    </Popover>
  )
}
