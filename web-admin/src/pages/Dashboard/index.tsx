import { useState, useEffect, useMemo } from 'react'
import { Row, Col, Card, Progress, Table, Tag, Space, Button, DatePicker, Tooltip, message } from 'antd'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  UserOutlined,
  FileTextOutlined,
  BankOutlined,
  ArrowRightOutlined,
  RiseOutlined,
  SafetyCertificateOutlined,
  DownloadOutlined,
  CalendarOutlined,
  AppstoreOutlined,
  AuditOutlined,
  ScheduleOutlined,
  BookOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { analyticsApi, taskApi, statisticsApi } from '@/services/api'
import { useNavigate } from 'react-router-dom'
import { formatTaskDisplay, taskStatusLabel } from '@/utils/display'
import { useAuthStore } from '@/stores/auth'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

export default function Dashboard() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [stats, setStats] = useState<any>(null)
  /** 审核项目概览（与「审核项目」列表同源，保证卡片数字与跳转后的列表条数一致） */
  const [projectOverview, setProjectOverview] = useState<any>(null)
  const [recentTasks, setRecentTasks] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [trends, setTrends] = useState<any>(null)
  const [enterpriseRisk, setEnterpriseRisk] = useState<any>(null)
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(30, 'days'),
    dayjs(),
  ])

  useEffect(() => {
    fetchData()
  }, [])

  useEffect(() => {
    if (dateRange[0] && dateRange[1]) {
      fetchTrends()
    }
  }, [dateRange])

  const fetchData = async () => {
    try {
      const [dashboardRes, tasksRes, riskRes, overviewRes]: any[] = await Promise.all([
        analyticsApi.getDashboard(),
        taskApi.getTasks({ limit: 8 }),
        analyticsApi.getEnterpriseRisk(),
        statisticsApi.getOverview(),
      ])
      setStats(dashboardRes.data)
      setRecentTasks(tasksRes.data.items || [])
      setEnterpriseRisk(riskRes.data)
      setProjectOverview(overviewRes.data)
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchTrends = async () => {
    try {
      const res: any = await analyticsApi.getTrends({
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
      })
      setTrends(res.data)
    } catch (error) {
      console.error('Failed to fetch trends:', error)
    }
  }

  const handleExport = async () => {
    try {
      message.loading({ content: '正在导出数据...', key: 'export' })
      const res: any = await analyticsApi.exportData({
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
      })

      const csvContent = generateCSV(res.data.items)
      downloadCSV(csvContent, `检查数据导出_${dayjs().format('YYYY-MM-DD_HHmmss')}.csv`)
      message.success({ content: '数据导出成功', key: 'export' })
    } catch (error) {
      message.error({ content: '导出失败', key: 'export' })
    }
  }

  const generateCSV = (data: any[]) => {
    const headers = ['任务编号', '任务标题', '被检查对象', '状态', '创建时间', '完成时间', '合规项数', '不合规项数']
    const rows = (data || []).map((item) => [
      item.task_no,
      item.title,
      item.target_name,
      // 状态导出为中文，不要直接把 pending / in_progress 这类枚举写进文件
      taskStatusLabel(item.status),
      item.created_at,
      item.completed_at,
      item.compliant_items,
      item.non_compliant_items,
    ])
    return [headers, ...rows].map((row) => row.join(',')).join('\n')
  }

  const downloadCSV = (content: string, filename: string) => {
    const BOM = '\uFEFF'
    const blob = new Blob([BOM + content], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = filename
    link.click()
    URL.revokeObjectURL(link.href)
  }

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      pending: { color: 'default', text: '待开始' },
      in_progress: { color: 'processing', text: '进行中' },
      completed: { color: 'success', text: '已完成' },
      cancelled: { color: 'error', text: '已取消' },
    }
    const item = statusMap[status] || { color: 'default', text: status }
    return <Tag color={item.color} style={{ margin: 0 }}>{item.text}</Tag>
  }

  const columns = [
    {
      title: '任务名称',
      key: 'display',
      render: (_: any, record: any) => {
        const d = formatTaskDisplay(record)
        return (
          <div style={{ lineHeight: 1.3 }}>
            <div style={{ fontWeight: 600, color: '#1e293b', fontSize: 13 }}>{d.primary}</div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 1 }}>{d.secondary || record.task_no}</div>
          </div>
        )
      },
    },
    {
      title: '受审对象',
      dataIndex: 'target_name',
      key: 'target_name',
      width: 140,
      ellipsis: true,
      render: (v: string) => (
        <span style={{ fontSize: 12, color: '#475569' }}>{v || '-'}</span>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 120,
      render: (date: string) => (
        <span style={{ fontSize: 11, color: '#64748b' }}>
          {dayjs(date).format('MM-DD HH:mm')}
        </span>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 70,
      render: (_: any, record: any) => (
        <Button
          type="link"
          size="small"
          style={{ padding: 0, height: 'auto', fontSize: 12 }}
          onClick={(e) => {
            e.stopPropagation()
            navigate(record.status === 'completed' ? `/tasks/${record.id}` : `/inspection/${record.id}`)
          }}
        >
          {record.status === 'completed' ? '查看' : record.status === 'pending' ? '开始' : '继续'}
        </Button>
      ),
    },
  ]

  const inProgressTasks = stats?.tasks?.in_progress || 0
  const pendingTasks = stats?.tasks?.pending || 0
  const pendingCount = inProgressTasks + pendingTasks
  const complianceRate = stats?.inspections?.compliance_rate || 0
  const compliantItems = stats?.inspections?.compliant || 0
  const nonCompliantItems = stats?.inspections?.non_compliant || 0
  const notApplicableItems = stats?.inspections?.not_applicable || 0
  const observeItems = stats?.inspections?.observe || 0
  const filledItems = stats?.inspections?.filled || 0
  const notFilledItems = stats?.inspections?.not_filled || 0
  const totalItems = stats?.inspections?.total || 0

  // 合规率口径（全站唯一）：合格 ÷（总检查项 − 不适用项）。
  // 注意分母**包含未填报项**——后端 analytics / item_stats.compliance_rate 同式。
  // 此前页面文案写成「已填报合格项 / 已填报项」，与 50.59% 的实际取值互相矛盾，
  // 且与趋势图（旧式：合格 ÷(合格+不合格)）给出同一屏两个数字。
  const COMPLIANCE_FORMULA = '合格 ÷（总检查项 − 不适用项）'
  // 把分母直接算出来展示，避免副标题只给「已填报 N 项」时读者自己拿它当分母，
  // 算出与主数字不同的比例（实测 46÷70=65.7% vs 主数字 52.87%）。
  const complianceDenominator = Math.max(totalItems - notApplicableItems, 0)

  // 趋势图展示区间跟随日期筛选，不再固定截断 14 天
  const trendDays = Math.max(dateRange[1].diff(dateRange[0], 'day') + 1, 1)

  // 审核项目概览：口径与「审核项目」列表完全一致（均排除软删除项目）
  const projectTotal = projectOverview?.total || 0
  const projectInProgress = projectOverview?.in_progress || 0
  const projectCompleted = projectOverview?.completed || 0
  const projectThisMonth = projectOverview?.this_month || 0
  const projectCompletionRate =
    projectTotal > 0 ? Math.round((projectCompleted / projectTotal) * 100) : 0

  const highRisk = enterpriseRisk?.high || 0
  const mediumRisk = enterpriseRisk?.medium || 0
  const lowRisk = enterpriseRisk?.low || 0
  const totalRiskEnterprises = highRisk + mediumRisk + lowRisk || 1

  const maxInspectionCount = trends?.inspection_trend
    ? Math.max(...trends.inspection_trend.map((t: any) => t.count), 1)
    : 1
  const maxComplianceRate = 100

  return (
    <div className="dashboard-container">
      {/* 1. Light Modern Filter Header Bar */}
      <div className="dashboard-header-bar">
        <div className="dashboard-header-left">
          <h1 className="dashboard-header-title">
            工作台
          </h1>
          <div className="dashboard-header-desc">
            全生命周期协同 · 优先处理待办事项（合规率口径 = {COMPLIANCE_FORMULA}）
          </div>
        </div>

        <div className="dashboard-header-actions">
          <Space size={6}>
            <Button
              size="small"
              onClick={() => setDateRange([dayjs().subtract(7, 'days'), dayjs()])}
            >
              近7天
            </Button>
            <Button
              size="small"
              onClick={() => setDateRange([dayjs().subtract(30, 'days'), dayjs()])}
            >
              近30天
            </Button>
            <RangePicker
              value={dateRange}
              size="small"
              onChange={(dates) => dates && setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
              allowClear={false}
              placeholder={['开始日期', '结束日期']}
              style={{ width: 210 }}
            />
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={handleExport}
            >
              导出数据
            </Button>
            <Button
              size="small"
              type="primary"
              icon={<RiseOutlined />}
              onClick={() => navigate('/analytics')}
            >
              数据分析
            </Button>
          </Space>
        </div>
      </div>

      {/* 2. Unified High-Density KPI Layer (1 Row, 4 Columns) */}
      <Row gutter={[10, 10]}>
        {/* Metric 1: Pending & Active Tasks */}
        <Col xs={24} sm={12} lg={6}>
          <div
            className="dashboard-kpi-card"
            onClick={() => navigate('/tasks?status=in_progress')}
          >
            <div>
              <div className="dashboard-kpi-header">
                <span className="dashboard-kpi-title">日常检查任务待办</span>
                <div className="dashboard-kpi-icon" style={{ background: '#e0f2fe', color: '#0284c7' }}>
                  <ClockCircleOutlined />
                </div>
              </div>
              <div className="dashboard-kpi-body">
                <span className="dashboard-kpi-value" style={{ color: '#0369a1' }}>
                  {pendingCount}
                </span>
                <Tag color={pendingCount > 0 ? 'processing' : 'default'} style={{ margin: 0, fontSize: 11 }}>
                  {pendingCount > 0 ? '待推进' : '全部就绪'}
                </Tag>
              </div>
            </div>
            <div className="dashboard-kpi-footer">
              <span>进行中 {stats?.tasks?.in_progress || 0} · 待开始 {stats?.tasks?.pending || 0}</span>
              <span style={{ color: '#0284c7', fontWeight: 600 }}>去处理 →</span>
            </div>
          </div>
        </Col>

        {/* Metric 2: Audit Projects & Completion
            数据源与「审核项目」列表一致（statisticsApi.getOverview，均排除软删除项目），
            否则会出现「卡片 27 条、点进去只有 10 条」的口径错位。 */}
        <Col xs={24} sm={12} lg={6}>
          <div
            className="dashboard-kpi-card"
            onClick={() => navigate('/audit-projects')}
          >
            <div>
              <div className="dashboard-kpi-header">
                <span className="dashboard-kpi-title">审核项目总览</span>
                <div className="dashboard-kpi-icon" style={{ background: '#ccfbf1', color: '#0d9488' }}>
                  <FileTextOutlined />
                </div>
              </div>
              <div className="dashboard-kpi-body">
                <span className="dashboard-kpi-value" style={{ color: '#0f766e' }}>
                  {projectTotal}
                </span>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: 11, color: '#64748b' }}>完成率 </span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#0d9488' }}>{projectCompletionRate}%</span>
                </div>
              </div>
            </div>
            <div className="dashboard-kpi-footer">
              <span>进行中 {projectInProgress} · 已完成 {projectCompleted} · 本月新增 {projectThisMonth} / 共 {projectTotal} 项</span>
              <span style={{ color: '#0d9488', fontWeight: 600 }}>项目库 →</span>
            </div>
          </div>
        </Col>

        {/* Metric 3: Overall Compliance Rate
            口径为「日常检查检查项」，跳转目标因此对齐到日常检查任务列表，
            不再跳到检查记录（那是另一套数据集，数量必然对不上）。 */}
        <Col xs={24} sm={12} lg={6}>
          <div
            className="dashboard-kpi-card"
            onClick={() => navigate('/tasks')}
          >
            <div>
              <div className="dashboard-kpi-header">
                <span className="dashboard-kpi-title">综合检查合规率</span>
                <div className="dashboard-kpi-icon" style={{ background: '#dcfce7', color: '#16a34a' }}>
                  <SafetyCertificateOutlined />
                </div>
              </div>
              <div className="dashboard-kpi-body">
                <span className="dashboard-kpi-value" style={{ color: '#15803d' }}>
                  {complianceRate}%
                </span>
                <Tag color={complianceRate >= 80 ? 'success' : complianceRate >= 60 ? 'warning' : 'error'} style={{ margin: 0, fontSize: 11 }}>
                  {complianceRate >= 80 ? '达标' : '预警'}
                </Tag>
              </div>
            </div>
            <div className="dashboard-kpi-footer">
              <span>
                合格 {compliantItems} ÷ 分母 {complianceDenominator} 项
                （总 {totalItems} − 不适用 {notApplicableItems}）
              </span>
              <span style={{ color: '#16a34a', fontWeight: 600 }}>查看任务 →</span>
            </div>
          </div>
        </Col>

        {/* Metric 4: Enterprise Risk Warnings */}
        <Col xs={24} sm={12} lg={6}>
          <div
            className="dashboard-kpi-card"
            onClick={() => navigate('/enterprises')}
          >
            <div>
              <div className="dashboard-kpi-header">
                <span className="dashboard-kpi-title">风险预警企业</span>
                <div className="dashboard-kpi-icon" style={{ background: '#fee2e2', color: '#dc2626' }}>
                  <BankOutlined />
                </div>
              </div>
              <div className="dashboard-kpi-body">
                <span className="dashboard-kpi-value" style={{ color: highRisk > 0 ? '#dc2626' : '#d97706' }}>
                  {highRisk + mediumRisk}
                </span>
                <Space size={4}>
                  {highRisk > 0 && (
                    <Tag color="error" style={{ margin: 0, fontSize: 10, padding: '0 4px' }}>
                      高风险 {highRisk}
                    </Tag>
                  )}
                  {mediumRisk > 0 && (
                    <Tag color="warning" style={{ margin: 0, fontSize: 10, padding: '0 4px' }}>
                      中风险 {mediumRisk}
                    </Tag>
                  )}
                </Space>
              </div>
            </div>
            <div className="dashboard-kpi-footer">
              <span>企业总库 {stats?.enterprises?.total || (highRisk + mediumRisk + lowRisk)} 家</span>
              <span style={{ color: '#dc2626', fontWeight: 600 }}>风险排查 →</span>
            </div>
          </div>
        </Col>
      </Row>

      {/* 3. Dual Column High-Density Workstation */}
      <Row gutter={[10, 10]}>
        {/* Left Column (15/24): Trends + Recent Tasks Table */}
        <Col xs={24} lg={15} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* Trends Monitor */}
          <Card
            className="dashboard-section-card"
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <RiseOutlined style={{ color: 'var(--primary-color)' }} />
                <span>检查与合规趋势态势</span>
              </div>
            }
            extra={
              <span style={{ fontSize: 11, color: '#94a3b8' }}>
                最近 {trendDays} 日走势
              </span>
            } variant="borderless"
            loading={!trends}
          >
            {trends && (
              <Row gutter={16}>
                {/* Left Mini Chart: Inspection Volume */}
                <Col span={12} style={{ borderRight: '1px solid #f1f5f9', paddingRight: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>每日检查频次</span>
                    <span style={{ fontSize: 11, color: '#94a3b8' }}>峰值: {maxInspectionCount} 次</span>
                  </div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'flex-end',
                    height: 100,
                    gap: 3,
                    paddingTop: 8,
                  }}>
                    {trends.inspection_trend.map((item: any, idx: number) => {
                      const pct = (item.count / maxInspectionCount) * 100
                      return (
                        <Tooltip key={idx} title={`${item.date} : 检查 ${item.count} 次`}>
                          <div style={{
                            flex: 1,
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            height: '100%',
                            justifyContent: 'flex-end',
                            cursor: 'pointer',
                          }}>
                            <div style={{
                              width: '100%',
                              height: `${pct}%`,
                              minHeight: item.count > 0 ? 4 : 2,
                              background: 'linear-gradient(180deg, #0284c7 0%, #38bdf8 100%)',
                              borderRadius: '3px 3px 0 0',
                              transition: 'all 0.2s ease',
                            }} />
                            <div style={{
                              fontSize: 9,
                              color: '#94a3b8',
                              marginTop: 3,
                              transform: 'scale(0.85)',
                              whiteSpace: 'nowrap',
                            }}>
                              {item.date.slice(5)}
                            </div>
                          </div>
                        </Tooltip>
                      )
                    })}
                  </div>
                </Col>

                {/* Right Mini Chart: Compliance Rate */}
                <Col span={12} style={{ paddingLeft: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>合规率走势 (%)</span>
                    <span style={{ fontSize: 11, color: '#94a3b8' }}>基准: 100%</span>
                  </div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'flex-end',
                    height: 100,
                    gap: 3,
                    paddingTop: 8,
                  }}>
                    {trends.compliance_trend.map((item: any, idx: number) => {
                      const pct = (item.rate / maxComplianceRate) * 100
                      const barColor = item.rate >= 80
                        ? 'linear-gradient(180deg, #10b981 0%, #34d399 100%)'
                        : item.rate >= 60
                          ? 'linear-gradient(180deg, #f59e0b 0%, #fbbf24 100%)'
                          : 'linear-gradient(180deg, #ef4444 0%, #f87171 100%)'
                      return (
                        <Tooltip key={idx} title={`${item.date} : 合规率 ${item.rate}%`}>
                          <div style={{
                            flex: 1,
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            height: '100%',
                            justifyContent: 'flex-end',
                            cursor: 'pointer',
                          }}>
                            <div style={{
                              width: '100%',
                              height: `${pct}%`,
                              minHeight: 4,
                              background: barColor,
                              borderRadius: '3px 3px 0 0',
                              transition: 'all 0.2s ease',
                            }} />
                            <div style={{
                              fontSize: 9,
                              color: '#94a3b8',
                              marginTop: 3,
                              transform: 'scale(0.85)',
                              whiteSpace: 'nowrap',
                            }}>
                              {item.date.slice(5)}
                            </div>
                          </div>
                        </Tooltip>
                      )
                    })}
                  </div>
                </Col>
              </Row>
            )}
          </Card>

          {/* Recent Tasks Compact Table */}
          <Card
            className="dashboard-section-card"
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <ClockCircleOutlined style={{ color: 'var(--primary-color)' }} />
                <span>最近日常检查任务</span>
              </div>
            }
            extra={
              <Button
                type="link"
                size="small"
                onClick={() => navigate('/tasks')}
                style={{ padding: 0, display: 'flex', alignItems: 'center', gap: 2, fontSize: 12 }}
              >
                全部任务 <ArrowRightOutlined />
              </Button>
            }
            loading={loading} variant="borderless"
          >
            <Table
              dataSource={recentTasks}
              columns={columns}
              rowKey="id"
              pagination={false}
              size="small"
              onRow={(record) => ({
                onClick: () => navigate(`/tasks/${record.id}`),
                style: { cursor: 'pointer' },
              })}
            />
          </Card>
        </Col>

        {/* Right Column (9/24): Quick Actions + Risk Meters + Inspection Health */}
        <Col xs={24} lg={9} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* Quick Operations 2x2 Tiles */}
          <Card
            className="dashboard-section-card"
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <AppstoreOutlined style={{ color: 'var(--primary-color)' }} />
                <span>常用工作流</span>
              </div>
            } variant="borderless"
          >
            <div className="dashboard-quick-grid">
              <div
                className="dashboard-quick-tile"
                onClick={() => navigate('/audit-projects')}
              >
                <div className="dashboard-tile-icon" style={{ background: '#eff6ff', color: '#2563eb' }}>
                  <AuditOutlined />
                </div>
                <div>
                  <div className="dashboard-tile-title">审核项目</div>
                  <div className="dashboard-tile-desc">策划 · 现场 · 交付</div>
                </div>
              </div>

              <div
                className="dashboard-quick-tile"
                onClick={() => navigate('/my-audit-tasks')}
              >
                <div className="dashboard-tile-icon" style={{ background: '#f0fdf4', color: '#16a34a' }}>
                  <ScheduleOutlined />
                </div>
                <div>
                  <div className="dashboard-tile-title">我的审核任务</div>
                  <div className="dashboard-tile-desc">项目计划派发 · 现场录入</div>
                </div>
              </div>

              <div
                className="dashboard-quick-tile"
                onClick={() => navigate('/enterprises')}
              >
                <div className="dashboard-tile-icon" style={{ background: '#fff7ed', color: '#ea580c' }}>
                  <BankOutlined />
                </div>
                <div>
                  <div className="dashboard-tile-title">企业档案</div>
                  <div className="dashboard-tile-desc">风险资质全景</div>
                </div>
              </div>

              <div
                className="dashboard-quick-tile"
                onClick={() => navigate('/knowledge')}
              >
                <div className="dashboard-tile-icon" style={{ background: '#f5f3ff', color: '#7c3aed' }}>
                  <BookOutlined />
                </div>
                <div>
                  <div className="dashboard-tile-title">智审知识库</div>
                  <div className="dashboard-tile-desc">标准与法规检索</div>
                </div>
              </div>
            </div>
          </Card>

          {/* Enterprise Risk Distribution */}
          <Card
            className="dashboard-section-card"
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <BankOutlined style={{ color: '#dc2626' }} />
                <span>企业风险分布态势</span>
              </div>
            }
            extra={
              <span style={{ fontSize: 11, color: '#64748b' }}>
                已纳管 {stats?.enterprises?.total || (highRisk + mediumRisk + lowRisk)} 家
              </span>
            } variant="borderless"
          >
            <div className="dashboard-risk-meter">
              <div className="dashboard-risk-row">
                <span style={{ color: '#dc2626', fontWeight: 600, minWidth: 70 }}>
                  ● 高风险 ({highRisk})
                </span>
                <div className="dashboard-risk-bar-bg">
                  <div
                    className="dashboard-risk-bar-fill"
                    style={{
                      width: `${(highRisk / totalRiskEnterprises) * 100}%`,
                      background: '#ef4444',
                    }}
                  />
                </div>
                <span style={{ color: '#94a3b8', fontSize: 11, width: 36, textAlign: 'right' }}>
                  {Math.round((highRisk / totalRiskEnterprises) * 100)}%
                </span>
              </div>

              <div className="dashboard-risk-row">
                <span style={{ color: '#d97706', fontWeight: 600, minWidth: 70 }}>
                  ● 中风险 ({mediumRisk})
                </span>
                <div className="dashboard-risk-bar-bg">
                  <div
                    className="dashboard-risk-bar-fill"
                    style={{
                      width: `${(mediumRisk / totalRiskEnterprises) * 100}%`,
                      background: '#f59e0b',
                    }}
                  />
                </div>
                <span style={{ color: '#94a3b8', fontSize: 11, width: 36, textAlign: 'right' }}>
                  {Math.round((mediumRisk / totalRiskEnterprises) * 100)}%
                </span>
              </div>

              <div className="dashboard-risk-row">
                <span style={{ color: '#16a34a', fontWeight: 600, minWidth: 70 }}>
                  ● 低风险 ({lowRisk})
                </span>
                <div className="dashboard-risk-bar-bg">
                  <div
                    className="dashboard-risk-bar-fill"
                    style={{
                      width: `${(lowRisk / totalRiskEnterprises) * 100}%`,
                      background: '#10b981',
                    }}
                  />
                </div>
                <span style={{ color: '#94a3b8', fontSize: 11, width: 36, textAlign: 'right' }}>
                  {Math.round((lowRisk / totalRiskEnterprises) * 100)}%
                </span>
              </div>
            </div>
          </Card>

          {/* Inspection Items Health Breakdown */}
          {stats && (
            <Card
              className="dashboard-section-card"
              title={
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <CheckCircleOutlined style={{ color: '#16a34a' }} />
                  <span>现场检查项体检</span>
                </div>
              } variant="borderless"
            >
              <div style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                  <span style={{ color: '#64748b' }}>检查项达标率（{COMPLIANCE_FORMULA}）</span>
                  <span style={{ fontWeight: 700, color: '#16a34a' }}>{complianceRate}%</span>
                </div>
                <Progress
                  percent={complianceRate}
                  strokeColor={{
                    '0%': '#10b981',
                    '100%': '#0284c7',
                  }}
                  trailColor="#f1f5f9"
                  size="small"
                />
              </div>

              <Row gutter={8}>
                <Col span={6}>
                  <div style={{
                    padding: '8px 4px',
                    background: '#f0fdf4',
                    borderRadius: 6,
                    textAlign: 'center',
                    border: '1px solid #dcfce7',
                  }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#16a34a', lineHeight: 1.1 }}>
                      {compliantItems}
                    </div>
                    <div style={{ fontSize: 10, color: '#15803d', marginTop: 2 }}>合格项</div>
                  </div>
                </Col>
                <Col span={6}>
                  <div style={{
                    padding: '8px 4px',
                    background: '#fef2f2',
                    borderRadius: 6,
                    textAlign: 'center',
                    border: '1px solid #fee2e2',
                  }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#ef4444', lineHeight: 1.1 }}>
                      {nonCompliantItems}
                    </div>
                    <div style={{ fontSize: 10, color: '#b91c1c', marginTop: 2 }}>不合格项</div>
                  </div>
                </Col>
                <Col span={6}>
                  <div style={{
                    padding: '8px 4px',
                    background: '#eff6ff',
                    borderRadius: 6,
                    textAlign: 'center',
                    border: '1px solid #dbeafe',
                  }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#0369a1', lineHeight: 1.1 }}>
                      {notApplicableItems}
                    </div>
                    <div style={{ fontSize: 10, color: '#1d4ed8', marginTop: 2 }}>不适用项</div>
                  </div>
                </Col>
                <Col span={6}>
                  <div style={{
                    padding: '8px 4px',
                    background: '#f8fafc',
                    borderRadius: 6,
                    textAlign: 'center',
                    border: '1px solid #e2e8f0',
                  }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#64748b', lineHeight: 1.1 }}>
                      {notFilledItems}
                    </div>
                    <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>未填报</div>
                  </div>
                </Col>
              </Row>

              {/* 口径说明：各项相加必须等于总检查项，避免「135 + 21 ≠ 248」这类对不上的数字。
                  「观察项」是已填写但不属于合格/不合格/不适用的中间态，
                  必须单独列出——否则汇总表差额无处归属。 */}
              <div style={{ marginTop: 10, fontSize: 11, color: '#94a3b8', lineHeight: 1.7 }}>
                总检查项 {totalItems} 项 = 合格 {compliantItems} + 不合格 {nonCompliantItems}
                {notApplicableItems > 0 ? ` + 不适用 ${notApplicableItems}` : ''}
                {observeItems > 0 ? ` + 观察项 ${observeItems}` : ''}
                {notFilledItems > 0 ? ` + 未填报 ${notFilledItems}` : ''}
                <br />
                已填报 {filledItems} 项；达标率分母 = 总检查项 − 不适用项 = {Math.max(totalItems - notApplicableItems, 0)} 项。
              </div>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  )
}
