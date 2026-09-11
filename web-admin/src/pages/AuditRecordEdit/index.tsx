import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Button, Space, message, Progress, Table,
  Form, Input, Select, DatePicker, Upload, Drawer, Spin, Alert, Badge, Image
} from 'antd'
import {
  ArrowLeftOutlined, SaveOutlined, SendOutlined, CameraOutlined,
  BulbOutlined, BookOutlined, EyeOutlined, CheckCircleOutlined,
  FolderOpenOutlined, FileTextOutlined, ProjectOutlined,
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
  result_options?: any
  // 必填相关
  is_required?: boolean
  allow_attachment?: boolean
  attachment_required?: boolean
  // 结果字段
  result?: string
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
  rectification_suggestion?: string
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
  const [templates, setTemplates] = useState<any[]>([])
  const [treeItems, setTreeItems] = useState<RecordItem[]>([])
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

  // 递归构建树形结构，确保叶子节点的 children 为 undefined，避免 AntD Table 出现无意义的加号
  const buildTreeData = (items: any[], recordItemsMap: Record<string, any> = {}): RecordItem[] => {
    return (items || []).map((item) => {
      const recordItem = item.id ? recordItemsMap[item.id] : null
      const hasChildren = Array.isArray(item.children) && item.children.length > 0
      const childNodes = hasChildren
        ? buildTreeData(item.children, recordItemsMap)
        : undefined

      let radioVal = recordItem?.radio_value
      if (!radioVal && recordItem) {
        if (recordItem.result === 'pass' || recordItem.evaluation_3level === '1' || recordItem.evaluation_3level === '2') {
          radioVal = 'pass'
        } else if (recordItem.result === 'fail' || recordItem.evaluation_3level === '3') {
          radioVal = 'fail'
        }
      }

      const mergedItem: RecordItem = {
        ...item,
        ...(recordItem || {}),
        title: item.title || recordItem?.item_title,
        id: recordItem?.id || item.id,
        template_item_id: item.id,
        result: recordItem?.result,
        radio_value: radioVal,
        evaluation_3level: recordItem?.evaluation_3level,
        audit_evidence: recordItem?.audit_evidence || recordItem?.inspector_note,
        audit_findings: recordItem?.audit_findings || recordItem?.problem_description,
        rectification_suggestion: recordItem?.rectification_suggestion,
        inspector_note: recordItem?.inspector_note,
        photos: recordItem?.photos || (recordItem?.media_file_id ? [recordItem.media_file_id] : []),
        is_category: !!item.is_category || (hasChildren && !item.result_type),
        children: childNodes && childNodes.length > 0 ? childNodes : undefined,
      }
      return mergedItem
    })
  }

  // 提取所有底层的实际检查项（用于统计和进度）
  const extractFlatCheckItems = (treeNodes: RecordItem[]): RecordItem[] => {
    let list: RecordItem[] = []
    for (const node of treeNodes) {
      if (!node.is_category && (!node.children || node.children.length === 0)) {
        list.push(node)
      } else if (node.children && node.children.length > 0) {
        list = list.concat(extractFlatCheckItems(node.children))
      }
    }
    return list
  }

  const processTemplateAndRecords = (templateItems: any[], recordItems: any[] = []) => {
    const recordItemsMap: Record<string, any> = {}
    for (const ri of recordItems) {
      if (ri.template_item_id) {
        recordItemsMap[ri.template_item_id] = ri
      } else if (ri.id) {
        recordItemsMap[ri.id] = ri
      }
    }

    if (templateItems && templateItems.length > 0) {
      const tree = buildTreeData(templateItems, recordItemsMap)
      const flat = extractFlatCheckItems(tree)
      setTreeItems(tree)
      setFlatItems(flat)
    } else if (recordItems && recordItems.length > 0) {
      const flat: RecordItem[] = recordItems.map((item: any) => {
        let radioVal = item.radio_value
        if (!radioVal) {
          if (item.result === 'pass' || item.evaluation_3level === '1' || item.evaluation_3level === '2') {
            radioVal = 'pass'
          } else if (item.result === 'fail' || item.evaluation_3level === '3') {
            radioVal = 'fail'
          }
        }
        return {
          id: item.id,
          template_item_id: item.template_item_id || item.id,
          title: item.item_title || item.title || item.clause_no_snapshot || '检查项',
          description: item.description,
          is_category: false,
          result: item.result,
          radio_value: radioVal,
          evaluation_3level: item.evaluation_3level,
          audit_evidence: item.audit_evidence || item.inspector_note,
          audit_findings: item.audit_findings || item.problem_description,
          rectification_suggestion: item.rectification_suggestion,
          inspector_note: item.inspector_note,
          photos: item.photos || (item.media_file_id ? [item.media_file_id] : []),
        }
      })
      setTreeItems(flat)
      setFlatItems(flat)
    } else {
      setTreeItems([])
      setFlatItems([])
    }
  }

  const fetchData = async () => {
    setLoading(true)
    try {
      // 1. 获取项目信息
      const projectRes = await auditProjectApi.get(projectId!)
      setProject(projectRes.data)

      // 2. 获取模板列表
      const templatesRes: any = await templateApi.getTemplates({ limit: 100 })
      const availableTemplates = templatesRes.data?.items || templatesRes.data || []
      setTemplates(availableTemplates)

      // 3. 如果有计划项ID，获取计划项详情
      let loadedPlanItem: any = null
      if (planItemId) {
        const planRes = await auditPlanApi.get(planItemId)
        loadedPlanItem = planRes.data
        setPlanItem(loadedPlanItem)
      }

      // 4. 如果有记录ID，获取记录详情
      if (recordId && recordId !== 'new') {
        const recordRes = await auditRecordApi.get(recordId!)
        setRecord(recordRes.data)
        const formData = {
          ...recordRes.data,
          audit_date: recordRes.data.audit_date ? dayjs(recordRes.data.audit_date) : undefined,
        }
        form.setFieldsValue(formData)

        // 获取模板（支持从 record 自身、plan_item、或单独查询关联 planItem）
        let targetTemplateId = recordRes.data.template_id || recordRes.data.plan_item?.template_id || loadedPlanItem?.template_id
        if (!targetTemplateId && recordRes.data.plan_item_id) {
          try {
            const planRes = await auditPlanApi.get(recordRes.data.plan_item_id)
            if (planRes.data?.template_id) {
              targetTemplateId = planRes.data.template_id
            }
          } catch (e) {
            console.error('加载关联计划项模板失败:', e)
          }
        }

        if (targetTemplateId) {
          try {
            const templateRes = await templateApi.getTemplate(targetTemplateId)
            setTemplate(templateRes.data)
            processTemplateAndRecords(templateRes.data.items || [], recordRes.data.items || [])
          } catch (e) {
            console.error('加载模板详情失败:', e)
            processTemplateAndRecords([], recordRes.data.items || [])
          }
        } else {
          processTemplateAndRecords([], recordRes.data.items || [])
        }
      } else {
        // 新建记录
        const defaultTemplateId = loadedPlanItem?.template_id || (availableTemplates.length > 0 ? availableTemplates[0].id : undefined)
        const initialFormData = {
          audit_date: loadedPlanItem?.plan_date ? dayjs(loadedPlanItem.plan_date) : dayjs(),
          audit_time_start: loadedPlanItem?.start_time || '09:00',
          audit_time_end: loadedPlanItem?.end_time || '12:00',
          certification_systems: loadedPlanItem?.certification_systems || (loadedPlanItem?.certification_system ? [loadedPlanItem.certification_system] : []),
          template_id: defaultTemplateId,
        }
        form.setFieldsValue(initialFormData)

        if (defaultTemplateId) {
          try {
            const templateRes = await templateApi.getTemplate(defaultTemplateId)
            setTemplate(templateRes.data)
            processTemplateAndRecords(templateRes.data.items || [], [])
          } catch (e) {
            console.error('加载初始模板详情失败:', e)
          }
        }
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取数据失败')
    } finally {
      setLoading(false)
    }
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
        template_id: values.template_id || template?.id,
      }

      if (recordId && recordId !== 'new') {
        await auditRecordApi.update(recordId!, data)
        message.success('记录已更新')
      } else {
        const res = await auditRecordApi.create(projectId!, data)
        message.success('记录已创建')
        navigate(`/audit-projects/${projectId}/records/${res.data.id}`, { replace: true })
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleSelectTemplate = async (templateId?: string) => {
    if (readOnly) return

    if (!templateId) {
      setTemplate(null)
      setTreeItems([])
      setFlatItems([])
      form.setFieldsValue({ template_id: undefined })
      return
    }

    try {
      const res = await templateApi.getTemplate(templateId)
      setTemplate(res.data)
      form.setFieldsValue({ template_id: templateId })
      processTemplateAndRecords(res.data.items || [], record?.items || [])
    } catch (error) {
      message.error('获取模板失败')
    }
  }

  const handleItemChange = async (item: RecordItem, field: string, value: any) => {
    if (readOnly) return

    const updateTreeNode = (nodes: RecordItem[]): RecordItem[] => {
      return nodes.map((node) => {
        if (node.id === item.id || node.template_item_id === item.template_item_id) {
          return { ...node, [field]: value }
        }
        if (node.children && node.children.length > 0) {
          return { ...node, children: updateTreeNode(node.children) }
        }
        return node
      })
    }

    const newTree = updateTreeNode(treeItems)
    setTreeItems(newTree)
    setFlatItems(extractFlatCheckItems(newTree))

    if (selectedItem && (selectedItem.id === item.id || selectedItem.template_item_id === item.template_item_id)) {
      setSelectedItem({ ...selectedItem, [field]: value })
    }
  }

  const handleAIEvaluate = async () => {
    if (readOnly) return

    const evidence = form.getFieldValue('conclusion') || record?.conclusion
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
      // 优先用检查记录项 ID，后端据此换算为任务检查项，保住照片与条目的关联
      const res: any = await mediaApi.upload(file, { record_id: selectedItem?.id || recordId })
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

  // 统计结果与进度
  const passCount = useMemo(() => flatItems.filter((i) => i.radio_value === 'pass' || i.result === 'pass' || i.evaluation_3level === '1' || i.evaluation_3level === '2').length, [flatItems])
  const failCount = useMemo(() => flatItems.filter((i) => i.radio_value === 'fail' || i.result === 'fail' || i.evaluation_3level === '3').length, [flatItems])
  const naCount = useMemo(() => flatItems.filter((i) => i.radio_value === 'na' || i.radio_value === 'not_applicable').length, [flatItems])
  const pendingCount = useMemo(() => flatItems.filter((i) => i.radio_value === 'pending_rectification').length, [flatItems])
  const completedCount = useMemo(() => {
    return flatItems.filter((item) =>
      item.radio_value ||
      item.result ||
      item.evaluation_3level ||
      (item.score_value !== undefined && item.score_value !== null && String(item.score_value) !== '') ||
      (item.numeric_value !== undefined && item.numeric_value !== null && String(item.numeric_value) !== '') ||
      item.text_value ||
      item.audit_evidence
    ).length
  }, [flatItems])
  const totalCount = flatItems.length
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  // 检查项表格列定义（层级树形展示）
  const itemColumns = [
    {
      title: '序号',
      key: 'index',
      width: 70,
      align: 'center' as const,
      render: (_: any, item: RecordItem, index: number) => {
        if (item.is_category) {
          return null
        }
        return <span style={{ color: '#64748b', fontWeight: 500 }}>{index + 1}</span>
      },
    },
    {
      title: '检查项目',
      key: 'title',
      render: (_: any, item: RecordItem) => {
        if (item.is_category) {
          const childCheckItems = extractFlatCheckItems(item.children || [])
          const childCompleted = childCheckItems.filter(i => !!i.radio_value || !!i.text_value || !!i.evaluation_3level || !!i.result).length
          const childTotal = childCheckItems.length
          const allPass = childTotal > 0 && childCheckItems.every(i => i.radio_value === 'pass' || i.evaluation_3level === '1' || i.evaluation_3level === '2' || i.result === 'pass')

          return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 0' }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>
                <FolderOpenOutlined style={{ marginRight: 8, color: '#1677ff' }} />
                {item.title}
              </span>
              <Space size="small">
                <Tag color={childCompleted === childTotal && childTotal > 0 ? 'success' : 'processing'} style={{ borderRadius: 10 }}>
                  {childCompleted}/{childTotal} 已完成
                </Tag>
                {allPass && <Tag color="green" style={{ borderRadius: 10 }}>全部符合</Tag>}
              </Space>
            </div>
          )
        }

        return (
          <div style={{ padding: '4px 0' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 13, color: '#1e293b', fontWeight: 600 }}>
                {item.title}
              </span>
              {item.is_required !== false && (
                <Tag color="error" style={{ fontSize: 11, padding: '0 4px', lineHeight: '18px', borderRadius: 2 }}>必填</Tag>
              )}
              {item.attachment_required && (
                <Tag color="purple" style={{ fontSize: 11, padding: '0 4px', lineHeight: '18px', borderRadius: 2 }}>
                  <CameraOutlined style={{ marginRight: 2 }} />附件
                </Tag>
              )}
              {item.result_type && (
                <Tag color="default" style={{ fontSize: 11, padding: '0 4px', lineHeight: '18px', borderRadius: 2 }}>
                  {item.result_type === 'pass_fail' ? '判定' : item.result_type === 'numeric' ? '数值' : item.result_type === 'score' ? '打分' : '描述'}
                </Tag>
              )}
            </div>
            {item.description && (
              <div style={{ fontSize: 12, color: '#64748b', marginTop: 3, lineHeight: 1.5 }}>
                {item.description}
              </div>
            )}
            {(item.audit_evidence || item.inspector_note) && (
              <div style={{ fontSize: 12, color: '#334155', marginTop: 5, background: '#f0f9ff', padding: '5px 10px', borderRadius: 4, borderLeft: '3px solid #0284c7' }}>
                <span style={{ fontWeight: 600, color: '#0369a1' }}>🔍 审核证据：</span>{item.audit_evidence || item.inspector_note}
              </div>
            )}
            {item.audit_findings && (
              <div style={{ fontSize: 12, color: '#991b1b', marginTop: 4, background: '#fef2f2', padding: '5px 10px', borderRadius: 4, borderLeft: '3px solid #ef4444' }}>
                <span style={{ fontWeight: 600, color: '#dc2626' }}>⚠️ 审核发现：</span>{item.audit_findings}
              </div>
            )}
            {item.rectification_suggestion && (
              <div style={{ fontSize: 12, color: '#9a3412', marginTop: 4, background: '#fff7ed', padding: '5px 10px', borderRadius: 4, borderLeft: '3px solid #f97316' }}>
                <span style={{ fontWeight: 600, color: '#ea580c' }}>💡 整改建议：</span>{item.rectification_suggestion}
              </div>
            )}
          </div>
        )
      },
    },
    {
      title: '检查结果',
      key: 'result',
      width: 170,
      render: (_: any, item: RecordItem) => {
        if (item.is_category) return null

        if (item.evaluation_3level) {
          const evalMap: Record<string, { color: string; text: string }> = {
            '1': { color: 'success', text: '符合' },
            '2': { color: 'warning', text: '基本符合' },
            '3': { color: 'error', text: '不符合' },
          }
          const evalInfo = evalMap[item.evaluation_3level] || { color: 'default', text: item.evaluation_3level }
          return (
            <Space direction="vertical" size={2}>
              <Tag color={evalInfo.color} style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, fontWeight: 600 }}>
                {evalInfo.text}
              </Tag>
              {item.photos && item.photos.length > 0 && (
                <Tag color="purple" style={{ fontSize: 11, borderRadius: 2 }}>
                  📷 {item.photos.length} 张照片
                </Tag>
              )}
            </Space>
          )
        }
        if (item.radio_value || item.result) {
          const rVal = item.radio_value || item.result
          const map: Record<string, { color: string; text: string }> = {
            'pass': { color: 'success', text: '合格' },
            'fail': { color: 'error', text: '不合格' },
            'na': { color: 'default', text: '不适用' },
            'not_applicable': { color: 'default', text: '不适用' },
            'pending_rectification': { color: 'warning', text: '待整改' },
          }
          const info = map[rVal!] || { color: 'default', text: rVal! }
          return (
            <Space direction="vertical" size={2}>
              <Tag color={info.color} style={{ fontSize: 12, padding: '2px 8px', borderRadius: 4, fontWeight: 500 }}>
                {info.text}
              </Tag>
              {item.photos && item.photos.length > 0 && (
                <Tag color="purple" style={{ fontSize: 11, borderRadius: 2 }}>
                  📷 {item.photos.length} 张照片
                </Tag>
              )}
            </Space>
          )
        }
        if (item.score_value !== undefined && item.score_value !== null && String(item.score_value) !== '') {
          return <Tag color="processing">{item.score_value} 分</Tag>
        }
        if (item.numeric_value !== undefined && item.numeric_value !== null && String(item.numeric_value) !== '') {
          return <Tag color="processing">{item.numeric_value}</Tag>
        }
        if (item.text_value) {
          return <Tag color="default">已填写</Tag>
        }
        return <Tag color="warning">未检查</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      align: 'center' as const,
      render: (_: any, item: RecordItem) => {
        if (item.is_category) return null
        return (
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
        )
      },
    },
  ]

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" tip="正在加载审核记录..." />
      </div>
    )
  }

  return (
    <div style={{ padding: '16px 20px', background: '#f1f5f9', minHeight: '100vh' }}>
      {/* 顶部导航与操作栏 */}
      <div
        style={{
          background: '#fff',
          padding: '14px 20px',
          marginBottom: 16,
          borderRadius: 8,
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <Space size="middle">
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate(`/audit-projects/${projectId}`)}
            style={{ borderRadius: 6 }}
          >
            返回项目
          </Button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 17, fontWeight: 700, color: '#0f172a' }}>
              {readOnly ? '查看审核记录' : recordId === 'new' ? '新建审核记录' : '编辑审核记录'}
            </span>
            {record?.record_no && (
              <Tag color="cyan" style={{ borderRadius: 4, fontFamily: 'monospace' }}>
                {record.record_no}
              </Tag>
            )}
            {record && (
              <Tag
                color={record.status === 'submitted' ? 'success' : 'warning'}
                style={{ borderRadius: 4, fontWeight: 500 }}
              >
                {record.status === 'submitted' ? '已提交' : '草稿'}
              </Tag>
            )}
          </div>
        </Space>

        {!readOnly && (
          <Space>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={saving}
              onClick={handleSaveRecord}
              style={{ borderRadius: 6 }}
            >
              保存记录
            </Button>
            {progressPercent === 100 && record?.status !== 'submitted' && (
              <Button
                type="primary"
                icon={<SendOutlined />}
                style={{ background: '#16a34a', borderColor: '#16a34a', borderRadius: 6 }}
              >
                提交审核
              </Button>
            )}
          </Space>
        )}
      </div>

      {/* 检查进度与统计概览卡片 */}
      {template && (
        <Card
          bordered={false}
          bodyStyle={{ padding: '14px 20px' }}
          style={{ marginBottom: 16, borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, flex: 1, minWidth: 320 }}>
              <span style={{ fontWeight: 600, color: '#334155', whiteSpace: 'nowrap', fontSize: 13 }}>
                检查进度：
              </span>
              <Progress
                percent={progressPercent}
                status={progressPercent === 100 ? 'success' : 'active'}
                strokeColor={progressPercent === 100 ? '#16a34a' : '#2563eb'}
                style={{ flex: 1 }}
              />
              <span style={{ fontWeight: 700, color: '#0f172a', whiteSpace: 'nowrap', fontSize: 14 }}>
                {completedCount} / {totalCount} 项
              </span>
            </div>

            <Space size="middle" wrap style={{ fontSize: 13 }}>
              <Badge color="#16a34a" text={<span style={{ color: '#475569' }}>合格: <strong style={{ color: '#16a34a' }}>{passCount}</strong></span>} />
              <Badge color="#dc2626" text={<span style={{ color: '#475569' }}>不合格: <strong style={{ color: '#dc2626' }}>{failCount}</strong></span>} />
              <Badge color="#d97706" text={<span style={{ color: '#475569' }}>待整改: <strong style={{ color: '#d97706' }}>{pendingCount}</strong></span>} />
              <Badge color="#94a3b8" text={<span style={{ color: '#475569' }}>不适用: <strong style={{ color: '#64748b' }}>{naCount}</strong></span>} />
            </Space>
          </div>
        </Card>
      )}

      {/* 主体两栏布局 */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        {/* 左侧主体内容区 */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* 基本信息卡片 */}
          <Card
            title={
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Space size="small">
                  <BookOutlined style={{ color: '#2563eb' }} />
                  <span style={{ fontSize: 15, fontWeight: 600, color: '#0f172a' }}>基本信息</span>
                </Space>
                <Tag color="blue" style={{ borderRadius: 4 }}>现场审核记录</Tag>
              </div>
            }
            bordered={false}
            bodyStyle={{ padding: readOnly ? '12px 16px' : '16px 20px' }}
            style={{ marginBottom: 16, borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}
          >
            {readOnly ? (
              <Descriptions
                bordered
                size="small"
                column={{ xs: 1, sm: 2, md: 3 }}
                labelStyle={{ width: '110px', background: '#f8fafc', fontWeight: 500, color: '#475569', fontSize: 13 }}
                contentStyle={{ background: '#fff', color: '#0f172a', fontSize: 13 }}
              >
                <Descriptions.Item label="审核日期">
                  {record?.audit_date || (record?.created_at ? dayjs(record.created_at).format('YYYY-MM-DD') : '-')}
                </Descriptions.Item>
                <Descriptions.Item label="审核时间">
                  {record?.audit_time_start && record?.audit_time_end
                    ? `${record.audit_time_start} ~ ${record.audit_time_end}`
                    : record?.audit_time_start || '全天'}
                </Descriptions.Item>
                <Descriptions.Item label="检查模板">
                  {template ? (
                    <Tag color="cyan" style={{ borderRadius: 4, fontWeight: 500 }}>
                      {template.name} (v{template.version || '1.0'})
                    </Tag>
                  ) : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="认证体系">
                  {record?.certification_systems && record.certification_systems.length > 0 ? (
                    <Space size={4} wrap>
                      {record.certification_systems.map((sys: string) => {
                        const sysMap: Record<string, { label: string; color: string }> = {
                          'Q': { label: 'Q - 质量', color: 'blue' },
                          'E': { label: 'E - 环境', color: 'green' },
                          'S': { label: 'S - 职业健康安全', color: 'purple' },
                          'En': { label: 'En - 能源', color: 'orange' }
                        }
                        const info = sysMap[sys] || { label: sys, color: 'blue' }
                        return <Tag key={sys} color={info.color} style={{ borderRadius: 4 }}>{info.label}</Tag>
                      })}
                    </Space>
                  ) : <Tag color="blue">三体系 (Q/E/S)</Tag>}
                </Descriptions.Item>
                <Descriptions.Item label="审核区域">
                  {planItem?.area_name || record?.area_name || '生产现场 / 车间'}
                </Descriptions.Item>
                <Descriptions.Item label="记录人员">
                  {record?.auditor_name || record?.created_by_name || '审核员'}
                </Descriptions.Item>
              </Descriptions>
            ) : (
              <Form form={form} layout="vertical">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px 16px' }}>
                  <Form.Item
                    name="audit_date"
                    label="审核日期"
                    rules={[{ required: true, message: '请选择审核日期' }]}
                    style={{ marginBottom: 12 }}
                  >
                    <DatePicker style={{ width: '100%' }} />
                  </Form.Item>

                  <Form.Item name="template_id" label="检查模板" style={{ marginBottom: 12 }}>
                    <Select
                      placeholder="选择检查模板"
                      onChange={handleSelectTemplate}
                      allowClear
                      showSearch
                      optionFilterProp="label"
                      options={templates.map((t: any) => ({
                        value: t.id,
                        label: `${t.name} (v${t.version || '1.0'}${t.category ? ` · ${t.category}` : ''})`,
                      }))}
                    />
                  </Form.Item>

                  <Form.Item
                    name="audit_time_start"
                    label="开始时间"
                    rules={[{ required: true, message: '请输入开始时间' }]}
                    style={{ marginBottom: 12 }}
                  >
                    <Input placeholder="如：09:00" />
                  </Form.Item>

                  <Form.Item
                    name="audit_time_end"
                    label="结束时间"
                    rules={[{ required: true, message: '请输入结束时间' }]}
                    style={{ marginBottom: 12 }}
                  >
                    <Input placeholder="如：12:00" />
                  </Form.Item>
                </div>

                <Form.Item
                  name="certification_systems"
                  label="认证体系"
                  style={{ marginBottom: 0 }}
                >
                  <Select mode="multiple" placeholder="选择认证体系">
                    <Select.Option value="Q">Q - 质量</Select.Option>
                    <Select.Option value="E">E - 环境</Select.Option>
                    <Select.Option value="S">S - 职业健康安全</Select.Option>
                    <Select.Option value="En">En - 能源</Select.Option>
                  </Select>
                </Form.Item>
              </Form>
            )}
          </Card>

          {/* 检查项列表卡片（支持模板层级展示） */}
          {template && (
            <Card
              title={
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Space size="small">
                    <FileTextOutlined style={{ color: '#2563eb' }} />
                    <span style={{ fontSize: 15, fontWeight: 600, color: '#0f172a' }}>检查项列表</span>
                  </Space>
                  {!readOnly && (
                    <Button
                      icon={<BulbOutlined />}
                      onClick={handleAIEvaluate}
                      loading={aiLoading}
                      style={{ background: '#faad14', borderColor: '#faad14', color: '#fff', borderRadius: 6 }}
                    >
                      AI 证据评估
                    </Button>
                  )}
                </div>
              }
              bordered={false}
              bodyStyle={{ padding: 0 }}
              style={{ marginBottom: 16, borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}
            >
              <Table
                columns={itemColumns}
                dataSource={treeItems}
                rowKey="id"
                pagination={false}
                size="middle"
                expandable={{
                  defaultExpandAllRows: true,
                  rowExpandable: (recordItem) => !!(recordItem.children && recordItem.children.length > 0),
                }}
              />
            </Card>
          )}

          {/* 审核结论卡片 */}
          <Card
            title={
              <Space size="small">
                <CheckCircleOutlined style={{ color: '#16a34a' }} />
                <span style={{ fontSize: 15, fontWeight: 600, color: '#0f172a' }}>审核结论</span>
              </Space>
            }
            bordered={false}
            bodyStyle={{ padding: '16px 20px' }}
            style={{ borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}
          >
            {readOnly ? (
              <div
                style={{
                  background: '#f8fafc',
                  borderLeft: '4px solid #2563eb',
                  padding: '14px 18px',
                  borderRadius: '0 8px 8px 0',
                  fontSize: 14,
                  lineHeight: 1.8,
                  color: '#1e293b',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {record?.conclusion || '暂未填写审核结论'}
              </div>
            ) : (
              <Form form={form} layout="vertical">
                <Form.Item
                  name="conclusion"
                  label="审核结论与总结评价"
                  rules={[
                    { required: true, message: '请输入审核结论' },
                    { min: 10, message: '审核结论至少10个字符' }
                  ]}
                  style={{ marginBottom: 0 }}
                >
                  <TextArea
                    rows={4}
                    placeholder="请输入现场审核结论、审核发现以及总结评价..."
                    style={{ borderRadius: 6 }}
                  />
                </Form.Item>
              </Form>
            )}

            {/* AI 评估结果提示 */}
            {aiResult && (
              <Alert
                type="info"
                style={{ marginTop: 16, borderRadius: 6 }}
                message={
                  <div>
                    <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <strong>证据充分性：</strong>
                      <Tag color={aiResult.is_sufficient ? 'green' : 'red'}>
                        {aiResult.is_sufficient ? '充分' : '不充分'}
                      </Tag>
                      <strong style={{ marginLeft: 8 }}>建议评级：</strong>
                      <Tag color="blue">
                        {aiResult.suggested_evaluation === '1' ? '符合' :
                         aiResult.suggested_evaluation === '2' ? '基本符合' : '不符合'}
                      </Tag>
                    </div>
                    <div style={{ marginBottom: 6, color: '#334155', fontSize: 13 }}>
                      <strong>评估理由：</strong>{aiResult.reasoning}
                    </div>
                    {aiResult.additional_evidence_needed && (
                      <div style={{ color: '#d97706', fontSize: 13 }}>
                        <strong>建议补充：</strong>{aiResult.additional_evidence_needed}
                      </div>
                    )}
                  </div>
                }
              />
            )}
          </Card>
        </div>

        {/* 右侧边栏信息区 */}
        <div style={{ width: 300, flexShrink: 0 }}>
          {/* 企业风险档案 */}
          {project?.enterprise_id && (
            <div style={{ marginBottom: 16 }}>
              <EnterpriseRiskProfile enterpriseId={project.enterprise_id} compact />
            </div>
          )}

          {/* 项目信息 */}
          <Card
            title={
              <Space size="small">
                <ProjectOutlined style={{ color: '#2563eb' }} />
                <span style={{ fontSize: 14, fontWeight: 600 }}>项目信息</span>
              </Space>
            }
            size="small"
            bordered={false}
            style={{ marginBottom: 16, borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}
          >
            <Descriptions column={1} size="small" labelStyle={{ color: '#64748b', fontSize: 12 }} contentStyle={{ color: '#0f172a', fontSize: 12 }}>
              <Descriptions.Item label="项目编号">{project?.project_no || '-'}</Descriptions.Item>
              <Descriptions.Item label="项目名称">{project?.title || '-'}</Descriptions.Item>
              <Descriptions.Item label="企业名称">{project?.enterprise_name || '-'}</Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 计划项信息 */}
          {planItem && (
            <Card
              title="审核计划"
              size="small"
              bordered={false}
              style={{ marginBottom: 16, borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}
            >
              <Descriptions column={1} size="small" labelStyle={{ color: '#64748b', fontSize: 12 }} contentStyle={{ color: '#0f172a', fontSize: 12 }}>
                <Descriptions.Item label="审核区域">{planItem.area_name || '-'}</Descriptions.Item>
                <Descriptions.Item label="计划日期">{planItem.plan_date || '-'}</Descriptions.Item>
                <Descriptions.Item label="审核时间">
                  {planItem.time_start && planItem.time_end ? `${planItem.time_start} - ${planItem.time_end}` : '待定'}
                </Descriptions.Item>
              </Descriptions>
            </Card>
          )}

          {!readOnly && (
            <Card
              title="操作提示"
              size="small"
              bordered={false}
              style={{ borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}
            >
              <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.8 }}>
                <p style={{ margin: '0 0 4px' }}>1. 确认审核日期与检查模板</p>
                <p style={{ margin: '0 0 4px' }}>2. 逐项填写或查看检查结果</p>
                <p style={{ margin: '0 0 4px' }}>3. 点击详情查看说明并上传现场照片</p>
                <p style={{ margin: '0 0 4px' }}>4. 可使用 AI 证据评估辅助评定</p>
                <p style={{ margin: '0 0 4px' }}>5. 填写审核结论后保存或提交</p>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* 检查项详情抽屉 */}
      <Drawer
        title={selectedItem?.title || '检查项详情'}
        placement="right"
        width={560}
        onClose={() => setItemDrawerVisible(false)}
        open={itemDrawerVisible}
      >
        {selectedItem && (
          <div>
            {/* 检查项基本信息 */}
            <Card title="检查项信息" size="small" style={{ marginBottom: 16, borderRadius: 6 }}>
              <Descriptions column={1} size="small" labelStyle={{ width: '80px', color: '#64748b' }}>
                <Descriptions.Item label="检查项目">{selectedItem.title}</Descriptions.Item>
                {selectedItem.description && (
                  <Descriptions.Item label="检查内容">{selectedItem.description}</Descriptions.Item>
                )}
                {selectedItem.check_method && (
                  <Descriptions.Item label="检查方法">{selectedItem.check_method}</Descriptions.Item>
                )}
                {selectedItem.legal_basis && (
                  <Descriptions.Item label="法律依据">{selectedItem.legal_basis}</Descriptions.Item>
                )}
              </Descriptions>
            </Card>

            {/* 检查结果 */}
            <Card title="检查结果" size="small" style={{ marginBottom: 16, borderRadius: 6 }}>
              {selectedItem.is_required !== false && (
                <Alert
                  type="info"
                  message="本检查项为必填项"
                  style={{ marginBottom: 14, fontSize: 12, borderRadius: 4 }}
                  showIcon
                />
              )}

              <div style={{ marginBottom: 14 }}>
                <div style={{ marginBottom: 6, fontWeight: 500, fontSize: 13, color: '#334155' }}>
                  {selectedItem.is_required !== false && <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>}
                  检查结论
                </div>
                <Space style={{ width: '100%', marginBottom: 8 }}>
                  <Select
                    value={selectedItem.radio_value}
                    disabled={readOnly}
                    onChange={(value) => handleItemChange(selectedItem, 'radio_value', value)}
                    style={{ width: 220 }}
                    placeholder="选择检查结果"
                  >
                    <Select.Option value="pass">合格</Select.Option>
                    <Select.Option value="fail">不合格</Select.Option>
                    <Select.Option value="pending_rectification">待整改</Select.Option>
                    <Select.Option value="na">不适用</Select.Option>
                  </Select>
                  {selectedItem.evaluation_3level && (
                    <Tag color={selectedItem.evaluation_3level === '1' ? 'success' : selectedItem.evaluation_3level === '3' ? 'error' : 'warning'} style={{ padding: '3px 8px', borderRadius: 4, fontWeight: 600 }}>
                      {selectedItem.evaluation_3level === '1' ? '符合' : selectedItem.evaluation_3level === '3' ? '不符合' : '基本符合'}
                    </Tag>
                  )}
                </Space>
              </div>

              <div style={{ marginBottom: 14 }}>
                <div style={{ marginBottom: 6, fontWeight: 500, fontSize: 13, color: '#334155' }}>审核证据</div>
                <TextArea
                  rows={3}
                  placeholder="请输入审核证据"
                  value={selectedItem.audit_evidence || ''}
                  readOnly={readOnly}
                  onChange={(e) => handleItemChange(selectedItem, 'audit_evidence', e.target.value)}
                  style={{ borderRadius: 4 }}
                />
              </div>

              {(selectedItem.radio_value === 'fail' || selectedItem.evaluation_3level === '3' || selectedItem.audit_findings) && (
                <div style={{ marginBottom: 14 }}>
                  <div style={{ marginBottom: 6, fontWeight: 500, fontSize: 13, color: '#334155' }}>
                    <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>
                    审核发现 / 不符合描述
                  </div>
                  <TextArea
                    rows={3}
                    placeholder="请描述发现的不符合问题"
                    value={selectedItem.audit_findings || ''}
                    readOnly={readOnly}
                    onChange={(e) => handleItemChange(selectedItem, 'audit_findings', e.target.value)}
                    style={{ borderRadius: 4 }}
                  />
                </div>
              )}

              {selectedItem.rectification_suggestion && (
                <div style={{ marginBottom: 14 }}>
                  <div style={{ marginBottom: 6, fontWeight: 500, fontSize: 13, color: '#334155' }}>
                    整改要求与建议
                  </div>
                  <TextArea
                    rows={2}
                    placeholder="请描述整改建议"
                    value={selectedItem.rectification_suggestion || ''}
                    readOnly={readOnly}
                    onChange={(e) => handleItemChange(selectedItem, 'rectification_suggestion', e.target.value)}
                    style={{ borderRadius: 4 }}
                  />
                </div>
              )}

              <div style={{ marginBottom: 14 }}>
                <div style={{ marginBottom: 6, fontWeight: 500, fontSize: 13, color: '#334155' }}>审核员记录</div>
                <TextArea
                  rows={2}
                  placeholder="请输入现场记录与备注"
                  value={selectedItem.inspector_note || ''}
                  readOnly={readOnly}
                  onChange={(e) => handleItemChange(selectedItem, 'inspector_note', e.target.value)}
                  style={{ borderRadius: 4 }}
                />
              </div>

              {/* 现场照片 */}
              {(selectedItem.allow_attachment || selectedItem.attachment_required || (selectedItem.photos && selectedItem.photos.length > 0)) && (
                <div>
                  <div style={{ marginBottom: 6, fontWeight: 500, fontSize: 13, color: '#334155' }}>
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
                  {selectedItem.photos && selectedItem.photos.length > 0 ? (
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
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
                  ) : (
                    <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>暂无现场照片</div>
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
