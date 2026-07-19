import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Descriptions, Tag, Button, Progress, Table, message, Space } from 'antd'
import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { taskApi } from '@/services/api'
import dayjs from 'dayjs'

const PASS_RESULTS = new Set(['compliant', 'pass', 'qualified', '1'])
const FAIL_RESULTS = new Set(['non_compliant', 'fail', 'unqualified', '3', 'pending_rectification'])
const NA_RESULTS = new Set(['not_applicable', 'na', 'n/a', '不适用'])

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
      pass: { color: 'success', text: '合格' },
      fail: { color: 'error', text: '不合格' },
      pending_rectification: { color: 'warning', text: '待整改' },
      na: { color: 'default', text: '未涉及' },
    }
    const item = resultMap[result] || { color: 'default', text: result || '未填写' }
    return <Tag color={item.color}>{item.text}</Tag>
  }

  const getItemTitle = (record: any) =>
    record?.check_item?.title ||
    record?.template_item?.title ||
    record?.item_title ||
    '未命名检查项'

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
    {
      title: '检查项',
      key: 'title',
      render: (_: any, record: any) => getItemTitle(record),
    },
    {
      title: '结果',
      dataIndex: 'result',
      key: 'result',
      width: 120,
      render: (result: string) => getResultTag(result),
    },
    { title: '说明', dataIndex: 'result_text', key: 'result_text', ellipsis: true },
    { title: '专家备注', dataIndex: 'inspector_note', key: 'inspector_note', ellipsis: true },
  ]

  // 前端兜底统计（兼容后端旧版本）
  const localStats = (() => {
    const list = (records || []).filter((r) => !(r.template_item?.is_category || r.check_item?.is_category))
    const total = list.length
    const completed = list.filter((r) => r.result).length
    const compliant = list.filter((r) => PASS_RESULTS.has(r.result)).length
    const non_compliant = list.filter((r) => FAIL_RESULTS.has(r.result)).length
    const not_applicable = list.filter((r) => NA_RESULTS.has(r.result)).length
    const compliance_rate = completed > 0 ? Math.round((compliant / completed) * 10000) / 100 : 0
    return { total, completed, compliant, non_compliant, not_applicable, compliance_rate }
  })()

  const stats = summary
    ? {
        total: summary.total ?? localStats.total,
        completed: summary.completed ?? localStats.completed,
        compliant: summary.compliant ?? localStats.compliant,
        non_compliant: summary.non_compliant ?? localStats.non_compliant,
        not_applicable: summary.not_applicable ?? localStats.not_applicable,
        compliance_rate: summary.compliance_rate ?? localStats.compliance_rate,
      }
    : localStats

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
          返回
        </Button>
        <h1 className="page-title" style={{ margin: 0 }}>
          任务详情
        </h1>
        {task && (
          <Space style={{ marginLeft: 'auto' }}>
            <Button
              type="primary"
              icon={<EditOutlined />}
              onClick={() => navigate(`/inspection/${id}`)}
            >
              {task.status === 'completed' ? '查看/修改检查' : '执行检查'}
            </Button>
          </Space>
        )}
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

          <Card title="检查进度" style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
              <div style={{ flex: '0 0 200px' }}>
                <Progress
                  type="circle"
                  percent={
                    stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0
                  }
                  format={() => `${stats.completed}/${stats.total}`}
                />
              </div>
              <div>
                <p>
                  <Tag color="success">合规/合格: {stats.compliant}</Tag>
                </p>
                <p>
                  <Tag color="error">不合规/不合格: {stats.non_compliant}</Tag>
                </p>
                <p>
                  <Tag>不适用: {stats.not_applicable}</Tag>
                </p>
                <p>
                  <strong>合规率: {stats.compliance_rate}%</strong>
                </p>
              </div>
            </div>
          </Card>

          <Card
            title="检查记录"
            style={{ marginTop: 16 }}
            extra={
              task.status === 'in_progress' && (
                <Button type="primary" onClick={handleComplete}>
                  完成任务
                </Button>
              )
            }
          >
            <Table
              dataSource={records}
              columns={columns}
              rowKey="id"
              loading={loading}
              scroll={{ x: 800 }}
              locale={{ emptyText: '暂无检查项记录' }}
            />
          </Card>
        </>
      )}
    </div>
  )
}
