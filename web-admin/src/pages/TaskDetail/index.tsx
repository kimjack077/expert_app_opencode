import { useState, useEffect, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Descriptions, Tag, Button, Progress, Table, message, Space, Tooltip, Input, Modal } from 'antd'
import {
  ArrowLeftOutlined,
  EditOutlined,
  FolderFilled,
  FileTextOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { taskApi, templateApi } from '@/services/api'
import { formatRemarksForDisplay } from '@/utils/display'
import dayjs from 'dayjs'

const PASS_RESULTS = new Set(['compliant', 'pass', 'qualified', '1'])
const FAIL_RESULTS = new Set(['non_compliant', 'fail', 'unqualified', '3', 'pending_rectification'])
const NA_RESULTS = new Set(['not_applicable', 'na', 'n/a', '不适用'])

export default function TaskDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [task, setTask] = useState<any>(null)
  const [records, setRecords] = useState<any[]>([])
  const [treeData, setTreeData] = useState<any[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [expandedKeys, setExpandedKeys] = useState<string[]>([])
  const [noteModalOpen, setNoteModalOpen] = useState(false)
  const [noteSaving, setNoteSaving] = useState(false)
  const [noteForm, setNoteForm] = useState<{
    id?: string
    templateItemId?: string
    title: string
    value: string
  }>({ title: '', value: '' })

  useEffect(() => {
    fetchTaskDetail()
  }, [id])

  // 从模板项与任务检查记录中装配树形表格数据（实现分类上级、层级缩进与醒目分类）
  const buildTreeRecords = (templateItems: any[], taskRecords: any[]) => {
    const recordMap = new Map<string, any>()
    for (const r of taskRecords) {
      const key = r.template_item_id || r.template_item?.id || r.check_item?.id
      if (key) recordMap.set(String(key), r)
      if (r.id) recordMap.set(String(r.id), r)
    }

    const allCategoryKeys: string[] = []

    const processItem = (item: any): any => {
      const hasChildren = item.children && item.children.length > 0
      const isCategory = !!item.is_category || hasChildren
      if (isCategory) {
        const catKey = `cat_${item.id}`
        allCategoryKeys.push(catKey)
        const rawChildren = item.children || []
        const children = rawChildren.map(processItem)

        // 递归统计该分类下的检查项数量与完成状态
        let totalLeaves = 0
        let completedLeaves = 0
        const countLeaves = (node: any) => {
          if (node.is_category) {
            ;(node.children || []).forEach(countLeaves)
          } else {
            totalLeaves++
            if (node.result) completedLeaves++
          }
        }
        children.forEach(countLeaves)

        return {
          id: catKey,
          title: item.title,
          description: item.description,
          clause_no: item.clause_no,
          is_category: true,
          totalLeaves,
          completedLeaves,
          children: children.length > 0 ? children : undefined,
        }
      } else {
        const matched = recordMap.get(String(item.id))
        return {
          id: matched?.id || `item_${item.id}`,
          template_item_id: item.id,
          title: item.title,
          description: item.description,
          clause_no: item.clause_no,
          is_category: false,
          result: matched?.result || '',
          result_text: matched?.result_text || '',
          inspector_note: matched?.inspector_note || '',
        }
      }
    }

    const tree = (templateItems || []).map(processItem)
    return { tree, allCategoryKeys }
  }

  // 无模板树时的降级处理（根据 parent_id 还原树形）
  const buildFallbackTree = (taskRecords: any[]) => {
    const list = (taskRecords || []).map((r) => ({
      ...r,
      title:
        r?.check_item?.title ||
        r?.template_item?.title ||
        r?.item_title ||
        '未命名检查项',
      parent_id: r?.template_item?.parent_id || r?.check_item?.parent_id || null,
      is_category: !!(r?.template_item?.is_category || r?.check_item?.is_category),
    }))

    const idMap = new Map<string, any>()
    list.forEach(item => idMap.set(String(item.template_item_id || item.id), { ...item, children: [] }))

    const roots: any[] = []
    list.forEach(item => {
      const node = idMap.get(String(item.template_item_id || item.id))
      if (item.parent_id && idMap.has(String(item.parent_id))) {
        idMap.get(String(item.parent_id)).children.push(node)
      } else {
        roots.push(node)
      }
    })

    const cleanChildren = (node: any) => {
      if (node.children?.length > 0) {
        node.is_category = true
        node.children.forEach(cleanChildren)
      } else {
        delete node.children
      }
    }
    roots.forEach(cleanChildren)
    return roots
  }

  const fetchTaskDetail = async () => {
    if (!id) return
    setLoading(true)
    try {
      const [taskRes, recordsRes, summaryRes]: any[] = await Promise.all([
        taskApi.getTask(id),
        taskApi.getTaskRecords(id),
        taskApi.getTaskSummary(id),
      ])

      const taskData = taskRes.data
      const recordsData = recordsRes.data || []
      setTask(taskData)
      setRecords(recordsData)
      setSummary(summaryRes.data)

      // 关联模板构建层级分类树
      if (taskData?.template_id) {
        try {
          const tplRes: any = await templateApi.getTemplate(taskData.template_id)
          if (tplRes.data?.items && tplRes.data.items.length > 0) {
            const { tree, allCategoryKeys } = buildTreeRecords(tplRes.data.items, recordsData)
            setTreeData(tree)
            setExpandedKeys(allCategoryKeys)
          } else {
            setTreeData(buildFallbackTree(recordsData))
          }
        } catch (e) {
          console.warn('获取模板树失败，降级为常规列表展示', e)
          setTreeData(buildFallbackTree(recordsData))
        }
      } else {
        setTreeData(buildFallbackTree(recordsData))
      }
    } catch (error) {
      console.error('Failed to fetch task detail:', error)
      message.error('获取任务详情失败')
    } finally {
      setLoading(false)
    }
  }

  // Web 端补录专家备注 / 审核说明（与 H5 填报写入同一字段 inspector_note）
  const openNoteEditor = (record: any) => {
    setNoteForm({
      id: record.id,
      templateItemId: record.template_item_id,
      title: record.title,
      value: record.inspector_note || '',
    })
    setNoteModalOpen(true)
  }

  const handleSaveNote = async () => {
    if (!id) return
    setNoteSaving(true)
    try {
      const persisted = noteForm.id && !String(noteForm.id).startsWith('item_')
      if (persisted) {
        await taskApi.updateRecord(noteForm.id as string, {
          inspector_note: noteForm.value,
        })
      } else if (noteForm.templateItemId) {
        await taskApi.createRecord(id, {
          template_item_id: noteForm.templateItemId,
          inspector_note: noteForm.value,
        })
      }
      message.success('备注已保存')
      setNoteModalOpen(false)
      fetchTaskDetail()
    } catch (error) {
      message.error('保存备注失败')
    } finally {
      setNoteSaving(false)
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
      na: { color: 'default', text: '不适用' },
    }
    const item = resultMap[result] || { color: 'default', text: result || '未评定' }
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

  // 提取所有分类节点 Key，支持一键全部展开/折叠
  const allCategoryKeys = useMemo(() => {
    const keys: string[] = []
    const collectKeys = (nodes: any[]) => {
      for (const node of nodes) {
        if (node.is_category) {
          keys.push(node.id)
          if (node.children?.length) {
            collectKeys(node.children)
          }
        }
      }
    }
    collectKeys(treeData)
    return keys
  }, [treeData])

  const isAllExpanded = allCategoryKeys.length > 0 && expandedKeys.length >= allCategoryKeys.length

  const handleToggleExpandAll = () => {
    if (isAllExpanded) {
      setExpandedKeys([])
    } else {
      setExpandedKeys([...allCategoryKeys])
    }
  }

  const columns = [
    {
      title: '检查项 / 分类目录',
      key: 'title',
      render: (_: any, record: any) => {
        if (record.is_category) {
          return (
            <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, padding: '4px 0' }}>
              <FolderFilled style={{ color: '#1677ff', fontSize: 16 }} />
              <span style={{ fontWeight: 700, fontSize: 15, color: '#0f172a' }}>
                {record.title}
              </span>
              <Tag color="blue" style={{ borderRadius: 4, fontWeight: 500, margin: 0 }}>
                大类分类
              </Tag>
              {record.description && (
                <span style={{ color: '#64748b', fontSize: 13, fontStyle: 'italic' }}>
                  （{record.description}）
                </span>
              )}
            </div>
          )
        }
        return (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '2px 0' }}>
            <FileTextOutlined style={{ color: '#94a3b8', marginTop: 4, flexShrink: 0 }} />
            <div>
              <span style={{ color: '#1e293b', fontSize: 14, lineHeight: '1.6' }}>
                {record.title}
              </span>
              {record.clause_no && (
                <Tag color="cyan" style={{ marginLeft: 8, borderRadius: 2 }}>
                  条款 {record.clause_no}
                </Tag>
              )}
            </div>
          </div>
        )
      },
    },
    {
      title: '结果',
      dataIndex: 'result',
      key: 'result',
      width: 140,
      render: (result: string, record: any) => {
        if (record.is_category) {
          const total = record.totalLeaves || 0
          const done = record.completedLeaves || 0
          return (
            <Tag
              style={{
                borderRadius: 12,
                background: '#e2e8f0',
                borderColor: 'transparent',
                color: '#334155',
                fontWeight: 600,
                padding: '2px 10px',
              }}
            >
              共 {total} 项 {done > 0 ? `(${done}已评)` : ''}
            </Tag>
          )
        }
        return getResultTag(result)
      },
    },
    {
      title: '审核记录 / 说明',
      key: 'note',
      ellipsis: true,
      render: (_: any, record: any) => {
        if (record.is_category) return null
        const text = record.result_text || record.inspector_note
        return (
          <Space size={8}>
            <span style={{ color: text ? '#1e293b' : '#94a3b8' }}>{text || '暂无'}</span>
            <Button size="small" type="link" style={{ padding: 0 }} onClick={() => openNoteEditor(record)}>
              编辑备注
            </Button>
          </Space>
        )
      },
    },
  ]

  // 前端兜底统计（兼容后端旧版本）
  const localStats = (() => {
    const list = (records || []).filter(
      (r) => !(r.template_item?.is_category || r.check_item?.is_category)
    )
    const total = list.length
    const completed = list.filter((r) => r.result).length
    const compliant = list.filter((r) => PASS_RESULTS.has(r.result)).length
    const non_compliant = list.filter((r) => FAIL_RESULTS.has(r.result)).length
    const not_applicable = list.filter((r) => NA_RESULTS.has(r.result)).length
    const evaluated = compliant + non_compliant
    const compliance_rate = evaluated > 0 ? Math.round((compliant / evaluated) * 10000) / 100 : 0
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

  // 三色占比条的分段：合格 / 不合格 / 不适用 / 未填写，四者相加等于总检查项
  const progressSegments = (() => {
    const total = stats.total || 0
    if (total <= 0) return []
    const notFilled = Math.max(total - (stats.completed || 0), 0)
    return [
      { key: 'compliant', label: '合格', value: stats.compliant || 0, color: '#52c41a' },
      { key: 'non_compliant', label: '不合格', value: stats.non_compliant || 0, color: '#ff4d4f' },
      { key: 'not_applicable', label: '不适用', value: stats.not_applicable || 0, color: '#bfbfbf' },
      { key: 'not_filled', label: '未填写', value: notFilled, color: '#e2e8f0' },
    ].filter((seg) => seg.value > 0)
  })()

  return (
    <div>
      <style>{`
        /* 分类行突出高亮与类别明显化 */
        .task-record-category-row {
          background-color: #f1f5f9 !important;
          border-top: 1px solid #cbd5e1 !important;
          border-bottom: 1px solid #cbd5e1 !important;
        }
        .task-record-category-row > td {
          background-color: #f1f5f9 !important;
          padding-top: 13px !important;
          padding-bottom: 13px !important;
        }
        .task-record-category-row:hover > td {
          background-color: #e2e8f0 !important;
        }
        .task-record-item-row > td {
          background-color: #ffffff !important;
          padding-top: 11px !important;
          padding-bottom: 11px !important;
        }
        .task-record-item-row:hover > td {
          background-color: #f8fafc !important;
        }
      `}</style>

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
                  {formatRemarksForDisplay(task.remarks)}
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>

          <Card title="检查进度" style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 32, flexWrap: 'wrap' }}>
              <div style={{ flex: '0 0 160px', textAlign: 'center' }}>
                {/* 进度圈只表达「完成度」，用中性蓝而非绿色：
                    绿色在检查场景里代表「通过」，和可能只有 50% 的合规率互相矛盾。 */}
                <Progress
                  type="circle"
                  percent={
                    stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0
                  }
                  strokeColor={{ '0%': '#60a5fa', '100%': '#2563eb' }}
                  format={() => (
                    <span style={{ fontSize: 16 }}>
                      {stats.completed}/{stats.total}
                      <div style={{ fontSize: 11, color: '#64748b', fontWeight: 400 }}>
                        完成率
                      </div>
                    </span>
                  )}
                />
              </div>
              <div style={{ flex: 1, minWidth: 320 }}>
                {/* 三色占比条：同时呈现合格 / 不合格 / 不适用 / 未填的构成与比例 */}
                <div
                  style={{
                    display: 'flex',
                    height: 12,
                    borderRadius: 6,
                    overflow: 'hidden',
                    background: '#f1f5f9',
                  }}
                >
                  {progressSegments.map((seg) => (
                    <div
                      key={seg.key}
                      title={`${seg.label} ${seg.value} 项`}
                      style={{
                        width: `${(seg.value / (stats.total || 1)) * 100}%`,
                        background: seg.color,
                      }}
                    />
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 12 }}>
                  {progressSegments.map((seg) => (
                    <span key={seg.key} style={{ fontSize: 13, color: '#475569' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          width: 8,
                          height: 8,
                          borderRadius: 2,
                          background: seg.color,
                          marginRight: 6,
                        }}
                      />
                      {seg.label} <strong>{seg.value}</strong> 项
                    </span>
                  ))}
                </div>
                <div style={{ marginTop: 12, fontSize: 13, color: '#475569' }}>
                  <strong>合规率 {stats.compliance_rate}%</strong>
                  <span style={{ color: '#94a3b8', marginLeft: 8 }}>
                    （口径：合格 ÷ 已判定项，不含不适用）
                  </span>
                </div>
              </div>
            </div>
          </Card>

          <Card
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>检查记录</span>
                {allCategoryKeys.length > 0 && (
                  <Tag color="cyan" style={{ borderRadius: 10, fontSize: 12 }}>
                    已按分类层级呈现
                  </Tag>
                )}
              </div>
            }
            style={{ marginTop: 16 }}
            extra={
              <Space>
                {allCategoryKeys.length > 0 && (
                  <Button
                    size="small"
                    icon={isAllExpanded ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
                    onClick={handleToggleExpandAll}
                  >
                    {isAllExpanded ? '折叠分类' : '展开全部'}
                  </Button>
                )}
                {task.status === 'in_progress' && (
                  <Button type="primary" onClick={handleComplete}>
                    完成任务
                  </Button>
                )}
              </Space>
            }
          >
            <Table
              dataSource={treeData.length > 0 ? treeData : records}
              columns={columns}
              rowKey="id"
              loading={loading}
              scroll={{ x: 800 }}
              pagination={false}
              expandable={{
                expandedRowKeys: expandedKeys,
                onExpandedRowsChange: (keys) => setExpandedKeys(keys as string[]),
                indentSize: 32,
              }}
              rowClassName={(record) =>
                record.is_category ? 'task-record-category-row' : 'task-record-item-row'
              }
              locale={{ emptyText: '暂无检查项记录' }}
            />
          </Card>
        </>
      )}

      <Modal
        title={noteForm.title ? `编辑备注：${noteForm.title}` : '编辑备注'}
        open={noteModalOpen}
        onOk={handleSaveNote}
        confirmLoading={noteSaving}
        onCancel={() => setNoteModalOpen(false)}
        okText="保存"
        cancelText="取消"
      >
        <Input.TextArea
          rows={4}
          value={noteForm.value}
          onChange={(e) => setNoteForm((prev) => ({ ...prev, value: e.target.value }))}
          placeholder="请输入专家备注 / 审核说明..."
        />
      </Modal>
    </div>
  )
}
