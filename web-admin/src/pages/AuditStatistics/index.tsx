import { useState, useEffect } from 'react'
import { Row, Col, Card, Table, Tag, Space, Select, Spin, Empty } from 'antd'
import {
  ProjectOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CalendarOutlined,
  WarningOutlined,
  TeamOutlined,
  TrophyOutlined,
  FileTextOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import { statisticsApi } from '@/services/api'

// 项目概览统计类型
interface OverviewStats {
  total: number
  in_progress: number
  completed: number
  this_month: number
}

// 分布数据类型
interface DistributionItem {
  name: string
  value: number
}

// 趋势数据类型
interface TrendItem {
  month: string
  created: number
  completed: number
}

// 不符合项趋势类型
interface NCTrendItem {
  month: string
  total: number
  major: number
  minor: number
  observation: number
}

// 不符合项条款统计
interface NCClauseItem {
  clause_no: string
  count: number
}

// 审核员工作量类型
interface AuditorWorkload {
  user_id: string
  name: string
  project_count: number
  area_count: number
  nc_count: number
}

// 审核员排名类型
interface AuditorRanking extends AuditorWorkload {
  rank: number
}

export default function AuditStatistics() {
  // 项目概览
  const [overview, setOverview] = useState<OverviewStats | null>(null)
  const [projectDistribution, setProjectDistribution] = useState<DistributionItem[]>([])
  const [projectTrend, setProjectTrend] = useState<TrendItem[]>([])

  // 不符合项统计
  const [ncDistribution, setNcDistribution] = useState<DistributionItem[]>([])
  const [ncBySystem, setNcBySystem] = useState<DistributionItem[]>([])
  const [ncByClause, setNcByClause] = useState<NCClauseItem[]>([])
  const [ncTrend, setNcTrend] = useState<NCTrendItem[]>([])

  // 审核员统计
  const [auditorWorkload, setAuditorWorkload] = useState<AuditorWorkload[]>([])
  const [auditorRanking, setAuditorRanking] = useState<AuditorRanking[]>([])
  const [rankingMetric, setRankingMetric] = useState<'projects' | 'areas' | 'ncs'>('projects')

  // 加载状态
  const [loading, setLoading] = useState(true)

  // 筛选器
  const [selectedProjectId, setSelectedProjectId] = useState<string | undefined>()
  const [trendMonths, setTrendMonths] = useState(6)

  useEffect(() => {
    fetchAllData()
  }, [])

  useEffect(() => {
    fetchNCDistribution()
    fetchNCBySystem()
    fetchNCByClause()
    fetchAuditorWorkload()
  }, [selectedProjectId])

  useEffect(() => {
    fetchProjectTrend()
    fetchNCTrend()
  }, [trendMonths])

  useEffect(() => {
    fetchAuditorRanking()
  }, [rankingMetric])

  const fetchAllData = async () => {
    setLoading(true)
    try {
      await Promise.all([
        fetchOverview(),
        fetchProjectDistribution(),
        fetchProjectTrend(),
        fetchNCDistribution(),
        fetchNCBySystem(),
        fetchNCByClause(),
        fetchNCTrend(),
        fetchAuditorWorkload(),
        fetchAuditorRanking(),
      ])
    } finally {
      setLoading(false)
    }
  }

  const fetchOverview = async () => {
    try {
      const res: any = await statisticsApi.getOverview()
      setOverview(res.data)
    } catch (error) {
      console.error('Failed to fetch overview:', error)
    }
  }

  const fetchProjectDistribution = async () => {
    try {
      const [statusRes, typeRes]: any[] = await Promise.all([
        statisticsApi.getProjectDistribution({ by: 'status' }),
        statisticsApi.getProjectDistribution({ by: 'type' }),
      ])
      setProjectDistribution(statusRes.data || [])
    } catch (error) {
      console.error('Failed to fetch project distribution:', error)
    }
  }

  const fetchProjectTrend = async () => {
    try {
      const res: any = await statisticsApi.getProjectTrend({ months: trendMonths })
      setProjectTrend(res.data || [])
    } catch (error) {
      console.error('Failed to fetch project trend:', error)
    }
  }

  const fetchNCDistribution = async () => {
    try {
      const res: any = await statisticsApi.getNCDistribution(
        selectedProjectId ? { project_id: selectedProjectId } : undefined
      )
      setNcDistribution(res.data || [])
    } catch (error) {
      console.error('Failed to fetch NC distribution:', error)
    }
  }

  const fetchNCBySystem = async () => {
    try {
      const res: any = await statisticsApi.getNCBySystem(
        selectedProjectId ? { project_id: selectedProjectId } : undefined
      )
      setNcBySystem(res.data || [])
    } catch (error) {
      console.error('Failed to fetch NC by system:', error)
    }
  }

  const fetchNCByClause = async () => {
    try {
      const res: any = await statisticsApi.getNCByClause(
        selectedProjectId ? { project_id: selectedProjectId } : undefined
      )
      setNcByClause(res.data || [])
    } catch (error) {
      console.error('Failed to fetch NC by clause:', error)
    }
  }

  const fetchNCTrend = async () => {
    try {
      const res: any = await statisticsApi.getNCTrend({ months: trendMonths })
      setNcTrend(res.data || [])
    } catch (error) {
      console.error('Failed to fetch NC trend:', error)
    }
  }

  const fetchAuditorWorkload = async () => {
    try {
      const res: any = await statisticsApi.getAuditorWorkload(
        selectedProjectId ? { project_id: selectedProjectId } : undefined
      )
      setAuditorWorkload(res.data || [])
    } catch (error) {
      console.error('Failed to fetch auditor workload:', error)
    }
  }

  const fetchAuditorRanking = async () => {
    try {
      const res: any = await statisticsApi.getAuditorRanking({ metric: rankingMetric, limit: 10 })
      setAuditorRanking(res.data || [])
    } catch (error) {
      console.error('Failed to fetch auditor ranking:', error)
    }
  }

  // 项目概览卡片
  const overviewCards = [
    {
      title: '总项目数',
      value: overview?.total || 0,
      icon: <ProjectOutlined />,
      color: 'var(--primary-color)',
      bgColor: 'linear-gradient(135deg, rgba(100, 116, 139, 0.1) 0%, rgba(100, 116, 139, 0.05) 100%)',
    },
    {
      title: '进行中',
      value: overview?.in_progress || 0,
      icon: <ClockCircleOutlined />,
      color: 'var(--info-color)',
      bgColor: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%)',
    },
    {
      title: '已完成',
      value: overview?.completed || 0,
      icon: <CheckCircleOutlined />,
      color: 'var(--success-color)',
      bgColor: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(16, 185, 129, 0.05) 100%)',
    },
    {
      title: '本月新增',
      value: overview?.this_month || 0,
      icon: <CalendarOutlined />,
      color: 'var(--accent-color)',
      bgColor: 'linear-gradient(135deg, rgba(249, 115, 22, 0.1) 0%, rgba(249, 115, 22, 0.05) 100%)',
    },
  ]

  // 不符合项严重程度颜色
  const ncSeverityColors: Record<string, string> = {
    '严重不符合': '#EF4444',
    '一般不符合': '#F59E0B',
    '观察项': '#3B82F6',
  }

  // 体系颜色
  const systemColors: Record<string, string> = {
    '质量体系(Q)': '#3B82F6',
    '环境体系(E)': '#10B981',
    '职业健康安全体系(S)': '#F59E0B',
    '能源体系(En)': '#8B5CF6',
  }

  // 审核员工作量表格列
  const workloadColumns = [
    {
      title: '审核员',
      dataIndex: 'name',
      key: 'name',
      width: 120,
    },
    {
      title: '参与项目',
      dataIndex: 'project_count',
      key: 'project_count',
      width: 100,
      sorter: (a: AuditorWorkload, b: AuditorWorkload) => a.project_count - b.project_count,
    },
    {
      title: '负责区域',
      dataIndex: 'area_count',
      key: 'area_count',
      width: 100,
      sorter: (a: AuditorWorkload, b: AuditorWorkload) => a.area_count - b.area_count,
    },
    {
      title: '开具NC',
      dataIndex: 'nc_count',
      key: 'nc_count',
      width: 100,
      sorter: (a: AuditorWorkload, b: AuditorWorkload) => a.nc_count - b.nc_count,
    },
  ]

  // 排名表格列
  const rankingColumns = [
    {
      title: '排名',
      dataIndex: 'rank',
      key: 'rank',
      width: 60,
      render: (rank: number) => {
        if (rank === 1) return <TrophyOutlined style={{ color: '#FFD700', fontSize: 18 }} />
        if (rank === 2) return <TrophyOutlined style={{ color: '#C0C0C0', fontSize: 18 }} />
        if (rank === 3) return <TrophyOutlined style={{ color: '#CD7F32', fontSize: 18 }} />
        return <span style={{ fontWeight: 600 }}>{rank}</span>
      },
    },
    {
      title: '审核员',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '项目数',
      dataIndex: 'project_count',
      key: 'project_count',
    },
    {
      title: '区域数',
      dataIndex: 'area_count',
      key: 'area_count',
    },
    {
      title: 'NC数',
      dataIndex: 'nc_count',
      key: 'nc_count',
    },
  ]

  // 渲染条形图
  const renderBarChart = (data: DistributionItem[], colors: Record<string, string> = {}) => {
    if (!data || data.length === 0) return <Empty description="暂无数据" />

    const maxValue = Math.max(...data.map(d => d.value), 1)

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {data.map((item, index) => (
          <div key={index} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 100, fontSize: 13, color: 'var(--text-muted)', textAlign: 'right' }}>
              {item.name}
            </div>
            <div style={{ flex: 1, height: 24, background: 'var(--border-color)', borderRadius: 4, overflow: 'hidden' }}>
              <div
                style={{
                  height: '100%',
                  width: `${(item.value / maxValue) * 100}%`,
                  background: colors[item.name] || 'var(--primary-color)',
                  borderRadius: 4,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  paddingRight: 8,
                  minWidth: item.value > 0 ? 40 : 0,
                  transition: 'width 0.3s ease',
                }}
              >
                {item.value > 0 && (
                  <span style={{ color: 'white', fontSize: 12, fontWeight: 600 }}>{item.value}</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  // 渲染趋势图
  const renderTrendChart = (data: TrendItem[]) => {
    if (!data || data.length === 0) return <Empty description="暂无数据" />

    const maxValue = Math.max(...data.flatMap(d => [d.created, d.completed]), 1)

    return (
      <div style={{ height: 200, position: 'relative' }}>
        <div style={{
          display: 'flex',
          alignItems: 'flex-end',
          height: 160,
          gap: 4,
          paddingBottom: 20,
        }}>
          {data.map((item, index) => (
            <div key={index} style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              height: '100%',
            }}>
              <div style={{
                display: 'flex',
                gap: 2,
                height: '100%',
                alignItems: 'flex-end',
              }}>
                <div style={{
                  width: 12,
                  height: `${(item.created / maxValue) * 100}%`,
                  minHeight: item.created > 0 ? 4 : 0,
                  background: 'linear-gradient(180deg, var(--primary-color) 0%, #94A3B8 100%)',
                  borderRadius: '2px 2px 0 0',
                  transition: 'height 0.3s ease',
                }} />
                <div style={{
                  width: 12,
                  height: `${(item.completed / maxValue) * 100}%`,
                  minHeight: item.completed > 0 ? 4 : 0,
                  background: 'linear-gradient(180deg, var(--success-color) 0%, #34D399 100%)',
                  borderRadius: '2px 2px 0 0',
                  transition: 'height 0.3s ease',
                }} />
              </div>
              <div style={{
                fontSize: 10,
                color: 'var(--text-muted)',
                marginTop: 4,
                transform: 'rotate(-45deg)',
                transformOrigin: 'center',
                whiteSpace: 'nowrap',
              }}>
                {item.month.slice(5)}
              </div>
            </div>
          ))}
        </div>
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          gap: 24,
          marginTop: 8,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 12, height: 12, background: 'var(--primary-color)', borderRadius: 2 }} />
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>新增</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 12, height: 12, background: 'var(--success-color)', borderRadius: 2 }} />
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>完成</span>
          </div>
        </div>
      </div>
    )
  }

  // 渲染不符合项趋势图
  const renderNCTrendChart = (data: NCTrendItem[]) => {
    if (!data || data.length === 0) return <Empty description="暂无数据" />

    const maxValue = Math.max(...data.map(d => d.total), 1)

    return (
      <div style={{ height: 200, position: 'relative' }}>
        <div style={{
          display: 'flex',
          alignItems: 'flex-end',
          height: 160,
          gap: 4,
          paddingBottom: 20,
        }}>
          {data.map((item, index) => (
            <div key={index} style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              height: '100%',
            }}>
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                width: 20,
                height: `${(item.total / maxValue) * 100}%`,
                minHeight: item.total > 0 ? 8 : 0,
              }}>
                {/* 观察项 - 最底层 */}
                {item.observation > 0 && (
                  <div style={{
                    flex: item.observation,
                    background: '#3B82F6',
                    borderRadius: '0 0 2px 2px',
                    minHeight: 2,
                  }} />
                )}
                {/* 一般不符合 - 中间层 */}
                {item.minor > 0 && (
                  <div style={{
                    flex: item.minor,
                    background: '#F59E0B',
                    minHeight: 2,
                  }} />
                )}
                {/* 严重不符合 - 最顶层 */}
                {item.major > 0 && (
                  <div style={{
                    flex: item.major,
                    background: '#EF4444',
                    borderRadius: '2px 2px 0 0',
                    minHeight: 2,
                  }} />
                )}
              </div>
              <div style={{
                fontSize: 10,
                color: 'var(--text-muted)',
                marginTop: 4,
                transform: 'rotate(-45deg)',
                transformOrigin: 'center',
                whiteSpace: 'nowrap',
              }}>
                {item.month.slice(5)}
              </div>
            </div>
          ))}
        </div>
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          gap: 16,
          marginTop: 8,
          flexWrap: 'wrap',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 12, height: 12, background: '#EF4444', borderRadius: 2 }} />
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>严重</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 12, height: 12, background: '#F59E0B', borderRadius: 2 }} />
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>一般</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 12, height: 12, background: '#3B82F6', borderRadius: 2 }} />
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>观察项</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <Spin spinning={loading}>
      <div>
        <div className="page-header">
          <h1 className="page-title">审核统计</h1>
          <Space>
            <Select
              value={trendMonths}
              onChange={setTrendMonths}
              style={{ width: 120 }}
              options={[
                { value: 3, label: '近3个月' },
                { value: 6, label: '近6个月' },
                { value: 12, label: '近12个月' },
              ]}
            />
          </Space>
        </div>

        {/* 项目概览 */}
        <Row gutter={[16, 16]}>
          {overviewCards.map((card, index) => (
            <Col xs={24} sm={12} lg={6} key={index}>
              <Card className="stat-card" variant="borderless" style={{ background: card.bgColor }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{
                      color: 'var(--text-muted)',
                      fontSize: 14,
                      marginBottom: 8,
                      fontWeight: 500,
                    }}>
                      {card.title}
                    </div>
                    <div style={{
                      fontSize: 32,
                      fontWeight: 700,
                      color: card.color,
                      lineHeight: 1,
                    }}>
                      {card.value}
                    </div>
                  </div>
                  <div style={{
                    width: 48,
                    height: 48,
                    background: card.color,
                    borderRadius: 12,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: `0 4px 12px ${card.color}40`,
                  }}>
                    <span style={{ fontSize: 24, color: 'white' }}>{card.icon}</span>
                  </div>
                </div>
              </Card>
            </Col>
          ))}
        </Row>

        {/* 项目趋势 */}
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col xs={24} lg={12}>
            <Card
              title={
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <BarChartOutlined style={{ color: 'var(--primary-color)' }} />
                  <span>项目趋势</span>
                </div>
              } variant="borderless"
            >
              {renderTrendChart(projectTrend)}
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card
              title={
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <ProjectOutlined style={{ color: 'var(--primary-color)' }} />
                  <span>项目状态分布</span>
                </div>
              } variant="borderless"
            >
              {renderBarChart(projectDistribution, {
                '策划中': '#8B5CF6',
                '进行中': '#3B82F6',
                '已完成': '#10B981',
                '已取消': '#EF4444',
              })}
            </Card>
          </Col>
        </Row>

        {/* 不符合项分析 */}
        <div style={{ marginTop: 24 }}>
          <div style={{
            fontSize: 16,
            fontWeight: 600,
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            <WarningOutlined style={{ color: 'var(--accent-color)' }} />
            不符合项分析
          </div>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={8}>
              <Card
                title="严重程度分布" variant="borderless"
                size="small"
              >
                {renderBarChart(ncDistribution, ncSeverityColors)}
              </Card>
            </Col>
            <Col xs={24} lg={8}>
              <Card
                title="按体系分布" variant="borderless"
                size="small"
              >
                {renderBarChart(ncBySystem, systemColors)}
              </Card>
            </Col>
            <Col xs={24} lg={8}>
              <Card
                title="条款TOP 10" variant="borderless"
                size="small"
              >
                {ncByClause.length === 0 ? (
                  <Empty description="暂无数据" />
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {ncByClause.slice(0, 10).map((item, index) => (
                      <div key={index} style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '8px 12px',
                        background: index < 3 ? 'rgba(239, 68, 68, 0.05)' : 'var(--bg-color)',
                        borderRadius: 6,
                      }}>
                        <span style={{
                          fontWeight: index < 3 ? 600 : 400,
                          color: index < 3 ? '#EF4444' : 'var(--text-main)',
                        }}>
                          {item.clause_no}
                        </span>
                        <Tag color={index < 3 ? 'error' : 'default'}>{item.count}</Tag>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </Col>
          </Row>
        </div>

        {/* 不符合项趋势 */}
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col xs={24}>
            <Card
              title={
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <BarChartOutlined style={{ color: 'var(--error-color)' }} />
                  <span>不符合项趋势</span>
                </div>
              } variant="borderless"
            >
              {renderNCTrendChart(ncTrend)}
            </Card>
          </Col>
        </Row>

        {/* 审核员工作量 */}
        <div style={{ marginTop: 24 }}>
          <div style={{
            fontSize: 16,
            fontWeight: 600,
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            <TeamOutlined style={{ color: 'var(--info-color)' }} />
            审核员工作量
          </div>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={14}>
              <Card
                title="工作量统计" variant="borderless"
              >
                <Table
                  dataSource={auditorWorkload}
                  columns={workloadColumns}
                  rowKey="user_id"
                  pagination={{ pageSize: 10, showSizeChanger: false }}
                  size="small"
                />
              </Card>
            </Col>
            <Col xs={24} lg={10}>
              <Card
                title={
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span>审核员排名</span>
                    <Select
                      value={rankingMetric}
                      onChange={setRankingMetric}
                      style={{ width: 100 }}
                      size="small"
                      options={[
                        { value: 'projects', label: '按项目数' },
                        { value: 'areas', label: '按区域数' },
                        { value: 'ncs', label: '按NC数' },
                      ]}
                    />
                  </div>
                } variant="borderless"
              >
                <Table
                  dataSource={auditorRanking}
                  columns={rankingColumns}
                  rowKey="user_id"
                  pagination={false}
                  size="small"
                />
              </Card>
            </Col>
          </Row>
        </div>
      </div>
    </Spin>
  )
}