import { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  message,
  Space,
  Tag,
  Tabs,
  Upload,
  Steps,
  Progress,
  Alert,
} from 'antd'
import {
  PlusOutlined,
  EyeOutlined,
  EditOutlined,
  DeleteOutlined,
  UploadOutlined,
  FileMarkdownOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  ArrowLeftOutlined,
  CopyOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import { knowledgeApi } from '@/services/api'
import dayjs from 'dayjs'

const { TextArea } = Input
const { TabPane } = Tabs

interface Document {
  id: string
  title: string
  doc_type: string
  doc_no: string
  summary: string
  issue_authority: string
  issue_date: string
  effective_date: string
  status: string
  markdown_path?: string
}

export default function Knowledge() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [guidelines, setGuidelines] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [docModalVisible, setDocModalVisible] = useState(false)
  const [guidelineModalVisible, setGuidelineModalVisible] = useState(false)
  const [detailVisible, setDetailVisible] = useState(false)
  const [currentDoc, setCurrentDoc] = useState<any>(null)
  const [docForm] = Form.useForm()
  const [guidelineForm] = Form.useForm()
  const [editingDocId, setEditingDocId] = useState<string | null>(null)
  const [selectedDocType, setSelectedDocType] = useState<string | null>(null)
  const [searchKeyword, setSearchKeyword] = useState('')

  // 两阶段上传 Modal 状态
  const [uploadModalVisible, setUploadModalVisible] = useState(false)
  const [uploadStep, setUploadStep] = useState<number>(0)
  const [uploadFileList, setUploadFileList] = useState<UploadFile[]>([])
  const [uploadForm] = Form.useForm()
  const [parsing, setParsing] = useState(false)
  const [parsedMarkdown, setParsedMarkdown] = useState<string>('')
  const [parsedMeta, setParsedMeta] = useState<{ filename?: string; size?: number; char_count?: number }>({})
  const [indexing, setIndexing] = useState(false)
  const [indexProgress, setIndexProgress] = useState<{
    pct: number
    statusText: string
    current: number
    total: number
    completed: boolean
    error?: string
  }>({
    pct: 0,
    statusText: '',
    current: 0,
    total: 0,
    completed: false,
  })

  useEffect(() => {
    fetchDocuments()
    fetchGuidelines()
  }, [])

  const fetchDocuments = async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (selectedDocType) params.doc_type = selectedDocType
      if (searchKeyword) params.keyword = searchKeyword
      const res: any = await knowledgeApi.getDocuments(params)
      setDocuments(res.data || [])
    } catch (error) {
      console.error('Failed to fetch documents:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchGuidelines = async () => {
    try {
      const res: any = await knowledgeApi.getGuidelines()
      setGuidelines(res.data || [])
    } catch (error) {
      console.error('Failed to fetch guidelines:', error)
    }
  }

  const showIndexingResult = (res: any, actionText: string) => {
    const indexingData = res?.data?.indexing
    const count = indexingData?.embeddings_created || 0
    if (count > 0) {
      message.success(`${actionText}，已生成 ${count} 个知识片段索引`)
    } else {
      message.warning(`${actionText}，但向量索引未生成，请检查嵌入模型配置`)
    }
  }

  const openCreateDocument = () => {
    setEditingDocId(null)
    docForm.resetFields()
    docForm.setFieldValue('status', 'effective')
    setDocModalVisible(true)
  }

  const handleSubmitDocument = async (values: any) => {
    try {
      const res: any = editingDocId
        ? await knowledgeApi.updateDocument(editingDocId, values)
        : await knowledgeApi.createDocument(values)
      showIndexingResult(res, editingDocId ? '文档更新成功' : '文档创建成功')
      setDocModalVisible(false)
      setEditingDocId(null)
      docForm.resetFields()
      fetchDocuments()
    } catch (error) {
      message.error(editingDocId ? '更新失败' : '创建失败')
    }
  }

  const handleEditDocument = async (id: string) => {
    try {
      const res: any = await knowledgeApi.getDocument(id)
      setEditingDocId(id)
      docForm.setFieldsValue(res.data)
      setDocModalVisible(true)
    } catch (error) {
      message.error('获取文档内容失败')
    }
  }

  // 重置上传 Modal 状态
  const handleCloseUploadModal = () => {
    if (indexing && !indexProgress.completed) {
      Modal.confirm({
        title: '提示',
        content: '索引正在建立中，关闭窗口不会中断后台任务。确定关闭吗？',
        onOk: () => {
          setUploadModalVisible(false)
          resetUploadState()
          fetchDocuments()
        },
      })
      return
    }
    setUploadModalVisible(false)
    resetUploadState()
    if (indexProgress.completed) {
      fetchDocuments()
    }
  }

  const resetUploadState = () => {
    setUploadStep(0)
    setUploadFileList([])
    uploadForm.resetFields()
    setParsedMarkdown('')
    setParsedMeta({})
    setIndexing(false)
    setIndexProgress({ pct: 0, statusText: '', current: 0, total: 0, completed: false })
  }

  // 第一步：解析文件为 Markdown
  const handleParseDocument = async (values: any) => {
    const file = uploadFileList[0]?.originFileObj
    if (!file) {
      message.error('请选择要上传的知识库文件')
      return
    }

    const formData = new FormData()
    formData.append('file', file)

    setParsing(true)
    try {
      const res: any = await knowledgeApi.parseDocument(formData)
      const data = res.data
      setParsedMarkdown(data.markdown || '')
      setParsedMeta({
        filename: data.filename,
        size: data.size,
        char_count: data.char_count,
      })
      // 如果没有填写标题，自动填充为文件名
      if (!uploadForm.getFieldValue('title') && data.filename) {
        uploadForm.setFieldValue('title', data.filename.replace(/\.[^/.]+$/, ''))
      }
      setUploadStep(1)
      message.success('文档已成功解析为 Markdown，请校验内容')
    } catch (error: any) {
      message.error(error.response?.data?.detail || '文档解析失败，请检查文件格式')
    } finally {
      setParsing(false)
    }
  }

  // 第二步：流式建立索引 (SSE)
  const handleStartIndexing = async () => {
    const formValues = uploadForm.getFieldsValue()
    const title = formValues.title || parsedMeta.filename || '未命名知识文档'
    const doc_type = formValues.doc_type || 'standard'
    const doc_no = formValues.doc_no || ''
    const keywords = formValues.keywords || ''
    const status = formValues.status || 'effective'
    const filename = parsedMeta.filename || ''

    const formData = new FormData()
    formData.append('title', title)
    formData.append('doc_type', doc_type)
    formData.append('content', parsedMarkdown)
    if (doc_no) formData.append('doc_no', doc_no)
    if (keywords) formData.append('keywords', keywords)
    formData.append('status', status)
    if (filename) formData.append('filename', filename)

    setUploadStep(2)
    setIndexing(true)
    setIndexProgress({
      pct: 5,
      statusText: '正在保存文档到知识库...',
      current: 0,
      total: 0,
      completed: false,
    })

    try {
      const stream = knowledgeApi.indexDocumentStream(formData)
      for await (const event of stream) {
        if (event.stage === 'saved') {
          setIndexProgress((prev) => ({
            ...prev,
            pct: 15,
            statusText: '文档已保存，正在按 Markdown 结构智能切块...',
          }))
        } else if (event.stage === 'prepare') {
          setIndexProgress((prev) => ({
            ...prev,
            pct: 25,
            statusText: event.message || '正在准备向量索引...',
            total: event.total || prev.total,
          }))
        } else if (event.stage === 'embed') {
          const calculatedPct = 25 + Math.round((event.pct || 0) * 0.7)
          setIndexProgress({
            pct: calculatedPct,
            statusText: `正在生成向量嵌入 (${event.current}/${event.total})...`,
            current: event.current,
            total: event.total,
            completed: false,
          })
        } else if (event.stage === 'done') {
          setIndexProgress({
            pct: 100,
            statusText: `向量索引建立完成！共生成 ${event.embeddings_created} 个结构化知识片段。`,
            current: event.total_chunks,
            total: event.total_chunks,
            completed: true,
          })
          message.success('知识库上传并建立索引成功！')
        } else if (event.stage === 'error') {
          setIndexProgress((prev) => ({
            ...prev,
            statusText: `建立索引失败: ${event.message}`,
            error: event.message,
            completed: true,
          }))
          message.error(event.message || '建立索引失败')
        }
      }
    } catch (error: any) {
      setIndexProgress((prev) => ({
        ...prev,
        statusText: `建立索引异常: ${error.message || '连接断开'}`,
        error: error.message || '网络连接异常',
        completed: true,
      }))
      message.error('建立索引发生异常')
    } finally {
      setIndexing(false)
    }
  }

  const handleCreateGuideline = async (values: any) => {
    try {
      await knowledgeApi.createGuideline(values)
      message.success('审查细则创建成功')
      setGuidelineModalVisible(false)
      guidelineForm.resetFields()
      fetchGuidelines()
    } catch (error) {
      message.error('创建失败')
    }
  }

  const handleViewDocument = async (id: string) => {
    try {
      const res: any = await knowledgeApi.getDocument(id)
      setCurrentDoc(res.data)
      setDetailVisible(true)
    } catch (error) {
      message.error('获取详情失败')
    }
  }

  const handleDeleteDocument = async (id: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该文档吗？此操作将同时清除其向量索引。',
      onOk: async () => {
        try {
          await knowledgeApi.deleteDocument(id)
          message.success('删除成功')
          fetchDocuments()
        } catch (error) {
          message.error('删除失败')
        }
      },
    })
  }

  const getDocTypeTag = (type: string) => {
    const typeMap: Record<string, { color: string; text: string }> = {
      regulation: { color: 'blue', text: '法规' },
      policy: { color: 'green', text: '政策' },
      standard: { color: 'orange', text: '标准' },
      guideline: { color: 'purple', text: '细则' },
    }
    const item = typeMap[type] || { color: 'default', text: type }
    return <Tag color={item.color}>{item.text}</Tag>
  }

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      effective: { color: 'success', text: '有效' },
      expired: { color: 'error', text: '已失效' },
      draft: { color: 'default', text: '草稿' },
    }
    const item = statusMap[status] || { color: 'default', text: status }
    return <Tag color={item.color}>{item.text}</Tag>
  }

  const docColumns = [
    { title: '标题', dataIndex: 'title', key: 'title', width: 280 },
    {
      title: '类型',
      dataIndex: 'doc_type',
      key: 'doc_type',
      width: 80,
      render: (type: string) => getDocTypeTag(type),
    },
    { title: '文号', dataIndex: 'doc_no', key: 'doc_no', width: 140 },
    { title: '发布机关', dataIndex: 'issue_authority', key: 'issue_authority', width: 140 },
    {
      title: '格式形式',
      key: 'storage_format',
      width: 120,
      render: (_: any, record: Document) =>
        record.markdown_path ? (
          <Tag color="cyan" icon={<FileMarkdownOutlined />}>
            Markdown
          </Tag>
        ) : (
          <Tag color="default">纯文本</Tag>
        ),
    },
    {
      title: '发布日期',
      dataIndex: 'issue_date',
      key: 'issue_date',
      width: 110,
      render: (date: string) => (date ? dayjs(date).format('YYYY-MM-DD') : '-'),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: Document) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewDocument(record.id)}>
            查看
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEditDocument(record.id)}>
            编辑
          </Button>
          <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteDocument(record.id)}>
            删除
          </Button>
        </Space>
      ),
    },
  ]

  const guidelineColumns = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 250 },
    { title: '编号', dataIndex: 'code', key: 'code', width: 120 },
    { title: '产品类别', dataIndex: 'product_category', key: 'product_category', width: 150 },
    { title: '版本', dataIndex: 'version', key: 'version', width: 80 },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (active: boolean) => (
        <Tag color={active ? 'success' : 'default'}>{active ? '有效' : '失效'}</Tag>
      ),
    },
    {
      title: '生效日期',
      dataIndex: 'effective_date',
      key: 'effective_date',
      width: 120,
      render: (date: string) => (date ? dayjs(date).format('YYYY-MM-DD') : '-'),
    },
  ]

  return (
    <div>
      <Tabs defaultActiveKey="documents">
        <TabPane tab="政策法规" key="documents">
          <Card
            title="政策法规管理"
            extra={
              <Space>
                <Button
                  icon={<UploadOutlined />}
                  onClick={() => {
                    resetUploadState()
                    setUploadModalVisible(true)
                  }}
                >
                  上传知识库 (Markdown 模式)
                </Button>
                <Button type="primary" icon={<PlusOutlined />} onClick={openCreateDocument}>
                  新增文档
                </Button>
              </Space>
            }
          >
            <div style={{ marginBottom: 16, display: 'flex', gap: 16 }}>
              <Select
                placeholder="文档类型"
                allowClear
                style={{ width: 160 }}
                value={selectedDocType || undefined}
                onChange={(v) => setSelectedDocType(v || null)}
              >
                <Select.Option value="regulation">法规</Select.Option>
                <Select.Option value="policy">政策</Select.Option>
                <Select.Option value="standard">标准</Select.Option>
                <Select.Option value="guideline">细则</Select.Option>
              </Select>
              <Input
                placeholder="搜索关键词"
                value={searchKeyword}
                onChange={(e) => setSearchKeyword(e.target.value)}
                style={{ width: 300 }}
                onPressEnter={fetchDocuments}
              />
              <Button type="primary" onClick={fetchDocuments}>
                查询
              </Button>
            </div>

            <Table
              columns={docColumns}
              dataSource={documents}
              rowKey="id"
              loading={loading}
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </TabPane>

        <TabPane tab="审查细则" key="guidelines">
          <Card
            title="审查细则管理"
            extra={
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setGuidelineModalVisible(true)}>
                新增细则
              </Button>
            }
          >
            <Table
              columns={guidelineColumns}
              dataSource={guidelines}
              rowKey="id"
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </TabPane>
      </Tabs>

      {/* 新增/编辑文档 Modal */}
      <Modal
        title={editingDocId ? '编辑知识文档' : '新增知识文档'}
        open={docModalVisible}
        onCancel={() => {
          setDocModalVisible(false)
          setEditingDocId(null)
          docForm.resetFields()
        }}
        footer={null}
        width={800}
      >
        <Form form={docForm} layout="vertical" onFinish={handleSubmitDocument}>
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item name="doc_type" label="文档类型" rules={[{ required: true }]}>
              <Select>
                <Select.Option value="regulation">法规</Select.Option>
                <Select.Option value="policy">政策</Select.Option>
                <Select.Option value="standard">标准</Select.Option>
                <Select.Option value="guideline">细则</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="doc_no" label="文号">
              <Input />
            </Form.Item>
            <Form.Item name="issue_authority" label="发布机关">
              <Input />
            </Form.Item>
            <Form.Item name="issue_date" label="发布日期">
              <Input type="date" />
            </Form.Item>
            <Form.Item name="effective_date" label="生效日期">
              <Input type="date" />
            </Form.Item>
            <Form.Item name="keywords" label="关键词">
              <Input placeholder="多个关键词用逗号分隔" />
            </Form.Item>
            <Form.Item name="status" label="状态" initialValue="effective">
              <Select>
                <Select.Option value="effective">有效</Select.Option>
                <Select.Option value="expired">已失效</Select.Option>
                <Select.Option value="draft">草稿</Select.Option>
              </Select>
            </Form.Item>
          </div>
          <Form.Item name="summary" label="摘要">
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item name="content" label="内容 (支持 Markdown 语法)" rules={[{ required: true, message: '请输入知识正文' }]}>
            <TextArea rows={10} />
          </Form.Item>
          <Form.Item style={{ marginTop: 16, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setDocModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit">
                确定
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 两阶段上传与建立索引 Modal */}
      <Modal
        title="上传知识库文件（智能 Markdown 解析 & 向量化）"
        open={uploadModalVisible}
        onCancel={handleCloseUploadModal}
        footer={null}
        width={760}
        destroyOnClose={false}
        maskClosable={false}
      >
        <Steps
          current={uploadStep}
          style={{ marginBottom: 24 }}
          items={[
            { title: '选择并解析文档' },
            { title: 'Markdown 预览与校对' },
            { title: '建立向量索引' },
          ]}
        />

        {/* Step 0: 选择文件与基础信息 */}
        {uploadStep === 0 && (
          <Form
            form={uploadForm}
            layout="vertical"
            initialValues={{ doc_type: 'standard', status: 'effective' }}
            onFinish={handleParseDocument}
          >
            <Form.Item
              label="知识文件"
              required
              extra="支持 PDF、Word (.docx/.doc)、Excel (.xlsx/.xls)、TXT。上传后将自动使用结构化引擎转换为 Markdown。"
            >
              <Upload.Dragger
                accept=".pdf,.doc,.docx,.xls,.xlsx,.txt"
                maxCount={1}
                beforeUpload={() => false}
                fileList={uploadFileList}
                onChange={({ fileList }) => setUploadFileList(fileList.slice(-1))}
                onRemove={() => {
                  setUploadFileList([])
                  return true
                }}
              >
                <p className="ant-upload-drag-icon">
                  <UploadOutlined />
                </p>
                <p className="ant-upload-text">点击或拖拽文件到此区域</p>
                <p className="ant-upload-hint">推荐上传正式法规、标准或细则文件（PDF/Word 支持自动识别章节层级与表格）</p>
              </Upload.Dragger>
            </Form.Item>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Form.Item name="doc_type" label="文档类型" rules={[{ required: true }]}>
                <Select>
                  <Select.Option value="regulation">法规</Select.Option>
                  <Select.Option value="policy">政策</Select.Option>
                  <Select.Option value="standard">标准</Select.Option>
                  <Select.Option value="guideline">细则</Select.Option>
                </Select>
              </Form.Item>
              <Form.Item name="title" label="显示标题">
                <Input placeholder="不填则自动使用原文件名" />
              </Form.Item>
              <Form.Item name="doc_no" label="文号/标准号">
                <Input placeholder="如 GB/T 38154-2019" />
              </Form.Item>
              <Form.Item name="keywords" label="检索关键词">
                <Input placeholder="如 压力容器,充装追溯,安全技术规范" />
              </Form.Item>
              <Form.Item name="status" label="状态">
                <Select>
                  <Select.Option value="effective">有效</Select.Option>
                  <Select.Option value="draft">草稿</Select.Option>
                </Select>
              </Form.Item>
            </div>

            <Form.Item style={{ marginTop: 12, textAlign: 'right' }}>
              <Space>
                <Button onClick={handleCloseUploadModal}>取消</Button>
                <Button type="primary" htmlType="submit" loading={parsing} icon={<FileMarkdownOutlined />}>
                  {parsing ? '正在提取并转换为 Markdown...' : '下一步：解析文档'}
                </Button>
              </Space>
            </Form.Item>
          </Form>
        )}

        {/* Step 1: Markdown 预览与校对 */}
        {uploadStep === 1 && (
          <div>
            <Alert
              type="info"
              showIcon
              message="Markdown 格式转换成功"
              description="文档已保留标题层级与表格。您可以在下方直接校对或修正文字；确认无误后点击下方按钮开始建立向量索引。"
              style={{ marginBottom: 16 }}
            />

            <div style={{ marginBottom: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
              <Tag color="blue">原文件名: {parsedMeta.filename || '-'}</Tag>
              <Tag color="cyan">解析字数: {parsedMeta.char_count || parsedMarkdown.length} 字符</Tag>
              <Tag color="purple">格式: 结构化 Markdown</Tag>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontWeight: 500 }}>Markdown 正文内容（可在线编辑）：</span>
                <Button
                  type="link"
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => {
                    navigator.clipboard.writeText(parsedMarkdown)
                    message.success('已复制 Markdown 内容到剪贴板')
                  }}
                >
                  复制内容
                </Button>
              </div>
              <TextArea
                rows={13}
                value={parsedMarkdown}
                onChange={(e) => setParsedMarkdown(e.target.value)}
                style={{ fontFamily: 'Consolas, Monaco, monospace', fontSize: 13 }}
              />
            </div>

            <div style={{ textAlign: 'right' }}>
              <Space>
                <Button icon={<ArrowLeftOutlined />} onClick={() => setUploadStep(0)}>
                  返回重选
                </Button>
                <Button type="primary" onClick={handleStartIndexing}>
                  确认并建立索引
                </Button>
              </Space>
            </div>
          </div>
        )}

        {/* Step 2: 建立向量索引实时进度 (SSE) */}
        {uploadStep === 2 && (
          <div style={{ padding: '24px 12px', textAlign: 'center' }}>
            <div style={{ marginBottom: 20 }}>
              {indexProgress.completed && !indexProgress.error ? (
                <CheckCircleOutlined style={{ fontSize: 52, color: '#52c41a' }} />
              ) : indexProgress.error ? (
                <Alert type="error" message="建立索引遇到问题" description={indexProgress.error} showIcon />
              ) : (
                <LoadingOutlined style={{ fontSize: 52, color: '#1677ff' }} />
              )}
            </div>

            <div style={{ width: '80%', margin: '0 auto 20px auto' }}>
              <Progress
                percent={indexProgress.pct}
                status={
                  indexProgress.error
                    ? 'exception'
                    : indexProgress.completed
                    ? 'success'
                    : 'active'
                }
                strokeColor={indexProgress.completed ? '#52c41a' : '#1677ff'}
              />
            </div>

            <p style={{ fontSize: 15, color: '#333', fontWeight: 500, minHeight: 24 }}>
              {indexProgress.statusText || '正在处理...'}
            </p>

            {indexProgress.total > 0 && (
              <p style={{ color: '#888', fontSize: 13 }}>
                已完成进度: {indexProgress.current} / {indexProgress.total} 个片段
              </p>
            )}

            <div style={{ marginTop: 28 }}>
              {indexProgress.completed ? (
                <Button
                  type="primary"
                  onClick={() => {
                    setUploadModalVisible(false)
                    resetUploadState()
                    fetchDocuments()
                  }}
                >
                  完成并查看列表
                </Button>
              ) : (
                <Button onClick={handleCloseUploadModal} disabled={indexing}>
                  关闭
                </Button>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* 新增审查细则 Modal */}
      <Modal
        title="新增审查细则"
        open={guidelineModalVisible}
        onCancel={() => setGuidelineModalVisible(false)}
        footer={null}
        width={800}
      >
        <Form form={guidelineForm} layout="vertical" onFinish={handleCreateGuideline}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item name="name" label="名称" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="code" label="编号">
              <Input />
            </Form.Item>
            <Form.Item name="product_category" label="产品类别" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="version" label="版本" initialValue="1.0">
              <Input />
            </Form.Item>
            <Form.Item name="effective_date" label="生效日期">
              <Input type="date" />
            </Form.Item>
          </div>
          <Form.Item name="legal_basis" label="法律依据">
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item name="content" label="细则内容" rules={[{ required: true }]}>
            <TextArea rows={10} />
          </Form.Item>
          <Form.Item style={{ marginTop: 16, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setGuidelineModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit">
                确定
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 文档详情 Modal */}
      <Modal
        title="文档详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={900}
      >
        {currentDoc && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <h2>{currentDoc.title}</h2>
              {currentDoc.markdown_path && (
                <Tag color="cyan" icon={<FileMarkdownOutlined />}>
                  Markdown 存储: {currentDoc.markdown_path.split(/[\\/]/).pop()}
                </Tag>
              )}
            </div>
            <div style={{ marginBottom: 16, color: '#666' }}>
              <Space split={<span>|</span>}>
                <span>文号：{currentDoc.doc_no || '-'}</span>
                <span>发布机关：{currentDoc.issue_authority || '-'}</span>
                <span>发布日期：{currentDoc.issue_date ? dayjs(currentDoc.issue_date).format('YYYY-MM-DD') : '-'}</span>
              </Space>
            </div>
            {currentDoc.summary && (
              <div style={{ marginBottom: 16, padding: 16, background: '#f5f5f5', borderRadius: 4 }}>
                <strong>摘要：</strong>
                <p style={{ margin: '8px 0 0' }}>{currentDoc.summary}</p>
              </div>
            )}
            <div
              style={{
                whiteSpace: 'pre-wrap',
                lineHeight: 1.8,
                background: '#fafafa',
                padding: 16,
                borderRadius: 6,
                border: '1px solid #f0f0f0',
                fontFamily: 'Consolas, Monaco, monospace',
                maxHeight: '500px',
                overflowY: 'auto',
              }}
            >
              {currentDoc.content}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
