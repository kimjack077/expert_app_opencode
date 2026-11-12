import React, { useState, useEffect, useCallback } from 'react';
import { Button, Form, Input, InputNumber, Switch, message, Space, Tag, Tree, Dropdown, Empty, Tooltip, Divider } from 'antd';
import { PlusOutlined, DeleteOutlined, FolderOutlined, FolderOpenOutlined, ExpandOutlined, CompressOutlined, HolderOutlined, SaveOutlined, EditOutlined } from '@ant-design/icons';
import { industryApi } from '@/services/api';

const { TextArea } = Input

interface TreeNodeData {
  id: string
  name: string
  code?: string
  description?: string
  parent_id?: string | null
  sort_order?: number
  icon?: string
  is_active?: boolean
  created_at?: string
  updated_at?: string
  children?: TreeNodeData[]
}

const Industries: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [treeData, setTreeData] = useState<TreeNodeData[]>([])
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([])
  const [selectedNode, setSelectedNode] = useState<TreeNodeData | null>(null)
  const [editForm] = Form.useForm()
  const [hasChanges, setHasChanges] = useState(false)

  useEffect(() => {
    fetchTreeData()
  }, [])

  const fetchTreeData = async (preserveSelection = true) => {
    setLoading(true)
    try {
      const res: any = await industryApi.getTree()
      const items = res.data || []
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
      console.error('Failed to fetch industry tree:', error)
      message.error('获取行业分类失败')
    } finally {
      setLoading(false)
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
      setHasChanges(false)
      editForm.setFieldsValue({
        name: node.name,
        code: node.code,
        description: node.description,
        sort_order: node.sort_order || 0,
        is_active: node.is_active !== false,
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

  const handleAddRoot = async () => {
    try {
      const payload = {
        name: '新行业分类',
        is_active: true,
        sort_order: 0,
      }
      await industryApi.createIndustry(payload)
      message.success('添加成功')
      fetchTreeData()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '添加失败')
    }
  }

  const handleAddChild = async (parentNode: TreeNodeData) => {
    try {
      const payload = {
        name: '新子分类',
        parent_id: parentNode.id,
        is_active: true,
        sort_order: 0,
      }
      await industryApi.createIndustry(payload)
      message.success('添加子分类成功')
      fetchTreeData()
      if (!expandedKeys.includes(parentNode.id)) {
        setExpandedKeys([...expandedKeys, parentNode.id])
      }
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '添加失败')
    }
  }

  const handleAddSibling = async (node: TreeNodeData) => {
    try {
      const payload = {
        name: '新同级分类',
        parent_id: node.parent_id || null,
        is_active: true,
        sort_order: 0,
      }
      await industryApi.createIndustry(payload)
      message.success('添加同级分类成功')
      fetchTreeData()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '添加失败')
    }
  }

  const handleDeleteNode = async (node: TreeNodeData) => {
    try {
      await industryApi.deleteIndustry(node.id)
      message.success('删除成功')
      if (selectedNode?.id === node.id) {
        setSelectedNode(null)
        editForm.resetFields()
      }
      fetchTreeData()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '删除失败')
    }
  }

  const handleSaveNode = async (values: any) => {
    if (!selectedNode) return
    try {
      setLoading(true)
      const payload = {
        name: values.name,
        code: values.code || null,
        description: values.description,
        sort_order: values.sort_order || 0,
        is_active: values.is_active,
      }
      await industryApi.updateIndustry(selectedNode.id, payload)
      message.success('保存成功')
      setHasChanges(false)
      fetchTreeData()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '保存失败')
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

      if (!info.dropToGap) {
        newParentId = dropNodeId
      } else if (
        (dropNode.children || []).length > 0 &&
        info.node.expanded &&
        dropPosition === 1
      ) {
        newParentId = dropNodeId
      } else {
        newParentId = dropNode.parent_id || null
      }

      await industryApi.updateIndustry(dragNodeId, {
        parent_id: newParentId,
      })

      if (newParentId && !expandedKeys.includes(newParentId)) {
        setExpandedKeys(prev => [...prev, newParentId as React.Key])
      }

      message.success('移动成功')
      fetchTreeData()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '移动失败')
    }
  }

  const getNodeMenuItems = (node: TreeNodeData) => [
    {
      key: 'addChild',
      icon: <PlusOutlined />,
      label: '添加子分类',
      onClick: () => handleAddChild(node),
    },
    {
      key: 'addSibling',
      icon: <PlusOutlined />,
      label: '添加同级分类',
      onClick: () => handleAddSibling(node),
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
    const hasChildren = node.children && node.children.length > 0
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
          {hasChildren ? (
            <FolderOutlined style={{ color: '#0369A1', fontSize: 16 }} />
          ) : (
            <FolderOpenOutlined style={{ color: '#6b7280', fontSize: 16 }} />
          )}
          <span style={{
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            fontWeight: hasChildren ? 600 : 400,
            fontSize: 14,
            color: '#333'
          }}>
            {node.name}
          </span>
          {node.code && (
            <Tag color="blue" bordered={false} style={{ margin: 0, borderRadius: 4, transform: 'scale(0.9)', transformOrigin: 'right' }}>
              {node.code}
            </Tag>
          )}
          {node.is_active === false && (
            <Tag color="red" bordered={false} style={{ margin: 0, borderRadius: 4, transform: 'scale(0.9)', transformOrigin: 'right' }}>
              禁用
            </Tag>
          )}
        </div>
      </Dropdown>
    )
  }

  const handleFormValuesChange = useCallback(() => {
    setHasChanges(true)
  }, [])

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
          <span style={{ fontSize: 22, fontWeight: 700, color: '#fff', letterSpacing: 0.5 }}>行业分类管理</span>
          <Tag color="rgba(255,255,255,0.2)" style={{ borderRadius: 6, border: 'none', color: '#fff' }}>
            共 {getAllNodeKeys(treeData).length} 个分类
          </Tag>
        </div>
        <Space size={12}>
          <Button
            icon={<ExpandOutlined />}
            onClick={expandAll}
            style={{
              background: 'rgba(255,255,255,0.2)',
              color: '#fff',
              border: '1px solid rgba(255,255,255,0.3)',
              fontWeight: 500,
              borderRadius: 6
            }}
          >
            展开全部
          </Button>
          <Button
            icon={<CompressOutlined />}
            onClick={collapseAll}
            style={{
              background: 'rgba(255,255,255,0.2)',
              color: '#fff',
              border: '1px solid rgba(255,255,255,0.3)',
              fontWeight: 500,
              borderRadius: 6
            }}
          >
            折叠全部
          </Button>
          <Button
            type="primary"
            size="large"
            icon={<PlusOutlined />}
            onClick={handleAddRoot}
            style={{
              background: '#fff',
              color: '#0369A1',
              border: 'none',
              fontWeight: 600,
              borderRadius: 6,
              boxShadow: '0 4px 8px rgba(0,0,0,0.1)'
            }}
          >
            添加顶级分类
          </Button>
        </Space>
      </div>

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0, gap: 16 }}>

        {/* Left Tree Panel */}
        <div style={{
          width: 420,
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
            <span style={{ fontWeight: 600, color: '#333', fontSize: 15 }}>分类树</span>
            <span style={{ fontSize: 12, color: '#999' }}>右键可添加/删除</span>
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: '12px 8px' }}>
            {treeData.length === 0 ? (
              <Empty
                description="暂无行业分类"
                style={{ marginTop: 60 }}
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Button type="primary" icon={<PlusOutlined />} onClick={handleAddRoot}>
                  添加第一个分类
                </Button>
              </Empty>
            ) : (
              <Tree
                treeData={treeData}
                fieldNames={{ key: 'id', title: 'name', children: 'children' }}
                expandedKeys={expandedKeys}
                selectedKeys={selectedNode ? [selectedNode.id] : []}
                onSelect={handleSelect}
                onExpand={handleExpand}
                titleRender={titleRender}
                draggable
                onDrop={handleDrop}
                blockNode
                style={{ fontSize: 14 }}
              />
            )}
          </div>
        </div>

        {/* Right Edit Panel */}
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
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <EditOutlined style={{ color: '#0369A1', fontSize: 18 }} />
                  <span style={{ fontWeight: 600, color: '#333', fontSize: 15 }}>编辑分类</span>
                  {hasChanges && (
                    <Tag color="orange" style={{ marginLeft: 8 }}>未保存</Tag>
                  )}
                </div>
                <Space>
                  <Button
                    type="primary"
                    icon={<SaveOutlined />}
                    onClick={() => editForm.submit()}
                    loading={loading}
                    style={{ borderRadius: 6 }}
                  >
                    保存
                  </Button>
                  <Button
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleDeleteNode(selectedNode)}
                    style={{ borderRadius: 6 }}
                  >
                    删除
                  </Button>
                </Space>
              </div>
              <div style={{ flex: 1, overflow: 'auto', padding: '24px 32px' }}>
                <Form
                  form={editForm}
                  layout="vertical"
                  onFinish={handleSaveNode}
                  onValuesChange={handleFormValuesChange}
                  style={{ maxWidth: 600 }}
                >
                  <Form.Item
                    name="name"
                    label="分类名称"
                    rules={[{ required: true, message: '请输入分类名称' }]}
                  >
                    <Input placeholder="请输入分类名称" size="large" style={{ borderRadius: 6 }} />
                  </Form.Item>
                  <Form.Item name="code" label="分类编码">
                    <Input placeholder="请输入分类编码（可选）" style={{ borderRadius: 6 }} />
                  </Form.Item>
                  <Form.Item name="description" label="描述">
                    <TextArea placeholder="请输入描述" rows={3} style={{ borderRadius: 6 }} />
                  </Form.Item>
                  <Form.Item name="sort_order" label="排序" tooltip="数值越小越靠前">
                    <InputNumber min={0} style={{ width: '100%', borderRadius: 6 }} />
                  </Form.Item>
                  <Form.Item name="is_active" label="状态" valuePropName="checked">
                    <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                  </Form.Item>
                </Form>
              </div>
            </>
          ) : (
            <div style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#999',
            }}>
              <Empty
                description="请从左侧选择一个分类进行编辑"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            </div>
          )}
        </div>
      </div>

      <style>{`
        .tree-node-wrapper:hover {
          background: #f5f5f5;
        }
        .tree-node-wrapper.active {
          background: #e6f4ff;
          border-color: #91caff;
        }
        .drag-handle:hover {
          color: #0369A1 !important;
        }
        .ant-tree-node-content-wrapper {
          padding: 0 !important;
          flex: 1;
        }
        .ant-tree-treenode {
          width: 100%;
          padding: 2px 0 !important;
        }
        .ant-tree-draggable-icon {
          display: none;
        }
      `}</style>
    </div>
  )
}

export default Industries
