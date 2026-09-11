import { useState, useEffect, useRef, useCallback } from 'react'
import { Button, Form, Input, Select, Tree, message, Space, Tag, InputNumber, Switch, Empty, Tooltip, Row, Col, Dropdown, Divider } from 'antd'
import { PlusOutlined, DeleteOutlined, ArrowLeftOutlined, FolderOutlined, FileTextOutlined, ExpandOutlined, CompressOutlined, RobotOutlined, HolderOutlined, SaveOutlined } from '@ant-design/icons'
import { templateApi } from '@/services/api'
import AiExtractModal from './AiExtractModal'

const { TextArea } = Input

const RESULT_TYPES = [
  { label: '合格/不合格', value: 'pass_fail' },
  { label: '数值判定', value: 'numeric' },
  { label: '文字描述', value: 'text' },
]

const RESULT_TYPE_COLORS: Record<string, string> = {
  pass_fail: 'success',
  numeric: 'warning',
  text: 'processing',
}

const RESULT_TYPE_LABELS: Record<string, string> = {
  pass_fail: '合格/不合格',
  numeric: '数值判定',
  text: '文字描述',
}

const RISK_LEVELS = [
  { label: '低风险', value: 'low' },
  { label: '中风险', value: 'medium' },
  { label: '高风险', value: 'high' },
]

const RISK_LEVEL_COLORS: Record<string, string> = {
  low: 'default',
  medium: 'warning',
  high: 'error',
}

const RISK_LEVEL_LABELS: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

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
  risk_level?: string
  is_category?: boolean
  sort_order?: number
  score_weight?: number
  default_score?: number
  allow_attachment?: boolean
  is_required?: boolean
  attachment_required?: boolean // legacy field, migrated to is_required
  ai_prompt_template?: string
  children?: TreeNodeData[]
  parent_id?: string | null
}

export default function TemplateEditorV2({
  selectedTemplate,
  onBack,
  refreshTemplates,
  onSwitchToOld,
}: {
  selectedTemplate: any
  onBack: () => void
  refreshTemplates: () => void
  onSwitchToOld?: () => void
}) {
  const [loading, setLoading] = useState(false)
  const [treeData, setTreeData] = useState<TreeNodeData[]>([])
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([])
  const [selectedNode, setSelectedNode] = useState<TreeNodeData | null>(null)
  const [editForm] = Form.useForm()
  const [aiModalOpen, setAiModalOpen] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(380)
  const [isDraggingPanel, setIsDraggingPanel] = useState(false)
  const [isQuantified, setIsQuantified] = useState(selectedTemplate?.is_quantified || false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (selectedTemplate) {
      setIsQuantified(selectedTemplate.is_quantified || false)
    }
  }, [selectedTemplate])

  useEffect(() => {
    if (selectedTemplate) {
      fetchTemplateDetail(selectedTemplate.id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTemplate])

  const fetchTemplateDetail = async (id: string, preserveSelection = true) => {
    try {
      const res: any = await templateApi.getTemplate(id)
      const items = res.data?.items || []
      setTreeData(items)

      if (!preserveSelection) {
        const allKeys = getAllNodeKeys(items)
        setExpandedKeys(allKeys)
      }

      if (preserveSelection && selectedNode) {
        const found = findNodeById(items, selectedNode.id)
        if (found) {
          setSelectedNode(found)
        } else {
          setSelectedNode(null)
          editForm.resetFields()
        }
      } else if (!preserveSelection) {
        setSelectedNode(null)
        editForm.resetFields()
      }
    } catch (error) {
      console.error('Failed to fetch template detail:', error)
      message.error('获取模板详情失败')
    }
  }

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

  const findNodeById = (nodes: TreeNodeData[], id: string): TreeNodeData | null => {
    for (const node of nodes) {
      if (node.id === id) return node
      if (node.children) {
        const found = findNodeById(node.children, id)
        if (found) return found
      }
    }
    return null
  }

  const handleSelect = (selectedKeys: React.Key[], info: any) => {
    if (selectedKeys.length > 0) {
      const node = info.node as unknown as TreeNodeData
      setSelectedNode(node)
      editForm.setFieldsValue({
        title: node.title,
        is_category: node.is_category,
        result_type: node.result_type || 'pass_fail',
        risk_level: node.risk_level || 'medium',
        description: node.description,
        check_method: node.check_method,
        legal_basis: node.legal_basis,
        standard_ref: node.standard_ref,
        min_value: node.min_value,
        max_value: node.max_value,
        unit: node.unit,
        use_ai: node.use_ai,
        score_weight: node.score_weight,
        default_score: node.default_score,
        attachment_required: node.attachment_required ?? false,
        ai_prompt_template: node.ai_prompt_template,
      })
    }
  }

  const handleExpand = (keys: React.Key[]) => {
    setExpandedKeys(keys)
  }

  const expandAll = () => {
    setExpandedKeys(getAllNodeKeys(treeData) as React.Key[])
  }

  const collapseAll = () => {
    setExpandedKeys([])
  }

  const handleAddSibling = async (node: TreeNodeData) => {
    try {
      const templateId = selectedTemplate.id
      const parentId = node.parent_id === undefined ? null : node.parent_id
      const payload = {
        title: '新同级节点',
        is_category: false,
        parent_id: parentId,
      }
      await templateApi.createItem(templateId, payload)
      message.success('添加同级节点成功')
      fetchTemplateDetail(templateId)
    } catch (error: any) {
      message.error(error?.response?.data?.message || '添加失败')
    }
  }

  const handleAddChild = async (node: TreeNodeData) => {
    try {
      const templateId = selectedTemplate.id
      const payload = {
        title: '新子节点',
        is_category: false,
        parent_id: node.id,
      }
      await templateApi.createItem(templateId, payload)
      message.success('添加子节点成功')
      fetchTemplateDetail(templateId)
      if (!expandedKeys.includes(node.id)) {
        setExpandedKeys([...expandedKeys, node.id])
      }
    } catch (error: any) {
      message.error(error?.response?.data?.message || '添加失败')
    }
  }

  const handleAddRoot = async () => {
    try {
      const templateId = selectedTemplate.id
      const payload = {
        title: '新根节点',
        is_category: false,
        parent_id: null,
      }
      await templateApi.createItem(templateId, payload)
      message.success('添加根节点成功')
      fetchTemplateDetail(templateId)
    } catch (error: any) {
      message.error(error?.response?.data?.message || '添加失败')
    }
  }

  const handleDeleteNode = async (node: TreeNodeData) => {
    try {
      await templateApi.deleteItem(node.id)
      message.success('删除成功')
      if (selectedNode?.id === node.id) {
        setSelectedNode(null)
      }
      fetchTemplateDetail(selectedTemplate.id)
    } catch (error) {
      message.error('删除失败')
    }
  }

  const handleSaveNode = async (values: any) => {
    if (!selectedNode) return
    try {
      setLoading(true)
      const payload = {
        title: values.title,
        is_category: values.is_category,
        result_type: values.is_category ? undefined : values.result_type,
        description: values.is_category ? undefined : values.description,
        check_method: values.is_category ? undefined : values.check_method,
        legal_basis: values.is_category ? undefined : values.legal_basis,
        standard_ref: values.is_category ? undefined : values.standard_ref,
        risk_level: values.is_category ? undefined : values.risk_level,
        min_value: !values.is_category && values.result_type === 'numeric' ? values.min_value : undefined,
        max_value: !values.is_category && values.result_type === 'numeric' ? values.max_value : undefined,
        unit: !values.is_category && values.result_type === 'numeric' ? values.unit : undefined,
        use_ai: values.use_ai,
        score_weight: !values.is_category ? values.score_weight : undefined,
        default_score: !values.is_category ? values.default_score : undefined,
        allow_attachment: true,
        attachment_required: !values.is_category ? (values.attachment_required ?? false) : undefined,
        ai_prompt_template: !values.is_category ? values.ai_prompt_template : undefined,
      }
      await templateApi.updateItem(selectedNode.id, payload)
      message.success('保存成功')
      fetchTemplateDetail(selectedTemplate.id)
    } catch (error: any) {
      message.error(error?.response?.data?.message || '保存失败')
    } finally {
      setLoading(false)
    }
  }

  const handleDrop = async (info: any) => {
    const dropNode = info.node
    const dragNode = info.dragNode
    const dropPos = info.node.pos.split('-')
    const dropPosition = info.dropPosition - Number(dropPos[dropPos.length - 1])

    const dragNodeId = dragNode.id
    const dropNodeId = dropNode.id

    if (!dragNodeId || !dropNodeId) {
      message.error('无法获取拖拽节点ID')
      return
    }
    if (dragNodeId === dropNodeId) {
      message.warning('不能将节点移动到自己')
      return
    }

    const isDescendant = (parentId: string, childId: string, nodes: TreeNodeData[]): boolean => {
      const parent = findNodeById(nodes, parentId)
      if (!parent || !parent.children) return false
      for (const child of parent.children) {
        if (child.id === childId) return true
        if (isDescendant(child.id, childId, nodes)) return true
      }
      return false
    }

    if (isDescendant(dragNodeId, dropNodeId, treeData)) {
      message.warning('不能将节点移动到其子节点下')
      return
    }

    try {
      let newParentId: string | null = null
      let newSortOrder = 0

      if (!info.dropToGap) {
        // Drop on the node content (become child)
        newParentId = dropNodeId
        const targetNode = findNodeById(treeData, dropNodeId)
        const children = targetNode?.children || []
        newSortOrder = children.length
      } else if (
        (dropNode.children || []).length > 0 &&
        info.node.expanded &&
        dropPosition === 1
      ) {
        // Drop on the bottom gap, but node is expanded. It visually becomes the 1st child
        newParentId = dropNodeId
        newSortOrder = 0
      } else {
        // Drop on the gap (before or after) as sibling
        newParentId = dropNode.parent_id === undefined ? null : dropNode.parent_id

        let siblings: TreeNodeData[] = []
        if (newParentId) {
          siblings = findNodeById(treeData, newParentId)?.children || []
        } else {
          siblings = treeData
        }

        const dropIndex = siblings.findIndex(s => s.id === dropNodeId)
        if (dropPosition === -1) {
          newSortOrder = Math.max(0, dropIndex)
        } else {
          newSortOrder = dropIndex + 1
        }
      }

      await templateApi.updateItem(dragNodeId, {
        parent_id: newParentId,
        sort_order: newSortOrder,
      })

      if (newParentId && !expandedKeys.includes(newParentId)) {
        setExpandedKeys(prev => [...prev, newParentId as React.Key])
      }

      message.success('移动排序成功')
      fetchTemplateDetail(selectedTemplate.id, true)
    } catch (error: any) {
      message.error(error?.response?.data?.message || '移动失败')
    }
  }

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDraggingPanel(true)
  }, [])

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDraggingPanel || !containerRef.current) return
    const containerRect = containerRef.current.getBoundingClientRect()
    const newWidth = e.clientX - containerRect.left
    if (newWidth >= 250 && newWidth <= 800) {
      setLeftPanelWidth(newWidth)
    }
  }, [isDraggingPanel])

  const handleMouseUp = useCallback(() => {
    setIsDraggingPanel(false)
  }, [])

  useEffect(() => {
    if (isDraggingPanel) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = 'col-resize'
    } else {
      document.body.style.cursor = ''
    }
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
    }
  }, [isDraggingPanel, handleMouseMove, handleMouseUp])

  const getNodeMenuItems = (node: TreeNodeData) => [
    {
      key: 'addChild',
      icon: <PlusOutlined />,
      label: '添加子项目',
      onClick: () => handleAddChild(node),
    },
    {
      key: 'addSibling',
      icon: <PlusOutlined />,
      label: '添加同级项目',
      onClick: () => handleAddSibling(node),
    },
    { type: 'divider' as const },
    {
      key: 'edit_mode',
      label: '快速切换分类属性',
      onClick: async () => {
        try {
          await templateApi.updateItem(node.id, { is_category: !node.is_category })
          message.success('切换属性成功')
          fetchTemplateDetail(selectedTemplate.id)
        } catch {
          message.error('切换失败')
        }
      }
    },
    { type: 'divider' as const },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: '删除',
      danger: true,
      onClick: () => handleDeleteNode(node),
    },
  ]

  const titleRender = (node: any) => {
    const isSelected = selectedNode?.id === node.id
    return (
      <Dropdown
        menu={{ items: getNodeMenuItems(node as TreeNodeData) }}
        trigger={['contextMenu']}
      >
        <div
          className={`tree-node-wrapper ${isSelected ? 'active' : ''}`}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '6px 10px',
            borderRadius: 6,
            transition: 'all 0.2s',
            border: isSelected ? '1px solid #91caff' : '1px solid transparent',
            background: isSelected ? '#e6f4ff' : 'transparent',
            userSelect: 'none',
          }}
        >
          <HolderOutlined className="drag-handle" style={{ color: '#bfbfbf', cursor: 'grab', display: 'flex' }} />
          {node.is_category ? (
            <FolderOutlined style={{ color: '#0369A1', fontSize: 16 }} />
          ) : (
            <FileTextOutlined style={{ color: '#22C55E', fontSize: 16 }} />
          )}
          <span style={{
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            fontWeight: node.is_category ? 600 : 400,
            fontSize: 14,
            color: '#333'
          }}>
            {node.title}
          </span>
          {node.is_category ? (
            <Tag color="cyan" bordered={false} style={{ margin: 0, borderRadius: 4, transform: 'scale(0.9)', transformOrigin: 'right' }}>
              分类
            </Tag>
          ) : (
            <div style={{ display: 'flex', gap: 4 }}>
              {node.result_type && (
                <Tag color={RESULT_TYPE_COLORS[node.result_type]} bordered={false} style={{ margin: 0, borderRadius: 4, transform: 'scale(0.9)', transformOrigin: 'right' }}>
                  {RESULT_TYPE_LABELS[node.result_type]}
                </Tag>
              )}
              {node.risk_level && (
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  backgroundColor: RISK_LEVEL_COLORS[node.risk_level] === 'default' ? '#d9d9d9' : RISK_LEVEL_COLORS[node.risk_level] === 'warning' ? '#faad14' : '#ff4d4f',
                  margin: 'auto 0 auto 4px'
                }} title={RISK_LEVEL_LABELS[node.risk_level]} />
              )}
            </div>
          )}
        </div>
      </Dropdown>
    )
  }

  return (
    <div style={{ height: 'calc(100vh - 100px)', display: 'flex', flexDirection: 'column', background: '#f5f7f9', borderRadius: 8, padding: 16, overflow: 'hidden' }}>

      {/* Header Area */}
      <div style={{
        background: 'linear-gradient(135deg, #0369A1 0%, #0284C7 100%)',
        borderRadius: 8,
        padding: '16px 24px',
        marginBottom: 16,
        flexShrink: 0,
        boxShadow: '0 4px 12px rgba(3, 105, 161, 0.25)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <Button
            type="default"
            icon={<ArrowLeftOutlined />}
            onClick={onBack}
            style={{
              background: 'rgba(255,255,255,0.95)',
              border: 'none',
              fontWeight: 600,
              boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
              borderRadius: 6
            }}
          >
            返回
          </Button>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <span style={{ fontSize: 22, fontWeight: 700, color: '#fff', letterSpacing: 0.5 }}>{selectedTemplate.name}</span>
            <Tag
              color={selectedTemplate.is_published ? '#22C55E' : 'rgba(255,255,255,0.2)'}
              style={{ marginLeft: 16, borderRadius: 6, border: 'none', color: '#fff', fontWeight: 600 }}
            >
              {selectedTemplate.is_published ? '🟢 已发布' : '🟡 未发布'}
            </Tag>
          </div>
        </div>
        <Space size={12}>
          {onSwitchToOld && (
            <Button
              onClick={onSwitchToOld}
              style={{
                background: 'rgba(255,255,255,0.2)',
                color: '#fff',
                border: '1px solid rgba(255,255,255,0.3)',
                fontWeight: 500,
                borderRadius: 6
              }}
            >
              切换旧版
            </Button>
          )}
          <Switch
            checkedChildren="已开启计分"
            unCheckedChildren="未启用计分"
            checked={isQuantified}
            onChange={async (checked) => {
              try {
                await templateApi.updateTemplate(selectedTemplate.id, { is_quantified: checked })
                setIsQuantified(checked)
                message.success('模板计分状态已更新')
                refreshTemplates()
              } catch {
                message.error('更新模板计分状态失败')
              }
            }}
          />
          <Button
            type="primary"
            size="large"
            icon={<RobotOutlined />}
            onClick={() => setAiModalOpen(true)}
            style={{
              background: '#fff',
              color: '#0369A1',
              border: 'none',
              fontWeight: 600,
              borderRadius: 6,
              boxShadow: '0 4px 8px rgba(0,0,0,0.1)'
            }}
          >
            AI 智能录入
          </Button>
        </Space>
      </div>

      {/* Main Content Area */}
      <div ref={containerRef} style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0, gap: 16 }}>

        {/* Left Tree Panel */}
        <div style={{
          width: leftPanelWidth,
          background: '#fff',
          borderRadius: 8,
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
          overflow: 'hidden',
          flexShrink: 0,
        }}>
          <div style={{
            padding: '16px 20px',
            borderBottom: '1px solid #f0f0f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: '#fafafa',
          }}>
            <span style={{ fontWeight: 600, fontSize: 16, color: '#1f2937' }}>模板结构视图</span>
            <Space size={8}>
              <Tooltip title="添加根节点">
                <Button type="primary" ghost size="small" icon={<PlusOutlined />} onClick={handleAddRoot} />
              </Tooltip>
              <Tooltip title="展开全部">
                <Button type="default" size="small" icon={<ExpandOutlined />} onClick={expandAll} />
              </Tooltip>
              <Tooltip title="折叠全部">
                <Button type="default" size="small" icon={<CompressOutlined />} onClick={collapseAll} />
              </Tooltip>
            </Space>
          </div>

          <div style={{ flex: 1, overflow: 'auto', padding: '12px 8px', minHeight: 0 }}>
            {treeData.length > 0 ? (
              <Tree
                treeData={treeData as any[]}
                fieldNames={{ key: 'id', title: 'title', children: 'children' }}
                expandedKeys={expandedKeys}
                onExpand={handleExpand}
                onSelect={handleSelect}
                onDrop={handleDrop}
                selectedKeys={selectedNode ? [selectedNode.id] : []}
                draggable={{
                  icon: false,
                  nodeDraggable: () => true,
                }}
                titleRender={titleRender}
                blockNode
                virtual={true}
                showLine={{ showLeafIcon: false }}
                style={{
                  background: 'transparent'
                }}
              />
            ) : (
              <Empty
                description={<span style={{ color: '#8c8c8c' }}>这里空空如也，快来创建项目吧</span>}
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                style={{ marginTop: 60 }}
              >
                <Button type="primary" icon={<PlusOutlined />} onClick={handleAddRoot} size="large" style={{ borderRadius: 6 }}>
                  立即创建根节点
                </Button>
              </Empty>
            )}
          </div>
        </div>

        {/* Resizer */}
        <div
          style={{
            width: 8,
            cursor: 'col-resize',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 4,
            background: isDraggingPanel ? '#0369A1' : 'transparent',
            transition: 'background 0.2s',
            zIndex: 10,
          }}
          onMouseDown={handleMouseDown}
          className="panel-resizer"
        >
          <div style={{ width: 4, height: 32, background: '#d9d9d9', borderRadius: 2 }} className="resizer-handle" />
        </div>

        {/* Right Detail Panel */}
        <div style={{
          flex: 1,
          background: '#fff',
          borderRadius: 8,
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
          overflow: 'hidden',
        }}>
          {selectedNode ? (
            <>
              <div style={{
                padding: '16px 24px',
                borderBottom: '1px solid #f0f0f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: '#fafafa',
              }}>
                <span style={{ fontWeight: 600, fontSize: 16, color: '#1f2937' }}>节点配置 - {selectedNode.title}</span>
                <Space size={12}>
                  <Button icon={<PlusOutlined />} onClick={() => handleAddSibling(selectedNode)}>同级</Button>
                  <Button type="primary" ghost icon={<PlusOutlined />} onClick={() => handleAddChild(selectedNode)}>子级</Button>
                  <Button danger icon={<DeleteOutlined />} onClick={() => handleDeleteNode(selectedNode)}>删除</Button>
                </Space>
              </div>

              <div style={{ flex: 1, overflow: 'auto', padding: '24px 32px' }}>
                <Form
                  form={editForm}
                  layout="vertical"
                  onFinish={handleSaveNode}
                  initialValues={{ is_category: false, use_ai: false }}
                  requiredMark="optional"
                >
                  {/* ----- 基本信息 ----- */}
                  <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
                    <span style={{ width: 4, height: 16, background: '#0369A1', borderRadius: 2, marginRight: 8 }}></span>
                    <span style={{ fontSize: 15, fontWeight: 600, color: '#1f2937' }}>基本信息</span>
                  </div>

                  <Row gutter={32}>
                    <Col span={10}>
                      <Form.Item name="title" label="条目名称" rules={[{ required: true, message: '请输入条目名称' }]}>
                        <Input placeholder="输入条目名称" style={{ borderRadius: 6 }} size="large" />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item
                        name="is_category"
                        label="条目属性：分类目录 / 检查项"
                        valuePropName="checked"
                        tooltip="【分类目录】仅作为层级容器和分组标题，现场审核时不作为考核项；【具体检查项】需录入检查结论、指标与证据佐证"
                      >
                        <Switch checkedChildren="📂 分类目录（分组）" unCheckedChildren="📝 检查项（需评定）" />
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item name="use_ai" label="是否允许AI智能判断" valuePropName="checked">
                        <Switch checkedChildren="🤖 已开启" unCheckedChildren="关闭" />
                      </Form.Item>
                    </Col>
                  </Row>

                  {/* ----- 检查设置 ----- */}
                  <Form.Item noStyle shouldUpdate={(prev, current) => prev.is_category !== current.is_category}>
                    {({ getFieldValue }) => {
                      const isCategory = getFieldValue('is_category')
                      if (isCategory) return (
                        <div style={{ padding: '36px 0', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: 8, border: '1px dashed #cbd5e1' }}>
                          📂 <strong>当前条目设为分类目录</strong>：仅作为层级结构分组展示，现场审核时不作为检查项考核，请在其下方添加具体检查项
                        </div>
                      )
                      return (
                        <div style={{ marginTop: 8 }}>
                          <Divider style={{ margin: '12px 0 24px 0' }} />
                          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
                            <span style={{ width: 4, height: 16, background: '#22C55E', borderRadius: 2, marginRight: 8 }}></span>
                            <span style={{ fontSize: 15, fontWeight: 600, color: '#1f2937' }}>检查指标</span>
                          </div>

                          <Row gutter={32}>
                            <Col span={8}>
                              <Form.Item name="result_type" label="采集结果类型" rules={[{ required: true }]}>
                                <Select options={RESULT_TYPES} size="large" placeholder="选择类型" style={{ width: '100%' }} />
                              </Form.Item>
                            </Col>
                            <Col span={8}>
                              <Form.Item name="risk_level" label="异常风险等级">
                                <Select options={RISK_LEVELS} size="large" placeholder="选择风险" style={{ width: '100%' }} />
                              </Form.Item>
                            </Col>
                            <Col span={8}>
                              <Form.Item name="standard_ref" label="标准依据编号">
                                <Input placeholder="如：GB/T 12345" size="large" />
                              </Form.Item>
                            </Col>
                          </Row>

                          <Form.Item noStyle shouldUpdate={(prev, current) => prev.result_type !== current.result_type}>
                            {({ getFieldValue }) => {
                              if (getFieldValue('result_type') === 'numeric') {
                                return (
                                  <div style={{ background: '#fffbe6', padding: 16, borderRadius: 8, marginBottom: 24, border: '1px solid #ffe58f' }}>
                                    <Row gutter={24}>
                                      <Col span={8}>
                                        <Form.Item name="min_value" label={<span style={{ color: '#d46b08' }}>阈值 - 最小值</span>} style={{ marginBottom: 0 }}>
                                          <InputNumber placeholder="最小数值" size="large" style={{ width: '100%' }} />
                                        </Form.Item>
                                      </Col>
                                      <Col span={8}>
                                        <Form.Item name="max_value" label={<span style={{ color: '#d46b08' }}>阈值 - 最大值</span>} style={{ marginBottom: 0 }}>
                                          <InputNumber placeholder="最大数值" size="large" style={{ width: '100%' }} />
                                        </Form.Item>
                                      </Col>
                                      <Col span={8}>
                                        <Form.Item name="unit" label={<span style={{ color: '#d46b08' }}>计量单位</span>} style={{ marginBottom: 0 }}>
                                          <Input placeholder="如：℃, mm, Mpa" size="large" />
                                        </Form.Item>
                                      </Col>
                                    </Row>
                                  </div>
                                )
                              }
                              return null
                            }}
                          </Form.Item>

                          <Divider style={{ margin: '12px 0 24px 0' }} />
                          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
                            <span style={{ width: 4, height: 16, background: '#722ed1', borderRadius: 2, marginRight: 8 }}></span>
                            <span style={{ fontSize: 15, fontWeight: 600, color: '#1f2937' }}>详细说明</span>
                          </div>

                          <Row gutter={32}>
                            <Col span={24}>
                              <Form.Item name="description" label="项目描述 / 检查内容">
                                <TextArea rows={3} placeholder="详细描述该项需要检查的具体内容" style={{ borderRadius: 6 }} />
                              </Form.Item>
                            </Col>
                            <Col span={12}>
                              <Form.Item name="check_method" label="检查方法操作指导">
                                <TextArea rows={3} placeholder="如何进行此项检查（工具、步骤等）" style={{ borderRadius: 6 }} />
                              </Form.Item>
                            </Col>
                            <Col span={12}>
                              <Form.Item name="legal_basis" label="相关法律/法规条款">
                                <TextArea rows={3} placeholder="对应的法律法规明细" style={{ borderRadius: 6 }} />
                              </Form.Item>
                            </Col>
                          </Row>

                          {/* ---- 附件配置 ---- */}
                          <Divider style={{ margin: '12px 0 20px 0' }} />
                          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
                            <span style={{ width: 4, height: 16, background: '#0ea5e9', borderRadius: 2, marginRight: 8 }}></span>
                            <span style={{ fontSize: 15, fontWeight: 600, color: '#1f2937' }}>附件配置</span>
                            <span style={{ marginLeft: 8, fontSize: 12, color: '#8c8c8c' }}>所有检查项均支持上传附件</span>
                          </div>
                          <Row gutter={32}>
                            <Col span={8}>
                              <Form.Item
                                name="attachment_required"
                                label="附件是否必填"
                                valuePropName="checked"
                                tooltip="开启后，完成该检查项时必须上传至少一张附件照片"
                              >
                                <Switch checkedChildren="📎 必须上传" unCheckedChildren="选填" />
                              </Form.Item>
                            </Col>
                          </Row>

                          {/* ---- 量化配置（仅启用计分时显示） ---- */}
                          {isQuantified && (
                            <>
                              <Divider style={{ margin: '12px 0 20px 0' }} />
                              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
                                <span style={{ width: 4, height: 16, background: '#F59E0B', borderRadius: 2, marginRight: 8 }}></span>
                                <span style={{ fontSize: 15, fontWeight: 600, color: '#1f2937' }}>量化配置</span>
                                <span style={{ marginLeft: 8, fontSize: 12, color: '#8c8c8c' }}>当前模板已启用计分，以下配置生效</span>
                              </div>
                              <Row gutter={32}>
                                <Col span={12}>
                                  <Form.Item name="score_weight" label="节点权重 (满分)">
                                    <InputNumber placeholder="权重数值" size="large" style={{ width: '100%' }} />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item name="default_score" label="默认得分">
                                    <InputNumber placeholder="默认得分" size="large" style={{ width: '100%' }} />
                                  </Form.Item>
                                </Col>
                              </Row>
                            </>
                          )}

                          {/* ---- AI 提示词 ---- */}
                          <Divider style={{ margin: '12px 0 20px 0' }} />
                          <Row gutter={32}>
                            <Col span={24}>
                              <Form.Item name="ai_prompt_template" label="AI 提示词模板 (当开启AI辅助时生效)">
                                <TextArea rows={3} placeholder="在此配置特定的 AI 提示词指令" style={{ borderRadius: 6 }} />
                              </Form.Item>
                            </Col>
                          </Row>
                        </div>
                      )
                    }}
                  </Form.Item>

                  <div style={{ position: 'sticky', bottom: 0, padding: '16px 0', background: '#fff', textAlign: 'right', marginTop: 8, borderTop: '1px solid #f0f0f0', display: 'flex', justifyContent: 'flex-end', zIndex: 10 }}>
                    <Button type="primary" size="large" htmlType="submit" icon={<SaveOutlined />} loading={loading} style={{ width: 140, borderRadius: 6, fontWeight: 600 }}>
                      保存配置
                    </Button>
                  </div>
                </Form>
              </div>
            </>
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
              <Empty
                description={<span style={{ fontSize: 16, color: '#8c8c8c' }}>点击左侧节点进行详情配置</span>}
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                style={{ transform: 'scale(1.2)' }}
              />
            </div>
          )}
        </div>
      </div>

      <AiExtractModal
        open={aiModalOpen}
        onCancel={() => setAiModalOpen(false)}
        templateId={selectedTemplate?.id}
        onSuccess={() => {
          setAiModalOpen(false)
          fetchTemplateDetail(selectedTemplate.id)
          refreshTemplates()
        }}
      />

      <style>{`
        .tree-node-wrapper {
          position: relative;
        }
        .tree-node-wrapper:hover {
          background: rgba(0, 0, 0, 0.02);
        }
        .ant-tree .ant-tree-node-content-wrapper {
          padding: 0 !important;
          border-radius: 6px;
        }
        .ant-tree .ant-tree-node-content-wrapper.ant-tree-node-selected {
          background-color: transparent !important;
        }
        .ant-tree-title {
          width: 100%;
        }
        .drag-handle {
          opacity: 0.3;
          transition: opacity 0.2s;
        }
        .tree-node-wrapper:hover .drag-handle {
          opacity: 1;
        }
        .panel-resizer:hover .resizer-handle {
          background: #0369A1 !important;
        }

        /* Highlight node visually when dragged over to become child */
        .ant-tree-node-content-wrapper.drag-over .tree-node-wrapper {
          border: 2px dashed #0369A1 !important;
          background: rgba(3, 105, 161, 0.08) !important;
          box-shadow: inset 0 0 0 1px rgba(3, 105, 161, 0.1);
          transform: scale(0.98);
          transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
        }
        
        /* Custom Tree Drag & Drop Indicator Styles for high visibility */
        .ant-tree .ant-tree-drop-indicator {
          background-color: #0369A1;
          height: 3px;
          border-radius: 2px;
          z-index: 10;
        }
        .ant-tree .ant-tree-drop-indicator::after {
           content: '';
           position: absolute;
           left: -4px;
           top: -2px;
           width: 8px;
           height: 8px;
           background-color: #0369A1;
           border-radius: 50%;
           border: 2px solid #fff;
        }
      `}</style>
    </div>
  )
}
