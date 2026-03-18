import { useState, useEffect } from 'react'
import { Card, Descriptions, Tag, Tabs, Button, Space, message, Progress, Dropdown, Modal, Spin, Alert } from 'antd'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  EditOutlined, 
  ArrowLeftOutlined, 
  DownloadOutlined, 
  FileWordOutlined, 
  FilePdfOutlined,
  RobotOutlined,
  BulbOutlined,
} from '@ant-design/icons'
import { auditProjectApi, auditReportApi, auditAIApi } from '@/services/auditProjectApi'
import TeamManagement from './components/TeamManagement'
import PlanManagement from './components/PlanManagement'
import RecordsList from './components/RecordsList'
import NonconformitiesList from './components/NonconformitiesList'

const auditTypeMap: Record<string, string> = {
  initial: '初审',
  surveillance: '监督',
  recertification: '再认证',
  expansion: '扩项',
}

const statusMap: Record<string, { text: string; color: string }> = {
  planning: { text: '策划中', color: 'default' },
  in_progress: { text: '进行中', color: 'processing' },
  completed: { text: '已完成', color: 'success' },
  cancelled: { text: '已取消', color: 'error' },
}

export default function AuditProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [project, setProject] = useState<any>(null)
  const [progress, setProgress] = useState<any>(null)
  const [aiModalVisible, setAiModalVisible] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResult, setAiResult] = useState<any>(null)

  useEffect(() => {
    if (id) {
      fetchProject()
      fetchProgress()
    }
  }, [id])

  const fetchProject = async () => {
    setLoading(true)
    try {
      const response = await auditProjectApi.get(id!)
      setProject(response.data)
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取项目详情失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchProgress = async () => {
    try {
      const response = await auditProjectApi.getProgress(id!)
      setProgress(response.data)
    } catch (error) {
      console.error('获取进度失败:', error)
    }
  }

  const handleAIPrepare = async () => {
    setAiModalVisible(true)
    setAiLoading(true)
    setAiResult(null)
    try {
      const response = await auditAIApi.prepareAudit(id!)
      setAiResult({
        type: 'prepare',
        data: response.data,
      })
    } catch (error: any) {
      message.error(error.response?.data?.message || 'AI 分析失败')
      setAiModalVisible(false)
    } finally {
      setAiLoading(false)
    }
  }

  const handleAIGenerateReport = async () => {
    setAiModalVisible(true)
    setAiLoading(true)
    setAiResult(null)
    try {
      const response = await auditAIApi.generateReport(id!)
      setAiResult({
        type: 'report',
        data: response.data,
      })
    } catch (error: any) {
      message.error(error.response?.data?.message || 'AI 生成报告失败')
      setAiModalVisible(false)
    } finally {
      setAiLoading(false)
    }
  }

  const renderAIResult = () => {
    if (!aiResult) return null

    if (aiResult.type === 'prepare') {
      const data = aiResult.data
      return (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Card title="审核人天评估" size="small">
            {data.audit_days_assessment}
          </Card>
          <Card title="高风险区域" size="small">
            <ul>
              {data.high_risk_areas?.map((area: string, idx: number) => (
                <li key={idx}>{area}</li>
              ))}
            </ul>
          </Card>
          <Card title="重点审核条款" size="small">
            <ul>
              {data.key_clauses?.map((clause: string, idx: number) => (
                <li key={idx}>{clause}</li>
              ))}
            </ul>
          </Card>
          <Card title="审核注意事项" size="small">
            <ul>
              {data.attention_points?.map((point: string, idx: number) => (
                <li key={idx}>{point}</li>
              ))}
            </ul>
          </Card>
          <Card title="总体建议" size="small">
            {data.overall_suggestion}
          </Card>
        </Space>
      )
    }

    if (aiResult.type === 'report') {
      const data = aiResult.data
      return (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Alert
            message="AI 生成的报告内容"
            description="以下内容由 AI 自动生成，请审核后使用"
            type="info"
            showIcon
          />
          <Card title="3.1 文件化信息" size="small">
            {data.section_3_1}
          </Card>
          <Card title="3.2 目标和指标" size="small">
            {data.section_3_2}
          </Card>
          <Card title="3.3 风险和机遇" size="small">
            {data.section_3_3}
          </Card>
          <Card title="3.4 支持过程" size="small">
            {data.section_3_4}
          </Card>
          <Card title="3.5 运行控制" size="small">
            {data.section_3_5}
          </Card>
          <Card title="3.6 绩效评价" size="small">
            {data.section_3_6}
          </Card>
          <Card title="3.7 改进" size="small">
            {data.section_3_7}
          </Card>
          <Card title="3.8 管理评审" size="small">
            {data.section_3_8}
          </Card>
          <Card title="3.9 总体评价" size="small">
            {data.section_3_9}
          </Card>
        </Space>
      )
    }

    return null
  }

  if (!project) {
    return <div style={{ padding: '24px' }}>加载中...</div>
  }

  const statusConfig = statusMap[project.status] || { text: project.status, color: 'default' }

  return (
    <div style={{ padding: '24px' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card>
          <Space style={{ marginBottom: 16 }}>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/audit-projects')}>
              返回
            </Button>
            <Button
              type="primary"
              icon={<EditOutlined />}
              onClick={() => navigate(`/audit-projects/${id}/edit`)}
            >
              编辑项目
            </Button>
            <Dropdown
              menu={{
                items: [
                  {
                    key: 'word',
                    label: '导出 Word',
                    icon: <FileWordOutlined />,
                    onClick: () => {
                      auditReportApi.exportWord(id!)
                      message.success('正在生成 Word 报告...')
                    },
                  },
                  {
                    key: 'pdf',
                    label: '导出 PDF',
                    icon: <FilePdfOutlined />,
                    onClick: () => {
                      auditReportApi.exportPdf(id!)
                      message.success('正在生成 PDF 报告...')
                    },
                  },
                ],
              }}
            >
              <Button icon={<DownloadOutlined />}>
                导出报告
              </Button>
            </Dropdown>
            <Dropdown
              menu={{
                items: [
                  {
                    key: 'prepare',
                    label: 'AI 审核准备建议',
                    icon: <BulbOutlined />,
                    onClick: handleAIPrepare,
                  },
                  {
                    key: 'generate',
                    label: 'AI 生成报告内容',
                    icon: <FileWordOutlined />,
                    onClick: handleAIGenerateReport,
                  },
                ],
              }}
            >
              <Button type="primary" icon={<RobotOutlined />}>
                AI 助手
              </Button>
            </Dropdown>
          </Space>

          <Descriptions title="项目基本信息" column={2} bordered>
            <Descriptions.Item label="项目编号">{project.project_no}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusConfig.color}>{statusConfig.text}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="项目名称" span={2}>
              {project.title}
            </Descriptions.Item>
            <Descriptions.Item label="审核类型">
              {auditTypeMap[project.audit_type] || project.audit_type}
            </Descriptions.Item>
            <Descriptions.Item label="审核人天">{project.audit_days || 0} 天</Descriptions.Item>
            <Descriptions.Item label="认证体系">
              <Space size={4}>
                {project.certification_systems?.map((sys: string) => (
                  <Tag key={sys}>{sys}</Tag>
                ))}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="审核准则">
              {project.audit_criteria?.join(', ')}
            </Descriptions.Item>
            <Descriptions.Item label="计划开始时间">
              {project.scheduled_start
                ? new Date(project.scheduled_start).toLocaleString()
                : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="计划结束时间">
              {project.scheduled_end ? new Date(project.scheduled_end).toLocaleString() : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="备注" span={2}>
              {project.remarks || '-'}
            </Descriptions.Item>
          </Descriptions>

          {progress && (
            <Card title="项目进度" style={{ marginTop: 16 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <div style={{ marginBottom: 8 }}>
                    审核计划完成度：{progress.plan_items?.completion_rate || 0}%
                  </div>
                  <Progress percent={progress.plan_items?.completion_rate || 0} />
                </div>
                <Descriptions column={4} size="small">
                  <Descriptions.Item label="总计划项">
                    {progress.plan_items?.total || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label="待开始">
                    {progress.plan_items?.pending || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label="进行中">
                    {progress.plan_items?.in_progress || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label="已完成">
                    {progress.plan_items?.completed || 0}
                  </Descriptions.Item>
                </Descriptions>
                <Descriptions column={4} size="small">
                  <Descriptions.Item label="不符合项总数">
                    {progress.nonconformities?.total || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label="严重不符合">
                    {progress.nonconformities?.major || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label="一般不符合">
                    {progress.nonconformities?.minor || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label="观察项">
                    {progress.nonconformities?.observations || 0}
                  </Descriptions.Item>
                </Descriptions>
              </Space>
            </Card>
          )}
        </Card>

        <Card>
          <Tabs
            items={[
              {
                key: 'team',
                label: '审核组',
                children: <TeamManagement projectId={id!} />,
              },
              {
                key: 'plan',
                label: '审核计划',
                children: <PlanManagement projectId={id!} />,
              },
              {
                key: 'records',
                label: '审核记录',
                children: <RecordsList projectId={id!} />,
              },
              {
                key: 'nonconformities',
                label: '不符合项',
                children: <NonconformitiesList projectId={id!} />,
              },
            ]}
          />
        </Card>
      </Space>

      <Modal
        title="AI 助手"
        open={aiModalVisible}
        onCancel={() => setAiModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setAiModalVisible(false)}>
            关闭
          </Button>,
        ]}
        width={800}
      >
        {aiLoading ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16 }}>AI 正在分析中...</div>
          </div>
        ) : (
          renderAIResult()
        )}
      </Modal>
    </div>
  )
}
