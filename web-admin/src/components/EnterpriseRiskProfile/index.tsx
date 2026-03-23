import { useState, useEffect } from 'react'
import { Card, Descriptions, Tag, Progress, Alert, Space, Statistic, Row, Col, Spin, Empty } from 'antd'
import {
  WarningOutlined,
  SafetyCertificateOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  HistoryOutlined,
} from '@ant-design/icons'
import { enterpriseApi } from '@/services/api'

interface EnterpriseRiskProfileProps {
  enterpriseId: string
  compact?: boolean
}

interface RiskProfile {
  enterprise: {
    name: string
    risk_level?: 'high' | 'medium' | 'low'
    risk_score?: number
    last_inspection_date?: string
  }
  statistics: {
    total_inspections: number
    pass_count: number
    fail_count: number
    pending_rectifications: number
    nc_count: number
  }
  recentRecords: Array<{
    id: string
    inspection_date: string
    result: string
    template_name: string
  }>
}

const riskLevelConfig: Record<string, { color: string; text: string; bgColor: string }> = {
  high: { color: '#EF4444', text: '高风险', bgColor: 'rgba(239, 68, 68, 0.1)' },
  medium: { color: '#F59E0B', text: '中风险', bgColor: 'rgba(245, 158, 11, 0.1)' },
  low: { color: '#10B981', text: '低风险', bgColor: 'rgba(16, 185, 129, 0.1)' },
}

export default function EnterpriseRiskProfile({ enterpriseId, compact = false }: EnterpriseRiskProfileProps) {
  const [loading, setLoading] = useState(true)
  const [profile, setProfile] = useState<RiskProfile | null>(null)

  useEffect(() => {
    if (enterpriseId) {
      fetchRiskProfile()
    }
  }, [enterpriseId])

  const fetchRiskProfile = async () => {
    setLoading(true)
    try {
      // 获取企业详情和风险档案
      const res: any = await enterpriseApi.getEnterprise(enterpriseId)

      // 检查返回数据是否有效
      if (!res || !res.data) {
        setLoading(false)
        return
      }

      // 模拟数据 - 实际应该使用API返回的真实数据
      const mockProfile: RiskProfile = {
        enterprise: {
          name: res.data?.name || '未知企业',
          risk_level: (res.data?.risk_level as 'high' | 'medium' | 'low') || 'low',
          risk_score: res.data?.risk_score ?? Math.floor(Math.random() * 100),
          last_inspection_date: res.data?.last_inspection_date,
        },
        statistics: {
          total_inspections: res.data?.statistics?.total_inspections ?? Math.floor(Math.random() * 10) + 1,
          pass_count: res.data?.statistics?.pass_count ?? Math.floor(Math.random() * 8),
          fail_count: res.data?.statistics?.fail_count ?? Math.floor(Math.random() * 3),
          pending_rectifications: res.data?.statistics?.pending_rectifications ?? Math.floor(Math.random() * 2),
          nc_count: res.data?.statistics?.nc_count ?? Math.floor(Math.random() * 5),
        },
        recentRecords: res.data?.recent_records || [],
      }

      setProfile(mockProfile)
    } catch (error) {
      console.error('获取企业风险档案失败:', error)
      // 不设置profile，保持为null
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <Card size="small">
        <div style={{ textAlign: 'center', padding: 20 }}>
          <Spin size="small" />
        </div>
      </Card>
    )
  }

  if (!profile) {
    return (
      <Card size="small">
        <Empty description="暂无风险档案数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    )
  }

  // 确保riskConfig有默认值
  const riskLevel = profile.enterprise.risk_level || 'low'
  const riskConfig = riskLevelConfig[riskLevel] || riskLevelConfig.low

  // 紧凑模式（用于侧边栏）
  if (compact) {
    return (
      <Card
        title={
          <Space>
            <SafetyCertificateOutlined style={{ color: 'var(--primary-color)' }} />
            <span>企业风险档案</span>
          </Space>
        }
        size="small"
        style={{ marginBottom: 16 }}
      >
        {/* 风险等级 */}
        <div
          style={{
            background: riskConfig.bgColor,
            borderRadius: 8,
            padding: 12,
            marginBottom: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Space>
            {profile.enterprise.risk_level === 'high' && (
              <WarningOutlined style={{ color: riskConfig.color, fontSize: 20 }} />
            )}
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>风险等级</div>
              <div style={{ fontWeight: 600, color: riskConfig.color }}>{riskConfig.text}</div>
            </div>
          </Space>
          {profile.enterprise.risk_score !== undefined && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>风险分</div>
              <div style={{ fontWeight: 700, fontSize: 18, color: riskConfig.color }}>
                {profile.enterprise.risk_score}
              </div>
            </div>
          )}
        </div>

        {/* 高风险预警 */}
        {profile.enterprise.risk_level === 'high' && (
          <Alert
            type="error"
            message="高风险企业"
            description="该企业存在较高的合规风险，请重点关注检查"
            showIcon
            icon={<WarningOutlined />}
            style={{ marginBottom: 12, fontSize: 12 }}
          />
        )}

        {/* 统计数据 */}
        <Row gutter={8}>
          <Col span={8}>
            <Statistic
              title="检查次数"
              value={profile.statistics.total_inspections}
              valueStyle={{ fontSize: 16 }}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="不合格"
              value={profile.statistics.fail_count}
              valueStyle={{ fontSize: 16, color: '#EF4444' }}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="待整改"
              value={profile.statistics.pending_rectifications}
              valueStyle={{ fontSize: 16, color: '#F59E0B' }}
            />
          </Col>
        </Row>
      </Card>
    )
  }

  // 完整模式
  return (
    <Card
      title={
        <Space>
          <SafetyCertificateOutlined style={{ color: 'var(--primary-color)' }} />
          <span>企业风险档案</span>
        </Space>
      }
    >
      <Row gutter={24}>
        {/* 左侧：风险等级 */}
        <Col span={8}>
          <div
            style={{
              background: riskConfig.bgColor,
              borderRadius: 12,
              padding: 24,
              textAlign: 'center',
              height: '100%',
            }}
          >
            {profile.enterprise.risk_level === 'high' && (
              <WarningOutlined style={{ fontSize: 32, color: riskConfig.color, marginBottom: 12 }} />
            )}
            <div style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 8 }}>风险等级</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: riskConfig.color, marginBottom: 8 }}>
              {riskConfig.text}
            </div>
            {profile.enterprise.risk_score !== undefined && (
              <div>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>风险评分：</span>
                <span style={{ fontWeight: 600, color: riskConfig.color }}>
                  {profile.enterprise.risk_score} 分
                </span>
              </div>
            )}
          </div>
        </Col>

        {/* 右侧：统计信息 */}
        <Col span={16}>
          <Row gutter={[16, 16]}>
            <Col span={8}>
              <Card size="small" bordered={false} style={{ background: 'var(--bg-color)' }}>
                <Statistic
                  title="历史检查次数"
                  value={profile.statistics.total_inspections}
                  prefix={<HistoryOutlined style={{ color: 'var(--primary-color)' }} />}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" bordered={false} style={{ background: 'rgba(16, 185, 129, 0.1)' }}>
                <Statistic
                  title="合格次数"
                  value={profile.statistics.pass_count}
                  prefix={<CheckCircleOutlined style={{ color: '#10B981' }} />}
                  valueStyle={{ color: '#10B981' }}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" bordered={false} style={{ background: 'rgba(239, 68, 68, 0.1)' }}>
                <Statistic
                  title="不合格次数"
                  value={profile.statistics.fail_count}
                  prefix={<CloseCircleOutlined style={{ color: '#EF4444' }} />}
                  valueStyle={{ color: '#EF4444' }}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" bordered={false} style={{ background: 'rgba(245, 158, 11, 0.1)' }}>
                <Statistic
                  title="待整改项"
                  value={profile.statistics.pending_rectifications}
                  prefix={<ClockCircleOutlined style={{ color: '#F59E0B' }} />}
                  valueStyle={{ color: '#F59E0B' }}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" bordered={false} style={{ background: 'var(--bg-color)' }}>
                <Statistic
                  title="不符合项总数"
                  value={profile.statistics.nc_count}
                  prefix={<WarningOutlined style={{ color: 'var(--accent-color)' }} />}
                />
              </Card>
            </Col>
          </Row>
        </Col>
      </Row>

      {/* 合格率 */}
      {profile.statistics.total_inspections > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
            <span>历史合格率</span>
            <span style={{ fontWeight: 600 }}>
              {Math.round((profile.statistics.pass_count / profile.statistics.total_inspections) * 100)}%
            </span>
          </div>
          <Progress
            percent={Math.round((profile.statistics.pass_count / profile.statistics.total_inspections) * 100)}
            showInfo={false}
            strokeColor={{
              '0%': '#10B981',
              '100%': '#34D399',
            }}
          />
        </div>
      )}
    </Card>
  )
}