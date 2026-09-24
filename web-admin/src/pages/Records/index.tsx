import { useState, useEffect } from 'react'
import { Card, Table, Button, Tag, Space, message, Modal, Drawer, Popconfirm, Alert, Collapse, Form, Input, Select, DatePicker, Row, Col, Badge, Tooltip, InputNumber } from 'antd'
import { EyeOutlined, DeleteOutlined, CheckCircleOutlined, FileTextOutlined, FilePdfOutlined, SearchOutlined, ReloadOutlined, FilterOutlined, FolderFilled, UpOutlined, DownOutlined } from '@ant-design/icons'
import { recordApi, templateApi } from '@/services/api'
import dayjs from 'dayjs'
import { useNavigate } from 'react-router-dom'
import InspectionReport from './InspectionReport'
import { hasQuantifiedItems, resultLabel, resultTagColor } from '@/utils/display'
import { isItemAssessed } from '@/utils/completion'
import { useAuthStore } from '@/stores/auth'

const { RangePicker } = DatePicker

export default function Records() {
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin'
  const [correctionForm] = Form.useForm()
  const [records, setRecords] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [selectedRecord, setSelectedRecord] = useState<any>(null)
  const [detailDrawer, setDetailDrawer] = useState(false)
  const [reportRecord, setReportRecord] = useState<any>(null)
  const [reportVisible, setReportVisible] = useState(false)
  const [correctionItem, setCorrectionItem] = useState<any>(null)
  const [correctionVisible, setCorrectionVisible] = useState(false)
  const [correctionSaving, setCorrectionSaving] = useState(false)
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
  const [searchTrigger, setSearchTrigger] = useState(0) // 搜索触发器

  // 仅在组件挂载时拉取一次模板列表（静态下拉选项数据）
  useEffect(() => {
    fetchTemplates()
  }, [])

  // 分页/排序/搜索触发时重新拉取记录
  useEffect(() => {
    fetchRecords()
  }, [pagination.current, pagination.pageSize, sorter.field, sorter.order, searchTrigger])

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
    setSearchTrigger(prev => prev + 1) // 触发搜索
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

  const openCorrection = (item: any) => {
    setCorrectionItem(item)
    correctionForm.setFieldsValue({
      radio_value: item.radio_value ?? item.result ?? undefined,
      score_value: item.score_value ?? undefined,
      numeric_value: item.numeric_value ?? undefined,
      text_value: item.text_value ?? undefined,
      problem_description: item.problem_description ?? undefined,
      inspector_note: item.inspector_note ?? undefined,
      reason: '',
    })
    setCorrectionVisible(true)
  }

  const handleCorrection = async () => {
    if (!selectedRecord || !correctionItem) return
    try {
      const values = await correctionForm.validateFields()
      setCorrectionSaving(true)
      await recordApi.correctSubmittedRecordItem(selectedRecord.id, correctionItem.id, values)
      message.success('已更正并记录审计信息')
      setCorrectionVisible(false)
      setCorrectionItem(null)
      const refreshed: any = await recordApi.getRecord(selectedRecord.id)
      setSelectedRecord(refreshed.data)
      fetchRecords()
    } catch (error: any) {
      if (error?.errorFields) return
      message.error(error?.response?.data?.detail || '更正失败，请检查权限和输入内容')
    } finally {
      setCorrectionSaving(false)
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
          const hasChildren = !!(item.children && item.children.length > 0)
          // 只要有子节点就一律按分类目录处理，与后端树接口及其它页面口径保持一致
          const isCategory = !!item.is_category || hasChildren
          if (!isCategory) {
            result.push(item)
          }
          if (hasChildren) {
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
        // 注意：接口未填写时返回的是 null，只判 undefined 会让校验恒为通过
        if (item.is_required !== false) {
          const hasResult =
            item.radio_value ||
            (item.numeric_value !== undefined &&
              item.numeric_value !== null &&
              item.numeric_value !== '') ||
            item.text_value ||
            (item.score_value !== undefined &&
              item.score_value !== null &&
              item.score_value !== '')
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

      // 最终判定结论是必填项：没有结论的记录不允许提交，
      // 否则会落库一条「已提交但没有总体结论」的脏记录。
      if (!recordData?.overall_result) {
        Modal.warning({
          title: '提交失败',
          content: (
            <div>
              <div style={{ marginBottom: 8 }}>该记录还没有填写「最终判定结论」，无法提交。</div>
              <div style={{ color: '#666' }}>
                请进入记录执行页，在页面底部选择「合格 / 基本合格 / 不合格」后再提交。
              </div>
            </div>
          ),
          okText: '去填写',
          onOk: () => navigate(`/record/${id}`),
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
          } catch (error: any) {
            // 透传后端校验原因，避免只显示「提交失败」
            const detail = error?.response?.data?.detail || error?.response?.data?.message
            message.error(typeof detail === 'string' && detail ? detail : '提交失败')
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
      submitted: { color: 'success', text: '已检查' },
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
          {/* 生成报告：草稿态禁用。
              未完成检查的记录没有检查结论，生成的报告必然是空壳，
              既误导用户也可能被当成正式交付物（外部复测已提，老杨批注「没完成检查不能生成报告」）。 */}
          <Tooltip
            title={record.status === 'draft' ? '该记录尚未完成检查，请先「继续检查」并提交后再生成报告' : ''}
          >
            <Button
              type="link"
              size="small"
              icon={<FilePdfOutlined />}
              disabled={record.status === 'draft'}
              onClick={() => handleGenerateReport(record)}
              style={{ color: record.status === 'draft' ? undefined : '#1e40af' }}
            >
              生成报告
            </Button>
          </Tooltip>
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
          items={[
            {
              key: 'filter',
              label: (
                <Space>
                  <FilterOutlined />
                  <span>高级筛选</span>
                  {activeFilterCount > 0 && (
                    <Badge count={activeFilterCount} style={{ backgroundColor: '#1890ff' }} />
                  )}
                </Space>
              ),
              children: (
                <>
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
                        { value: 'submitted', label: '已检查' },
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
                </>
              ),
            },
          ]}
        />
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
                {selectedRecord.template?.is_quantified && hasQuantifiedItems(selectedRecord.template) && (
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
                <div style={{ display: 'grid', gridTemplateColumns: `repeat(${(selectedRecord.stats.observe || 0) > 0 ? 6 : 5}, 1fr)`, gap: 12 }}>
                  <div style={{ textAlign: 'center', padding: 12, background: '#f6ffed', borderRadius: 8 }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color: '#52c41a' }}>{selectedRecord.stats.pass}</div>
                    <div style={{ fontSize: 12, color: '#666' }}>合格项</div>
                  </div>
                  <div style={{ textAlign: 'center', padding: 12, background: '#fff2f0', borderRadius: 8 }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color: '#ff4d4f' }}>{selectedRecord.stats.fail}</div>
                    <div style={{ fontSize: 12, color: '#666' }}>不合格项</div>
                  </div>
                  <div style={{ textAlign: 'center', padding: 12, background: '#f5f5f5', borderRadius: 8 }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color: '#8c8c8c' }}>{selectedRecord.stats.na}</div>
                    <div style={{ fontSize: 12, color: '#666' }}>不适用项</div>
                  </div>
                  {/* 观察项（已填写但不属三级判定的中间态）：与报告、H5 判定卡口径一致，
                      不加这一格则「合格+不合格+不适用」小于「总检查项」，用户会质疑汇总。
                      术语统一为「合格项/不合格项」——与现场执行页、H5 现场端一致；
                      「不符合项」在系统里是另一实体（项目下正式开具的不符合项单据），
                      两者混用会让客户以为检查项被开成了不符合项。 */}
                  {(selectedRecord.stats.observe || 0) > 0 && (
                    <div style={{ textAlign: 'center', padding: 12, background: '#ecfeff', borderRadius: 8 }}>
                      <div style={{ fontSize: 28, fontWeight: 700, color: '#0891b2' }}>{selectedRecord.stats.observe}</div>
                      <div style={{ fontSize: 12, color: '#666' }}>观察项</div>
                    </div>
                  )}
                  <div style={{ textAlign: 'center', padding: 12, background: '#e6f7ff', borderRadius: 8 }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color: '#1890ff' }}>{selectedRecord.stats.total}</div>
                    <div style={{ fontSize: 12, color: '#666' }}>总检查项</div>
                  </div>
                  <div style={{ textAlign: 'center', padding: 12, background: '#f9f0ff', borderRadius: 8 }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color: '#722ed1' }}>
                      {selectedRecord.stats.total - selectedRecord.stats.na > 0
                        ? `${Math.round((selectedRecord.stats.pass / (selectedRecord.stats.total - selectedRecord.stats.na)) * 1000) / 10}%`
                        : '0%'}
                    </div>
                    <div style={{ fontSize: 12, color: '#666' }}>合格率</div>
                  </div>
                </div>
              </div>
            )}

            {/* 判定说明 - 如果有 */}
            {selectedRecord.judgment_note && (
              <div style={{
                background: '#fffbe6',
                border: '1px solid #ffe58f',
                padding: '8px 12px',
                borderRadius: 6,
                marginBottom: 16,
                fontSize: 13,
              }}>
                <span style={{ color: '#d48806', fontWeight: 500, marginRight: 8 }}>判定说明：</span>
                <span style={{ color: '#666' }}>{selectedRecord.judgment_note}</span>
              </div>
            )}

            {/* 检查备注 - 如果有 */}
            {selectedRecord.remarks && (
              <div style={{
                background: '#f0f5ff',
                border: '1px solid #adc6ff',
                padding: '8px 12px',
                borderRadius: 6,
                marginBottom: 16,
                fontSize: 13,
              }}>
                <span style={{ color: '#1d39c4', fontWeight: 500, marginRight: 8 }}>检查备注：</span>
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
                    canCorrect={isAdmin && selectedRecord.status === 'submitted'}
                    onCorrect={openCorrection}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </Drawer>
      <Modal
        title={`更正已提交记录：${correctionItem?.title || ''}`}
        open={correctionVisible}
        onCancel={() => {
          setCorrectionVisible(false)
          setCorrectionItem(null)
          correctionForm.resetFields()
        }}
        onOk={handleCorrection}
        confirmLoading={correctionSaving}
        okText="提交更正"
        cancelText="取消"
        destroyOnClose
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="此操作会修改已提交记录，并将更正原因及字段变更写入审计日志。"
        />
        <Form form={correctionForm} layout="vertical">
          {(correctionItem?.result_type === 'radio' || correctionItem?.result_type === 'audit_3level' || correctionItem?.radio_value || correctionItem?.result) && (
            <Form.Item name="radio_value" label="检查结论">
              <Select allowClear options={(correctionItem?.result_options?.options || correctionItem?.result_options || [
                { value: 'pass', label: '合格' }, { value: 'fail', label: '不合格' }, { value: 'na', label: '不适用' },
              ]).map((option: any) => typeof option === 'string' ? ({ value: option, label: option }) : option)} />
            </Form.Item>
          )}
          {(correctionItem?.result_type === 'score' || correctionItem?.score_value !== null && correctionItem?.score_value !== undefined) && (
            <Form.Item name="score_value" label="评分"><InputNumber style={{ width: '100%' }} /></Form.Item>
          )}
          {(correctionItem?.result_type === 'number' || correctionItem?.result_type === 'numeric' || correctionItem?.numeric_value !== null && correctionItem?.numeric_value !== undefined) && (
            <Form.Item name="numeric_value" label={`数值${correctionItem?.unit ? `（${correctionItem.unit}）` : ''}`}>
              <InputNumber style={{ width: '100%' }} min={correctionItem?.min_value} max={correctionItem?.max_value} />
            </Form.Item>
          )}
          {(correctionItem?.result_type === 'text' || correctionItem?.text_value) && (
            <Form.Item name="text_value" label="文本结果"><Input.TextArea rows={3} /></Form.Item>
          )}
          <Form.Item name="problem_description" label="问题描述"><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="inspector_note" label="审核记录"><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="reason" label="更正原因" rules={[{ required: true, min: 2, max: 500, message: '请填写 2–500 字的更正原因' }]}>
            <Input.TextArea rows={3} maxLength={500} showCount />
          </Form.Item>
        </Form>
      </Modal>
      <InspectionReport
        open={reportVisible}
        record={reportRecord}
        onClose={() => setReportVisible(false)}
      />
    </div>
  )
}

// TreeItem 组件 - 递归显示树形层级结构，支持大类醒目识别与展开折叠
function TreeItem({
  item,
  index,
  isQuantified,
  canCorrect = false,
  onCorrect,
  parentIndex = '',
}: {
  item: any
  index: number
  isQuantified?: boolean
  canCorrect?: boolean
  onCorrect?: (item: any) => void
  parentIndex?: string
}) {
  const hasChildren = item.children && item.children.length > 0
  const isCategory = !!item.is_category || hasChildren

  // 分类目录默认展开子项，叶子项默认收起详情
  const [isCategoryExpanded, setIsCategoryExpanded] = useState(true)
  const [isDetailExpanded, setIsDetailExpanded] = useState(false)

  const currentIndex = parentIndex ? `${parentIndex}.${index + 1}` : `${index + 1}`

  // 递归统计该分类下的叶子数与已评定数
  const categoryStats = (() => {
    if (!isCategory) return null
    let total = 0
    let completed = 0
    const count = (node: any) => {
      const nodeHasChild = node.children && node.children.length > 0
      if (node.is_category || nodeHasChild) {
        ;(node.children || []).forEach(count)
      } else {
        total++
        // 统一判据：合格/不合格/不适用均算已评定；描述型/数值型/打分型有内容也算
        if (isItemAssessed(node)) {
          completed++
        }
      }
    }
    ;(item.children || []).forEach(count)
    return { total, completed }
  })()

  // 获取检查结论（严格杜绝分类节点显示未填写）
  const getResultDisplay = () => {
    if (isCategory) return null

    // 单选/通过不通过
    if (item.radio_value || item.result) {
      // 统一走公共映射，避免 observe / not_applicable 这类值直接显示英文
      const val = item.radio_value || item.result
      return <Tag color={resultTagColor(val)}>{resultLabel(val)}</Tag>
    }

    // 打分
    if (item.score_value !== null && item.score_value !== undefined && item.score_value !== '') {
      const passed = item.pass_score && Number(item.score_value) >= Number(item.pass_score)
      return <Tag color={passed ? 'success' : 'warning'}>{item.score_value}分</Tag>
    }

    // 数值
    if (item.numeric_value !== null && item.numeric_value !== undefined && item.numeric_value !== '') {
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
    const radio = item.radio_value || item.result
    if (radio === 'pass' || radio === 'compliant') {
      return Number(item.score_weight || item.default_score || 0)
    } else if (radio === 'fail' || radio === 'non_compliant') {
      return 0
    } else if (radio === 'na' || radio === 'not_applicable') {
      return Number(item.default_score || 0)
    }
    return null
  }
  const computedScore = getItemScore()

  // 分类节点样式与交互
  if (isCategory) {
    return (
      <div style={{ marginBottom: 12 }}>
        <div
          onClick={() => setIsCategoryExpanded(!isCategoryExpanded)}
          style={{
            padding: '12px 16px',
            background: '#f0f7ff',
            borderRadius: 8,
            border: '1px solid #bae0ff',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}
        >
          <FolderFilled style={{ color: '#1677ff', fontSize: 18 }} />
          <span style={{
            fontSize: 15,
            fontWeight: 700,
            color: '#0958d9',
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexWrap: 'wrap'
          }}>
            <span>{currentIndex} {item.title}</span>
            <Tag color="blue" style={{ borderRadius: 4, fontWeight: 500, margin: 0 }}>
              大类分类
            </Tag>
            {item.description && (
              <span style={{ fontSize: 13, color: '#64748b', fontWeight: 'normal' }}>
                ({item.description})
              </span>
            )}
          </span>
          {categoryStats && (
            <Tag
              style={{
                borderRadius: 12,
                background: '#e2e8f0',
                borderColor: 'transparent',
                color: '#334155',
                fontWeight: 600,
                padding: '2px 10px',
              }}
            >
              共 {categoryStats.total} 项 {categoryStats.completed > 0 ? `(${categoryStats.completed}已评)` : ''}
            </Tag>
          )}
          <span style={{ color: '#1677ff', fontSize: 12, marginLeft: 4 }}>
            {isCategoryExpanded ? <UpOutlined /> : <DownOutlined />}
          </span>
        </div>

        {/* 递归展示子项 */}
        {hasChildren && isCategoryExpanded && (
          <div style={{
            paddingLeft: 18,
            borderLeft: '2px solid #bae0ff',
            marginLeft: 14,
            marginTop: 8,
          }}>
            {item.children.map((child: any, cIdx: number) => (
              <TreeItem
                key={child.id || cIdx}
                item={child}
                index={cIdx}
                isQuantified={isQuantified}
                canCorrect={canCorrect}
                onCorrect={onCorrect}
                parentIndex={currentIndex}
              />
            ))}
          </div>
        )}
      </div>
    )
  }

  // 检查项节点样式与交互
  return (
    <div style={{ marginBottom: 8 }}>
      <div
        className="record-tree-item"
        onClick={() => setIsDetailExpanded(!isDetailExpanded)}
        style={{
          padding: '10px 14px',
          background: 'white',
          borderRadius: isDetailExpanded ? '8px 8px 0 0' : 8,
          border: '1px solid #e2e8f0',
          borderBottom: isDetailExpanded ? 'none' : undefined,
          boxShadow: '0 1px 2px rgba(0, 0, 0, 0.03)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          cursor: 'pointer',
          transition: 'all 0.2s',
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            minWidth: 32,
            height: 22,
            padding: '0 6px',
            background: '#f1f5f9',
            color: '#475569',
            borderRadius: '4px',
            fontSize: 12,
            fontWeight: 600,
            flexShrink: 0,
          }}
        >
          {currentIndex}
        </span>
        <span
          style={{
            flex: 1,
            fontSize: 14,
            fontWeight: 500,
            color: '#1e293b',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {item.title}
          {computedScore !== null && (
            <span style={{ color: '#d46b08', marginLeft: 8, fontSize: 13, fontWeight: 'normal' }}>
              ({computedScore}分)
            </span>
          )}
        </span>
        {/* 附件 / 审核记录 上提到折叠行内直接可见。
            此前两者都只在展开区深处渲染，用户不点开就以为「没传附件、没写审核记录」，
            外部复测正是这么提的（附件不能隐藏太深）。 */}
        {Array.isArray(item.photos) && item.photos.length > 0 && (
          <Tag
            color="blue"
            style={{ margin: 0, fontSize: 11, lineHeight: '18px', flexShrink: 0 }}
            title={`已上传 ${item.photos.length} 张附件`}
          >
            📎 附件 {item.photos.length}
          </Tag>
        )}
        {item.inspector_note && (
          <Tag
            color="cyan"
            style={{ margin: 0, fontSize: 11, lineHeight: '18px', flexShrink: 0 }}
            title={item.inspector_note}
          >
            审核记录
          </Tag>
        )}
        {getResultDisplay()}
        <div style={{ color: '#94a3b8', fontSize: 12, marginLeft: 8 }}>
          {isDetailExpanded ? '▲' : '▼'}
        </div>
      </div>

      {/* 展开的详情内容 */}
      {isDetailExpanded && (
        <div style={{
          padding: '14px 16px',
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderTop: 'none',
          borderRadius: '0 0 8px 8px',
          fontSize: '13px',
          color: '#475569',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
        }}>
          {/* 检查项基本信息 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase' }}>检查项说明</div>
            {item.description && <div style={{ display: 'flex', gap: 8 }}><b style={{ color: '#1e293b', flexShrink: 0 }}>检查要求：</b><span>{item.description}</span></div>}
            {item.check_method && <div style={{ display: 'flex', gap: 8 }}><b style={{ color: '#1e293b', flexShrink: 0 }}>检查方法：</b><span>{item.check_method}</span></div>}
            {item.legal_basis && <div style={{ display: 'flex', gap: 8 }}><b style={{ color: '#1e293b', flexShrink: 0 }}>依据条款：</b><span>{item.legal_basis}</span></div>}
            {item.ai_prompt_template && <div style={{ display: 'flex', gap: 8 }}><b style={{ color: '#1e293b', flexShrink: 0 }}>知识库：</b><span>{item.ai_prompt_template}</span></div>}
          </div>

          <div style={{ height: 1, background: '#e2e8f0', margin: '2px 0' }}></div>

          {/* 检查结论信息 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
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
                <b style={{ color: '#1e293b', flexShrink: 0 }}>审核记录：</b>
                <span>{item.inspector_note}</span>
              </div>
            )}

            {canCorrect && item.id && onCorrect && (
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
                <Button size="small" type="primary" onClick={(event) => {
                  event.stopPropagation()
                  onCorrect(item)
                }}>
                  更正此项
                </Button>
              </div>
            )}

            {item.ai_suggestion && item.ai_suggestion !== '0' && (
              <div style={{
                marginTop: 6,
                background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.05) 0%, rgba(129, 140, 248, 0.05) 100%)',
                border: '1px solid rgba(79, 70, 229, 0.2)',
                borderRadius: 8,
                padding: 10,
              }}>
                <div style={{ color: '#4f46e5', fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                  💡 AI 智能裁定与建议
                </div>
                <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6, color: '#334155' }}>
                  {item.ai_suggestion}
                </div>
              </div>
            )}

            {/* 照片列表 (附件) */}
            {item.photos && item.photos.length > 0 && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
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
    </div>
  )
}
