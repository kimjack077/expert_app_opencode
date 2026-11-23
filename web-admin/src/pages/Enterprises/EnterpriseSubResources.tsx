/**
 * 企业详情子资源维护：资质、产品、整改记录。
 *
 * 此前企业详情中的资质/产品只读、整改记录无页面，后端 CRUD 接口已齐全但前端未接入。
 * 写操作后端要求管理角色，这里对非管理员隐藏新增/编辑/删除按钮。
 */
import { useEffect, useState } from 'react'
import {
  AutoComplete,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  DatePicker,
  InputNumber,
  Space,
  Tag,
  Popconfirm,
  message,
  Tooltip,
  Typography,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { enterpriseApi } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { isAdminRole } from '@/utils/roles'

const { TextArea } = Input

const errMsg = (error: any, fallback: string) => {
  const detail = error?.response?.data?.detail || error?.response?.data?.message
  return typeof detail === 'string' ? detail : fallback
}

const toDate = (v: any) => (v ? dayjs(v).format('YYYY-MM-DD') : undefined)

const useIsAdmin = () => isAdminRole(useAuthStore((s) => s.user?.role))

/* ============================ 资质 ============================ */

const QUAL_TYPES = ['生产许可证', '食品经营许可证', '3C 认证', '体系认证证书', '特种设备许可', '营业执照', '其他']

export function QualificationsPanel({ enterpriseId, initial, onCount }: { enterpriseId: string; initial?: any[]; onCount?: (n: number) => void }) {
  const canEdit = useIsAdmin()
  const [items, setItems] = useState<any[]>(initial || [])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const res: any = await enterpriseApi.getQualifications(enterpriseId)
      const list = res.data || []
      setItems(list)
      onCount?.(list.length)
    } catch (error) {
      message.error(errMsg(error, '资质列表加载失败'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enterpriseId])

  const openForm = (record?: any) => {
    setEditing(record || null)
    form.resetFields()
    if (record) {
      form.setFieldsValue({
        ...record,
        issue_date: record.issue_date ? dayjs(record.issue_date) : undefined,
        valid_from: record.valid_from ? dayjs(record.valid_from) : undefined,
        valid_until: record.valid_until ? dayjs(record.valid_until) : undefined,
      })
    } else {
      form.setFieldsValue({ status: 'valid' })
    }
    setOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    const payload = {
      ...values,
      issue_date: toDate(values.issue_date),
      valid_from: toDate(values.valid_from),
      valid_until: toDate(values.valid_until),
    }
    setSaving(true)
    try {
      if (editing) {
        await enterpriseApi.updateQualification(editing.id, payload)
        message.success('资质已更新')
      } else {
        await enterpriseApi.createQualification(enterpriseId, payload)
        message.success('资质已添加')
      }
      setOpen(false)
      load()
    } catch (error) {
      message.error(errMsg(error, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id: string) => {
    try {
      await enterpriseApi.deleteQualification(id)
      message.success('资质已删除')
      load()
    } catch (error) {
      message.error(errMsg(error, '删除失败'))
    }
  }

  const expiryTag = (v?: string, status?: string) => {
    if (status && status !== 'valid') return <Tag color="error">失效</Tag>
    if (!v) return <Tag color="success">有效</Tag>
    const days = dayjs(v).startOf('day').diff(dayjs().startOf('day'), 'day')
    if (days < 0) return <Tag color="error">已过期</Tag>
    if (days <= 90) return <Tag color="warning">{days} 天后到期</Tag>
    return <Tag color="success">有效</Tag>
  }

  return (
    <>
      {canEdit && (
        <div style={{ marginBottom: 12, textAlign: 'right' }}>
          <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => openForm()}>
            新增资质
          </Button>
        </div>
      )}
      <Table
        dataSource={items}
        rowKey="id"
        size="middle"
        loading={loading}
        pagination={false}
        locale={{ emptyText: '暂无资质信息' }}
        columns={[
          { title: '资质类型', dataIndex: 'qual_type' },
          { title: '证书编号', dataIndex: 'cert_no', render: (v) => v || '-' },
          { title: '产品/范围', dataIndex: 'product_name', render: (v) => v || '-' },
          { title: '发证机关', dataIndex: 'issue_authority', render: (v) => v || '-' },
          { title: '有效期至', dataIndex: 'valid_until', render: (v) => (v ? dayjs(v).format('YYYY-MM-DD') : '-') },
          { title: '状态', dataIndex: 'status', render: (s, r: any) => expiryTag(r.valid_until, s) },
          ...(canEdit
            ? [
                {
                  title: '操作',
                  key: 'action',
                  width: 110,
                  render: (_: any, r: any) => (
                    <Space size={0}>
                      <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openForm(r)} />
                      <Popconfirm title="确定删除该资质？" onConfirm={() => remove(r.id)} okText="删除" cancelText="取消">
                        <Button type="link" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    </Space>
                  ),
                },
              ]
            : []),
        ]}
      />
      <Modal
        title={editing ? '编辑资质' : '新增资质'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={submit}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="qual_type" label="资质类型" rules={[{ required: true, message: '请选择或输入资质类型' }]}>
            <AutoComplete
              allowClear
              placeholder="选择常用类型或直接输入"
              options={QUAL_TYPES.map((t) => ({ value: t, label: t }))}
              filterOption={(input, option) => String(option?.value || '').includes(input)}
            />
          </Form.Item>
          <Form.Item name="cert_no" label="证书编号">
            <Input placeholder="证书编号" />
          </Form.Item>
          <Form.Item name="product_name" label="产品/认证范围">
            <Input placeholder="例如：乳制品（液体乳）" />
          </Form.Item>
          <Form.Item name="issue_authority" label="发证机关">
            <Input />
          </Form.Item>
          <Space style={{ width: '100%' }} size={12} wrap>
            <Form.Item name="issue_date" label="发证日期">
              <DatePicker />
            </Form.Item>
            <Form.Item name="valid_from" label="有效期起">
              <DatePicker />
            </Form.Item>
            <Form.Item name="valid_until" label="有效期至">
              <DatePicker />
            </Form.Item>
          </Space>
          <Form.Item name="status" label="状态">
            <Select
              options={[
                { value: 'valid', label: '有效' },
                { value: 'expired', label: '过期' },
                { value: 'revoked', label: '吊销/注销' },
              ]}
            />
          </Form.Item>
          <Form.Item name="remarks" label="备注">
            <TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}

/* ============================ 产品 ============================ */

export function ProductsPanel({ enterpriseId, initial, onCount }: { enterpriseId: string; initial?: any[]; onCount?: (n: number) => void }) {
  const canEdit = useIsAdmin()
  const [items, setItems] = useState<any[]>(initial || [])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const res: any = await enterpriseApi.getProducts(enterpriseId)
      const list = res.data || []
      setItems(list)
      onCount?.(list.length)
    } catch (error) {
      message.error(errMsg(error, '产品列表加载失败'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enterpriseId])

  const openForm = (record?: any) => {
    setEditing(record || null)
    form.resetFields()
    if (record) form.setFieldsValue(record)
    setOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      if (editing) {
        await enterpriseApi.updateProduct(enterpriseId, editing.id, values)
        message.success('产品已更新')
      } else {
        await enterpriseApi.createProduct(enterpriseId, values)
        message.success('产品已添加')
      }
      setOpen(false)
      load()
    } catch (error) {
      message.error(errMsg(error, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id: string) => {
    try {
      await enterpriseApi.deleteProduct(enterpriseId, id)
      message.success('产品已删除')
      load()
    } catch (error) {
      message.error(errMsg(error, '删除失败'))
    }
  }

  return (
    <>
      {canEdit && (
        <div style={{ marginBottom: 12, textAlign: 'right' }}>
          <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => openForm()}>
            新增产品
          </Button>
        </div>
      )}
      <Table
        dataSource={items}
        rowKey="id"
        size="middle"
        loading={loading}
        pagination={false}
        locale={{ emptyText: '暂无产品信息' }}
        columns={[
          { title: '产品名称', dataIndex: 'name' },
          { title: '产品类别', dataIndex: 'category', render: (v) => v || '-' },
          { title: '规格型号', dataIndex: 'specification', render: (v) => v || '-' },
          {
            title: '年产量',
            dataIndex: 'annual_output',
            render: (v, r: any) => (v != null ? `${v}${r.output_unit ? ` ${r.output_unit}` : ''}` : '-'),
          },
          { title: '获证状态', dataIndex: 'cert_status', render: (v) => v || '-' },
          ...(canEdit
            ? [
                {
                  title: '操作',
                  key: 'action',
                  width: 110,
                  render: (_: any, r: any) => (
                    <Space size={0}>
                      <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openForm(r)} />
                      <Popconfirm title="确定删除该产品？" onConfirm={() => remove(r.id)} okText="删除" cancelText="取消">
                        <Button type="link" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    </Space>
                  ),
                },
              ]
            : []),
        ]}
      />
      <Modal
        title={editing ? '编辑产品' : '新增产品'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={submit}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="产品名称" rules={[{ required: true, message: '请输入产品名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="category" label="产品类别">
            <Input />
          </Form.Item>
          <Form.Item name="specification" label="规格型号">
            <Input />
          </Form.Item>
          <Space size={12} wrap>
            <Form.Item name="annual_output" label="年产量">
              <InputNumber min={0} style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="output_unit" label="单位">
              <Input placeholder="吨 / 件 / 台" style={{ width: 120 }} />
            </Form.Item>
          </Space>
          <Form.Item name="cert_status" label="获证状态">
            <Select
              allowClear
              options={[
                { value: '已获证', label: '已获证' },
                { value: '申请中', label: '申请中' },
                { value: '未获证', label: '未获证' },
              ]}
            />
          </Form.Item>
          <Form.Item name="remarks" label="备注">
            <TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}

/* ============================ 整改记录 ============================ */

const RECT_STATUS: Record<string, { text: string; color: string }> = {
  pending: { text: '待整改', color: 'error' },
  rectifying: { text: '整改中', color: 'processing' },
  submitted: { text: '已提交待复核', color: 'warning' },
  rejected: { text: '复核驳回', color: 'error' },
  completed: { text: '复核通过', color: 'success' },
  closed: { text: '已关闭', color: 'default' },
}

export function RectificationsPanel({ enterpriseId }: { enterpriseId: string }) {
  const canAdmin = useIsAdmin()
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [form] = Form.useForm()
  const [reviewTarget, setReviewTarget] = useState<{ record: any; pass: boolean } | null>(null)
  const [reviewNote, setReviewNote] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const res: any = await enterpriseApi.getRectifications(enterpriseId)
      setItems(res.data || [])
    } catch (error) {
      message.error(errMsg(error, '整改记录加载失败'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enterpriseId])

  const openForm = (record?: any) => {
    setEditing(record || null)
    form.resetFields()
    if (record) {
      form.setFieldsValue({
        ...record,
        deadline: record.deadline ? dayjs(record.deadline) : undefined,
      })
    } else {
      form.setFieldsValue({ status: 'pending', deadline: dayjs().add(15, 'day') })
    }
    setOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    const payload: any = { ...values, deadline: toDate(values.deadline) }
    if (payload.status === 'submitted' && !editing?.rectified_at) {
      payload.rectified_at = dayjs().toISOString()
    }
    setSaving(true)
    try {
      if (editing) {
        await enterpriseApi.updateRectification(editing.id, payload)
        message.success('整改记录已更新')
      } else {
        await enterpriseApi.createRectification(enterpriseId, payload)
        message.success('整改记录已创建')
      }
      setOpen(false)
      load()
    } catch (error) {
      message.error(errMsg(error, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  const doReview = async () => {
    if (!reviewTarget) return
    if (!reviewTarget.pass && !reviewNote.trim()) {
      message.warning('驳回时请填写原因')
      return
    }
    // 后端复核接口会用 rectification_result 覆盖原值。此前复核意见直接把企业填写的
    // 「整改情况说明」冲掉了（远程实测发现），这里改为在原说明后追加复核意见。
    const prev = String(reviewTarget.record.rectification_result || '').trim()
    const note = reviewNote.trim()
    const stamp = dayjs().format('MM-DD')
    const reviewLine = note
      ? `【复核${reviewTarget.pass ? '通过' : '驳回'} ${stamp}】${note}`
      : reviewTarget.pass ? `【复核通过 ${stamp}】` : ''
    const merged = [prev, reviewLine].filter(Boolean).join('\n')
    try {
      await enterpriseApi.reviewRectification(reviewTarget.record.id, {
        status: reviewTarget.pass ? 'completed' : 'rejected',
        rectification_result: merged || undefined,
      })
      message.success(reviewTarget.pass ? '已复核通过' : '已驳回，企业需重新整改')
      setReviewTarget(null)
      setReviewNote('')
      load()
    } catch (error) {
      message.error(errMsg(error, '复核失败'))
    }
  }

  const visible = statusFilter ? items.filter((i) => (i.status || 'pending') === statusFilter) : items
  const openCount = items.filter((i) => !['completed', 'closed'].includes(i.status || 'pending')).length
  // 整改单可由企业/审核员推进到这几个状态；复核通过 / 驳回只能走复核按钮
  const EDITABLE_STATUS = ['pending', 'rectifying', 'submitted']
  const editingStatus = editing?.status || 'pending'

  return (
    <>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <Space>
          <Select
            allowClear
            size="small"
            placeholder="全部状态"
            style={{ width: 140 }}
            value={statusFilter}
            onChange={setStatusFilter}
            options={Object.entries(RECT_STATUS).map(([value, c]) => ({ value, label: c.text }))}
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            共 {items.length} 条，未闭环 {openCount} 条
          </Typography.Text>
        </Space>
        {canAdmin && (
          <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => openForm()}>
            新建整改单
          </Button>
        )}
      </div>
      <Table
        dataSource={visible}
        rowKey="id"
        size="middle"
        loading={loading}
        pagination={visible.length > 10 ? { pageSize: 10 } : false}
        locale={{ emptyText: '暂无整改记录' }}
        columns={[
          { title: '问题描述', dataIndex: 'issue_description', ellipsis: true },
          { title: '整改要求', dataIndex: 'rectification_requirement', ellipsis: true, render: (v) => v || '-' },
          {
            title: '期限',
            dataIndex: 'deadline',
            width: 120,
            render: (v, r: any) => {
              if (!v) return '-'
              const overdue = dayjs(v).isBefore(dayjs(), 'day') && !['completed', 'closed'].includes(r.status)
              return <span style={{ color: overdue ? '#EF4444' : undefined }}>{dayjs(v).format('YYYY-MM-DD')}{overdue ? '（逾期）' : ''}</span>
            },
          },
          {
            title: '状态',
            dataIndex: 'status',
            width: 120,
            render: (s) => {
              const c = RECT_STATUS[s || 'pending'] || { text: s, color: 'default' }
              return <Tag color={c.color}>{c.text}</Tag>
            },
          },
          { title: '整改结果', dataIndex: 'rectification_result', ellipsis: true, render: (v) => v || '-' },
          {
            title: '操作',
            key: 'action',
            width: 170,
            render: (_: any, r: any) => (
              <Space size={0}>
                {!['completed', 'closed'].includes(r.status) && (
                  <Tooltip title="更新整改进度">
                    <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openForm(r)} />
                  </Tooltip>
                )}
                {canAdmin && r.status === 'submitted' && (
                  <>
                    <Button type="link" size="small" icon={<CheckOutlined />} onClick={() => setReviewTarget({ record: r, pass: true })}>
                      通过
                    </Button>
                    <Button type="link" size="small" danger icon={<CloseOutlined />} onClick={() => setReviewTarget({ record: r, pass: false })}>
                      驳回
                    </Button>
                  </>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? '更新整改记录' : '新建整改单'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={submit}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="issue_description" label="问题描述" rules={[{ required: true, message: '请填写问题描述' }]}>
            <TextArea rows={3} placeholder="现场发现的问题" />
          </Form.Item>
          <Form.Item name="rectification_requirement" label="整改要求">
            <TextArea rows={2} />
          </Form.Item>
          <Space size={12} wrap>
            <Form.Item name="deadline" label="整改期限">
              <DatePicker />
            </Form.Item>
            <Form.Item name="status" label="状态">
              <Select
                style={{ width: 160 }}
                // 被驳回的整改单回填当前状态时显示中文「复核驳回」，而不是原始的 rejected
                options={[
                  ...(!EDITABLE_STATUS.includes(editingStatus) && RECT_STATUS[editingStatus]
                    ? [{ value: editingStatus, label: RECT_STATUS[editingStatus].text, disabled: true }]
                    : []),
                  ...EDITABLE_STATUS.map((v) => ({ value: v, label: RECT_STATUS[v].text })),
                ]}
              />
            </Form.Item>
          </Space>
          <Form.Item name="rectification_result" label="整改情况说明">
            <TextArea rows={2} placeholder="企业整改措施与完成情况" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={reviewTarget?.pass ? '复核通过' : '驳回整改'}
        open={!!reviewTarget}
        onCancel={() => {
          setReviewTarget(null)
          setReviewNote('')
        }}
        onOk={doReview}
        okText={reviewTarget?.pass ? '确认通过' : '确认驳回'}
        okButtonProps={{ danger: !reviewTarget?.pass }}
        cancelText="取消"
      >
        <TextArea
          rows={3}
          value={reviewNote}
          onChange={(e) => setReviewNote(e.target.value)}
          placeholder={reviewTarget?.pass ? '复核意见（可选）' : '请填写驳回原因'}
        />
      </Modal>
    </>
  )
}
