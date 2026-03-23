import { useState, useEffect } from 'react'
import { Card, Table, Button, Tag, Space, message, Modal, Drawer, Popconfirm, Alert, Collapse, Form, Input, Select, DatePicker, Row, Col, Badge } from 'antd'
import { EyeOutlined, DeleteOutlined, CheckCircleOutlined, FileTextOutlined, FilePdfOutlined, SearchOutlined, ReloadOutlined, FilterOutlined } from '@ant-design/icons'
import { recordApi, templateApi } from '@/services/api'
import dayjs from 'dayjs'
import { useNavigate } from 'react-router-dom'
import InspectionReport from './InspectionReport'

const { RangePicker } = DatePicker
const { Panel } = Collapse

export default function Records() {
  const navigate = useNavigate()
  const [records, setRecords] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [selectedRecord, setSelectedRecord] = useState<any>(null)
  const [detailDrawer, setDetailDrawer] = useState(false)
  const [reportRecord, setReportRecord] = useState<any>(null)
  const [reportVisible, setReportVisible] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 })
  const [sorter, setSorter] = useState<{ field: string | null; order: 'ascend' | 'descend' | null }>({ field: null, order: null })

  // 筛选相关状态
  const [filters, setFilters] = useState({
    enterprise_name: '',
    status: undefined as string | undefined,
    overall_result: undefined as string | undefined,
    template_id: undefined as string | undefined,
    dateRange: null as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null,
  })
  const [templates, setTemplates] = useState<any[]>([])
  const [activeFilterKeys, setActiveFilterKeys] = useState<string[]>([])

  useEffect(() => {
    fetchRecords()
    fetchTemplates()
  }, [pagination.current, pagination.pageSize, sorter.field, sorter.order])

  // 获取模板列表用于筛选
  const fetchTemplates = async () => {
    try {
      const res: any = await templateApi.getTemplates({ limit: 100 })
      setTemplates(res.data || [])
    } catch (error) {
      console.error('Failed to fetch templates:', error)
    }
  }

  const fetchRecords = async () => {
    setLoading(true)
    try {
      const params: any = {
        skip: (pagination.current - 1) * pagination.pageSize,
        limit: pagination.pageSize,
      }
      if (sorter.field && sorter.order) {
        params.sort_by = sorter.field
        params.sort_order = sorter.order === 'ascend' ? 'asc' : 'desc'
      }
      // 添加筛选条件
      if (filters.enterprise_name) {
        params.enterprise_name = filters.enterprise_name
      }
      if (filters.status) {
        params.status = filters.status
      }
      if (filters.overall_result) {
        params.overall_result = filters.overall_result
      }
      if (filters.template_id) {
        params.template_id = filters.template_id
      }
      if (filters.dateRange && filters.dateRange[0] && filters.dateRange[1]) {
        params.start_date = filters.dateRange[0].startOf('day').toISOString()
        params.end_date = filters.dateRange[1].endOf('day').toISOString()
      }
      const res: any = await recordApi.getRecords(params)
      setRecords(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } catch (error) {
      console.error('Failed to fetch records:', error)
      message.error('获取记录列表失败')
    } finally {
      setLoading(false)
    }
  }

  // 处理筛选条件变化
  const handleFilterChange = (key: string, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  // 重置筛选条件
  const handleResetFilters = () => {
    setFilters({
      enterprise_name: '',
      status: undefined,
      overall_result: undefined,
      template_id: undefined,
      dateRange: null,
    })
    setPagination(prev => ({ ...prev, current: 1 }))
  }

  // 执行搜索
  const handleSearch = () => {
    setPagination(prev => ({ ...prev, current: 1 }))
    fetchRecords()
  }

  // 计算当前激活的筛选条件数量
  const activeFilterCount = [
    filters.enterprise_name,
    filters.status,
    filters.overall_result,
    filters.template_id,
    filters.dateRange,
  ].filter(Boolean).length


  const handleViewDetail = async (record: any) => {
    try {
      const res: any = await recordApi.getRecord(record.id)
      setSelectedRecord(res.data)
      setDetailDrawer(true)
    } catch (error) {
      console.error('Failed to fetch record detail:', error)
      message.error('获取记录详情失败')
    }
  }

  const handleSubmit = async (id: string) => {
    // 先获取记录详情进行校验
    try {
      const res: any = await recordApi.getRecord(id)
      const recordData = res.data

      // 扁平化检查项
      const flattenItems = (items: any[], result: any[] = []): any[] => {
        for (const item of items) {
          if (!item.is_category) {
            result.push(item)
          }
          if (item.children && item.children.length > 0) {
            flattenItems(item.children, result)
          }
        }
        return result
      }

      const flatItems = flattenItems(recordData?.template?.items || [])

      // 校验必填项和必传附件
      const incompleteItems: string[] = []
      const missingAttachments: string[] = []

      flatItems.forEach((item, index) => {
        // 检查必填项是否已填写
        if (item.is_required !== false) {
          const hasResult = item.radio_value ||
            item.numeric_value !== undefined ||
            item.text_value ||
            item.score_value !== undefined
          if (!hasResult) {
            incompleteItems.push(`第${index + 1}项: ${item.title || '未命名'}`)
          }
        }

        // 检查必传附件是否已上传
        if (item.attachment_required) {
          const hasPhotos = item.photos && item.photos.length > 0
          if (!hasPhotos) {
            missingAttachments.push(`第${index + 1}项: ${item.title || '未命名'}`)
          }
        }
      })

      // 如果有未完成的必填项或缺少附件，显示错误
      if (incompleteItems.length > 0 || missingAttachments.length > 0) {
        Modal.error({
          title: '提交失败',
          width: 520,
          content: (
            <div>
              {incompleteItems.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 500, marginBottom: 4, color: '#ff4d4f' }}>
                    以下必填项未完成：
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 20, color: '#666', maxHeight: 150, overflow: 'auto' }}>
                    {incompleteItems.slice(0, 10).map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                    {incompleteItems.length > 10 && (
                      <li>... 还有 {incompleteItems.length - 10} 项未完成</li>
                    )}
                  </ul>
                </div>
              )}
              {missingAttachments.length > 0 && (
                <div>
                  <div style={{ fontWeight: 500, marginBottom: 4, color: '#faad14' }}>
                    以下检查项需要上传照片：
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 20, color: '#666', maxHeight: 150, overflow: 'auto' }}>
                    {missingAttachments.slice(0, 10).map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                    {missingAttachments.length > 10 && (
                      <li>... 还有 {missingAttachments.length - 10} 项需要上传</li>
                    )}
                  </ul>
                </div>
              )}
            </div>
          ),
        })
        return
      }

      // 校验通过，显示确认对话框
      Modal.confirm({
        title: '确认提交',
        content: '确定要提交这条检查记录吗？提交后将不能修改。',
        onOk: async () => {
          try {
            await recordApi.submitRecord(id)
            message.success('记录已提交')
            fetchRecords()
          } catch (error) {
            message.error('提交失败')
          }
        },
      })
    } catch (error) {
      console.error('Failed to validate record:', error)
      message.error('获取记录详情失败')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await recordApi.deleteRecord(id)
      message.success('删除成功')
      fetchRecords()
    } catch (error) {
      message.error('删除失败')
    }
  }

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要删除的记录')
      return
    }
    Modal.confirm({
      title: '批量删除确认',
      content: `确定要删除选中的 ${selectedRowKeys.length} 条记录吗？此操作不可恢复。`,
      okText: '确定删除',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await Promise.all(selectedRowKeys.map(id => recordApi.deleteRecord(id as string)))
          message.success(`成功删除 ${selectedRowKeys.length} 条记录`)
          setSelectedRowKeys([])
          fetchRecords()
        } catch (error) {
          message.error('批量删除失败')
        }
      },
    })
  }

  const handleGenerateReport = async (record: any) => {
    try {
      const res: any = await recordApi.getRecord(record.id)
      setReportRecord(res.data)
      setReportVisible(true)
    } catch (error) {
      message.error('获取记录详情失败')
    }
  }

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      draft: { color: 'default', text: '草稿' },
      submitted: { color: 'success', text: '已提交' },
    }
    const item = statusMap[status] || { color: 'default', text: status }
    return <Tag color={item.color}>{item.text}</Tag>
  }


  const columns = [
    {
      title: '被检查对象',
      key: 'enterprise',
      dataIndex: 'enterprise_name',
      width: 220,
      render: (name: string, record: any) => (
        <div style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {name || record.enterprise?.name || '手动输入'}
        </div>
      ),
    },
    {
      title: '检查模板',
      dataIndex: 'template',
      key: 'template',
      width: 180,
      render: (template: any) => (
        <div style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {template?.name || '-'}
        </div>
      ),
    },
    {
      title: '检查员',
      dataIndex: 'inspector',
      key: 'inspector',
      width: 100,
      render: (inspector: any) => inspector?.real_name || inspector?.username || '-',
    },
    {
      title: '检查时间',
      dataIndex: 'inspection_date',
      key: 'inspection_date',
      width: 150,
      sorter: true,
      sortOrder: sorter.field === 'inspection_date' ? (sorter.order || null) : null,
      render: (date: string) => date ? dayjs(date).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '总分',
      dataIndex: 'total_score',
      key: 'total_score',
      width: 70,
      sorter: true,
      sortOrder: sorter.field === 'total_score' ? (sorter.order || null) : null,
      render: (score: string, record: any) => record.template?.is_quantified ? <span style={{ color: '#F59E0B', fontWeight: 'bold' }}>{score ?? '-'}</span> : '-',
    },
    {
      title: '总体结果',
      dataIndex: 'overall_result',
      key: 'overall_result',
      width: 90,
      render: (result: string) => {
        if (!result) return '-'
        const resultMap: Record<string, { color: string; text: string }> = {
          pass: { color: 'success', text: '合格' },
          partial_pass: { color: 'warning', text: '基本合格' },
          fail: { color: 'error', text: '不合格' },
        }
        const item = resultMap[result] || { color: 'default', text: result }
        return <Tag color={item.color}>{item.text}</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 280,
      fixed: 'right' as const,
      render: (_: any, record: any) => (
        <Space>
          {record.status === 'draft' && (
            <Button
              type="link"
              size="small"
              icon={<FileTextOutlined />}
              onClick={() => navigate(`/record/${record.id}`)}
            >
              继续检查
            </Button>
          )}
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record)}
          >
            详情
          </Button>
          <Button
            type="link"
            size="small"
            icon={<FilePdfOutlined />}
            onClick={() => handleGenerateReport(record)}
            style={{ color: '#1e40af' }}
          >
            生成报告
          </Button>
          {record.status === 'draft' && (
            <Button
              type="link"
              size="small"
              icon={<CheckCircleOutlined />}
              onClick={() => handleSubmit(record.id)}
            >
              提交
            </Button>
          )}
          <Popconfirm
            title="确定删除此记录？"
            description="此操作不可恢复"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const handleTableChange = (pag: any, filters: any, sort: any) => {
    setPagination({ current: pag.current, pageSize: pag.pageSize })
    if (sort.field) {
      setSorter({ field: sort.field, order: sort.order })
    } else {
      setSorter({ field: null, order: null })
    }
  }

  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys)
    },
    getCheckboxProps: (record: any) => ({
      disabled: record.status !== 'draft',
    }),
  }

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 className="page-title">检查记录</h1>
        <Space>
          {selectedRowKeys.length > 0 && (
            <Popconfirm
              title={`确定删除选中的 ${selectedRowKeys.length} 条记录？`}
              description="此操作不可恢复"
              onConfirm={handleBatchDelete}
              okText="确定删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Button danger icon={<DeleteOutlined />}>
                批量删除 ({selectedRowKeys.length})
              </Button>
            </Popconfirm>
          )}
          <Button
            type="primary"
            icon={<FileTextOutlined />}
            onClick={() => navigate('/inspection/new')}
          >
            新建检查
          </Button>
        </Space>
      </div>

      {selectedRowKeys.length > 0 && (
        <Alert
          message={`已选择 ${selectedRowKeys.length} 条记录（仅草稿状态可删除）`}
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={() => setSelectedRowKeys([])}>
              取消选择
            </Button>
          }
        />
      )}

      {/* 高级筛选面板 */}
      <Card style={{ marginBottom: 16 }}>
        <Collapse
          activeKey={activeFilterKeys}
          onChange={(keys) => setActiveFilterKeys(keys as string[])}
          ghost
          expandIconPosition="end"
        >
          <Panel
            header={
              <Space>
                <FilterOutlined />
                <span>高级筛选</span>
                {activeFilterCount > 0 && (
                  <Badge count={activeFilterCount} style={{ backgroundColor: '#1890ff' }} />
                )}
              </Space>
            }
            key="filter"
          >
            <Form layout="vertical">
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="企业名称">
                    <Input
                      placeholder="搜索企业名称"
                      value={filters.enterprise_name}
                      onChange={(e) => handleFilterChange('enterprise_name', e.target.value)}
                      allowClear
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="检查状态">
                    <Select
                      placeholder="选择状态"
                      value={filters.status}
                      onChange={(value) => handleFilterChange('status', value)}
                      allowClear
                      options={[
                        { value: 'draft', label: '草稿' },
                        { value: 'submitted', label: '已提交' },
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="总体结果">
                    <Select
                      placeholder="选择结果"
                      value={filters.overall_result}
                      onChange={(value) => handleFilterChange('overall_result', value)}
                      allowClear
                      options={[
                        { value: 'pass', label: '合格' },
                        { value: 'partial_pass', label: '基本合格' },
                        { value: 'fail', label: '不合格' },
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="检查模板">
                    <Select
                      placeholder="选择模板"
                      value={filters.template_id}
                      onChange={(value) => handleFilterChange('template_id', value)}
                      allowClear
                      showSearch
                      optionFilterProp="label"
                      options={templates.map((t: any) => ({
                        value: t.id,
                        label: t.name,
                      }))}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="检查时间范围">
                    <RangePicker
                      style={{ width: '100%' }}
                      value={filters.dateRange}
                      onChange={(dates) => handleFilterChange('dateRange', dates)}
                      placeholder={['开始日期', '结束日期']}
                    />
                  </Form.Item>
                </Col>
                <Col span={16} style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-end', gap: 8 }}>
                  <Button icon={<ReloadOutlined />} onClick={handleResetFilters}>
                    重置
                  </Button>
                  <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
                    搜索
                  </Button>
                </Col>
              </Row>
            </Form>
          </Panel>
        </Collapse>
      </Card>

      <Card>
        <Table
          dataSource={records}
          columns={columns}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1200 }}
          rowSelection={rowSelection}
          onChange={handleTableChange}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (t) => `共 ${t} 条`,
            pageSizeOptions: ['10', '20', '50', '100'],
          }}
        />
      </Card>

      {/* 详情抽屉 */}
      <Drawer
        title="检查记录详情"
        placement="right"
        width={800}
        open={detailDrawer}
        onClose={() => setDetailDrawer(false)}
      >
        {selectedRecord && (
          <div>
            {/* 顶部简要信息 + 最终判定 - 横向布局 */}
            <div style={{
              background: '#fafafa',
              padding: '12px 16px',
              borderRadius: 8,
              marginBottom: 16,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              gap: 16
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, fontSize: 16 }}>{selectedRecord.template?.name}</span>
                  {getStatusTag(selectedRecord.status)}
                </div>
                <div style={{ color: '#888', fontSize: 13 }}>
                  {selectedRecord.enterprise_name || selectedRecord.enterprise?.name || '未指定企业'}
                  <span style={{ margin: '0 6px', color: '#ddd' }}>·</span>
                  {selectedRecord.inspector?.real_name || selectedRecord.inspector?.username}
                  <span style={{ margin: '0 6px', color: '#ddd' }}>·</span>
                  {selectedRecord.inspection_date ? dayjs(selectedRecord.inspection_date).format('YYYY-MM-DD HH:mm') : '-'}
                </div>
              </div>
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                {selectedRecord.template?.is_quantified && (
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>总分</div>
                    <span style={{ fontSize: 24, fontWeight: 'bold', color: '#F59E0B' }}>{selectedRecord.total_score || 0}</span>
                  </div>
                )}
                <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>最终判定</div>
                {selectedRecord.overall_result ? (
                  <Tag
                    color={
                      selectedRecord.overall_result === 'pass' ? 'success' :
                        selectedRecord.overall_result === 'partial_pass' ? 'warning' : 'error'
                    }
                    style={{ fontSize: 14, padding: '4px 16px', marginRight: 0 }}
                  >
                    {selectedRecord.overall_result === 'pass' ? '合格' :
                      selectedRecord.overall_result === 'partial_pass' ? '基本合格' : '不合格'}
                  </Tag>
                ) : (
                  <Tag color="default" style={{ marginRight: 0 }}>待判定</Tag>
                )}
              </div>
            </div>

            {/* 检查结果统计 */}
            {selectedRecord.stats && (
              <div style={{
                background: '#fff',
                border: '1px solid #e8e8e8',
                borderRadius: 8,
                padding: '16px',
                marginBottom: 16,
              }}>
                <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 14, color: '#333' }}>检查结果汇总</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                  <div style={{ textAlign: 'center', padding: 12, background: '#f6ffed', borderRadius: 8 }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color: '#52c41a' }}>{selectedRecord.stats.pass}</div>
                    <div style={{ fontSize: 12, color: '#666' }}>符合项</div>
                  </div>
                  <div style={{ textAlign: 'center', padding: 12, background: '#fff2f0', borderRadius: 8 }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color: '#ff4d4f' }}>{selectedRecord.stats.fail}</div>
                    <div style={{ fontSize: 12, color: '#666' }}>不符合项</div>
                  </div>
                  <div style={{ textAlign: 'center', padding: 12, background: '#f5f5f5', borderRadius: 8 }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color: '#8c8c8c' }}>{selectedRecord.stats.na}</div>
                    <div style={{ fontSize: 12, color: '#666' }}>不适用项</div>
                  </div>
                  <div style={{ textAlign: 'center', padding: 12, background: '#e6f7ff', borderRadius: 8 }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color: '#1890ff' }}>{selectedRecord.stats.total}</div>
                    <div style={{ fontSize: 12, color: '#666' }}>总检查项</div>
                  </div>
                </div>
              </div>
            )}

            {/* 判定说明 - 如果有 */}
            {selectedRecord.remarks && (
              <div style={{
                background: '#fffbe6',
                border: '1px solid #ffe58f',
                padding: '8px 12px',
                borderRadius: 6,
                marginBottom: 16,
                fontSize: 13,
              }}>
                <span style={{ color: '#d48806', fontWeight: 500, marginRight: 8 }}>判定说明：</span>
                <span style={{ color: '#666' }}>{selectedRecord.remarks}</span>
              </div>
            )}

            {/* 检查项目 */}
            <div>
              <h3 style={{ marginBottom: 12, fontSize: 15 }}>检查项目</h3>
              <div>
                {selectedRecord.template?.items?.map((item: any, index: number) => (
                  <TreeItem
                    key={item.id}
                    item={item}
                    index={index}
                    isQuantified={selectedRecord.template?.is_quantified}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </Drawer>
      <InspectionReport
        open={reportVisible}
        record={reportRecord}
        onClose={() => setReportVisible(false)}
      />
    </div>
  )
}

// TreeItem 组件 - 递归显示树形结构
function TreeItem({ item, index, isQuantified }: { item: any; index: number; isQuantified?: boolean }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const hasChildren = item.children && item.children.length > 0
  const isCategory = item.is_category

  // 获取检查结论
  const getResultDisplay = () => {
    if (isCategory) return null

    // 单选/通过不通过
    if (item.radio_value) {
      const color = item.radio_value === 'pass' ? 'success' : item.radio_value === 'fail' ? 'error' : 'default'
      const text = item.radio_value === 'pass' ? '合格' : item.radio_value === 'fail' ? '不合格' : '不适用'
      return <Tag color={color}>{text}</Tag>
    }

    // 打分
    if (item.score_value !== null && item.score_value !== undefined) {
      const passed = item.pass_score && Number(item.score_value) >= Number(item.pass_score)
      return <Tag color={passed ? 'success' : 'warning'}>{item.score_value}分</Tag>
    }

    // 数值
    if (item.numeric_value !== null && item.numeric_value !== undefined) {
      const range = (item.min_value !== null || item.max_value !== null)
        ? ` (${item.min_value || '-'}~${item.max_value || '-'})`
        : ''
      return <Tag color="blue">{item.numeric_value}{item.unit || ''}{range}</Tag>
    }

    // 文本
    if (item.text_value) {
      const text = item.text_value.length > 10 ? item.text_value.substring(0, 10) + '...' : item.text_value
      return <Tag color="purple">{text}</Tag>
    }

    // 多选
    if (item.multi_value && item.multi_value.length > 0) {
      return <Tag color="cyan">已选{item.multi_value.length}项</Tag>
    }

    return <Tag>未填写</Tag>
  }

  const getItemScore = () => {
    if (!isQuantified) return null
    if (item.score_value !== null && item.score_value !== undefined && item.score_value !== '') {
      return Number(item.score_value)
    }
    const radio = item.radio_value
    if (radio === 'pass') {
      return Number(item.score_weight || item.default_score || 0)
    } else if (radio === 'fail') {
      return 0
    } else if (radio === 'na') {
      return Number(item.default_score || 0)
    }
    return null
  }
  const computedScore = getItemScore()

  return (
    <div style={{ marginBottom: 12 }}>
      <div
        className="record-tree-item"
        onClick={() => { if (!isCategory) setIsExpanded(!isExpanded) }}
        style={{
          padding: '12px 16px',
          background: isCategory ? '#f8fafc' : 'white',
          borderRadius: isExpanded && !isCategory ? '8px 8px 0 0' : 8,
          border: isCategory ? '1px solid #e2e8f0' : '1px solid #cbd5e1',
          borderBottom: isExpanded && !isCategory ? 'none' : undefined,
          boxShadow: isCategory ? 'none' : '0 1px 3px rgba(0, 0, 0, 0.02)',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          transition: 'all 0.2s',
          cursor: isCategory ? 'default' : 'pointer',
        }}
        onMouseEnter={(e) => {
          if (!isCategory) {
            e.currentTarget.style.borderColor = '#cbd5e1'
            e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.05)'
          }
        }}
        onMouseLeave={(e) => {
          if (!isCategory) {
            e.currentTarget.style.borderColor = '#f1f5f9'
            e.currentTarget.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.02)'
          }
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 24,
            height: 24,
            background: isCategory ? '#e2e8f0' : 'var(--primary-color)',
            color: isCategory ? '#64748b' : 'white',
            borderRadius: '6px',
            fontSize: 12,
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {index + 1}
        </span>
        <span
          style={{
            flex: 1,
            fontSize: isCategory ? 15 : 14,
            fontWeight: isCategory ? 600 : 500,
            color: isCategory ? '#334155' : '#1e293b',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {item.title}
          {computedScore !== null && !isCategory && (
            <span style={{ color: '#d46b08', marginLeft: 8, fontSize: 13, fontWeight: 'normal' }}>
              ({computedScore}分)
            </span>
          )}
        </span>
        {getResultDisplay()}
        {!isCategory && (
          <div style={{ color: '#94a3b8', fontSize: 12, marginLeft: 8 }}>
            {isExpanded ? '▲' : '▼'}
          </div>
        )}
      </div>

      {/* 展开的详情内容 */}
      {!isCategory && isExpanded && (
        <div style={{
          padding: '16px',
          background: '#f8fafc',
          border: '1px solid #cbd5e1',
          borderTop: 'none',
          borderRadius: '0 0 8px 8px',
          fontSize: '13px',
          color: '#475569',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}>
          {/* 检查项基本信息 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase' }}>检查项说明</div>
            {item.description && <div style={{ display: 'flex', gap: 8 }}><b style={{ color: '#1e293b', flexShrink: 0 }}>检查要求：</b><span>{item.description}</span></div>}
            {item.check_method && <div style={{ display: 'flex', gap: 8 }}><b style={{ color: '#1e293b', flexShrink: 0 }}>检查方法：</b><span>{item.check_method}</span></div>}
            {item.legal_basis && <div style={{ display: 'flex', gap: 8 }}><b style={{ color: '#1e293b', flexShrink: 0 }}>依据条款：</b><span>{item.legal_basis}</span></div>}
            {item.ai_prompt_template && <div style={{ display: 'flex', gap: 8 }}><b style={{ color: '#1e293b', flexShrink: 0 }}>知识库：</b><span>{item.ai_prompt_template}</span></div>}
          </div>

          <div style={{ height: 1, background: '#e2e8f0', margin: '4px 0' }}></div>

          {/* 检查结论信息 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase' }}>检查结论与说明</div>

            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <b style={{ color: '#1e293b', flexShrink: 0 }}>检查结论：</b>
              <span>{getResultDisplay()}</span>
            </div>

            {item.problem_description && (
              <div style={{ display: 'flex', gap: 8 }}>
                <b style={{ color: '#ef4444', flexShrink: 0 }}>问题描述：</b>
                <span style={{ color: '#b91c1c' }}>{item.problem_description}</span>
              </div>
            )}

            {item.rectification_suggestion && (
              <div style={{ display: 'flex', gap: 8 }}>
                <b style={{ color: '#f59e0b', flexShrink: 0 }}>整改建议：</b>
                <span style={{ color: '#d97706' }}>{item.rectification_suggestion}</span>
              </div>
            )}

            {item.inspector_note && (
              <div style={{ display: 'flex', gap: 8 }}>
                <b style={{ color: '#1e293b', flexShrink: 0 }}>备注说明：</b>
                <span>{item.inspector_note}</span>
              </div>
            )}

            {item.ai_suggestion && item.ai_suggestion !== '0' && (
              <div style={{
                marginTop: 8,
                background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.05) 0%, rgba(129, 140, 248, 0.05) 100%)',
                border: '1px solid rgba(79, 70, 229, 0.2)',
                borderRadius: 8,
                padding: 12,
              }}>
                <div style={{ color: '#4f46e5', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  💡 AI 智能裁定与建议
                </div>
                <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6, color: '#334155' }}>
                  {item.ai_suggestion}
                </div>
              </div>
            )}

            {/* 照片列表 (附件) */}
            {item.photos && item.photos.length > 0 && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                {item.photos.map((url: string, idx: number) => {
                  const normalizedUrl = (!url || url.startsWith('/') || url.startsWith('http')) ? url : '/' + url
                  return (
                    <img
                      key={idx}
                      src={normalizedUrl}
                      alt={`附件图片 ${idx + 1}`}
                      style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 6, border: '1px solid #e2e8f0', cursor: 'pointer' }}
                      onClick={(e) => { e.stopPropagation(); window.open(normalizedUrl, '_blank') }}
                    />
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 递归渲染子节点 */}
      {hasChildren && (
        <div
          style={{
            marginLeft: 20,
            marginTop: 4,
          }}
        >
          {item.children.map((child: any, childIndex: number) => (
            <TreeItem key={child.id} item={child} index={childIndex} isQuantified={isQuantified} />
          ))}
        </div>
      )}
    </div>
  )
}
