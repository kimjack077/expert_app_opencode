import { useState, useEffect } from 'react'
import { Card, Table, Button, Modal, Form, Input, Select, message, Space, Tag, Tree, Tabs, Upload } from 'antd'
import { PlusOutlined, EyeOutlined, EditOutlined, DeleteOutlined, FolderOutlined, FileTextOutlined, UploadOutlined } from '@ant-design/icons'
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
  view_count: number
  category: { id: string; name: string }
}

export default function Knowledge() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [categories, setCategories] = useState<any[]>([])
  const [guidelines, setGuidelines] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [docModalVisible, setDocModalVisible] = useState(false)
  const [guidelineModalVisible, setGuidelineModalVisible] = useState(false)
  const [detailVisible, setDetailVisible] = useState(false)
  const [currentDoc, setCurrentDoc] = useState<any>(null)
  const [docForm] = Form.useForm()
  const [guidelineForm] = Form.useForm()
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [searchKeyword, setSearchKeyword] = useState('')

  useEffect(() => {
    fetchCategories()
    fetchDocuments()
    fetchGuidelines()
  }, [])

  const fetchCategories = async () => {
    try {
      const res: any = await knowledgeApi.getCategories()
      setCategories(res.data || [])
    } catch (error) {
      console.error('Failed to fetch categories:', error)
    }
  }

  const fetchDocuments = async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (selectedCategory) params.category_id = selectedCategory
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

  const handleCreateDocument = async (values: any) => {
    try {
      await knowledgeApi.createDocument(values)
      message.success('文档创建成功')
      setDocModalVisible(false)
      docForm.resetFields()
      fetchDocuments()
    } catch (error) {
      message.error('创建失败')
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
      content: '确定要删除该文档吗？此操作不可恢复。',
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
    { title: '标题', dataIndex: 'title', key: 'title', width: 300 },
    {
      title: '类型',
      dataIndex: 'doc_type',
      key: 'doc_type',
      width: 80,
      render: (type: string) => getDocTypeTag(type),
    },
    { title: '文号', dataIndex: 'doc_no', key: 'doc_no', width: 150 },
    { title: '发布机关', dataIndex: 'issue_authority', key: 'issue_authority', width: 150 },
    {
      title: '发布日期',
      dataIndex: 'issue_date',
      key: 'issue_date',
      width: 120,
      render: (date: string) => (date ? dayjs(date).format('YYYY-MM-DD') : '-'),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => getStatusTag(status),
    },
    { title: '浏览次数', dataIndex: 'view_count', key: 'view_count', width: 100 },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: Document) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewDocument(record.id)}>
            查看
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
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setDocModalVisible(true)}>
                新增文档
              </Button>
            }
          >
            <div style={{ marginBottom: 16, display: 'flex', gap: 16 }}>
              <Select
                placeholder="选择分类"
                allowClear
                style={{ width: 200 }}
                value={selectedCategory || undefined}
                onChange={(v) => setSelectedCategory(v || null)}
              >
                {categories.map((c) => (
                  <Select.Option key={c.id} value={c.id}>
                    {c.name}
                  </Select.Option>
                ))}
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

      <Modal
        title="新增文档"
        open={docModalVisible}
        onCancel={() => setDocModalVisible(false)}
        footer={null}
        width={800}
      >
        <Form form={docForm} layout="vertical" onFinish={handleCreateDocument}>
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item name="category_id" label="分类" rules={[{ required: true }]}>
              <Select>
                {categories.map((c) => (
                  <Select.Option key={c.id} value={c.id}>
                    {c.name}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
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
          <Form.Item name="content" label="内容">
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

      <Modal
        title="文档详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={900}
      >
        {currentDoc && (
          <div>
            <h2>{currentDoc.title}</h2>
            <div style={{ marginBottom: 16, color: '#666' }}>
              <Space split={<span>|</span>}>
                <span>文号：{currentDoc.doc_no || '-'}</span>
                <span>发布机关：{currentDoc.issue_authority || '-'}</span>
                <span>发布日期：{currentDoc.issue_date ? dayjs(currentDoc.issue_date).format('YYYY-MM-DD') : '-'}</span>
                <span>浏览次数：{currentDoc.view_count}</span>
              </Space>
            </div>
            {currentDoc.summary && (
              <div style={{ marginBottom: 16, padding: 16, background: '#f5f5f5', borderRadius: 4 }}>
                <strong>摘要：</strong>
                <p style={{ margin: '8px 0 0' }}>{currentDoc.summary}</p>
              </div>
            )}
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{currentDoc.content}</div>
          </div>
        )}
      </Modal>
    </div>
  )
}
