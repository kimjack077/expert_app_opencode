import { useState, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Button, Space, message, Progress, Table, Modal,
  Form, Input, Select, DatePicker, Upload, Drawer, Spin, Alert, Badge, Tabs, Image
} from 'antd'
import {
  ArrowLeftOutlined, SaveOutlined, SendOutlined, PlusOutlined, CameraOutlined,
  RobotOutlined, BulbOutlined, BookOutlined, DeleteOutlined, EyeOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { auditRecordApi, auditPlanApi, auditAIApi, auditProjectApi } from '@/services/auditProjectApi'
import { templateApi, mediaApi } from '@/services/api'
import EnterpriseRiskProfile from '@/components/EnterpriseRiskProfile'
import type { UploadProps } from 'antd'

const { TextArea } = Input

interface RecordItem {
  id: string
  template_item_id: string
  title: string
  description?: string
  check_method?: string
  legal_basis?: string
  is_category: boolean
  children?: RecordItem[]
  result_type?: string
  result_options?: Array<{ value: string; label: string }>
  // 必填相关
  is_required?: boolean
  allow_attachment?: boolean
  attachment_required?: boolean
  // 结果字段
  radio_value?: string
  score_value?: number
  numeric_value?: number
  text_value?: string
  multi_value?: string[]
  inspector_note?: string
  photos?: string[]
  evaluation_3level?: string
  audit_evidence?: string
  audit_findings?: string
  clause_no_snapshot?: string
}

export default function AuditRecordEdit() {
  const { projectId, recordId } = useParams<{ projectId: string; recordId: string }>()
  const [searchParams] = useSearchParams()
  const planItemId = searchParams.get('planItemId')
  const readOnly = searchParams.get('mode') === 'view'
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [project, setProject] = useState<any>(null)
  const [planItem, setPlanItem] = useState<any>(null)
  const [record, setRecord] = useState<any>(null)
  const [template, setTemplate] = useState<any>(null)
  const [items, setItems] = useState<RecordItem[]>([])
  const [flatItems, setFlatItems] = useState<RecordItem[]>([])
  const [selectedItem, setSelectedItem] = useState<RecordItem | null>(null)
  const [itemDrawerVisible, setItemDrawerVisible] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResult, setAiResult] = useState<any>(null)
  const [form] = Form.useForm()

  useEffect(() => {
    if (projectId) {
      fetchData()
    }
  }, [projectId, recordId, planItemId])

  const fetchData = async () => {
    setLoading(true)
    try {
      // 获取项目信息
      const projectRes = await auditProjectApi.get(projectId!)
      setProject(projectRes.data)

      // 如果有计划项ID，获取计划项详情
      if (planItemId) {
        const planRes = await auditPlanApi.get(planItemId)
        setPlanItem(planRes.data)
      }

      // 如果有记录ID，获取记录详情
      if (recordId && recordId !== 'new') {
        const recordRes = await auditRecordApi.get(recordId!)
        setRecord(recordRes.data)
        // 转换日期字符串为dayjs对象
        const formData = {
          ...recordRes.data,
          audit_date: recordRes.data.audit_date ? dayjs(recordRes.data.audit_date) : undefined,
        }
        form.setFieldsValue(formData)

        // 获取模板
        if (recordRes.data.template_id) {
          const templateRes = await templateApi.getTemplate(recordRes.data.template_id)
          setTemplate(templateRes.data)
          // 把已保存的记录项数据合并到模板项中
          const recordItems = recordRes.data.items || []
          const recordItemsByTemplateId: Record<string, any> = {}
          for (const ri of recordItems) {
            if (ri.template_item_id) {
              recordItemsByTemplateId[ri.template_item_id] = ri
            }
          }
          flattenTemplateItems(templateRes.data.items || [], [], recordItemsByTemplateId)
        }
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取数据失败')
    } finally {
      setLoading(false)
    }
  }

  const flattenTemplateItems = (items: any[], result: RecordItem[] = [], recordItemsMap: Record<string, any> = {}): RecordItem[] => {
    for (const item of items) {
      // 合并已保存的记录项数据
      const recordItem = item.id ? recordItemsMap[item.id] : null
      const mergedItem = recordItem
        ? {
            ...item,
            ...recordItem,
            title: item.title, // 保留模板项标题
            id: recordItem.id || item.id, // 使用记录项 ID
            template_item_id: item.id, // 保留模板项 ID 作为关联
          }
        : item
      result.push(mergedItem)
      if (item.children && item.children.length > 0) {
        flattenTemplateItems(item.children, result, recordItemsMap)
      }
    }
    setFlatItems(result.filter(i => !i.is_category))
    setItems(items)
    return result
  }

  const handleSaveRecord = async () => {
    if (readOnly) return

    try {
      const values = await form.validateFields()
      setSaving(true)

      const data = {
        ...values,
        audit_date: values.audit_date?.format('YYYY-MM-DD'),
        plan_item_id: planItemId,
        template_id: template?.id,
      }

      if (recordId && recordId !== 'new') {
        await auditRecordApi.update(recordId!, data)
        message.success('记录已更新')
      } else {
        const res = await auditRecordApi.create(projectId!, data)
        message.success('记录已创建')
        // 跳转到编辑页面
        navigate(`/audit-projects/${projectId}/records/${res.data.id}`, { replace: true })
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleSelectTemplate = async (templateId: string) => {
    if (readOnly) return

    try {
      const res = await templateApi.getTemplate(templateId)
      setTemplate(res.data)
      flattenTemplateItems(res.data.items || [])
    } catch (error) {
      message.error('获取模板失败')
    }
  }

  const handleItemChange = async (item: RecordItem, field: string, value: any) => {
    if (readOnly) return

    // 更新本地状态
    const updatedItems = flatItems.map(i => {
      if (i.id === item.id || i.template_item_id === item.id) {
        return { ...i, [field]: value }
      }
      return i
    })
    setFlatItems(updatedItems)

    // 保存到后端（如果有recordId）
    if (recordId && recordId !== 'new') {
      try {
        // 这里需要调用实际的API保存检查项结果
        // await auditRecordApi.saveItemResult(recordId, item.id, { [field]: value })
      } catch (error) {
        console.error('保存失败:', error)
      }
    }
  }

  const handleAIEvaluate = async () => {
    if (readOnly) return

    const evidence = form.getFieldValue('conclusion')
    if (!evidence || evidence.length < 10) {
      message.warning('请先填写审核结论（至少10个字符）')
      return
    }

    const clauseNo = planItem?.clauses?.[0]
      || record?.items?.find((item: RecordItem) => item?.clause_no_snapshot)?.clause_no_snapshot
    if (!clauseNo) {
      message.warning('当前审核计划项未配置条款，无法进行 AI 证据评估')
      return
    }

    setAiLoading(true)
    setAiResult(null)
    try {
      const response = await auditAIApi.evaluateEvidence(projectId!, {
        evidence,
        clause_no: clauseNo,
        certification_system: record?.certification_systems?.[0] || 'ISO 9001',
      })
      setAiResult(response.data)
    } catch (error: any) {
      message.error(error.response?.data?.message || 'AI 评估失败')
    } finally {
      setAiLoading(false)
    }
  }

  const handleUpload = async (uploadInfo: any) => {
    if (readOnly) {
      if (uploadInfo.onError) uploadInfo.onError(new Error('只读模式不能上传照片'))
      return
    }

    const file = uploadInfo.file as File
    if (!recordId || recordId === 'new') {
      message.warning('请先保存记录后再上传照片')
      if (uploadInfo.onError) uploadInfo.onError(new Error('请先保存记录'))
      return
    }
    try {
      const res: any = await mediaApi.upload(file, { record_id: recordId })
      const photoUrl = res.data?.file_path
      if (photoUrl && selectedItem) {
        const updatedPhotos = [...(selectedItem.photos || []), photoUrl]
        handleItemChange(selectedItem, 'photos', updatedPhotos)
      }
      if (uploadInfo.onSuccess) uploadInfo.onSuccess({}, uploadInfo.file)
    } catch (error) {
      message.error('上传失败')
      if (uploadInfo.onError) uploadInfo.onError(error)
    }
  }

  const uploadProps: UploadProps = {
    accept: 'image/*',
    showUploadList: false,
    customRequest: handleUpload,
  }

  // 计算完成进度
  const completedCount = flatItems.filter(item =>
    item.radio_value ||
    (item.score_value !== undefined && item.score_value !== null) ||
    (item.numeric_value !== undefined && item.numeric_value !== null) ||
    item.text_value
  ).length
  const progress = flatItems.length > 0 ? Math.round((completedCount / flatItems.length) * 100) : 0

  // 检查项表格列
  const itemColumns = [
    {
      title: '序号',
      key: 'index',
      width: 60,
      render: (_: any, __: any, index: number) => index + 1,
    },
    {
      title: '检查项目',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '检查结果',
      key: 'result',
      width: 150,
      render: (_: any, item: RecordItem) => {
        if (item.radio_value) {
          const valueMap: Record<string, { color: string; text: string }> = {
            'pass': { color: 'success', text: '合格' },
            'fail': { color: 'error', text: '不合格' },
            'na': { color: 'default', text: '不适用' },
          }
          const info = valueMap[item.radio_value] || { color: 'default', text: item.radio_value }
          return <Tag color={info.color}>{info.text}</Tag>
        }
        if (item.score_value !== undefined && item.score_value !== null) {
          return <Tag color="processing">{item.score_value} 分</Tag>
        }
        if (item.numeric_value !== undefined && item.numeric_value !== null) {
          return <Tag color="processing">{item.numeric_value}</Tag>
        }
        if (item.text_value) {
          return <Tag color="default">已填写</Tag>
        }
        return <Tag color="warning">未填写</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, item: RecordItem) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => {
            setSelectedItem(item)
            setItemDrawerVisible(true)
          }}
        >
          详情
        </Button>
      ),
    },
  ]

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ padding: 24, background: '#f0f2f5', minHeight: '100vh' }}>
      {/* 页面头部 */}
      <div style={{ background: '#fff', padding: '16px 24px', marginBottom: 16, borderRadius: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/audit-projects/${projectId}`)}>
              返回
            </Button>
            <span style={{ fontSize: 18, fontWeight: 600 }}>
              {readOnly ? '查看审核记录' : recordId === 'new' ? '新建审核记录' : '编辑审核记录'}
            </span>
            {record && (
              <Tag color={record.status === 'submitted' ? 'success' : 'warning'}>
                {record.status === 'submitted' ? '已提交' : '草稿'}
              </Tag>
            )}
          </Space>
          {!readOnly && (
            <Space>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                loading={saving}
                onClick={handleSaveRecord}
              >
                保存
              </Button>
              {progress === 100 && record?.status !== 'submitted' && (
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  style={{ background: '#52c41a', borderColor: '#52c41a' }}
                >
                  提交
                </Button>
              )}
            </Space>
          )}
        </div>
      </div>

      {/* 进度条 */}
      {template && (
        <Card bordered={false} style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span>检查进度：</span>
            <Progress
              percent={progress}
              status={progress === 100 ? 'success' : 'active'}
              style={{ flex: 1 }}
            />
            <span>{completedCount}/{flatItems.length}</span>
          </div>
        </Card>
      )}

      <div style={{ display: 'flex', gap: 16 }}>
        {/* 左侧表单 */}
        <div style={{ flex: 1 }}>
          {/* 基本信息 */}
          <Card title="基本信息" bordered={false} style={{ marginBottom: 16 }}>
            <Form form={form} layout="vertical" disabled={readOnly}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <Form.Item
                  name="audit_date"
                  label="审核日期"
                  rules={[{ required: true, message: '请选择审核日期' }]}
                >
                  <DatePicker style={{ width: '100%' }} />
                </Form.Item>

                <Form.Item name="template_id" label="检查模板">
                  <Select
                    placeholder="选择检查模板"
                    onChange={handleSelectTemplate}
                    allowClear
                  >
                    {/* 这里需要从项目或计划项获取模板列表 */}
                  </Select>
                </Form.Item>

                <Form.Item
                  name="audit_time_start"
                  label="开始时间"
                  rules={[{ required: true, message: '请输入开始时间' }]}
                >
                  <Input placeholder="如：09:00" />
                </Form.Item>

                <Form.Item
                  name="audit_time_end"
                  label="结束时间"
                  rules={[{ required: true, message: '请输入结束时间' }]}
                >
                  <Input placeholder="如：12:00" />
                </Form.Item>
              </div>

              <Form.Item
                name="certification_systems"
                label="认证体系"
              >
                <Select mode="multiple" placeholder="选择认证体系">
                  <Select.Option value="Q">Q - 质量</Select.Option>
                  <Select.Option value="E">E - 环境</Select.Option>
                  <Select.Option value="S">S - 职业健康安全</Select.Option>
                  <Select.Option value="En">En - 能源</Select.Option>
                </Select>
              </Form.Item>
            </Form>
          </Card>

          {/* 检查项列表 */}
          {template && (
            <Card
              title="检查项列表"
              bordered={false}
              style={{ marginBottom: 16 }}
              extra={!readOnly ? (
                <Space>
                  <Button
                    icon={<BulbOutlined />}
                    onClick={handleAIEvaluate}
                    loading={aiLoading}
                    style={{ background: '#faad14', borderColor: '#faad14', color: '#fff' }}
                  >
                    AI 评估
                  </Button>
                </Space>
              ) : undefined}
            >
              <Table
                columns={itemColumns}
                dataSource={flatItems}
                rowKey="id"
                pagination={false}
                size="small"
              />
            </Card>
          )}

          {/* 审核结论 */}
          <Card title="审核结论" bordered={false}>
            <Form form={form} layout="vertical" disabled={readOnly}>
              <Form.Item
                name="conclusion"
                label="审核结论"
                rules={[
                  { required: true, message: '请输入审核结论' },
                  { min: 10, message: '审核结论至少10个字符' }
                ]}
              >
                <TextArea rows={4} placeholder="描述审核发现的主要情况" />
              </Form.Item>
            </Form>

            {/* AI 评估结果 */}
            {aiResult && (
              <Alert
                type="info"
                style={{ marginTop: 16 }}
                message={
                  <div>
                    <div style={{ marginBottom: 8 }}>
                      <strong>证据充分性：</strong>
                      <Tag color={aiResult.is_sufficient ? 'green' : 'red'}>
                        {aiResult.is_sufficient ? '充分' : '不充分'}
                      </Tag>
                    </div>
                    <div style={{ marginBottom: 8 }}>
                      <strong>建议评级：</strong>
                      <Tag color="blue">
                        {aiResult.suggested_evaluation === '1' ? '符合' :
                         aiResult.suggested_evaluation === '2' ? '基本符合' : '不符合'}
                      </Tag>
                    </div>
                    <div style={{ marginBottom: 8 }}>
                      <strong>评估理由：</strong>{aiResult.reasoning}
                    </div>
                    {aiResult.additional_evidence_needed && (
                      <div>
                        <strong>建议补充：</strong>{aiResult.additional_evidence_needed}
                      </div>
                    )}
                  </div>
                }
              />
            )}
          </Card>
        </div>

        {/* 右侧信息 */}
        <div style={{ width: 300 }}>
          {/* 企业风险档案 */}
          {project?.enterprise_id && (
            <EnterpriseRiskProfile enterpriseId={project.enterprise_id} compact />
          )}

          {/* 项目信息 */}
          <Card title="项目信息" size="small" style={{ marginBottom: 16 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="项目编号">{project?.project_no}</Descriptions.Item>
              <Descriptions.Item label="项目名称">{project?.title}</Descriptions.Item>
              <Descriptions.Item label="企业名称">{project?.enterprise_name}</Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 计划项信息 */}
          {planItem && (
            <Card title="审核计划" size="small" style={{ marginBottom: 16 }}>
              <Descriptions column={1} size="small">
                <Descriptions.Item label="审核区域">{planItem.area_name}</Descriptions.Item>
                <Descriptions.Item label="计划日期">{planItem.plan_date}</Descriptions.Item>
                <Descriptions.Item label="审核时间">
                  {planItem.time_start} - {planItem.time_end}
                </Descriptions.Item>
              </Descriptions>
            </Card>
          )}

          {!readOnly && (
            <Card title="操作提示" size="small">
              <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.8 }}>
                <p>1. 选择检查模板或使用计划项关联模板</p>
                <p>2. 填写审核日期和时间</p>
                <p>3. 逐项填写检查结果</p>
                <p>4. 点击详情可查看检查项详情、上传照片</p>
                <p>5. 使用AI评估获取智能建议</p>
                <p>6. 填写审核结论后保存</p>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* 检查项详情抽屉 */}
      <Drawer
        title={selectedItem?.title || '检查项详情'}
        placement="right"
        width={600}
        onClose={() => setItemDrawerVisible(false)}
        open={itemDrawerVisible}
      >
        {selectedItem && (
          <div>
            {/* 检查项基本信息 */}
            <Card title="检查项信息" size="small" style={{ marginBottom: 16 }}>
              <Descriptions column={1} size="small">
                <Descriptions.Item label="检查项目">{selectedItem.title}</Descriptions.Item>
                {selectedItem.description && (
                  <Descriptions.Item label="检查内容">{selectedItem.description}</Descriptions.Item>
                )}
                {selectedItem.check_method && (
                  <Descriptions.Item label="检查方法">{selectedItem.check_method}</Descriptions.Item>
                )}
              </Descriptions>
            </Card>

            {/* 检查结果 */}
            <Card title="检查结果" size="small" style={{ marginBottom: 16 }}>
              {/* 必填项提示 */}
              {selectedItem.is_required !== false && (
                <Alert
                  type="info"
                  message="本检查项为必填项，请完成检查结果填写"
                  style={{ marginBottom: 16, fontSize: 12 }}
                  showIcon
                />
              )}

              {/* 根据result_type显示不同的输入 */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8, fontWeight: 500 }}>
                  {selectedItem.is_required !== false && <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>}
                  检查结论
                </div>
                <Select
                  value={selectedItem.radio_value}
                  disabled={readOnly}
                  onChange={(value) => handleItemChange(selectedItem, 'radio_value', value)}
                  style={{ width: '100%' }}
                  placeholder="选择检查结果"
                >
                  <Select.Option value="pass">合格</Select.Option>
                  <Select.Option value="fail">不合格</Select.Option>
                  <Select.Option value="na">不适用</Select.Option>
                </Select>
              </div>

              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8, fontWeight: 500 }}>审核证据</div>
                <TextArea
                  rows={3}
                  placeholder="请输入审核证据"
                  value={selectedItem.audit_evidence || ''}
                  readOnly={readOnly}
                  onChange={(e) => handleItemChange(selectedItem, 'audit_evidence', e.target.value)}
                />
              </div>

              {selectedItem.radio_value === 'fail' && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ marginBottom: 8, fontWeight: 500 }}>
                    <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>
                    审核发现
                  </div>
                  <TextArea
                    rows={3}
                    placeholder="请描述发现的问题"
                    value={selectedItem.audit_findings || ''}
                    readOnly={readOnly}
                    onChange={(e) => handleItemChange(selectedItem, 'audit_findings', e.target.value)}
                  />
                </div>
              )}

              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8, fontWeight: 500 }}>审核记录</div>
                <TextArea
                  rows={2}
                  placeholder="请输入审核记录"
                  value={selectedItem.inspector_note || ''}
                  readOnly={readOnly}
                  onChange={(e) => handleItemChange(selectedItem, 'inspector_note', e.target.value)}
                />
              </div>

              {/* 照片 - 仅当允许附件时显示 */}
              {(selectedItem.allow_attachment || selectedItem.attachment_required) && (
                <div>
                  <div style={{ marginBottom: 8, fontWeight: 500 }}>
                    {selectedItem.attachment_required && <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>}
                    现场照片
                    {selectedItem.attachment_required && (
                      <span style={{ color: '#ff4d4f', fontSize: 12, marginLeft: 8 }}>（必填）</span>
                    )}
                  </div>
                  {!readOnly && (
                    <Upload {...uploadProps}>
                      <Button icon={<CameraOutlined />}>上传照片</Button>
                    </Upload>
                  )}
                  {selectedItem.photos && selectedItem.photos.length > 0 && (
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                      <Image.PreviewGroup>
                        {selectedItem.photos.map((url, idx) => (
                          <Image
                            key={idx}
                            src={url.startsWith('/') || url.startsWith('http') ? url : '/' + url}
                            alt={`照片 ${idx + 1}`}
                            width={80}
                            height={80}
                            style={{ borderRadius: 6, objectFit: 'cover' }}
                          />
                        ))}
                      </Image.PreviewGroup>
                    </div>
                  )}
                </div>
              )}
            </Card>
          </div>
        )}
      </Drawer>
    </div>
  )
}
