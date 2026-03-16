import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Descriptions, Tag, Button, Progress, Table, message } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { taskApi } from '@/services/api'
import dayjs from 'dayjs'

export default function TaskDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [task, setTask] = useState<any>(null)
  const [records, setRecords] = useState<any[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchTaskDetail()
  }, [id])

  const fetchTaskDetail = async () => {
    if (!id) return
    setLoading(true)
    try {
      const [taskRes, recordsRes, summaryRes]: any[] = await Promise.all([
        taskApi.getTask(id),
        taskApi.getTaskRecords(id),
        taskApi.getTaskSummary(id),
      ])
      setTask(taskRes.data)
      setRecords(recordsRes.data || [])
      setSummary(summaryRes.data)
    } catch (error) {
      console.error('Failed to fetch task detail:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      pending: { color: 'default', text: '待开始' },
      in_progress: { color: 'processing', text: '进行中' },
      completed: { color: 'success', text: '已完成' },
      cancelled: { color: 'error', text: '已取消' },
    }
    const item = statusMap[status] || { color: 'default', text: status }
    return <Tag color={item.color}>{item.text}</Tag>
  }

  const getResultTag = (result: string) => {
    const resultMap: Record<string, { color: string; text: string }> = {
      compliant: { color: 'success', text: '合规' },
      non_compliant: { color: 'error', text: '不合规' },
      not_applicable: { color: 'default', text: '不适用' },
    }
    const item = resultMap[result] || { color: 'default', text: result || '未填写' }
    return <Tag color={item.color}>{item.text}</Tag>
  }

  const handleComplete = async () => {
    try {
      await taskApi.completeTask(id!)
      message.success('任务已完成')
      fetchTaskDetail()
    } catch (error) {
      message.error('操作失败')
    }
  }

  const columns = [
    { title: '检查项', dataIndex: ['check_item', 'title'], key: 'title' },
    {
      title: '结果',
      dataIndex: 'result',
      key: 'result',
      render: (result: string) => getResultTag(result),
    },
    { title: '说明', dataIndex: 'result_text', key: 'result_text', ellipsis: true },
    { title: '专家备注', dataIndex: 'inspector_note', key: 'inspector_note', ellipsis: true },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
          返回
        </Button>
        <h1 className="page-title" style={{ margin: 0 }}>
          任务详情
        </h1>
      </div>

      {task && (
        <>
          <Card loading={loading}>
            <Descriptions bordered column={{ xs: 1, sm: 2, lg: 3 }}>
              <Descriptions.Item label="任务编号">{task.task_no}</Descriptions.Item>
              <Descriptions.Item label="任务标题">{task.title}</Descriptions.Item>
              <Descriptions.Item label="状态">{getStatusTag(task.status)}</Descriptions.Item>
              <Descriptions.Item label="被检查对象">{task.target_name}</Descriptions.Item>
              <Descriptions.Item label="检查地址">{task.target_address}</Descriptions.Item>
              <Descriptions.Item label="联系人">{task.target_contact}</Descriptions.Item>
              <Descriptions.Item label="联系电话">{task.target_phone}</Descriptions.Item>
              <Descriptions.Item label="计划时间">
                {task.scheduled_at ? dayjs(task.scheduled_at).format('YYYY-MM-DD HH:mm') : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {dayjs(task.created_at).format('YYYY-MM-DD HH:mm')}
              </Descriptions.Item>
              {task.remarks && (
                <Descriptions.Item label="备注" span={3}>
                  {task.remarks}
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>

          {summary && (
            <Card title="检查进度" style={{ marginTop: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
                <div style={{ flex: '0 0 200px' }}>
                  <Progress
                    type="circle"
                    percent={summary.completion_rate || 0}
                    format={() => `${summary.completed}/${summary.total}`}
                  />
                </div>
                <div>
                  <p>
                    <Tag color="success">合规: {summary.compliant}</Tag>
                  </p>
                  <p>
                    <Tag color="error">不合规: {summary.non_compliant}</Tag>
                  </p>
                  <p>
                    <Tag>不适用: {summary.not_applicable}</Tag>
                  </p>
                  <p>
                    <strong>合规率: {summary.compliance_rate}%</strong>
                  </p>
                </div>
              </div>
            </Card>
          )}

          <Card title="检查记录" style={{ marginTop: 16 }} extra={
            task.status === 'in_progress' && (
              <Button type="primary" onClick={handleComplete}>
                完成任务
              </Button>
            )
          }>
            <Table
              dataSource={records}
              columns={columns}
              rowKey="id"
              loading={loading}
              scroll={{ x: 800 }}
            />
          </Card>
        </>
      )}
    </div>
  )
}
