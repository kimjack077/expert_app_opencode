import { useState, useEffect, useRef } from 'react'
import { Card, Descriptions, Tag, Tabs, Button, Space, message, Progress, Dropdown, Modal, Spin, Alert, Typography } from 'antd'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  EditOutlined, 
  ArrowLeftOutlined, 
  FileWordOutlined, 
  RobotOutlined,
  BulbOutlined,
  DatabaseOutlined,
  FileDoneOutlined,
  ScheduleOutlined,
  CopyOutlined,
  PauseCircleOutlined,
  CheckOutlined,
} from '@ant-design/icons'
import { auditProjectApi, auditAIApi } from '@/services/auditProjectApi'
import TeamManagement from './components/TeamManagement'
import PlanManagement from './components/PlanManagement'
import RecordsList from './components/RecordsList'
import NonconformitiesList from './components/NonconformitiesList'
import ProjectDocuments from './components/ProjectDocuments'
import ProjectArtifacts from './components/ProjectArtifacts'
import MeetingManagement from './components/MeetingManagement'
import MarkdownView from '@/components/common/MarkdownView'

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
  const [aiModalTitle, setAiModalTitle] = useState('AI 审核准备建议')
  const [aiStreamingText, setAiStreamingText] = useState('')
  const [aiIsStreaming, setAiIsStreaming] = useState(false)
  const aiAbortControllerRef = useRef<AbortController | null>(null)
  const [activeTab, setActiveTab] = useState('team')

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
    if (aiAbortControllerRef.current) {
      aiAbortControllerRef.current.abort()
    }
    const controller = new AbortController()
    aiAbortControllerRef.current = controller

    setAiModalTitle('AI 审核准备建议')
    setAiStreamingText('')
    setAiIsStreaming(true)
    setAiModalVisible(true)

    try {
      const generator = auditAIApi.prepareAuditStream(id!, controller.signal)
      for await (const chunk of generator) {
        if (chunk.type === 'content' && chunk.content) {
          setAiStreamingText((prev) => prev + chunk.content)
        } else if (chunk.type === 'error') {
          message.error(chunk.content || 'AI 生成出错')
        }
      }
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        message.error(error.message || 'AI 准备建议生成失败')
      }
    } finally {
      setAiIsStreaming(false)
      aiAbortControllerRef.current = null
    }
  }

  const handleAIGenerateReport = async () => {
    if (aiAbortControllerRef.current) {
      aiAbortControllerRef.current.abort()
    }
    const controller = new AbortController()
    aiAbortControllerRef.current = controller

    setAiModalTitle('AI 生成审核报告叙述性评价')
    setAiStreamingText('')
    setAiIsStreaming(true)
    setAiModalVisible(true)

    try {
      const generator = auditAIApi.generateReportStream(id!, controller.signal)
      for await (const chunk of generator) {
        if (chunk.type === 'content' && chunk.content) {
          setAiStreamingText((prev) => prev + chunk.content)
        } else if (chunk.type === 'error') {
          message.error(chunk.content || 'AI 生成出错')
        }
      }
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        message.error(error.message || 'AI 报告评价生成失败')
      }
    } finally {
      setAiIsStreaming(false)
      aiAbortControllerRef.current = null
    }
  }

  const handleStopStreaming = () => {
    if (aiAbortControllerRef.current) {
      aiAbortControllerRef.current.abort()
      aiAbortControllerRef.current = null
      setAiIsStreaming(false)
      message.info('已停止生成')
    }
  }

  const handleCopyAiContent = async () => {
    if (!aiStreamingText) return
    try {
      await navigator.clipboard.writeText(aiStreamingText)
      message.success('已复制到剪贴板')
    } catch {
      message.error('复制失败，请手动选取复制')
    }
  }

  const renderStreamingMarkdown = (text: string) => {
    if (!text && aiIsStreaming) {
      return (
        <div style={{ textAlign: 'center', padding: '48px 0', color: '#8c8c8c' }}>
          <Spin size="default" style={{ marginRight: 8 }} />
          <span>AI 专家正在分析项目背景与历史记录，即将开始实时流式输出...</span>
        </div>
      )
    }

    if (!text && !aiIsStreaming) {
      return <div style={{ color: '#999', padding: '24px', textAlign: 'center' }}>暂无生成内容</div>
    }

    return <MarkdownView content={text} />
  }

  if (!project) {
    return <div style={{ padding: '24px' }}>加载中...</div>
  }

  const statusConfig = statusMap[project.status] || { text: project.status, color: 'default' }

  return (
    <div style={{ padding: '24px' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card
          bodyStyle={{ padding: '16px 20px' }}
          style={{
            borderRadius: 12,
            background: 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
            border: '1px solid #e2e8f0',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          }}
        >
          {/* 顶部行：返回、项目标题与核心状态、功能操作按钮 */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 12,
              marginBottom: 12,
            }}
          >
            <Space size={10} wrap align="center">
              <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/audit-projects')}>
                返回
              </Button>
              <span style={{ fontSize: 18, fontWeight: 700, color: '#0f172a' }}>
                {project.title}
              </span>
              <Tag color="blue" style={{ fontSize: 12, margin: 0, fontFamily: 'monospace' }}>
                {project.project_no}
              </Tag>
              <Tag color={statusConfig.color} style={{ fontSize: 12, margin: 0, fontWeight: 600 }}>
                {statusConfig.text}
              </Tag>
              <Tag color="cyan" style={{ fontSize: 12, margin: 0 }}>
                {auditTypeMap[project.audit_type] || project.audit_type} · {project.audit_days || 0}人天
              </Tag>
            </Space>

            <Space wrap size={8}>
              <Button
                icon={<EditOutlined />}
                onClick={() => navigate(`/audit-projects/${id}/edit`)}
              >
                编辑项目
              </Button>
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
                      label: 'AI 报告叙述性评价',
                      icon: <FileWordOutlined />,
                      onClick: handleAIGenerateReport,
                    },
                    {
                      key: 'artifacts',
                      label: '报告与资料包',
                      icon: <FileDoneOutlined />,
                      onClick: () => setActiveTab('artifacts'),
                    },
                    {
                      key: 'documents',
                      label: '项目资料与知识库',
                      icon: <DatabaseOutlined />,
                      onClick: () => setActiveTab('documents'),
                    },
                  ],
                }}
              >
                <Button type="primary" icon={<RobotOutlined />}>
                  AI 助手
                </Button>
              </Dropdown>
            </Space>
          </div>

          {/* 中间信息栅格：紧凑 1 行/2 行排布 */}
          <div
            style={{
              backgroundColor: '#ffffff',
              borderRadius: 8,
              border: '1px solid #e2e8f0',
              padding: '10px 14px',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '8px 16px',
              fontSize: 13,
              marginBottom: 12,
            }}
          >
            <div>
              <span style={{ color: '#64748b' }}>认证体系：</span>
              <Space size={3}>
                {project.certification_systems?.map((sys: string) => (
                  <Tag
                    key={sys}
                    color={sys === 'Q' ? 'blue' : sys === 'E' ? 'green' : sys === 'S' ? 'orange' : 'cyan'}
                    style={{ margin: 0, fontWeight: 600, fontSize: 11 }}
                  >
                    {sys}
                  </Tag>
                ))}
              </Space>
            </div>
            <div
              style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
              title={project.audit_criteria?.join(', ')}
            >
              <span style={{ color: '#64748b' }}>审核准则：</span>
              <span style={{ color: '#1e293b', fontWeight: 500 }}>
                {project.audit_criteria?.join(', ') || '-'}
              </span>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>审核排期：</span>
              <span style={{ color: '#1e293b', fontWeight: 500 }}>
                {project.scheduled_start ? String(project.scheduled_start).slice(0, 10) : '-'} ~{' '}
                {project.scheduled_end ? String(project.scheduled_end).slice(0, 10) : '-'}
              </span>
            </div>
            {project.remarks && (
              <div style={{ gridColumn: '1 / -1', color: '#64748b', fontSize: 12 }}>
                <span>备注：</span>
                <span style={{ color: '#334155' }}>{project.remarks}</span>
              </div>
            )}
          </div>

          {/* 底部紧凑工作台行动条：进度指标 + 快捷导航按钮 */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 12,
              paddingTop: 8,
              borderTop: '1px dashed #e2e8f0',
            }}
          >
            {/* 左侧紧凑指标 */}
            <Space size={16} wrap align="center">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, color: '#64748b' }}>计划进度:</span>
                <Progress
                  percent={progress?.plan_items?.completion_rate || 0}
                  size="small"
                  style={{ width: 90, margin: 0 }}
                />
              </div>
              <div style={{ fontSize: 12, color: '#475569' }}>
                计划项: <strong style={{ color: '#0f172a' }}>{progress?.plan_items?.total || 0}</strong>{' '}
                (已完: <strong style={{ color: '#16a34a' }}>{progress?.plan_items?.completed || 0}</strong>, 进行:{' '}
                <strong style={{ color: '#0284c7' }}>{progress?.plan_items?.in_progress || 0}</strong>, 待办:{' '}
                <strong style={{ color: '#94a3b8' }}>{progress?.plan_items?.pending || 0}</strong>)
              </div>
              <div style={{ fontSize: 12, color: '#475569' }}>
                不符合项:{' '}
                <strong style={{ color: (progress?.nonconformities?.total || 0) > 0 ? '#ef4444' : '#16a34a' }}>
                  {progress?.nonconformities?.total || 0}
                </strong>
              </div>
            </Space>

            {/* 右侧快速工作流导航按钮组 */}
            <Space size={6} wrap>
              <Button
                size="small"
                type={activeTab === 'team' ? 'primary' : 'default'}
                onClick={() => setActiveTab('team')}
              >
                审核组
              </Button>
              <Button
                size="small"
                type={activeTab === 'plan' ? 'primary' : 'default'}
                onClick={() => setActiveTab('plan')}
              >
                审核计划
              </Button>
              <Button
                size="small"
                type={activeTab === 'records' ? 'primary' : 'default'}
                onClick={() => setActiveTab('records')}
              >
                现场记录
              </Button>
              <Button
                size="small"
                type={activeTab === 'meetings' ? 'primary' : 'default'}
                onClick={() => setActiveTab('meetings')}
              >
                会议沟通
              </Button>
              <Button
                size="small"
                type={activeTab === 'nonconformities' ? 'primary' : 'default'}
                onClick={() => setActiveTab('nonconformities')}
              >
                不符合项
                {(progress?.nonconformities?.total || 0) > 0
                  ? ` (${progress.nonconformities.total})`
                  : ''}
              </Button>
              <Button
                size="small"
                type={activeTab === 'documents' ? 'primary' : 'default'}
                onClick={() => setActiveTab('documents')}
              >
                项目资料
              </Button>
              <Button
                size="small"
                type={activeTab === 'artifacts' ? 'primary' : 'default'}
                style={
                  activeTab === 'artifacts'
                    ? undefined
                    : {
                        borderColor: '#86efac',
                        color: '#15803d',
                        backgroundColor: '#f0fdf4',
                        fontWeight: 600,
                      }
                }
                onClick={() => setActiveTab('artifacts')}
              >
                质量门禁 / 生成资料包
              </Button>
            </Space>
          </div>
        </Card>

        <Card>
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
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
                label: '现场记录',
                children: <RecordsList projectId={id!} />,
              },
              {
                key: 'meetings',
                label: (
                  <Space size={6}>
                    <ScheduleOutlined />
                    会议与沟通
                  </Space>
                ),
                children: <MeetingManagement projectId={id!} />,
              },
              {
                key: 'nonconformities',
                label: '不符合项',
                children: <NonconformitiesList projectId={id!} />,
              },
              {
                key: 'documents',
                label: (
                  <Space size={6}>
                    <DatabaseOutlined />
                    项目资料与知识库
                  </Space>
                ),
                children: <ProjectDocuments projectId={id!} />,
              },
              {
                key: 'artifacts',
                label: (
                  <Space size={6}>
                    <FileDoneOutlined />
                    报告与资料包
                  </Space>
                ),
                children: <ProjectArtifacts projectId={id!} />,
              },
            ]}
          />
        </Card>
      </Space>

      <Modal
        title={
          <Space>
            <RobotOutlined style={{ color: '#1677ff' }} />
            <span>{aiModalTitle}</span>
            {aiIsStreaming && <Tag color="processing">正在实时输出中...</Tag>}
            {!aiIsStreaming && aiStreamingText && <Tag color="success">生成完成</Tag>}
          </Space>
        }
        open={aiModalVisible}
        onCancel={() => {
          if (aiIsStreaming) {
            handleStopStreaming()
          }
          setAiModalVisible(false)
        }}
        footer={[
          aiIsStreaming && (
            <Button
              key="stop"
              danger
              icon={<PauseCircleOutlined />}
              onClick={handleStopStreaming}
            >
              停止生成
            </Button>
          ),
          <Button
            key="copy"
            icon={<CopyOutlined />}
            disabled={!aiStreamingText}
            onClick={handleCopyAiContent}
          >
            一键复制
          </Button>,
          <Button
            key="close"
            type="primary"
            onClick={() => {
              if (aiIsStreaming) {
                handleStopStreaming()
              }
              setAiModalVisible(false)
            }}
          >
            完成
          </Button>,
        ].filter(Boolean)}
        width={850}
        destroyOnHidden
      >
        <div
          style={{
            maxHeight: '65vh',
            overflowY: 'auto',
            padding: '12px 16px',
            backgroundColor: '#fafafa',
            borderRadius: 8,
            border: '1px solid #f0f0f0',
          }}
        >
          {renderStreamingMarkdown(aiStreamingText)}
        </div>
      </Modal>
    </div>
  )
}
