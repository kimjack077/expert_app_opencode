import { useState, useEffect, useMemo } from 'react'
import { Table, Tag, Button, Space, message, Empty, Tabs, Radio, Card, Typography, Tooltip } from 'antd'
import {
  EyeOutlined, EditOutlined, FileTextOutlined, CheckCircleOutlined,
  HistoryOutlined, BranchesOutlined, AppstoreOutlined, UnorderedListOutlined
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { auditRecordApi, auditPlanApi } from '@/services/auditProjectApi'
import dayjs from 'dayjs'
import type { TabsProps } from 'antd'

interface Props {
  projectId: string
}

export default function RecordsList({ projectId }: Props) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState<any[]>([])
  const [planItems, setPlanItems] = useState<any[]>([])
  const [versionView, setVersionView] = useState<'latest' | 'all'>('latest')

  useEffect(() => {
    fetchData()
  }, [projectId])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [recordsRes, planItemsRes] = await Promise.all([
        auditRecordApi.list(projectId),
        auditPlanApi.list(projectId),
      ])
      setRecords(recordsRes.data || [])
      const itemsWithTasks = (planItemsRes.data || []).filter(
        (item: any) => item.inspection_task_id
      )
      setPlanItems(itemsWithTasks)
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取审核记录失败')
    } finally {
      setLoading(false)
    }
  }

  const handleViewTask = (taskId: string) => {
    navigate(`/inspection/${taskId}`)
  }

  const handleEditRecord = (recordId: string) => {
    navigate(`/audit-projects/${projectId}/records/${recordId}`)
  }

  const handleViewRecord = (recordId: string) => {
    navigate(`/audit-projects/${projectId}/records/${recordId}?mode=view`)
  }

  const handleViewPlanRecord = (planItem: any) => {
    const matchingRecord = records.find((record) => (
      record.plan_item_id === planItem.id || record.plan_item?.id === planItem.id
    ))

    if (!matchingRecord) {
      message.warning('未找到该检查任务对应的审核记录')
      return
    }

    handleViewRecord(matchingRecord.id)
  }

  // 1. 按关联计划项/任务将审核记录归集分组，明确当前最新有效版本与历史版本传承
  const { latestRecords, allProcessedRecords } = useMemo(() => {
    const planMap = new Map<string, any>()
    for (const p of planItems) {
      planMap.set(p.id, p)
    }

    const groups = new Map<string, any[]>()
    for (const r of records) {
      const key = r.plan_item_id || r.plan_item?.id || r.area_id || r.area_name || 'other'
      if (!groups.has(key)) {
        groups.set(key, [])
      }
      groups.get(key)!.push(r)
    }

    const latestList: any[] = []
    const allList: any[] = []

    groups.forEach((groupRecords) => {
      // 升序排列：最早的是 V1，最新的是 Vn
      const sorted = [...groupRecords].sort((a, b) => (
        new Date(a.created_at || a.audit_date).getTime() - new Date(b.created_at || b.audit_date).getTime()
      ))
      const totalInGroup = sorted.length

      sorted.forEach((rec, index) => {
        const isLatest = index === totalInGroup - 1
        const versionNo = `V${index + 1}`
        const matchedPlan = rec.plan_item_id ? planMap.get(rec.plan_item_id) : (rec.plan_item || null)

        const processed = {
          ...rec,
          is_latest: isLatest,
          version_no: versionNo,
          version_index: index + 1,
          total_versions: totalInGroup,
          matched_plan: matchedPlan,
          area_display: rec.area_name || matchedPlan?.area_name || '未指定区域',
          schedule_display: matchedPlan?.plan_date
            ? `${matchedPlan.plan_date} ${matchedPlan.time_start || ''}-${matchedPlan.time_end || ''}`
            : (rec.audit_date || '-'),
        }

        allList.unshift(processed)
      })

      // 取最新的有效记录，挂载历史版本
      const latestOne = sorted[totalInGroup - 1]
      const historyList = sorted.slice(0, totalInGroup - 1).reverse().map((h, hIdx) => {
        const vIdx = totalInGroup - 1 - hIdx
        return {
          ...h,
          is_latest: false,
          version_no: `V${vIdx}`,
          history_index: vIdx,
          area_display: h.area_name || (h.plan_item_id ? planMap.get(h.plan_item_id)?.area_name : '未指定区域'),
        }
      })

      const matchedPlan = latestOne.plan_item_id ? planMap.get(latestOne.plan_item_id) : (latestOne.plan_item || null)
      latestList.push({
        ...latestOne,
        is_latest: true,
        version_no: `V${totalInGroup}`,
        total_versions: totalInGroup,
        history_list: historyList,
        matched_plan: matchedPlan,
        area_display: latestOne.area_name || matchedPlan?.area_name || '未指定区域',
        schedule_display: matchedPlan?.plan_date
          ? `${matchedPlan.plan_date} ${matchedPlan.time_start || ''}-${matchedPlan.time_end || ''}`
          : (latestOne.audit_date || '-'),
      })
    })

    latestList.sort((a, b) => (
      new Date(b.created_at || b.audit_date).getTime() - new Date(a.created_at || a.audit_date).getTime()
    ))

    return { latestRecords: latestList, allProcessedRecords: allList }
  }, [records, planItems])

  // 检查任务表格（审核排期与任务维度）
  const inspectionTaskColumns = [
    { title: '审核区域 / 部门', dataIndex: 'area_name', key: 'area_name', width: 160 },
    {
      title: '计划日期与时间',
      key: 'plan_schedule',
      width: 180,
      render: (_: any, r: any) => (
        <span>
          {r.plan_date ? dayjs(r.plan_date).format('YYYY-MM-DD') : '-'}
          {r.time_start && r.time_end ? ` (${r.time_start}-${r.time_end})` : ''}
        </span>
      ),
    },
    { title: '工作组', dataIndex: 'group_no', key: 'group_no', width: 90, render: (g: any) => g ? `第 ${g} 组` : '-' },
    {
      title: '任务状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          pending: 'default',
          in_progress: 'processing',
          completed: 'success',
        }
        const textMap: Record<string, string> = {
          pending: '待开始',
          in_progress: '进行中',
          completed: '已完成',
        }
        return <Tag color={colorMap[status]}>{textMap[status] || status}</Tag>
      }
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: any, record: any) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={record.status === 'completed' ? <EyeOutlined /> : <EditOutlined />}
            onClick={() => record.status === 'completed'
              ? handleViewPlanRecord(record)
              : handleViewTask(record.inspection_task_id)
            }
          >
            {record.status === 'completed' ? '查看记录' : '执行检查'}
          </Button>
          {record.status === 'completed' && (
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleViewTask(record.inspection_task_id)}
            >
              重新检查
            </Button>
          )}
        </Space>
      ),
    },
  ]

  // 最新有效正式审核记录表格列
  const latestAuditRecordColumns = [
    {
      title: '关联审核任务',
      key: 'task_info',
      width: 220,
      render: (_: any, record: any) => (
        <div>
          <div style={{ fontWeight: 600, color: '#0f172a', fontSize: 13 }}>
            {record.area_display}
          </div>
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
            {record.schedule_display}
            {record.matched_plan?.group_no ? ` · 第 ${record.matched_plan.group_no} 组` : ''}
          </div>
        </div>
      ),
    },
    {
      title: '当前记录编号',
      dataIndex: 'record_no',
      key: 'record_no',
      width: 150,
      render: (no: string) => <span style={{ fontFamily: 'monospace', fontWeight: 500 }}>{no || '-'}</span>,
    },
    {
      title: '版本状态',
      key: 'version_info',
      width: 180,
      render: (_: any, record: any) => (
        <Space direction="vertical" size={2}>
          <Tag color="success" style={{ fontWeight: 600 }}>
            当前有效版本 ({record.version_no})
          </Tag>
          {record.total_versions > 1 && (
            <span style={{ fontSize: 11, color: '#64748b' }}>
              <HistoryOutlined style={{ marginRight: 4 }} />
              含 {record.total_versions - 1} 个历史版本（点左侧展开查看）
            </span>
          )}
        </Space>
      ),
    },
    {
      title: '检查项评定',
      key: 'items_summary',
      width: 180,
      render: (_: any, record: any) => {
        const count = record.items_count || (record.items ? record.items.length : 0)
        return (
          <Space size={4} wrap>
            <Tag color="blue">{count} 项已完成</Tag>
            {record.pass_count > 0 && <Tag color="green">{record.pass_count} 符合</Tag>}
            {record.fail_count > 0 && <Tag color="error">{record.fail_count} 不符合</Tag>}
          </Space>
        )
      },
    },
    {
      title: '区域审核结论',
      dataIndex: 'conclusion',
      key: 'conclusion',
      ellipsis: true,
      render: (c: string) => (
        <span style={{ color: c ? '#1e293b' : '#94a3b8', fontSize: 12 }}>
          {c || '未填写审核结论'}
        </span>
      ),
    },
    {
      title: '最后提交时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (t: string) => t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => {
        const map: Record<string, { color: string; text: string }> = {
          draft: { color: 'default', text: '草稿' },
          submitted: { color: 'processing', text: '已提交' },
          reviewed: { color: 'success', text: '已审核' },
        }
        const info = map[status] || { color: 'default', text: status }
        return <Tag color={info.color}>{info.text}</Tag>
      }
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: any) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewRecord(record.id)}
          >
            查看最新
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditRecord(record.id)}
          >
            编辑
          </Button>
        </Space>
      ),
    },
  ]

  // 全量明细表格列（扁平展示全部历史）
  const allAuditRecordColumns = [
    {
      title: '关联审核任务',
      key: 'task_info',
      width: 180,
      render: (_: any, record: any) => (
        <div>
          <div style={{ fontWeight: 600, color: '#0f172a' }}>{record.area_display}</div>
          <div style={{ fontSize: 12, color: '#64748b' }}>{record.schedule_display}</div>
        </div>
      ),
    },
    {
      title: '记录编号',
      dataIndex: 'record_no',
      key: 'record_no',
      width: 140,
      render: (no: string) => <span style={{ fontFamily: 'monospace' }}>{no || '-'}</span>,
    },
    {
      title: '版本类型',
      key: 'version_tag',
      width: 140,
      render: (_: any, record: any) => (
        record.is_latest ? (
          <Tag color="success" style={{ fontWeight: 600 }}>当前最新 ({record.version_no})</Tag>
        ) : (
          <Tag color="default">历史版本 ({record.version_no})</Tag>
        )
      ),
    },
    {
      title: '检查项评定',
      key: 'items_summary',
      width: 160,
      render: (_: any, record: any) => {
        const count = record.items_count || (record.items ? record.items.length : 0)
        return (
          <Space size={4} wrap>
            <Tag color="blue">{count} 项</Tag>
            {record.pass_count > 0 && <Tag color="green">{record.pass_count} 符合</Tag>}
            {record.fail_count > 0 && <Tag color="error">{record.fail_count} 不符合</Tag>}
          </Space>
        )
      },
    },
    {
      title: '审核结论',
      dataIndex: 'conclusion',
      key: 'conclusion',
      ellipsis: true,
      render: (c: string) => c || '-',
    },
    {
      title: '提交时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (t: string) => t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => {
        const map: Record<string, { color: string; text: string }> = {
          draft: { color: 'default', text: '草稿' },
          submitted: { color: 'processing', text: '已提交' },
          reviewed: { color: 'success', text: '已审核' },
        }
        const info = map[status] || { color: 'default', text: status }
        return <Tag color={info.color}>{info.text}</Tag>
      }
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: any) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => handleViewRecord(record.id)}
        >
          查看
        </Button>
      ),
    },
  ]

  // 展开行：展示该审核任务的历史版本记录
  const expandedHistoryRender = (record: any) => {
    const historyList = record.history_list || []
    if (!historyList.length) return null

    const historyColumns = [
      {
        title: '版本号',
        dataIndex: 'version_no',
        key: 'version_no',
        width: 100,
        render: (v: string) => <Tag color="default">{v} 历史版本</Tag>,
      },
      {
        title: '历史记录编号',
        dataIndex: 'record_no',
        key: 'record_no',
        width: 150,
        render: (no: string) => <span style={{ fontFamily: 'monospace' }}>{no}</span>,
      },
      {
        title: '提交归档时间',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 160,
        render: (t: string) => t ? dayjs(t).format('YYYY-MM-DD HH:mm:ss') : '-',
      },
      {
        title: '历史检查项数',
        key: 'history_items',
        width: 180,
        render: (_: any, h: any) => {
          const count = h.items_count || (h.items ? h.items.length : 0)
          return (
            <Space size={4}>
              <Tag color="blue">{count} 项</Tag>
              {h.pass_count > 0 && <Tag color="green">{h.pass_count} 符合</Tag>}
              {h.fail_count > 0 && <Tag color="error">{h.fail_count} 不符合</Tag>}
            </Space>
          )
        },
      },
      {
        title: '历史结论',
        dataIndex: 'conclusion',
        key: 'conclusion',
        ellipsis: true,
        render: (c: string) => c || '-',
      },
      {
        title: '操作',
        key: 'action',
        width: 120,
        render: (_: any, h: any) => (
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewRecord(h.id)}
          >
            查看此版本
          </Button>
        ),
      },
    ]

    return (
      <div style={{ margin: '8px 0 8px 30px', padding: '12px 16px', background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0' }}>
        <div style={{ marginBottom: 8, fontSize: 13, fontWeight: 600, color: '#475569', display: 'flex', alignItems: 'center', gap: 6 }}>
          <HistoryOutlined style={{ color: '#0284c7' }} />
          <span>「{record.area_display}」的历史审核版本列表（共 {historyList.length} 个历史版本）</span>
        </div>
        <Table
          columns={historyColumns}
          dataSource={historyList}
          rowKey="id"
          pagination={false}
          size="small"
        />
      </div>
    )
  }

  const hasAnyRecords = records.length > 0 || planItems.length > 0

  if (!hasAnyRecords && !loading) {
    return (
      <Empty
        description="暂无审核记录"
        style={{ padding: '40px 0' }}
      >
        <span style={{ color: '#999', fontSize: 13 }}>
          请先在"审核计划"中添加计划项，然后执行检查任务
        </span>
      </Empty>
    )
  }

  const tabItems: TabsProps['items'] = [
    {
      key: 'inspection_tasks',
      label: (
        <span>
          <FileTextOutlined style={{ marginRight: 8 }} />
          检查任务记录 ({planItems.length})
        </span>
      ),
      children: (
        <Table
          columns={inspectionTaskColumns}
          dataSource={planItems}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{ emptyText: '暂无检查任务' }}
        />
      ),
    },
  ]

  if (records.length > 0) {
    tabItems.push({
      key: 'audit_records',
      label: (
        <span>
          <CheckCircleOutlined style={{ marginRight: 8 }} />
          正式审核记录 ({latestRecords.length} 项任务有效记录 · 共 {records.length} 份记录单)
        </span>
      ),
      children: (
        <div>
          {/* 版本视图切换控制器 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, padding: '8px 12px', background: '#f8fafc', borderRadius: 6 }}>
            <span style={{ fontSize: 13, color: '#475569' }}>
              <strong>记录视图：</strong>
              {versionView === 'latest'
                ? `当前按审核任务展示最新有效版本（共 ${latestRecords.length} 个审核任务），展开可查看历史版本`
                : `展示全部历史填报记录单明细（共 ${records.length} 份记录单）`}
            </span>
            <Radio.Group
              value={versionView}
              onChange={(e) => setVersionView(e.target.value)}
              size="small"
              buttonStyle="solid"
            >
              <Radio.Button value="latest">
                <AppstoreOutlined style={{ marginRight: 4 }} />
                按任务聚合最新有效版本 ({latestRecords.length})
              </Radio.Button>
              <Radio.Button value="all">
                <UnorderedListOutlined style={{ marginRight: 4 }} />
                全部历史记录明细 ({records.length})
              </Radio.Button>
            </Radio.Group>
          </div>

          {versionView === 'latest' ? (
            <Table
              columns={latestAuditRecordColumns}
              dataSource={latestRecords}
              rowKey="id"
              loading={loading}
              pagination={false}
              expandable={{
                expandedRowRender: expandedHistoryRender,
                rowExpandable: (r) => (r.history_list && r.history_list.length > 0),
              }}
            />
          ) : (
            <Table
              columns={allAuditRecordColumns}
              dataSource={allProcessedRecords}
              rowKey="id"
              loading={loading}
              pagination={{ pageSize: 15 }}
            />
          )}
        </div>
      ),
    })
  }

  return <Tabs items={tabItems} defaultActiveKey="audit_records" />
}
