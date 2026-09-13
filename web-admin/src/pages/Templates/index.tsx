import { useState, useEffect } from 'react'
import { Card, Table, Button, Modal, Form, Input, Select, Tree, message, Space, Tag, Radio, InputNumber, Switch, Empty, Row, Col, Tooltip, Divider, RadioChangeEvent } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, CheckCircleOutlined, FolderOutlined, FileTextOutlined, PlusCircleOutlined, SaveOutlined, CloseOutlined, ArrowLeftOutlined, CopyOutlined, RobotOutlined } from '@ant-design/icons'
import { templateApi } from '@/services/api'
import AiExtractModal from './AiExtractModal'
import TemplateEditorV2 from './TemplateEditorV2'

const { TextArea } = Input

// 检查结论类型
const RESULT_TYPES = [
  { label: '通过/不通过', value: 'pass_fail' },
  { label: '数值判定', value: 'numeric' },
  { label: '文字描述', value: 'text' },
]

const RESULT_TYPE_COLORS: Record<string, string> = {
  pass_fail: 'green',
  numeric: 'orange',
  text: 'purple',
}

const RESULT_TYPE_LABELS: Record<string, string> = {
  pass_fail: '通过/不通过',
  numeric: '数值判定',
  text: '文字描述',
}

// 风险等级选项
const RISK_LEVELS = [
  { label: '低风险', value: 'low' },
  { label: '中风险', value: 'medium' },
  { label: '高风险', value: 'high' },
]

const RISK_LEVEL_COLORS: Record<string, string> = {
  low: 'default',
  medium: 'orange',
  high: 'red',
}

const RISK_LEVEL_LABELS: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

// 树形节点数据类型
interface TreeNodeData {
  id: string
  title: string
  description?: string
  check_method?: string
  legal_basis?: string
  standard_ref?: string
  result_type?: string
  result_options?: any
  min_value?: number
  max_value?: number
  unit?: string
  use_ai?: boolean
  score_weight?: number
  default_score?: number
  allow_attachment?: boolean
  attachment_required?: boolean
  ai_prompt_template?: string
  is_required?: boolean
  risk_level?: string
  is_category?: boolean
  sort_order?: number
  children?: TreeNodeData[]
  parent_id?: string | null
}

export default function Templates() {
  const [templates, setTemplates] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [templateModal, setTemplateModal] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<any>(null)
  const [selectedTemplate, setSelectedTemplate] = useState<any>(null)
  const [templateForm] = Form.useForm()

  // 检查项目树形数据
  const [treeData, setTreeData] = useState<TreeNodeData[]>([])
  const [expandedKeys, setExpandedKeys] = useState<string[]>([])

  // 添加项目相关状态
  const [addingNodeId, setAddingNodeId] = useState<string | null>(null) // 'root'表示添加到根级别，其他表示父节点ID
  const [addItemForm] = Form.useForm()

  // 编辑节点相关状态
  const [editingNode, setEditingNode] = useState<TreeNodeData | null>(null)
  const [editNodeForm] = Form.useForm()

  // 复制模板相关状态
  const [copySourceId, setCopySourceId] = useState<string | null>(null)

  // AI辅助录入相关状态
  const [aiModalOpen, setAiModalOpen] = useState(false)
  // 编辑版本选择
  const [editorVersion, setEditorVersion] = useState<'v1' | 'v2'>('v1')

  useEffect(() => {
    fetchTemplates()
  }, [])

  const fetchTemplates = async () => {
    setLoading(true)
    try {
      const res: any = await templateApi.getTemplates()
      setTemplates(res.data || [])
    } catch (error) {
      console.error('Failed to fetch templates:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchTemplateDetail = async (id: string) => {
    try {
      const res: any = await templateApi.getTemplate(id)
      setTreeData(res.data?.items || [])
      setSelectedTemplate(res.data)
      // 默认展开所有节点
      const allKeys = getAllNodeKeys(res.data?.items || [])
      setExpandedKeys(allKeys)
    } catch (error) {
      console.error('Failed to fetch template detail:', error)
      message.error('获取模板详情失败')
    }
  }

  // 获取所有节点key
  const getAllNodeKeys = (nodes: TreeNodeData[]): string[] => {
    const keys: string[] = []
    const traverse = (items: TreeNodeData[]) => {
      items.forEach(item => {
        keys.push(item.id)
        if (item.children?.length) {
          traverse(item.children)
        }
      })
    }
    traverse(nodes)
    return keys
  }

  const handleCreateTemplate = async (values: any) => {
    try {
      if (editingTemplate) {
        await templateApi.updateTemplate(editingTemplate.id, values)
        message.success('模板更新成功')
        setTemplateModal(false)
        templateForm.resetFields()
        setEditingTemplate(null)
        fetchTemplates()
      } else {
        // 新建模板
        if (copySourceId) {
          // 从现有模板复制
          await templateApi.copyTemplate(copySourceId, values.name)
          message.success('模板复制成功')
          setTemplateModal(false)
          templateForm.resetFields()
          setCopySourceId(null)
          fetchTemplates()
          // 可选：复制后直接进入编辑页面
          // fetchTemplateDetail(res.data?.id)
        } else {
          // 新建空白模板
          await templateApi.createTemplate(values)
          message.success('模板创建成功')
          setTemplateModal(false)
          templateForm.resetFields()
          fetchTemplates()
        }
      }
    } catch (error) {
      message.error('操作失败')
    }
  }

  const handleEdit = (record: any) => {
    setEditingTemplate(record)
    templateForm.setFieldsValue(record)
    setTemplateModal(true)
  }

  const handleDelete = async (id: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个模板吗？',
      onOk: async () => {
        try {
          await templateApi.deleteTemplate(id)
          message.success('删除成功')
          fetchTemplates()
        } catch (error) {
          message.error('删除失败')
        }
      },
    })
  }

  const handlePublish = async (id: string) => {
    try {
      await templateApi.publishTemplate(id)
      message.success('模板发布成功')
      fetchTemplates()
    } catch (error) {
      message.error('发布失败')
    }
  }

  // 复制模板
  const handleCopyTemplate = async (sourceId: string) => {
    try {
      const res: any = await templateApi.copyTemplate(sourceId)
      message.success(`模板复制成功：${res.data?.name}`)
      fetchTemplates()
    } catch (error) {
      message.error('复制失败')
    }
  }

  // 添加检查项目
  const handleAddItem = async (values: any) => {
    try {
      const templateId = selectedTemplate?.id
      if (!templateId) {
        message.error('请先选择模板')
        return
      }

      // 修复：如果是 'root'，则 parent_id 为 null，否则使用实际的父节点ID
      const parentId = addingNodeId === 'root' ? null : addingNodeId

      const payload = {
        title: values.title,
        is_category: values.is_category || false,
        result_type: values.is_category ? undefined : values.result_type,
        description: values.is_category ? undefined : values.description,
        check_method: values.is_category ? undefined : values.check_method,
        legal_basis: values.is_category ? undefined : values.legal_basis,
        standard_ref: values.is_category ? undefined : values.standard_ref,
        risk_level: values.is_category ? undefined : values.risk_level,
        parent_id: parentId,
        min_value: !values.is_category && values.result_type === 'numeric' ? values.min_value : undefined,
        max_value: !values.is_category && values.result_type === 'numeric' ? values.max_value : undefined,
        unit: !values.is_category && values.result_type === 'numeric' ? values.unit : undefined,
        use_ai: !values.is_category ? values.use_ai : undefined,
        score_weight: !values.is_category ? values.score_weight : undefined,
        default_score: !values.is_category ? values.default_score : undefined,
        allow_attachment: true,
        attachment_required: !values.is_category ? (values.attachment_required ?? false) : undefined,
        ai_prompt_template: !values.is_category ? values.ai_prompt_template : undefined,
      }

      console.log('Adding item with payload:', payload)

      await templateApi.createItem(templateId, payload)

      message.success(values.is_category ? '分类添加成功' : '检查项目添加成功')
      addItemForm.resetFields()
      setAddingNodeId(null)
      fetchTemplateDetail(templateId)
      fetchTemplates() // 刷新列表统计信息
    } catch (error: any) {
      console.error('Failed to add item:', error)
      message.error(error?.response?.data?.message || '添加失败')
    }
  }

  // 更新检查项目
  const handleUpdateItem = async (values: any) => {
    try {
      if (!editingNode) return

      const hasChildren = !!(editingNode.children && editingNode.children.length > 0)
      const isCat = hasChildren || !!values.is_category

      const payload = {
        title: values.title,
        is_category: isCat,
        result_type: isCat ? undefined : values.result_type,
        description: isCat ? undefined : values.description,
        check_method: isCat ? undefined : values.check_method,
        legal_basis: isCat ? undefined : values.legal_basis,
        standard_ref: isCat ? undefined : values.standard_ref,
        risk_level: isCat ? undefined : values.risk_level,
        min_value: !isCat && values.result_type === 'numeric' ? values.min_value : undefined,
        max_value: !isCat && values.result_type === 'numeric' ? values.max_value : undefined,
        unit: !isCat && values.result_type === 'numeric' ? values.unit : undefined,
        use_ai: isCat ? false : values.use_ai,
        score_weight: !isCat ? values.score_weight : undefined,
        default_score: !isCat ? values.default_score : undefined,
        allow_attachment: !isCat,
        attachment_required: !isCat ? (values.attachment_required ?? false) : undefined,
        ai_prompt_template: !isCat ? values.ai_prompt_template : undefined,
      }

      await templateApi.updateItem(editingNode.id, payload)

      message.success('更新成功')
      setEditingNode(null)
      fetchTemplateDetail(selectedTemplate.id)
    } catch (error: any) {
      console.error('Failed to update item:', error)
      message.error(error?.response?.data?.message || '更新失败')
    }
  }

  // 删除检查项目
  const handleDeleteItem = async (nodeId: string) => {
    try {
      await templateApi.deleteItem(nodeId)
      message.success('删除成功')
      fetchTemplateDetail(selectedTemplate.id)
    } catch (error) {
      console.error('Failed to delete item:', error)
      message.error('删除失败')
    }
  }

  // 开始编辑节点
  const startEditNode = (node: TreeNodeData) => {
    setEditingNode(node)
    const hasChildren = !!(node.children && node.children.length > 0)
    const isCat = hasChildren || !!node.is_category
    editNodeForm.setFieldsValue({
      title: node.title,
      is_category: isCat,
      result_type: isCat ? undefined : (node.result_type || 'pass_fail'),
      risk_level: isCat ? undefined : (node.risk_level || 'medium'),
      description: isCat ? undefined : node.description,
      check_method: isCat ? undefined : node.check_method,
      legal_basis: isCat ? undefined : node.legal_basis,
      standard_ref: isCat ? undefined : node.standard_ref,
      min_value: node.min_value,
      max_value: node.max_value,
      unit: node.unit,
      use_ai: isCat ? false : node.use_ai,
      score_weight: node.score_weight,
      default_score: node.default_score,
      attachment_required: isCat ? false : (node.attachment_required ?? false),
      ai_prompt_template: isCat ? undefined : node.ai_prompt_template,
    })
  }

  // 渲染树形节点的标题
  const renderTreeNodeTitle = (nodeData: TreeNodeData) => {
    const isEditing = editingNode?.id === nodeData.id
    const isAdding = addingNodeId === nodeData.id
    const nodeHasChildren = !!(nodeData.children && nodeData.children.length > 0)

    // 编辑状态 - 横向布局
    if (isEditing) {
      return (
        <div style={{
          background: '#f6ffed',
          padding: '12px 16px',
          borderRadius: 8,
          border: '1px solid #b7eb8f',
        }}>
          <Form form={editNodeForm} layout="vertical" onFinish={handleUpdateItem}>
            <Row gutter={16}>
              <Col span={6}>
                <Form.Item name="title" label="名称" rules={[{ required: true }]} style={{ marginBottom: 12 }}>
                  <Input placeholder="输入名称" />
                </Form.Item>
              </Col>
              <Col span={4}>
                <Form.Item name="is_category" label="节点类型" valuePropName="checked" style={{ marginBottom: 12 }}>
                  <Switch
                    checkedChildren="分类"
                    unCheckedChildren="检查"
                    style={{ width: '100%' }}
                    disabled={nodeHasChildren}
                  />
                </Form.Item>
              </Col>
              <Col span={14}>
                <Form.Item noStyle shouldUpdate={(prev, current) => prev.is_category !== current.is_category}>
                  {({ getFieldValue }) => {
                    const isCat = getFieldValue('is_category') || nodeHasChildren
                    if (isCat) {
                      return (
                        <div style={{ paddingTop: 28, color: '#0369a1', fontSize: 13 }}>
                          📂 <strong>分类目录</strong>（不可录入结论，仅作为下级检查项的聚合分组）
                        </div>
                      )
                    }
                    return (
                      <Row gutter={16}>
                        <Col span={10}>
                          <Form.Item name="result_type" label="结论类型" rules={[{ required: true }]} style={{ marginBottom: 12 }}>
                            <Radio.Group options={RESULT_TYPES} optionType="button" buttonStyle="solid" size="small" />
                          </Form.Item>
                        </Col>
                        <Col span={7}>
                          <Form.Item name="risk_level" label="风险等级" style={{ marginBottom: 12 }}>
                            <Select options={RISK_LEVELS} size="small" />
                          </Form.Item>
                        </Col>
                        <Col span={7}>
                          <Form.Item name="standard_ref" label="标准依据" style={{ marginBottom: 12 }}>
                            <Input placeholder="标准依据" />
                          </Form.Item>
                        </Col>
                      </Row>
                    )
                  }}
                </Form.Item>
              </Col>
            </Row>

            <Form.Item noStyle shouldUpdate={(prev, current) => prev.is_category !== current.is_category}>
              {({ getFieldValue }) => {
                const isCategory = getFieldValue('is_category')
                if (isCategory) return null
                return (
                  <>
                    <Form.Item noStyle shouldUpdate={(prev, current) => prev.result_type !== current.result_type}>
                      {({ getFieldValue }) => {
                        if (getFieldValue('result_type') === 'numeric') {
                          return (
                            <Row gutter={16} style={{ marginBottom: 12 }}>
                              <Col span={4}>
                                <Form.Item name="min_value" label="最小值" style={{ marginBottom: 0 }}>
                                  <InputNumber placeholder="最小" style={{ width: '100%' }} />
                                </Form.Item>
                              </Col>
                              <Col span={4}>
                                <Form.Item name="max_value" label="最大值" style={{ marginBottom: 0 }}>
                                  <InputNumber placeholder="最大" style={{ width: '100%' }} />
                                </Form.Item>
                              </Col>
                              <Col span={4}>
                                <Form.Item name="unit" label="单位" style={{ marginBottom: 0 }}>
                                  <Input placeholder="如：℃" style={{ width: '100%' }} />
                                </Form.Item>
                              </Col>
                              <Col span={12} />
                            </Row>
                          )
                        }
                        return null
                      }}
                    </Form.Item>

                    <Row gutter={16}>
                      <Col span={8}>
                        <Form.Item name="description" label="项目描述" style={{ marginBottom: 12 }}>
                          <TextArea rows={2} placeholder="描述" />
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item name="check_method" label="检查方法" style={{ marginBottom: 12 }}>
                          <TextArea rows={2} placeholder="检查方法" />
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item name="legal_basis" label="法律依据" style={{ marginBottom: 0 }}>
                          <TextArea rows={2} placeholder="法律依据" />
                        </Form.Item>
                      </Col>
                    </Row>

                    <Divider dashed style={{ margin: '8px 0 12px 0' }} />
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#0ea5e9', marginBottom: 8 }}>📎 附件配置（所有检查项均支持上传附件）</div>
                    <Row gutter={16}>
                      <Col span={8}>
                        <Form.Item name="attachment_required" label="附件是否必填" valuePropName="checked" style={{ marginBottom: 12 }} tooltip="开启后，完成该检查项时必须上传至少一张附件照片">
                          <Switch checkedChildren="📎 必须上传" unCheckedChildren="选填" />
                        </Form.Item>
                      </Col>
                    </Row>

                    {selectedTemplate?.is_quantified && (
                      <>
                        <Divider dashed style={{ margin: '8px 0 12px 0' }} />
                        <div style={{ fontSize: 12, fontWeight: 600, color: '#F59E0B', marginBottom: 8 }}>🏆 量化配置（当前模板已启用计分）</div>
                        <Row gutter={16}>
                          <Col span={8}>
                            <Form.Item name="score_weight" label="节点权重(满分)" style={{ marginBottom: 12 }}>
                              <InputNumber placeholder="权重数值" style={{ width: '100%' }} />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item name="default_score" label="默认得分" style={{ marginBottom: 12 }}>
                              <InputNumber placeholder="默认得分" style={{ width: '100%' }} />
                            </Form.Item>
                          </Col>
                        </Row>
                      </>
                    )}

                    <Row gutter={16}>
                      <Col span={6}>
                        <Form.Item name="use_ai" label="是否允许AI智能判断" valuePropName="checked" style={{ marginBottom: 12 }}>
                          <Switch />
                        </Form.Item>
                      </Col>
                      <Col span={18}>
                        <Form.Item name="ai_prompt_template" label="AI 提示词模板" style={{ marginBottom: 0 }}>
                          <TextArea rows={2} placeholder="特定 AI 提示词指令" />
                        </Form.Item>
                      </Col>
                    </Row>
                  </>
                )
              }}
            </Form.Item>

            <div style={{ marginTop: 16, textAlign: 'right' }}>
              <Space>
                <Button icon={<CloseOutlined />} onClick={() => setEditingNode(null)}>取消</Button>
                <Button type="primary" icon={<SaveOutlined />} htmlType="submit">保存</Button>
              </Space>
            </div>
          </Form>
        </div>
      )
    }

    // 添加子项目状态 - 横向布局
    if (isAdding) {
      return (
        <div style={{
          background: '#e6f7ff',
          padding: '12px 16px',
          borderRadius: 8,
          border: '1px solid #91d5ff',
        }}>
          <div style={{ marginBottom: 12, fontWeight: 500, color: '#1890ff', fontSize: 14 }}>
            在「{nodeData.title}」下添加子项
          </div>
          <Form form={addItemForm} layout="vertical" onFinish={handleAddItem}>
            <Row gutter={16}>
              <Col span={6}>
                <Form.Item name="title" label="名称" rules={[{ required: true }]} style={{ marginBottom: 12 }}>
                  <Input placeholder="输入名称" />
                </Form.Item>
              </Col>
              <Col span={4}>
                <Form.Item name="is_category" label="节点类型" valuePropName="checked" style={{ marginBottom: 12 }}>
                  <Switch checkedChildren="分类" unCheckedChildren="检查" style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={5}>
                <Form.Item name="result_type" label="结论类型" style={{ marginBottom: 12 }}>
                  <Radio.Group options={RESULT_TYPES} optionType="button" buttonStyle="solid" size="small" />
                </Form.Item>
              </Col>
              <Col span={4}>
                <Form.Item name="risk_level" label="风险等级" style={{ marginBottom: 12 }}>
                  <Select options={RISK_LEVELS} size="small" />
                </Form.Item>
              </Col>
              <Col span={5}>
                <Form.Item name="standard_ref" label="标准依据" style={{ marginBottom: 12 }}>
                  <Input placeholder="标准依据" />
                </Form.Item>
              </Col>
            </Row>

            <Form.Item noStyle shouldUpdate={(prev, current) => prev.is_category !== current.is_category}>
              {({ getFieldValue }) => {
                const isCategory = getFieldValue('is_category')
                if (isCategory) return null
                return (
                  <>
                    <Form.Item noStyle shouldUpdate={(prev, current) => prev.result_type !== current.result_type}>
                      {({ getFieldValue }) => {
                        if (getFieldValue('result_type') === 'numeric') {
                          return (
                            <Row gutter={16} style={{ marginBottom: 12 }}>
                              <Col span={4}>
                                <Form.Item name="min_value" label="最小值" style={{ marginBottom: 0 }}>
                                  <InputNumber placeholder="最小" style={{ width: '100%' }} />
                                </Form.Item>
                              </Col>
                              <Col span={4}>
                                <Form.Item name="max_value" label="最大值" style={{ marginBottom: 0 }}>
                                  <InputNumber placeholder="最大" style={{ width: '100%' }} />
                                </Form.Item>
                              </Col>
                              <Col span={4}>
                                <Form.Item name="unit" label="单位" style={{ marginBottom: 0 }}>
                                  <Input placeholder="如：℃" style={{ width: '100%' }} />
                                </Form.Item>
                              </Col>
                              <Col span={12} />
                            </Row>
                          )
                        }
                        return null
                      }}
                    </Form.Item>

                    <Row gutter={16}>
                      <Col span={8}>
                        <Form.Item name="description" label="项目描述" style={{ marginBottom: 12 }}>
                          <TextArea rows={2} placeholder="描述" />
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item name="check_method" label="检查方法" style={{ marginBottom: 12 }}>
                          <TextArea rows={2} placeholder="检查方法" />
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item name="legal_basis" label="法律依据" style={{ marginBottom: 0 }}>
                          <TextArea rows={2} placeholder="法律依据" />
                        </Form.Item>
                      </Col>
                    </Row>

                    <Divider dashed style={{ margin: '8px 0 12px 0' }} />
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#0ea5e9', marginBottom: 8 }}>📎 附件配置（所有检查项均支持上传附件）</div>
                    <Row gutter={16}>
                      <Col span={8}>
                        <Form.Item name="attachment_required" label="附件是否必填" valuePropName="checked" style={{ marginBottom: 12 }} tooltip="开启后，完成该检查项时必须上传至少一张附件照片">
                          <Switch checkedChildren="📎 必须上传" unCheckedChildren="选填" />
                        </Form.Item>
                      </Col>
                    </Row>

                    {selectedTemplate?.is_quantified && (
                      <>
                        <Divider dashed style={{ margin: '8px 0 12px 0' }} />
                        <div style={{ fontSize: 12, fontWeight: 600, color: '#F59E0B', marginBottom: 8 }}>🏆 量化配置（当前模板已启用计分）</div>
                        <Row gutter={16}>
                          <Col span={8}>
                            <Form.Item name="score_weight" label="节点权重(满分)" style={{ marginBottom: 12 }}>
                              <InputNumber placeholder="权重数值" style={{ width: '100%' }} />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item name="default_score" label="默认得分" style={{ marginBottom: 12 }}>
                              <InputNumber placeholder="默认得分" style={{ width: '100%' }} />
                            </Form.Item>
                          </Col>
                        </Row>
                      </>
                    )}

                    <Row gutter={16}>
                      <Col span={6}>
                        <Form.Item name="use_ai" label="是否允许AI智能判断" valuePropName="checked" style={{ marginBottom: 12 }}>
                          <Switch />
                        </Form.Item>
                      </Col>
                      <Col span={18}>
                        <Form.Item name="ai_prompt_template" label="AI 提示词模板" style={{ marginBottom: 0 }}>
                          <TextArea rows={2} placeholder="特定 AI 提示词指令" />
                        </Form.Item>
                      </Col>
                    </Row>
                  </>
                )
              }}
            </Form.Item>

            <div style={{ marginTop: 16, textAlign: 'right' }}>
              <Space>
                <Button icon={<CloseOutlined />} onClick={() => setAddingNodeId(null)}>取消</Button>
                <Button type="primary" icon={<PlusOutlined />} htmlType="submit">添加</Button>
              </Space>
            </div>
          </Form>
        </div>
      )
    }

    // 正常展示状态 - 横向布局，操作按钮直接显示
    return (
      <div
        className="template-item-row"
      >
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          {/* 图标 */}
          <div style={{
            width: 32,
            height: 32,
            borderRadius: 6,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: nodeData.is_category ? '#e6f4ff' : '#f6ffed',
          }}>
            {nodeData.is_category ? (
              <FolderOutlined style={{ color: '#1890ff', fontSize: 16 }} />
            ) : (
              <FileTextOutlined style={{ color: '#52c41a', fontSize: 16 }} />
            )}
          </div>

          {/* 标题 */}
          <span style={{
            fontWeight: nodeData.is_category ? 600 : 500,
            fontSize: nodeData.is_category ? 15 : 14,
            color: nodeData.is_category ? '#1890ff' : '#262626',
            minWidth: 120,
          }}>
            {nodeData.title}
          </span>

          {/* 类型标签 */}
          {nodeData.is_category ? (
            <Tag color="processing" style={{ borderRadius: 4 }}>分类</Tag>
          ) : nodeData.result_type ? (
            <Tag color={RESULT_TYPE_COLORS[nodeData.result_type]} style={{ borderRadius: 4 }}>
              {RESULT_TYPE_LABELS[nodeData.result_type]}
            </Tag>
          ) : null}

          {/* 风险等级标签 */}
          {!nodeData.is_category && nodeData.risk_level && (
            <Tag color={RISK_LEVEL_COLORS[nodeData.risk_level]} style={{ borderRadius: 4 }}>
              {RISK_LEVEL_LABELS[nodeData.risk_level]}
            </Tag>
          )}

          {/* 描述 - 横向显示 */}
          {!nodeData.is_category && nodeData.description && (
            <span style={{ color: '#595959', fontSize: 13, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              <span style={{ color: '#8c8c8c' }}>描述：</span>{nodeData.description}
            </span>
          )}

          {/* 检查方法 - 横向显示 */}
          {!nodeData.is_category && nodeData.check_method && (
            <span style={{ color: '#595959', fontSize: 13, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              <span style={{ color: '#8c8c8c' }}>方法：</span>{nodeData.check_method}
            </span>
          )}

          {/* 标准依据 - 横向显示 */}
          {!nodeData.is_category && nodeData.standard_ref && (
            <span style={{ color: '#595959', fontSize: 13, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              <span style={{ color: '#8c8c8c' }}>标准：</span>{nodeData.standard_ref}
            </span>
          )}

          {/* 数值范围 */}
          {!nodeData.is_category && nodeData.result_type === 'numeric' && (nodeData.min_value !== undefined || nodeData.max_value !== undefined) && (
            <Tag color="orange" style={{ borderRadius: 4 }}>
              范围：{nodeData.min_value !== undefined ? nodeData.min_value : '无下限'}
              ~ {nodeData.max_value !== undefined ? nodeData.max_value : '无上限'}
              {nodeData.unit ? ` ${nodeData.unit}` : ''}
            </Tag>
          )}
        </div>

        {/* 操作按钮 - 直接显示 */}
        <Space size={4}>
          <Tooltip title="添加子项">
            <Button
              type="text"
              size="small"
              icon={<PlusCircleOutlined style={{ color: '#1890ff' }} />}
              onClick={(e) => {
                e.stopPropagation()
                setAddingNodeId(nodeData.id)
                addItemForm.resetFields()
              }}
              style={{
                borderRadius: 4,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined style={{ color: '#52c41a' }} />}
              onClick={(e) => {
                e.stopPropagation()
                startEditNode(nodeData)
              }}
              style={{
                borderRadius: 4,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            />
          </Tooltip>
          <Tooltip title="删除">
            <Button
              type="text"
              size="small"
              icon={<DeleteOutlined style={{ color: '#ff4d4f' }} />}
              onClick={(e) => {
                e.stopPropagation()
                Modal.confirm({
                  title: '确认删除',
                  content: `确定要删除「${nodeData.title}」吗？${nodeData.children?.length ? '其下的所有子项也会被删除。' : ''}`,
                  onOk: () => handleDeleteItem(nodeData.id),
                })
              }}
              style={{
                borderRadius: 4,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            />
          </Tooltip>
        </Space>
      </div>
    )
  }

  const columns = [
    {
      title: '模板名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <span style={{ fontWeight: 500, color: '#1a1a2e' }}>{name}</span>
      )
    },
    {
      title: '类别',
      dataIndex: 'category',
      key: 'category',
      render: (category: string) => category ? (
        <Tag color="processing" style={{ borderRadius: 4 }}>{category}</Tag>
      ) : '-'
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      render: (version: string) => (
        <Tag color="default" style={{ borderRadius: 4 }}>v{version || '1.0'}</Tag>
      )
    },
    {
      title: '条目统计',
      key: 'stats',
      render: (_: any, record: any) => {
        const stats = record.stats
        if (!stats || stats.total_items === 0) {
          return <span style={{ color: '#bfbfbf' }}>暂无条目</span>
        }
        return (
          <Space size={8}>
            <Tooltip title="总条目数">
              <Tag color="blue" style={{ borderRadius: 4 }}>
                <FolderOutlined style={{ marginRight: 4 }} />
                {stats.total_items} 条
              </Tag>
            </Tooltip>
            <Tooltip title="分类目录数">
              <Tag color="cyan" style={{ borderRadius: 4 }}>
                <FolderOutlined style={{ marginRight: 4 }} />
                {stats.categories} 目录
              </Tag>
            </Tooltip>
            <Tooltip title="检查项数">
              <Tag color="green" style={{ borderRadius: 4 }}>
                <FileTextOutlined style={{ marginRight: 4 }} />
                {stats.check_items} 检查项
              </Tag>
            </Tooltip>
          </Space>
        )
      }
    },
    {
      title: '状态',
      dataIndex: 'is_published',
      key: 'is_published',
      render: (published: boolean) => (
        <Tag color={published ? 'success' : 'warning'} style={{ borderRadius: 6 }}>
          {published ? '已发布' : '未发布'}
        </Tag>
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => fetchTemplateDetail(record.id)}
          >
            编辑检查项
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑信息
          </Button>
          <Button
            type="link"
            size="small"
            icon={<CopyOutlined />}
            onClick={() => handleCopyTemplate(record.id)}
          >
            复制
          </Button>
          {!record.is_published && (
            <Button
              type="link"
              size="small"
              icon={<CheckCircleOutlined />}
              onClick={() => handlePublish(record.id)}
            >
              发布
            </Button>
          )}
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ]

  // 如果选中了模板，显示模板详情页面
  if (selectedTemplate) {
    // 如果选择了新版编辑器
    if (editorVersion === 'v2') {
      return (
        <TemplateEditorV2
          selectedTemplate={selectedTemplate}
          onBack={() => {
            setSelectedTemplate(null)
            setTreeData([])
            setAddingNodeId(null)
            setEditingNode(null)
            fetchTemplates()
          }}
          refreshTemplates={fetchTemplates}
          onSwitchToOld={() => setEditorVersion('v1')}
        />
      )
    }

    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div className="page-header" style={{
          background: 'linear-gradient(135deg, var(--primary-color) 0%, var(--primary-hover) 100%)',
          borderRadius: 'var(--border-radius)',
          marginBottom: 24,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Button
              type="default"
              icon={<ArrowLeftOutlined />}
              onClick={() => {
                setSelectedTemplate(null)
                setTreeData([])
                setAddingNodeId(null)
                setEditingNode(null)
                fetchTemplates()
              }}
              style={{
                background: 'rgba(255,255,255,0.9)',
                border: 'none',
                fontWeight: 500,
              }}
            >
              返回列表
            </Button>
            <div>
              <span style={{ fontSize: 20, fontWeight: 700, color: '#fff' }}>{selectedTemplate.name}</span>
              <Tag
                color={selectedTemplate.is_published ? 'success' : 'warning'}
                style={{ marginLeft: 12, borderRadius: 6 }}
              >
                {selectedTemplate.is_published ? '已发布' : '未发布'}
              </Tag>
            </div>
          </div>
          <Space size={12}>
            <Radio.Group
              value={editorVersion}
              onChange={(e: RadioChangeEvent) => setEditorVersion(e.target.value)}
              buttonStyle="solid"
              style={{ background: 'rgba(255,255,255,0.2)', borderRadius: 6, padding: 4 }}
            >
              <Radio.Button value="v1" style={{ borderRadius: 4 }}>旧版</Radio.Button>
              <Radio.Button value="v2" style={{ borderRadius: 4 }}>新版</Radio.Button>
            </Radio.Group>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setAddingNodeId('root')
                addItemForm.resetFields()
              }}
              style={{
                background: '#fff',
                color: 'var(--primary-color)',
                border: 'none',
                fontWeight: 500,
              }}
            >
              添加顶级项目
            </Button>
            <Button
              type="primary"
              icon={<RobotOutlined />}
              onClick={() => setAiModalOpen(true)}
              style={{
                background: 'linear-gradient(135deg, var(--success-color) 0%, #059669 100%)',
                border: 'none',
                fontWeight: 500,
              }}
            >
              AI辅助录入
            </Button>
            <Switch
              checkedChildren="已开启计分"
              unCheckedChildren="未启用计分"
              checked={selectedTemplate.is_quantified}
              onChange={async (checked) => {
                try {
                  await templateApi.updateTemplate(selectedTemplate.id, { is_quantified: checked })
                  message.success('模板计分状态已更新')
                  fetchTemplateDetail(selectedTemplate.id)
                  fetchTemplates()
                } catch {
                  message.error('更新模板计分状态失败')
                }
              }}
              style={{
                marginLeft: 16
              }}
            />
          </Space>
        </div>

        {selectedTemplate.description && (
          <div style={{
            marginBottom: 16,
            padding: '12px 16px',
            background: 'linear-gradient(90deg, rgba(100, 116, 139, 0.06) 0%, rgba(249, 115, 22, 0.06) 100%)',
            borderRadius: 'var(--border-radius-sm)',
            color: 'var(--text-muted)',
            fontSize: 14,
          }}>
            {selectedTemplate.description}
          </div>
        )}

        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <FileTextOutlined style={{ color: 'var(--primary-color)' }} />
              <span>检查项目</span>
              <Tag color="processing" style={{ borderRadius: 6 }}>{treeData.length} 个顶级项目</Tag>
            </div>
          }
          style={{ flex: 1, overflow: 'auto' }}
          bordered={false}
        >
          {/* 添加顶级项目表单 */}
          {addingNodeId === 'root' && (
            <div style={{
              background: '#e6f7ff',
              padding: '16px',
              borderRadius: 8,
              border: '1px solid #91d5ff',
              marginBottom: 16,
            }}>
              <div style={{ marginBottom: 12, fontWeight: 500, color: '#1890ff', fontSize: 14 }}>
                添加顶级项目
              </div>
              <Form form={addItemForm} layout="vertical" onFinish={handleAddItem}>
                <Row gutter={16}>
                  <Col span={6}>
                    <Form.Item name="title" label="名称" rules={[{ required: true }]} style={{ marginBottom: 12 }}>
                      <Input placeholder="输入名称" />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item name="is_category" label="节点类型" valuePropName="checked" style={{ marginBottom: 12 }}>
                      <Switch checkedChildren="分类节点" unCheckedChildren="检查项目" />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item name="result_type" label="结论类型" style={{ marginBottom: 12 }}>
                      <Radio.Group options={RESULT_TYPES} optionType="button" buttonStyle="solid" />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item name="standard_ref" label="标准依据" style={{ marginBottom: 12 }}>
                      <Input placeholder="标准依据" />
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item noStyle shouldUpdate={(prev, current) => prev.is_category !== current.is_category}>
                  {({ getFieldValue }) => {
                    const isCategory = getFieldValue('is_category')
                    if (isCategory) return null
                    return (
                      <>
                        <Form.Item noStyle shouldUpdate={(prev, current) => prev.result_type !== current.result_type}>
                          {({ getFieldValue }) => {
                            if (getFieldValue('result_type') === 'numeric') {
                              return (
                                <Row gutter={16} style={{ marginBottom: 12 }}>
                                  <Col span={6}>
                                    <Form.Item name="min_value" label="最小值" style={{ marginBottom: 0 }}>
                                      <InputNumber placeholder="最小" style={{ width: '100%' }} />
                                    </Form.Item>
                                  </Col>
                                  <Col span={6}>
                                    <Form.Item name="max_value" label="最大值" style={{ marginBottom: 0 }}>
                                      <InputNumber placeholder="最大" style={{ width: '100%' }} />
                                    </Form.Item>
                                  </Col>
                                  <Col span={6}>
                                    <Form.Item name="unit" label="单位" style={{ marginBottom: 0 }}>
                                      <Input placeholder="如：℃" style={{ width: '100%' }} />
                                    </Form.Item>
                                  </Col>
                                </Row>
                              )
                            }
                            return null
                          }}
                        </Form.Item>

                        <Row gutter={16}>
                          <Col span={8}>
                            <Form.Item name="description" label="项目描述" style={{ marginBottom: 12 }}>
                              <TextArea rows={2} placeholder="描述" />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item name="check_method" label="检查方法" style={{ marginBottom: 12 }}>
                              <TextArea rows={2} placeholder="检查方法" />
                            </Form.Item>
                          </Col>
                          <Col span={8}>
                            <Form.Item name="legal_basis" label="法律依据" style={{ marginBottom: 0 }}>
                              <TextArea rows={2} placeholder="法律依据" />
                            </Form.Item>
                          </Col>
                        </Row>
                      </>
                    )
                  }}
                </Form.Item>

                <div style={{ marginTop: 16, textAlign: 'right' }}>
                  <Space>
                    <Button icon={<CloseOutlined />} onClick={() => setAddingNodeId(null)}>取消</Button>
                    <Button type="primary" icon={<PlusOutlined />} htmlType="submit">添加</Button>
                  </Space>
                </div>
              </Form>
            </div>
          )}

          {/* 树形展示检查项目 */}
          {treeData.length > 0 ? (
            <Tree
              treeData={treeData.map(node => ({
                key: node.id,
                title: renderTreeNodeTitle(node),
                children: node.children?.map(child => ({
                  key: child.id,
                  title: renderTreeNodeTitle(child),
                  children: child.children?.map(grandChild => ({
                    key: grandChild.id,
                    title: renderTreeNodeTitle(grandChild),
                  })),
                })),
              }))}
              expandedKeys={expandedKeys}
              onExpand={(keys) => setExpandedKeys(keys as string[])}
              selectable={false}
              showLine
              blockNode
            />
          ) : addingNodeId !== 'root' ? (
            <Empty
              description="暂无检查项目"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            >
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  setAddingNodeId('root')
                  addItemForm.resetFields()
                }}
              >
                添加第一个项目
              </Button>
            </Empty>
          ) : null}
        </Card>

        <AiExtractModal
          open={aiModalOpen}
          onCancel={() => setAiModalOpen(false)}
          templateId={selectedTemplate?.id}
          onSuccess={() => {
            setAiModalOpen(false)
            fetchTemplateDetail(selectedTemplate.id)
            fetchTemplates()
          }}
        />
      </div>
    )
  }

  // 模板列表页面
  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">检查模板管理</h1>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setTemplateModal(true)}
          style={{
            background: 'linear-gradient(135deg, var(--primary-color) 0%, var(--primary-hover) 100%)',
            border: 'none',
          }}
        >
          新建模板
        </Button>
      </div>

      <Card bordered={false}>
        <Table
          columns={columns}
          dataSource={templates}
          loading={loading}
          rowKey="id"
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条记录`,
          }}
          style={{ borderRadius: 8 }}
        />
      </Card>

      {/* 创建/编辑模板弹窗 */}
      <Modal
        title={editingTemplate ? '编辑模板' : '新建模板'}
        open={templateModal}
        onCancel={() => {
          setTemplateModal(false)
          templateForm.resetFields()
          setEditingTemplate(null)
          setCopySourceId(null)
        }}
        onOk={() => templateForm.submit()}
      >
        <Form form={templateForm} layout="vertical" onFinish={handleCreateTemplate}>
          {!editingTemplate && (
            <>
              <Form.Item label="创建方式">
                <Select
                  value={copySourceId ? 'copy' : 'new'}
                  onChange={(value) => {
                    if (value === 'new') {
                      setCopySourceId(null)
                    } else if (value === 'copy' && templates.length > 0) {
                      setCopySourceId(templates[0].id)
                    }
                  }}
                >
                  <Select.Option value="new">新建空白模板</Select.Option>
                  <Select.Option value="copy" disabled={templates.length === 0}>
                    从现有模板复制
                  </Select.Option>
                </Select>
              </Form.Item>

              {copySourceId && (
                <Form.Item label="选择源模板">
                  <Select
                    value={copySourceId}
                    onChange={(value) => setCopySourceId(value)}
                    showSearch
                    optionFilterProp="children"
                    placeholder="选择要复制的模板"
                  >
                    {templates.map((t) => (
                      <Select.Option key={t.id} value={t.id}>
                        {t.name} {t.category ? `(${t.category})` : ''}
                      </Select.Option>
                    ))}
                  </Select>
                </Form.Item>
              )}

              <Divider style={{ margin: '12px 0' }} />
            </>
          )}

          <Form.Item name="name" label="模板名称" rules={[{ required: true }]}>
            <Input placeholder="如：食品安全检查模板" />
          </Form.Item>
          <Form.Item name="code" label="模板编码">
            <Input placeholder="如：SPAQ-2024" />
          </Form.Item>
          <Form.Item name="category" label="模板类别">
            <Select>
              <Select.Option value="食品安全">食品安全</Select.Option>
              <Select.Option value="安全生产">安全生产</Select.Option>
              <Select.Option value="质量管理">质量管理</Select.Option>
              <Select.Option value="环境保护">环境保护</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="description" label="模板描述">
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item name="is_quantified" label="启用计分" valuePropName="checked">
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
          <Form.Item name="version" label="版本号" initialValue="1.0">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
