import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Empty,
  List,
  Progress,
  Result,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'
import {
  CheckCircleOutlined,
  CloudDownloadOutlined,
  FileDoneOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
  WarningOutlined,
} from '@ant-design/icons'

import {
  projectArtifactApi,
  projectSessionApi,
  saveDownloadedBlob,
  type ProjectArtifact,
  type ProjectAuditSession,
  type ProjectQualityCheck,
} from '@/services/auditProjectApi'

const { Text } = Typography

interface Props {
  projectId: string
}

const unwrap = (response: any) => response?.data ?? response

const toList = <T,>(payload: any, keys: string[] = []): T[] => {
  if (Array.isArray(payload)) return payload
  for (const key of ['items', ...keys]) {
    if (Array.isArray(payload?.[key])) return payload[key]
  }
  return []
}

const artifactTypeText: Record<string, string> = {
  audit_report: '审核报告',
  report: '审核报告',
  area_record: '区域审核记录',
  area_records: '区域审核记录',
  nonconformity_summary: '不符合项汇总',
  nc_summary: '不符合项汇总',
  quality_check: '质量检查结果',
  project_summary: '项目摘要',
  manifest: '资料清单',
  package: '完整审核资料包',
  generation_job: '成果生成任务',
}

const statusConfig: Record<string, { text: string; color: string }> = {
  pending: { text: '待生成', color: 'default' },
  generating: { text: '生成中', color: 'processing' },
  completed: { text: '可下载', color: 'success' },
  ready: { text: '可下载', color: 'success' },
  failed: { text: '生成失败 / 可重试', color: 'error' },
  missing: { text: '文件缺失', color: 'error' },
}

const issueLevelConfig: Record<string, { text: string; color: string }> = {
  blocker: { text: '阻断', color: 'error' },
  error: { text: '阻断', color: 'error' },
  warning: { text: '提醒', color: 'warning' },
  info: { text: '建议', color: 'blue' },
}

const sessionStatusText: Record<string, string> = {
  draft: '草稿',
  active: '进行中',
  in_progress: '进行中',
  completed: '已完成',
  submitted: '已提交',
  cancelled: '已取消',
}

const formatTime = (value?: string) => value ? new Date(value).toLocaleString('zh-CN') : '-'

const formatFileSize = (size?: number) => {
  if (!size) return '-'
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

const getErrorMessage = (error: any, fallback: string) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return String(detail.message)
  return String(error?.response?.data?.message || error?.message || fallback)
}

type QualityIssue = NonNullable<ProjectQualityCheck['issues']>[number]

export default function ProjectArtifacts({ projectId }: Props) {
  const [artifacts, setArtifacts] = useState<ProjectArtifact[]>([])
  const [sessions, setSessions] = useState<ProjectAuditSession[]>([])
  const [quality, setQuality] = useState<ProjectQualityCheck>()
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [downloadingId, setDownloadingId] = useState<string>()
  const [downloadingPackage, setDownloadingPackage] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [artifactResult, sessionResult] = await Promise.allSettled([
        projectArtifactApi.list(projectId),
        projectSessionApi.list(projectId),
      ])

      if (artifactResult.status === 'fulfilled') {
        const artifactPayload = unwrap(artifactResult.value)
        const nextArtifacts = toList<ProjectArtifact>(artifactPayload, ['artifacts'])
        setArtifacts(nextArtifacts)
        setGenerating(nextArtifacts.some((item) =>
          item.artifact_type === 'generation_job' &&
          ['pending', 'generating'].includes(item.status || '')
        ))
        if (artifactPayload?.quality_check || artifactPayload?.quality) {
          setQuality(artifactPayload.quality_check || artifactPayload.quality)
        }
      } else {
        throw artifactResult.reason
      }

      if (sessionResult.status === 'fulfilled') {
        setSessions(toList<ProjectAuditSession>(unwrap(sessionResult.value), ['sessions']))
      }
    } catch (error: any) {
      message.error(getErrorMessage(error, '获取项目成果失败'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [projectId])

  const handleQualityCheck = async () => {
    setChecking(true)
    try {
      const response = await projectArtifactApi.qualityCheck(projectId)
      const payload = unwrap(response) || {}
      setQuality(payload.quality_check || payload.quality || payload)
      message.success('资料完整性与报告一致性检查已完成')
    } catch (error: any) {
      message.error(getErrorMessage(error, '质量检查失败'))
    } finally {
      setChecking(false)
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const qualityResponse = await projectArtifactApi.qualityCheck(projectId)
      const qualityPayload = unwrap(qualityResponse) || {}
      const latestQuality = qualityPayload.quality_check || qualityPayload.quality || qualityPayload
      setQuality(latestQuality)
      if (!latestQuality.passed) {
        message.warning('质量门禁未通过，请先处理阻断项')
        return
      }
      await projectArtifactApi.generate(projectId)
      message.success('成果生成任务已创建，可在列表中查看进度')
      await fetchData()
    } catch (error: any) {
      setGenerating(false)
      message.error(getErrorMessage(error, '生成项目成果失败'))
    }
  }

  const handleRetry = async (artifact: ProjectArtifact) => {
    if (!artifact.id) return
    setGenerating(true)
    try {
      await projectArtifactApi.retry(projectId, artifact.id)
      message.success('失败任务已重新提交')
      await fetchData()
    } catch (error: any) {
      setGenerating(false)
      message.error(getErrorMessage(error, '重试成果生成失败'))
    }
  }

  const handleDownload = async (artifact: ProjectArtifact) => {
    const artifactId = artifact.id || artifact.artifact_type || artifact.type
    if (!artifactId) {
      message.warning('该成果尚未生成可下载文件')
      return
    }

    setDownloadingId(artifactId)
    try {
      const response = await projectArtifactApi.download(projectId, artifactId)
      const type = artifact.artifact_type || artifact.type || 'artifact'
      const stamp = new Date().toISOString().slice(0, 10)
      const rawName = artifact.filename || artifact.file_name || artifact.name || `${type}.docx`
      const safeName = rawName.includes(projectId)
        ? rawName
        : `${projectId.slice(0, 8)}_${stamp}_${rawName}`
      saveDownloadedBlob(response, safeName)
      message.success('文件下载已开始')
    } catch (error: any) {
      const status = error?.response?.status
      const msg = getErrorMessage(error, '下载成果失败')
      if (status === 404 || /不存在|missing|not found/i.test(msg)) {
        message.error('文件缺失或尚未生成，请点击「重试生成」后再下载')
      } else {
        message.error(msg)
      }
    } finally {
      setDownloadingId(undefined)
    }
  }

  const handleDownloadPackage = async () => {
    const latestPackage = artifacts
      .filter((item) => item.artifact_type === 'package' && ['completed', 'ready'].includes(item.status || ''))
      .sort((left, right) => Number(right.version || 0) - Number(left.version || 0))[0]

    if (!latestPackage) {
      setGenerating(true)
      try {
        const qualityResponse = await projectArtifactApi.qualityCheck(projectId)
        const qualityPayload = unwrap(qualityResponse) || {}
        const latestQuality = qualityPayload.quality_check || qualityPayload.quality || qualityPayload
        setQuality(latestQuality)
        if (!latestQuality.passed) {
          message.warning('质量门禁未通过，请先处理阻断项')
          return
        }
        await projectArtifactApi.generate(projectId, { artifact_types: ['package'] })
        message.success('完整资料包生成任务已创建，可在列表中查看进度并在完成后下载')
        await fetchData()
      } catch (error: any) {
        setGenerating(false)
        message.error(getErrorMessage(error, '创建完整资料包生成任务失败'))
      }
      return
    }

    setDownloadingPackage(true)
    try {
      await handleDownload(latestPackage)
    } catch (error: any) {
      message.error(getErrorMessage(error, '导出完整资料包失败'))
    } finally {
      setDownloadingPackage(false)
    }
  }

  // P1-3 修复：避免阻断项同时显示为"建议"和"阻断"
  // 后端返回 blockers/warnings 两个独立数组，不重复渲染
  const rawIssues = Array.isArray(quality?.issues) ? quality.issues : []
  const rawBlockers = Array.isArray(quality?.blockers) ? quality.blockers : []
  const rawWarnings = Array.isArray(quality?.warnings) ? quality.warnings : []
  const rawReminders = Array.isArray(quality?.reminders) ? quality.reminders : []
  // 仅当后端未单独提供 blockers/warnings 时，才从 issues 中提取（向后兼容）
  const needExtractFromIssues = rawBlockers.length === 0 && rawWarnings.length === 0 && rawIssues.length > 0
  const issues = needExtractFromIssues
    ? rawIssues.map((value: any) => ({
        ...value,
        level: String(value.level || 'info'),
        title: value.title ? String(value.title) : undefined,
        message: value.message ? String(value.message) : undefined,
        suggestion: value.suggestion ? String(value.suggestion) : undefined,
      }))
    : [
        ...rawBlockers.map((value: any) => ({
          ...value,
          level: 'blocker',
          title: value.title ? String(value.title) : undefined,
          message: value.message ? String(value.message) : undefined,
          suggestion: value.suggestion ? String(value.suggestion) : undefined,
        })),
        ...rawWarnings.map((value: any) => ({
          ...value,
          level: 'warning',
          title: value.title ? String(value.title) : undefined,
          message: value.message ? String(value.message) : undefined,
          suggestion: value.suggestion ? String(value.suggestion) : undefined,
        })),
        ...rawReminders.map((value: any) => ({
          ...value,
          level: 'info',
          title: value.title ? String(value.title) : undefined,
          message: value.message ? String(value.message) : undefined,
          suggestion: value.suggestion ? String(value.suggestion) : undefined,
        })),
      ]
  const blockerCount = quality?.blocking_count ?? issues.filter((item) => ['blocker', 'error'].includes(item.level || '')).length
  const warningCount = quality?.warning_count ?? issues.filter((item) => item.level === 'warning').length
  const score = Math.max(0, Math.min(100, Number(quality?.score ?? quality?.overall_score ?? quality?.completeness_score ?? 0)))
  const passed = quality?.passed ?? (Boolean(quality) && blockerCount === 0)
  // P2-2 修复：默认仅展示每个类型的最新版本，旧版本折叠到「查看历史版本」
  const [showAllVersions, setShowAllVersions] = useState(false)
  const visibleArtifacts = useMemo(() => {
    if (showAllVersions) return artifacts
    // 每种类型仅保留版本号最大的
    const latestByType = new Map<string, ProjectArtifact>()
    for (const item of artifacts) {
      const type = item.artifact_type || item.type || 'unknown'
      const existing = latestByType.get(type)
      if (!existing || Number(item.version || 0) > Number(existing.version || 0)) {
        latestByType.set(type, item)
      }
    }
    return Array.from(latestByType.values())
  }, [artifacts, showAllVersions])
  const hiddenVersionCount = artifacts.length - visibleArtifacts.length

  const completedSessions = useMemo(
    () => sessions.filter((session) => ['completed', 'submitted'].includes(session.status || '')).length,
    [sessions]
  )

  const activeGenerationKey = artifacts
    .filter((item) => item.artifact_type === 'generation_job' && ['pending', 'generating'].includes(item.status || ''))
    .map((item) => `${item.id}:${item.status}:${item.progress}`)
    .join('|')

  useEffect(() => {
    if (!activeGenerationKey) return
    const timer = window.setTimeout(fetchData, 1500)
    return () => window.clearTimeout(timer)
  }, [activeGenerationKey, projectId])

  const columns: TableColumnsType<ProjectArtifact> = [
    {
      title: '成果',
      key: 'name',
      render: (_, artifact) => {
        const type = artifact.artifact_type || artifact.type || ''
        return (
          <Space direction="vertical" size={0}>
            <Text strong>{artifact.name || artifact.filename || artifact.file_name || artifactTypeText[type] || type || '项目成果'}</Text>
            {artifact.error_message ? <Text type="danger">{artifact.error_message}</Text> : null}
          </Space>
        )
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (value?: string) => {
        const config = statusConfig[value || 'pending'] || { text: value || '待生成', color: 'default' }
        return <Tag color={config.color}>{config.text}</Tag>
      },
    },
    {
      title: '版本',
      key: 'version',
      width: 80,
      render: (_, artifact) => artifact.version ? <Tag color="blue">v{artifact.version}</Tag> : <Text type="secondary">-</Text>,
    },
    {
      title: '生成时间',
      key: 'time',
      width: 190,
      render: (_, artifact) => formatTime(artifact.generated_at || artifact.updated_at),
    },
    {
      title: '大小',
      key: 'size',
      width: 100,
      render: (_, artifact) => formatFileSize(artifact.file_size || artifact.size),
    },
    {
      title: '进度',
      key: 'progress',
      width: 160,
      render: (_, artifact) => artifact.artifact_type === 'generation_job'
        ? <Progress percent={Math.round(Number(artifact.progress || 0))} size="small" status={artifact.status === 'failed' ? 'exception' : undefined} />
        : <Text type="secondary">100%</Text>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, artifact) => {
        const artifactId = artifact.id || artifact.artifact_type || artifact.type || ''
        if (artifact.artifact_type === 'generation_job') {
          return artifact.status === 'failed' ? (
            <Button
              icon={<ReloadOutlined />}
              loading={generating}
              onClick={() => handleRetry(artifact)}
            >
              重试
            </Button>
          ) : <Text type="secondary">{artifact.status === 'completed' ? '已完成' : '处理中'}</Text>
        }
        const canDownload = Boolean(artifactId) && (
          artifact.available === true ||
          !artifact.status ||
          ['completed', 'ready'].includes(artifact.status)
        )
        return (
          <Button
            icon={<CloudDownloadOutlined />}
            loading={downloadingId === artifactId}
            disabled={!canDownload}
            onClick={() => handleDownload(artifact)}
          >
            下载
          </Button>
        )
      },
    },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Row gutter={[16, 16]} align="middle">
          <Col flex="auto">
            <Space direction="vertical" size={4}>
              <Text strong style={{ fontSize: 18 }}>报告与项目成果</Text>
              <Text type="secondary">先检查资料质量，再由 Agent 生成报告、区域记录和完整归档包。</Text>
            </Space>
          </Col>
          <Col>
            <Space wrap>
              <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>刷新</Button>
              <Button
                icon={<SafetyCertificateOutlined />}
                loading={checking}
                onClick={handleQualityCheck}
              >
                运行质量检查
              </Button>
              <Button
                type="primary"
                icon={<SyncOutlined />}
                loading={generating}
                disabled={!passed || generating}
                onClick={handleGenerate}
              >
                生成/更新全部成果
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card size="small"><Statistic title="审核会话" value={sessions.length} suffix="个" /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small"><Statistic title="已完成会话" value={completedSessions} suffix="个" /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small"><Statistic title="可下载成果" value={artifacts.filter((item) => item.artifact_type !== 'generation_job' && ['completed', 'ready'].includes(item.status || '')).length} suffix="项" /></Card>
        </Col>
      </Row>

      <Card title={<Space><SafetyCertificateOutlined />资料质量门禁</Space>}>
        {!quality ? (
          <Result
            icon={<SafetyCertificateOutlined />}
            title="尚未运行质量检查"
            subTitle="检查会核对计划覆盖、证据完整性、不符合项状态以及报告内容一致性。"
            extra={<Button onClick={handleQualityCheck} loading={checking}>立即检查</Button>}
          />
        ) : (
          <Row gutter={[24, 24]}>
            <Col xs={24} md={8} style={{ textAlign: 'center' }}>
              <Progress
                type="dashboard"
                percent={score}
                status={passed ? 'success' : blockerCount > 0 ? 'exception' : 'normal'}
                format={(value) => `${value ?? 0} 分`}
              />
              <div>
                <Tag color={passed ? 'success' : 'error'} icon={passed ? <CheckCircleOutlined /> : <WarningOutlined />}>
                  {passed ? '质量门禁通过' : `仍有 ${blockerCount} 项阻断问题`}
                </Tag>
              </div>
            </Col>
            <Col xs={24} md={16}>
              {issues.length === 0 ? (
                <Alert type="success" showIcon message="未发现阻断问题" description="可以生成报告并导出完整资料包。" />
              ) : (
                <List
                  dataSource={issues}
                  renderItem={(issue) => {
                    const config = issueLevelConfig[issue.level || issue.type || 'info'] || issueLevelConfig.info
                    return (
                      <List.Item>
                        <List.Item.Meta
                          avatar={<Tag color={config.color}>{config.text}</Tag>}
                          title={issue.title || issue.message || '资料问题'}
                          description={issue.suggestion || (issue.title ? issue.message : undefined)}
                        />
                      </List.Item>
                    )
                  }}
                />
              )}
              <Space style={{ marginTop: 12 }} wrap>
                <Text type={blockerCount > 0 ? 'danger' : undefined}>阻断项：{blockerCount}</Text>
                <Text type={warningCount > 0 ? 'warning' : 'secondary'}>提醒项：{warningCount}</Text>
                <Text type="secondary">检查时间：{formatTime(quality.checked_at)}</Text>
              </Space>
            </Col>
          </Row>
        )}
      </Card>

      <Card title={<Space><FileDoneOutlined />已生成成果</Space>}>
        <Table<ProjectArtifact>
          rowKey={(artifact) => artifact.id || `${artifact.artifact_type || artifact.type}-${artifact.filename || artifact.file_name || artifact.name}`}
          columns={columns}
          dataSource={visibleArtifacts}
          loading={loading}
          pagination={false}
          locale={{ emptyText: <Empty description="尚未生成项目成果" /> }}
        />
        {hiddenVersionCount > 0 && (
          <div style={{ marginTop: 12, textAlign: 'center' }}>
            <Button type="link" onClick={() => setShowAllVersions(!showAllVersions)}>
              {showAllVersions ? '收起历史版本' : `查看历史版本（${hiddenVersionCount} 个）`}
            </Button>
          </div>
        )}
      </Card>

      <Collapse
        items={[
          {
            key: 'sessions',
            label: `审核会话来源（${sessions.length}）`,
            children: sessions.length > 0 ? (
              <List
                dataSource={sessions}
                renderItem={(session) => (
                  <List.Item
                    extra={<Tag>{sessionStatusText[session.status || ''] || session.status || '未知状态'}</Tag>}
                  >
                    <List.Item.Meta
                      title={session.title || session.area_name || '审核会话'}
                      description={`进度 ${Math.round(Number(session.progress || 0))}% · 异常 ${session.exception_count || 0} 项 · 更新于 ${formatTime(session.updated_at || session.created_at)}`}
                    />
                  </List.Item>
                )}
              />
            ) : <Empty description="当前项目暂无审核会话" />,
          },
        ]}
      />

      <Card>
        <Row gutter={[16, 16]} align="middle">
          <Col flex="auto">
            <Alert
              type={blockerCount > 0 ? 'warning' : 'info'}
              showIcon
              message="完整资料包"
                description={blockerCount > 0 ? '请先处理全部阻断项并重新运行质量检查，门禁通过后才能导出。' : '资料包会作为可重试的后台任务生成，完成后可下载已固化版本；面向用户的交付物均为 Word 文档（项目摘要、审核计划、区域记录、审核报告、不符合项汇总、完整性检查与文件清单），并附项目上传的原始资料。'}
            />
          </Col>
          <Col>
            <Button
              size="large"
              icon={<CloudDownloadOutlined />}
                loading={downloadingPackage || generating}
                disabled={!passed || generating}
                onClick={handleDownloadPackage}
              >
                生成或下载完整资料包
            </Button>
          </Col>
        </Row>
      </Card>
    </Space>
  )
}
