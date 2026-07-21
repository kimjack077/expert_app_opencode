import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  List,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Steps,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
  message,
} from 'antd'
import type { TableColumnsType, UploadProps } from 'antd'
import {
  CheckCircleOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  FileSearchOutlined,
  InboxOutlined,
  LoadingOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons'

import {
  projectDocumentApi,
  type ProjectDocument,
  type ProjectKnowledgeHit,
} from '@/services/auditProjectApi'

const { Dragger } = Upload
const { Paragraph, Text, Title } = Typography

interface Props {
  projectId: string
}

const unwrap = (response: any) => response?.data ?? response

const toList = <T,>(payload: any): T[] => {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.documents)) return payload.documents
  if (Array.isArray(payload?.results)) return payload.results
  if (Array.isArray(payload?.hits)) return payload.hits
  if (Array.isArray(payload?.matches)) return payload.matches
  return []
}

const documentName = (document: ProjectDocument) =>
  document.title || document.original_filename || document.file_name || document.filename || document.name || '未命名资料'

const statusConfig: Record<string, { text: string; color: string }> = {
  pending: { text: '等待解析', color: 'default' },
  parsing: { text: '解析中', color: 'processing' },
  indexing: { text: '建立索引中', color: 'processing' },
  processing: { text: '解析中', color: 'processing' },
  completed: { text: '已索引', color: 'success' },
  indexed: { text: '已索引', color: 'success' },
  ready: { text: '已索引', color: 'success' },
  uploaded: { text: '等待解析', color: 'default' },
  failed: { text: '解析失败', color: 'error' },
}

const categoryText: Record<string, string> = {
  organization: 'A 组织/资质/合同',
  audit_plan: 'B 审核通知/方案/计划',
  standard: '法律法规与标准',
  procedure: '程序文件',
  manual: '体系手册',
  audit_material: 'D 审核过程资料',
  record: '企业记录',
  previous_audit: '历史审核资料',
  certificate: 'Z 证书及其他',
  other: '其他',
}

const formatFileSize = (size?: number) => {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

/** Simulated stage timeline while the embedding + retrieval request is in flight. */
const SEARCH_STAGES = [
  { key: 'embed', title: '理解检索问题', description: '调用嵌入模型向量化查询' },
  { key: 'project', title: '匹配项目资料', description: '在本项目知识片段中语义检索' },
  { key: 'global', title: '补充法规库', description: '同步检索全局法规与标准' },
  { key: 'rank', title: '排序整理结果', description: '按相关度汇总并标注来源' },
] as const

const stageIndexFromElapsed = (seconds: number) => {
  if (seconds < 1.5) return 0
  if (seconds < 4) return 1
  if (seconds < 8) return 2
  return 3
}

export default function ProjectDocuments({ projectId }: Props) {
  const [documents, setDocuments] = useState<ProjectDocument[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [category, setCategory] = useState<string>()
  const [reindexingId, setReindexingId] = useState<string>()
  const [deletingId, setDeletingId] = useState<string>()
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [searchAttempted, setSearchAttempted] = useState(false)
  const [hits, setHits] = useState<ProjectKnowledgeHit[]>([])
  const [searchStage, setSearchStage] = useState(0)
  const [searchElapsed, setSearchElapsed] = useState(0)
  const [lastSearchMeta, setLastSearchMeta] = useState<{
    query: string
    count: number
    durationMs: number
  } | null>(null)
  const searchTimersRef = useRef<{ tick?: number; stages?: number }>({})

  const fetchDocuments = async () => {
    setLoading(true)
    try {
      const response = await projectDocumentApi.list(projectId)
      setDocuments(toList<ProjectDocument>(unwrap(response)))
    } catch (error: any) {
      message.error(error.response?.data?.detail || error.response?.data?.message || '获取项目资料失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDocuments()
  }, [projectId])

  useEffect(() => {
    // Only poll while indexing is in progress; avoid hammering the list API.
    const hasPendingDocument = documents.some((item) =>
      ['uploaded', 'pending', 'parsing', 'processing', 'indexing'].includes(item.parse_status || item.status || '')
    )
    if (!hasPendingDocument) return
    const timer = window.setTimeout(fetchDocuments, 8000)
    return () => window.clearTimeout(timer)
  }, [documents, projectId])

  const uploadProps: UploadProps = {
    name: 'file',
    multiple: true,
    showUploadList: true,
    accept: '.pdf,.doc,.docx,.xls,.xlsx,.txt,.md,.csv,.json,.zip',
    beforeUpload: (file) => {
      if (file.size > 50 * 1024 * 1024) {
        message.error(`${file.name} 超过 50 MB，请拆分后再上传`)
        return Upload.LIST_IGNORE
      }
      if (/\.(doc|xls)$/i.test(file.name)) {
        message.info(`${file.name} 将保留原件归档；旧格式需转换为 DOCX/XLSX 后才能全文检索`)
      }
      return true
    },
    customRequest: async ({ file, onError, onSuccess }) => {
      setUploading(true)
      try {
        const response = await projectDocumentApi.upload(projectId, file as File, category)
        onSuccess?.(response)
        message.success('资料已上传，系统正在解析并建立项目专属索引')
        await fetchDocuments()
      } catch (error: any) {
        onError?.(error)
        message.error(error.response?.data?.detail || error.response?.data?.message || '资料上传失败')
      } finally {
        setUploading(false)
      }
    },
  }

  const handleReindex = async (documentId: string) => {
    setReindexingId(documentId)
    try {
      await projectDocumentApi.reindex(projectId, documentId)
      message.success('已重新提交解析和索引任务')
      await fetchDocuments()
    } catch (error: any) {
      message.error(error.response?.data?.detail || error.response?.data?.message || '重建索引失败')
    } finally {
      setReindexingId(undefined)
    }
  }

  const handleDelete = async (documentId: string) => {
    setDeletingId(documentId)
    try {
      await projectDocumentApi.remove(projectId, documentId)
      message.success('项目资料及其索引已删除')
      await fetchDocuments()
    } catch (error: any) {
      message.error(error.response?.data?.detail || error.response?.data?.message || '删除资料失败')
    } finally {
      setDeletingId(undefined)
    }
  }

  const clearSearchTimers = () => {
    if (searchTimersRef.current.tick) {
      window.clearInterval(searchTimersRef.current.tick)
      searchTimersRef.current.tick = undefined
    }
    if (searchTimersRef.current.stages) {
      window.clearInterval(searchTimersRef.current.stages)
      searchTimersRef.current.stages = undefined
    }
  }

  useEffect(() => () => clearSearchTimers(), [])

  const handleSearch = async (value?: string) => {
    const keyword = (value ?? query).trim()
    if (!keyword) {
      message.info('请输入需要从项目资料中查找的问题')
      return
    }
    if (searching) return

    setSearching(true)
    setSearchAttempted(true)
    setHits([])
    setLastSearchMeta(null)
    setSearchStage(0)
    setSearchElapsed(0)

    const startedAt = performance.now()
    clearSearchTimers()
    searchTimersRef.current.tick = window.setInterval(() => {
      const elapsed = (performance.now() - startedAt) / 1000
      setSearchElapsed(elapsed)
      setSearchStage(stageIndexFromElapsed(elapsed))
    }, 200)

    try {
      const response = await projectDocumentApi.search(projectId, keyword)
      const results = toList<ProjectKnowledgeHit>(unwrap(response))
      setHits(results)
      setSearchStage(SEARCH_STAGES.length - 1)
      setLastSearchMeta({
        query: keyword,
        count: results.length,
        durationMs: Math.round(performance.now() - startedAt),
      })
    } catch (error: any) {
      setHits([])
      setLastSearchMeta(null)
      message.error(error.response?.data?.detail || error.response?.data?.message || '项目知识检索失败')
    } finally {
      clearSearchTimers()
      setSearchElapsed((performance.now() - startedAt) / 1000)
      setSearching(false)
    }
  }

  const indexedCount = useMemo(
    () => documents.filter((item) => ['completed', 'indexed', 'ready'].includes(item.parse_status || item.status || '')).length,
    [documents]
  )
  const chunkCount = useMemo(
    () => documents.reduce((total, item) => total + Number(item.chunk_count || 0), 0),
    [documents]
  )

  const columns: TableColumnsType<ProjectDocument> = [
    {
      title: '资料',
      key: 'name',
      render: (_, item) => (
        <Space direction="vertical" size={0}>
          <Space wrap size={6}>
            <Text strong>{documentName(item)}</Text>
            {Boolean((item.metadata as any)?.quarantined || (item.metadata as any)?.consistency?.risk_level === 'high') && (
              <Tag color="error">一致性风险·已隔离</Tag>
            )}
            {Boolean((item.metadata as any)?.archive_only) && <Tag color="gold">仅归档</Tag>}
          </Space>
          {item.summary && (
            <Text type="secondary" ellipsis style={{ maxWidth: 420 }} title={item.summary}>
              {item.summary}
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: '分类',
      key: 'category',
      width: 120,
      render: (_, item) => {
        const value = item.document_type || item.category
        return value ? <Tag>{categoryText[value] || value}</Tag> : <Text type="secondary">自动识别</Text>
      },
    },
    {
      title: '索引状态',
      key: 'status',
      width: 120,
      render: (_, item) => {
        const value = item.parse_status || item.status || 'pending'
        const config = statusConfig[value] || { text: value, color: 'default' }
        const tag = <Tag color={config.color}>{config.text}</Tag>
        return item.parse_error ? <Tooltip title={item.parse_error}>{tag}</Tooltip> : tag
      },
    },
    {
      title: '知识片段',
      dataIndex: 'chunk_count',
      width: 100,
      render: (value?: number) => value ?? 0,
    },
    {
      title: '大小',
      key: 'size',
      width: 100,
      render: (_, item) => formatFileSize(item.file_size || item.size),
    },
    {
      title: '操作',
      key: 'actions',
      width: 112,
      fixed: 'right',
      render: (_, item) => (
        <Space size={4}>
          <Tooltip title="重新解析并建立索引">
            <Button
              type="text"
              icon={<ReloadOutlined />}
              aria-label={`重新索引 ${documentName(item)}`}
              loading={reindexingId === item.id}
              disabled={Boolean(deletingId)}
              onClick={() => handleReindex(item.id)}
            />
          </Tooltip>
          <Popconfirm
            title="删除项目资料"
            description="资料及其项目知识索引将同时删除，此操作不可撤销。"
            okText="删除"
            okButtonProps={{ danger: true }}
            cancelText="取消"
            onConfirm={() => handleDelete(item.id)}
          >
            <Tooltip title="删除">
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                aria-label={`删除 ${documentName(item)}`}
                loading={deletingId === item.id}
                disabled={Boolean(reindexingId)}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="项目专属知识库"
        description="上传的资料只用于当前审核项目。Agent 会在生成审核建议、证据判断和报告时引用这些资料，并保留来源。"
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card size="small"><Statistic title="项目资料" value={documents.length} suffix="份" /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small"><Statistic title="已完成索引" value={indexedCount} suffix="份" /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small"><Statistic title="可检索片段" value={chunkCount} suffix="条" /></Card>
        </Col>
      </Row>

      <Card
        title={<Space><DatabaseOutlined />资料接入</Space>}
        extra={
          <Select
            allowClear
            value={category}
            placeholder="资料分类（可选）"
            style={{ width: 180 }}
            onChange={setCategory}
            options={[
              { label: 'A 组织/资质/合同', value: 'organization' },
              { label: 'B 审核通知/方案/计划', value: 'audit_plan' },
              { label: '法律法规与标准', value: 'standard' },
              { label: '程序文件', value: 'procedure' },
              { label: '体系手册', value: 'manual' },
              { label: 'D 审核过程资料', value: 'audit_material' },
              { label: '企业记录', value: 'record' },
              { label: '历史审核资料', value: 'previous_audit' },
              { label: 'Z 证书及其他', value: 'certificate' },
              { label: '其他', value: 'other' },
            ]}
          />
        }
      >
        <Dragger {...uploadProps} disabled={uploading}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">{uploading ? '正在上传并解析…' : '点击或拖拽多份资料到这里批量上传'}</p>
          <p className="ant-upload-hint">PDF、DOCX、XLSX 等会建立索引；旧 DOC/XLS 保留原件归档并提示转换，不会进入 AI 检索</p>
        </Dragger>
      </Card>

      <Card
        title="资料列表"
        extra={
          <Button icon={<ReloadOutlined />} onClick={fetchDocuments} loading={loading}>
            刷新状态
          </Button>
        }
      >
        <Table<ProjectDocument>
          rowKey="id"
          columns={columns}
          dataSource={documents}
          loading={loading}
          pagination={{ pageSize: 8, hideOnSinglePage: true }}
          scroll={{ x: 820 }}
          locale={{ emptyText: <Empty description="尚未上传项目资料" /> }}
        />
      </Card>

      <Card
        title={<Space><FileSearchOutlined />在项目资料中查找</Space>}
        extra={
          <Text type="secondary" style={{ fontSize: 12 }}>
            语义检索（嵌入模型），通常需数秒，请稍候
          </Text>
        }
      >
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={query}
            prefix={<SearchOutlined />}
            placeholder="例如：上次审核有哪些未关闭问题？本项目适用哪些标准？"
            allowClear
            disabled={searching}
            onChange={(event) => setQuery(event.target.value)}
            onPressEnter={() => handleSearch()}
            aria-label="项目知识检索问题"
          />
          <Button type="primary" loading={searching} onClick={() => handleSearch()}>
            {searching ? '检索中…' : '检索'}
          </Button>
        </Space.Compact>

        <div style={{ marginTop: 16 }} aria-live="polite" aria-busy={searching}>
          {searching && (
            <div
              style={{
                padding: 20,
                borderRadius: 8,
                background: 'linear-gradient(180deg, #f0f7ff 0%, #fafafa 100%)',
                border: '1px solid #d6e4ff',
              }}
            >
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Space align="center">
                  <Spin indicator={<LoadingOutlined style={{ fontSize: 20 }} spin />} />
                  <div>
                    <Text strong>
                      正在检索：{SEARCH_STAGES[searchStage]?.title}
                    </Text>
                    <div>
                      <Text type="secondary">
                        {SEARCH_STAGES[searchStage]?.description}
                        {' · '}
                        已用时 {searchElapsed.toFixed(1)} 秒
                        {searchElapsed >= 8 ? '（嵌入模型响应较慢，请继续等待）' : ''}
                      </Text>
                    </div>
                  </div>
                </Space>

                <Progress
                  percent={Math.min(95, Math.round(((searchStage + 1) / SEARCH_STAGES.length) * 70 + Math.min(searchElapsed, 12) * 2))}
                  status="active"
                  showInfo={false}
                  strokeColor={{ from: '#1677ff', to: '#69b1ff' }}
                />

                <Steps
                  size="small"
                  current={searchStage}
                  items={SEARCH_STAGES.map((stage, index) => ({
                    title: stage.title,
                    description: index < searchStage ? '完成' : index === searchStage ? '进行中' : '等待',
                    status:
                      index < searchStage
                        ? 'finish'
                        : index === searchStage
                          ? 'process'
                          : 'wait',
                  }))}
                />
              </Space>
            </div>
          )}

          {!searching && lastSearchMeta && (
            <Alert
              style={{ marginBottom: 12 }}
              type={lastSearchMeta.count > 0 ? 'success' : 'warning'}
              showIcon
              icon={lastSearchMeta.count > 0 ? <CheckCircleOutlined /> : undefined}
              message={
                lastSearchMeta.count > 0
                  ? `找到 ${lastSearchMeta.count} 条相关片段`
                  : '未找到相关内容'
              }
              description={
                <Text type="secondary">
                  查询「{lastSearchMeta.query}」· 用时 {(lastSearchMeta.durationMs / 1000).toFixed(1)} 秒
                  · 结果来自本项目资料与全局法规库，已标注来源
                </Text>
              }
            />
          )}

          {!searching && hits.length > 0 ? (
            <List
              dataSource={hits}
              renderItem={(hit, index) => {
                const score = hit.relevance ?? hit.score ?? hit.similarity
                const sourceName = hit.document_title || hit.file_name || hit.source
                const sourceLabel = hit.source_scope === 'global_regulation'
                  ? `全局法规：${sourceName || '未命名法规'}`
                  : `项目资料：${sourceName || '未命名资料'}`
                return (
                  <List.Item>
                    <List.Item.Meta
                      title={
                        <Space wrap>
                          <Text strong>来源 {index + 1}：{sourceLabel}</Text>
                          {typeof score === 'number' && (
                            <Tag color="blue">相关度 {score <= 1 ? Math.round(score * 100) : Math.round(score)}%</Tag>
                          )}
                        </Space>
                      }
                      description={
                        <Paragraph style={{ marginBottom: 0 }} ellipsis={{ rows: 4, expandable: true, symbol: '展开' }}>
                          {hit.content || hit.text || '未返回可展示的资料片段'}
                        </Paragraph>
                      }
                    />
                  </List.Item>
                )
              }}
            />
          ) : !searching && searchAttempted ? (
            <Empty description="未在当前项目资料中找到相关内容，可换一种问法或补充资料" />
          ) : !searching ? (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <Title level={5}>先问资料，再开始审核</Title>
              <Text type="secondary">
                检索会调用嵌入模型做语义匹配（非即时全文搜索），结果会明确标注来源，不会混入其他项目资料。
              </Text>
            </div>
          ) : null}
        </div>
      </Card>
    </Space>
  )
}
