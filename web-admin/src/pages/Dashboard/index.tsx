import { useState, useEffect } from 'react'
import { Row, Col, Card, Statistic, Progress, Table, Tag, Space, Button, DatePicker, Select, message } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  UserOutlined,
  FileTextOutlined,
  BankOutlined,
  ArrowRightOutlined,
  RiseOutlined,
  SafetyCertificateOutlined,
  DownloadOutlined,
  CalendarOutlined,
} from '@ant-design/icons'
import { analyticsApi, taskApi } from '@/services/api'
import { useNavigate } from 'react-router-dom'
import { formatTaskDisplay } from '@/utils/display'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<any>(null)
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
      const [dashboardRes, tasksRes, riskRes]: any[] = await Promise.all([
        analyticsApi.getDashboard(),
        taskApi.getTasks({ limit: 10 }),
        analyticsApi.getEnterpriseRisk(),
      ])
      setStats(dashboardRes.data)
      setRecentTasks(tasksRes.data.items || [])
      setEnterpriseRisk(riskRes.data)
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
    const rows = data.map(item => [
      item.task_no,
      item.title,
      item.target_name,
      item.status,
      item.created_at,
      item.completed_at,
      item.compliant_items,
      item.non_compliant_items,
    ])
    return [headers, ...rows].map(row => row.join(',')).join('\n')
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
    return <Tag color={item.color}>{item.text}</Tag>
  }

  const pendingTodos = (recentTasks || []).filter((t) => t.status === 'pending' || t.status === 'in_progress')
  const todoCards = [
    {
      title: '待开始 / 进行中任务',
      value: pendingTodos.length,
      action: () => navigate('/tasks?status=in_progress'),
      color: '#0369a1',
      hint: '点击进入日常检查任务',
    },
    {
      title: '高风险企业',
      value: enterpriseRisk?.high || enterpriseRisk?.high_risk || 0,
      action: () => navigate('/enterprises'),
      color: '#dc2626',
      hint: '优先安排现场复核',
    },
    {
      title: '中风险企业',
      value: enterpriseRisk?.medium || enterpriseRisk?.medium_risk || 0,
      action: () => navigate('/enterprises'),
      color: '#d97706',
      hint: '关注整改闭环',
    },
    {
      title: '审核项目',
      value: '进入',
      action: () => navigate('/audit-projects'),
      color: '#0f766e',
      hint: '计划 · 现场 · 交付',
    },
  ]

  const columns = [
    {
      title: '任务',
      key: 'display',
      render: (_: any, record: any) => {
        const d = formatTaskDisplay(record)
        return (
          <div>
            <div style={{ fontWeight: 600 }}>{d.primary}</div>
            <div style={{ fontSize: 12, color: '#64748b' }}>{d.secondary || record.task_no}</div>
          </div>
        )
      },
    },
    {
      title: '企业/对象',
      dataIndex: 'target_name',
      key: 'target_name',
      width: 150,
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: any) => (
        <Button
          type="link"
          size="small"
          onClick={() => navigate(record.status === 'completed' ? `/tasks/${record.id}` : `/inspection/${record.id}`)}
        >
          {record.status === 'completed' ? '查看' : record.status === 'pending' ? '开始' : '继续'}
        </Button>
      ),
    },
  ]

  const statCards = [
    {
      title: '总任务数',
      value: stats?.tasks?.total || 0,
      icon: <FileTextOutlined />,
      color: 'var(--primary-color)',
      bgColor: 'linear-gradient(135deg, rgba(100, 116, 139, 0.1) 0%, rgba(100, 116, 139, 0.05) 100%)',
    },
    {
      title: '已完成',
      value: stats?.tasks?.completed || 0,
      icon: <CheckCircleOutlined />,
      color: 'var(--success-color)',
      bgColor: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(16, 185, 129, 0.05) 100%)',
    },
    {
      title: '进行中',
      value: stats?.tasks?.in_progress || 0,
      icon: <ClockCircleOutlined />,
      color: 'var(--info-color)',
      bgColor: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%)',
    },
    {
      title: '合规率',
      value: stats?.inspections?.compliance_rate || 0,
      suffix: '%',
      icon: <SafetyCertificateOutlined />,
      color: 'var(--accent-color)',
      bgColor: 'linear-gradient(135deg, rgba(249, 115, 22, 0.1) 0%, rgba(249, 115, 22, 0.05) 100%)',
    },
  ]

  const maxInspectionCount = trends?.inspection_trend 
    ? Math.max(...trends.inspection_trend.map((t: any) => t.count), 1)
    : 1

  const maxComplianceRate = 100

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">工作台</h1>
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            优先处理待办事项；合规率口径 = 已填报合格项 / 已填报项
          </div>
        </div>
        <Space>
          <RangePicker
            value={dateRange}
            onChange={(dates) => dates && setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
            allowClear={false}
            placeholder={['开始日期', '结束日期']}
          />
          <Button 
            type="default"
            icon={<DownloadOutlined />}
            onClick={handleExport}
          >
            导出数据
          </Button>
          <Button 
            type="default"
            icon={<RiseOutlined />}
            onClick={() => navigate('/analytics')}
          >
            数据分析
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {todoCards.map((card) => (
          <Col xs={24} sm={12} lg={6} key={card.title}>
            <Card
              hoverable
              bordered={false}
              onClick={card.action}
              style={{ cursor: 'pointer', borderTop: `3px solid ${card.color}` }}
            >
              <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 6 }}>{card.title}</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: card.color }}>{card.value}</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>{card.hint}</div>
            </Card>
          </Col>
        ))}
      </Row>

      {stats && (
        <>
          <Row gutter={[16, 16]}>
            {statCards.map((card, index) => (
              <Col xs={24} sm={12} lg={6} key={index}>
                <Card 
                  className="stat-card" 
                  bordered={false}
                  style={{ background: card.bgColor }}
                >
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
                        {card.value}{card.suffix || ''}
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
                      {card.icon && <span style={{ fontSize: 24, color: 'white' }}>{card.icon}</span>}
                    </div>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={12}>
              <Card 
                title={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <FileTextOutlined style={{ color: 'var(--primary-color)' }} />
                    <span>任务完成进度</span>
                  </div>
                }
                bordered={false}
              >
                <div style={{ marginBottom: 24 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span style={{ color: 'var(--text-muted)', fontSize: 14 }}>完成率</span>
                    <span style={{ fontWeight: 600, color: 'var(--primary-color)' }}>
                      {stats.tasks.completion_rate}%
                    </span>
                  </div>
                  <Progress
                    percent={stats.tasks.completion_rate}
                    strokeColor={{
                      '0%': 'var(--primary-color)',
                      '100%': 'var(--accent-color)',
                    }}
                    trailColor="var(--border-color)"
                  />
                </div>
                <Row gutter={16}>
                  <Col span={8}>
                    <div style={{
                      padding: 16,
                      background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(16, 185, 129, 0.02) 100%)',
                      borderRadius: 8,
                      textAlign: 'center',
                    }}>
                      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--success-color)' }}>
                        {stats.inspections.compliant}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>合规项</div>
                    </div>
                  </Col>
                  <Col span={8}>
                    <div style={{
                      padding: 16,
                      background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(239, 68, 68, 0.02) 100%)',
                      borderRadius: 8,
                      textAlign: 'center',
                    }}>
                      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--error-color)' }}>
                        {stats.inspections.non_compliant}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>不合规项</div>
                    </div>
                  </Col>
                  <Col span={8}>
                    <div style={{
                      padding: 16,
                      background: 'linear-gradient(135deg, rgba(100, 116, 139, 0.08) 0%, rgba(100, 116, 139, 0.02) 100%)',
                      borderRadius: 8,
                      textAlign: 'center',
                    }}>
                      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--primary-color)' }}>
                        {stats.inspections.total}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>总检查项</div>
                    </div>
                  </Col>
                </Row>
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card 
                title={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <BankOutlined style={{ color: 'var(--primary-color)' }} />
                    <span>系统概览</span>
                  </div>
                }
                bordered={false}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 16,
                    background: 'linear-gradient(90deg, rgba(100, 116, 139, 0.06) 0%, rgba(249, 115, 22, 0.06) 100%)',
                    borderRadius: 8,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{
                        width: 40,
                        height: 40,
                        background: 'linear-gradient(135deg, var(--primary-color) 0%, var(--accent-color) 100%)',
                        borderRadius: 10,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}>
                        <UserOutlined style={{ color: 'white', fontSize: 18 }} />
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>系统用户</div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>已注册用户数量</div>
                      </div>
                    </div>
                    <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--primary-color)' }}>
                      {stats.users.total}
                    </div>
                  </div>

                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 16,
                    background: 'linear-gradient(90deg, rgba(100, 116, 139, 0.06) 0%, rgba(249, 115, 22, 0.06) 100%)',
                    borderRadius: 8,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{
                        width: 40,
                        height: 40,
                        background: 'linear-gradient(135deg, var(--info-color) 0%, #60A5FA 100%)',
                        borderRadius: 10,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}>
                        <BankOutlined style={{ color: 'white', fontSize: 18 }} />
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>企业数量</div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>已录入企业信息</div>
                      </div>
                    </div>
                    <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--info-color)' }}>
                      {stats.enterprises?.total || 0}
                    </div>
                  </div>

                  <Button 
                    type="link" 
                    style={{ padding: 0, display: 'flex', alignItems: 'center', gap: 4 }}
                    onClick={() => navigate('/enterprises')}
                  >
                    查看全部企业 <ArrowRightOutlined />
                  </Button>
                </div>
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={12}>
              <Card 
                title={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <RiseOutlined style={{ color: 'var(--primary-color)' }} />
                    <span>检查趋势图</span>
                  </div>
                }
                bordered={false}
                loading={!trends}
              >
                {trends && (
                  <div style={{ height: 200, position: 'relative' }}>
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'flex-end', 
                      height: 160, 
                      gap: 2,
                      paddingBottom: 20,
                    }}>
                      {trends.inspection_trend.slice(-14).map((item: any, index: number) => (
                        <div key={index} style={{ 
                          flex: 1, 
                          display: 'flex', 
                          flexDirection: 'column', 
                          alignItems: 'center',
                          height: '100%',
                        }}>
                          <div style={{ 
                            width: '100%', 
                            height: `${(item.count / maxInspectionCount) * 100}%`,
                            minHeight: item.count > 0 ? 4 : 0,
                            background: 'linear-gradient(180deg, var(--primary-color) 0%, var(--accent-color) 100%)',
                            borderRadius: '4px 4px 0 0',
                            transition: 'height 0.3s ease',
                          }} />
                          <div style={{ 
                            fontSize: 10, 
                            color: 'var(--text-muted)', 
                            marginTop: 4,
                            transform: 'rotate(-45deg)',
                            transformOrigin: 'center',
                            whiteSpace: 'nowrap',
                          }}>
                            {item.date.slice(5)}
                          </div>
                        </div>
                      ))}
                    </div>
                    <div style={{ 
                      position: 'absolute', 
                      top: 0, 
                      right: 0,
                      fontSize: 12,
                      color: 'var(--text-muted)',
                    }}>
                      最大值: {maxInspectionCount}
                    </div>
                  </div>
                )}
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card 
                title={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <SafetyCertificateOutlined style={{ color: 'var(--success-color)' }} />
                    <span>合规率趋势图</span>
                  </div>
                }
                bordered={false}
                loading={!trends}
              >
                {trends && (
                  <div style={{ height: 200, position: 'relative' }}>
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'flex-end', 
                      height: 160, 
                      gap: 2,
                      paddingBottom: 20,
                    }}>
                      {trends.compliance_trend.slice(-14).map((item: any, index: number) => (
                        <div key={index} style={{ 
                          flex: 1, 
                          display: 'flex', 
                          flexDirection: 'column', 
                          alignItems: 'center',
                          height: '100%',
                        }}>
                          <div style={{ 
                            width: '100%', 
                            height: `${(item.rate / maxComplianceRate) * 100}%`,
                            minHeight: 4,
                            background: item.rate >= 80 
                              ? 'linear-gradient(180deg, #10B981 0%, #34D399 100%)'
                              : item.rate >= 60
                                ? 'linear-gradient(180deg, #F59E0B 0%, #FBBF24 100%)'
                                : 'linear-gradient(180deg, #EF4444 0%, #F87171 100%)',
                            borderRadius: '4px 4px 0 0',
                            transition: 'height 0.3s ease',
                          }} />
                          <div style={{ 
                            fontSize: 10, 
                            color: 'var(--text-muted)', 
                            marginTop: 4,
                            transform: 'rotate(-45deg)',
                            transformOrigin: 'center',
                            whiteSpace: 'nowrap',
                          }}>
                            {item.date.slice(5)}
                          </div>
                        </div>
                      ))}
                    </div>
                    <div style={{ 
                      position: 'absolute', 
                      top: 0, 
                      right: 0,
                      fontSize: 12,
                      color: 'var(--text-muted)',
                    }}>
                      单位: %
                    </div>
                  </div>
                )}
              </Card>
            </Col>
          </Row>

          {enterpriseRisk && (
            <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
              <Col xs={24}>
                <Card 
                  title={
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <BankOutlined style={{ color: 'var(--primary-color)' }} />
                      <span>企业风险分布</span>
                    </div>
                  }
                  bordered={false}
                >
                  <Row gutter={16}>
                    <Col xs={24} sm={8}>
                      <div style={{
                        padding: 20,
                        background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%)',
                        borderRadius: 12,
                        textAlign: 'center',
                        border: '1px solid rgba(239, 68, 68, 0.2)',
                      }}>
                        <div style={{ 
                          fontSize: 36, 
                          fontWeight: 700, 
                          color: '#EF4444',
                          marginBottom: 8,
                        }}>
                          {enterpriseRisk.high}
                        </div>
                        <div style={{ 
                          fontSize: 14, 
                          color: '#EF4444',
                          fontWeight: 500,
                        }}>
                          高风险企业
                        </div>
                        <div style={{ 
                          marginTop: 12,
                          height: 4,
                          background: '#EF4444',
                          borderRadius: 2,
                        }} />
                      </div>
                    </Col>
                    <Col xs={24} sm={8}>
                      <div style={{
                        padding: 20,
                        background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%)',
                        borderRadius: 12,
                        textAlign: 'center',
                        border: '1px solid rgba(245, 158, 11, 0.2)',
                      }}>
                        <div style={{ 
                          fontSize: 36, 
                          fontWeight: 700, 
                          color: '#F59E0B',
                          marginBottom: 8,
                        }}>
                          {enterpriseRisk.medium}
                        </div>
                        <div style={{ 
                          fontSize: 14, 
                          color: '#F59E0B',
                          fontWeight: 500,
                        }}>
                          中风险企业
                        </div>
                        <div style={{ 
                          marginTop: 12,
                          height: 4,
                          background: '#F59E0B',
                          borderRadius: 2,
                        }} />
                      </div>
                    </Col>
                    <Col xs={24} sm={8}>
                      <div style={{
                        padding: 20,
                        background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(16, 185, 129, 0.05) 100%)',
                        borderRadius: 12,
                        textAlign: 'center',
                        border: '1px solid rgba(16, 185, 129, 0.2)',
                      }}>
                        <div style={{ 
                          fontSize: 36, 
                          fontWeight: 700, 
                          color: '#10B981',
                          marginBottom: 8,
                        }}>
                          {enterpriseRisk.low}
                        </div>
                        <div style={{ 
                          fontSize: 14, 
                          color: '#10B981',
                          fontWeight: 500,
                        }}>
                          低风险企业
                        </div>
                        <div style={{ 
                          marginTop: 12,
                          height: 4,
                          background: '#10B981',
                          borderRadius: 2,
                        }} />
                      </div>
                    </Col>
                  </Row>
                </Card>
              </Col>
            </Row>
          )}
        </>
      )}

      <Card 
        title={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <ClockCircleOutlined style={{ color: 'var(--primary-color)' }} />
              <span>最近任务</span>
            </div>
            <Button 
              type="link" 
              size="small"
              onClick={() => navigate('/tasks')}
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}
            >
              查看全部 <ArrowRightOutlined />
            </Button>
          </div>
        }
        style={{ marginTop: 16 }} 
        loading={loading}
        bordered={false}
      >
        <Table
          dataSource={recentTasks}
          columns={columns}
          rowKey="id"
          pagination={false}
          size="middle"
          onRow={(record) => ({
            onClick: () => navigate(`/tasks/${record.id}`),
            style: { cursor: 'pointer' },
          })}
        />
      </Card>
    </div>
  )
}
