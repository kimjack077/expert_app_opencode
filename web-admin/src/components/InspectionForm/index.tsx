import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Card, Button, Input, Space, Tag, Spin, message,
  Progress, Upload, Drawer, Radio, InputNumber, Select, Alert, Modal,
  Row, Col, Statistic, Divider, Tooltip
} from 'antd'
import {
  ArrowLeftOutlined, CheckCircleOutlined, CloseCircleOutlined,
  BulbOutlined, CameraOutlined,
  LoadingOutlined, SaveOutlined, SendOutlined, InfoCircleOutlined,
  SafetyCertificateOutlined, RobotOutlined, ExclamationCircleOutlined
} from '@ant-design/icons'
import { recordApi, llmApi, mediaApi, taskApi, templateApi } from '@/services/api'
import { resultTagColor, resolveOptionLabel, resultLabel } from '@/utils/display'
import { classifyItem, countBuckets } from '@/utils/completion'
import { useAuthStore } from '@/stores/auth'

const { TextArea } = Input

/**
 * 检查项步骤条的完成态样式与标记。
 *
 * 语义：**标记表示「已完成」，颜色表示结论性质**（与 H5 现场端一致 ——
 * H5 对任何已完成项都显示 success 图标，由状态类着色）。
 *
 * 修复背景：数值型/描述型项填了内容后，原实现落到 `isPass/isFail/isNa` 三者皆否的
 * 空档，被渲染成「·」且无任何完成态底色 —— 录入完成却看起来像漏填，
 * 演示现场极易被误读为未完成。
 *
 * 配色**必须放在 index.css**（`.ant-btn.efis-step-*`）：全局 `.ant-btn-default`
 * 的 border/color/background 都带 `!important`，内联样式覆盖不了，
 * 写成内联等于没写。
 */
const STEP_MARK: Record<string, { cls: string; mark: string }> = {
  pass: { cls: 'efis-step-pass', mark: ' ✓' },
  fail: { cls: 'efis-step-fail', mark: ' ✕' },
  na: { cls: 'efis-step-na', mark: ' ✓' },
  // 其他项（数值 / 描述 / 打分 / 观察项 / 待整改）：蓝色 ✓ 表示「已填写，非三级判定」
  other: { cls: 'efis-step-other', mark: ' ✓' },
}

interface InspectionFormProps {
  /** 返回路径 */
  backPath?: string
  /** 完成后的回调 */
  onComplete?: () => void
}

/**
 * 统一的检查表单组件
 * 支持两种模式：
 * 1. 检查记录 ID：读写 /api/records（独立快速检查）
 * 2. 任务 ID：读写 /api/tasks/{id}/records（任务检查，与审核计划共用）
 */
export default function InspectionForm({ backPath = '/records', onComplete }: InspectionFormProps) {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const { token } = useAuthStore()
  const [record, setRecord] = useState<any>(null)
  const [loadError, setLoadError] = useState<'' | 'not_found' | 'failed'>('')
  const [items, setItems] = useState<any[]>([])
  const [flatItems, setFlatItems] = useState<any[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [llmLoading, setLlmLoading] = useState(false)
  const [llmContent, setLlmContent] = useState<string | null>(null)
  const [drawerVisible, setDrawerVisible] = useState(false)
  const [availableTemplates, setAvailableTemplates] = useState<any[]>([])
  const [selectedTemplateIdForBind, setSelectedTemplateIdForBind] = useState<string | undefined>()
  const [bindingTemplate, setBindingTemplate] = useState(false)

  // 模板下拉只在「任务未关联模板」的空态卡片里用到。
  // 原实现在组件挂载时就无条件拉一次模板列表：检查表单每次打开都要多付
  // 一次串行请求（远程库时代约 100~300ms），而 99% 的任务并不需要它。
  // 改为空态出现后再懒加载，正常检查流程少一次请求。
  const [templatesLoaded, setTemplatesLoaded] = useState(false)
  useEffect(() => {
    if (flatItems.length > 0 || templatesLoaded) return
    setTemplatesLoaded(true)
    templateApi.getTemplates({ limit: 100 }).then((res: any) => {
      const list = res.data?.items || res.data || []
      setAvailableTemplates(list)
      if (list.length > 0) {
        setSelectedTemplateIdForBind(list[0].id)
      }
    }).catch((err: any) => console.error('加载模板列表失败:', err))
  }, [flatItems.length, templatesLoaded])

  const handleBindTemplateAndGenerate = async () => {
    if (!selectedTemplateIdForBind) {
      message.warning('请先选择检查模板')
      return
    }
    const currentTaskId = taskId || id
    if (!currentTaskId) {
      message.error('无法获取任务ID')
      return
    }
    setBindingTemplate(true)
    try {
      await taskApi.updateTask(currentTaskId, { template_id: selectedTemplateIdForBind })
      message.success('已成功绑定检查模板并自动生成检查项！')
      await fetchData()
    } catch (err: any) {
      message.error(err.response?.data?.message || err.response?.data?.detail || '绑定模板失败')
    } finally {
      setBindingTemplate(false)
    }
  }

  const [finalJudgment, setFinalJudgment] = useState({
    result: '',
    remarks: ''
  })
  const [savingJudgment, setSavingJudgment] = useState(false)
  const [aiJudgmentLoading, setAiJudgmentLoading] = useState(false)
  const [aiJudgmentThinking, setAiJudgmentThinking] = useState(false)
  const [aiJudgmentThinkingContent, setAiJudgmentThinkingContent] = useState('')
  const [aiJudgmentResult, setAiJudgmentResult] = useState('')
  const [aiJudgmentResultType, setAiJudgmentResultType] = useState('')

  // record = 独立检查记录；task = 任务明细（task_item_records）
  const [executionMode, setExecutionMode] = useState<'record' | 'task'>('record')
  const [actualRecordId, setActualRecordId] = useState<string | null>(null)
  const [taskId, setTaskId] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
  }, [id])

  const flattenItems = (list: any[], result: any[] = []): any[] => {
    for (const item of list) {
      if (!item.is_category) {
        result.push(item)
      }
      if (item.children && item.children.length > 0) {
        flattenItems(item.children, result)
      }
    }
    return result
  }

  /** 将任务检查项映射为表单项（与 H5 task 模式一致） */
  const mapTaskRecordsToFormItems = (taskRecords: any[]) => {
    return (taskRecords || [])
      .filter((tr) => {
        const meta = tr.template_item || tr.check_item
        return !meta?.is_category
      })
      .map((tr) => {
        const meta = tr.template_item || tr.check_item || {}
        const checkType = meta.check_type || meta.result_type || 'radio'
        const result = tr.result || ''
        return {
          id: tr.id,
          template_item_id: tr.template_item_id || meta.id,
          title: meta.title || '未命名检查项',
          description: meta.description,
          check_method: meta.check_method,
          legal_basis: meta.legal_basis,
          result_type: meta.result_type || (checkType === 'radio' ? 'pass_fail' : checkType),
          check_type: checkType,
          result_options: meta.result_options,
          is_required: meta.is_required !== false,
          attachment_required: !!meta.attachment_required,
          allow_attachment: meta.allow_attachment !== false,
          unit: meta.unit,
          min_value: meta.min_value,
          max_value: meta.max_value,
          max_score: meta.max_score,
          score_step: meta.score_step,
          pass_score: meta.pass_score,
          // task_item_records 用 result 存判定；表单用 radio_value 展示
          radio_value: result || '',
          result,
          numeric_value: tr.result_value ?? '',
          score_value: tr.result_value ?? '',
          text_value: tr.result_text || '',
          inspector_note: tr.inspector_note || '',
          // 附件由后端随记录返回（media_files），不能写死为空数组，
          // 否则上传后再次进入本页附件会全部消失。
          photos: tr.photos || [],
          llm_suggestion: tr.llm_suggestion,
        }
      })
  }

  /** 判定结果 → 中文（写库一律用中文，避免英文枚举回显到备注） */
  const verdictToCn = (result: string) =>
    result === 'pass' ? '合格'
      : result === 'fail' ? '不合格'
        : result === 'partial_pass' ? '基本合格'
          : result

  /**
   * 任务模式下「最终判定 + 判定说明」共用 inspection_tasks.remarks 一个字段存储。
   * 这里统一生成带标记的文本，读取侧按同一套标记解析，
   * 避免把任务备注原文误当成判定说明回显。
   */
  const buildTaskRemark = (result: string, remarks: string) => {
    // 先剥离已有的「判定说明:」前缀（可能多层累加），避免重复累加
    const cleanRemarks = remarks.replace(/^(判定说明\s*[:：]\s*)+/gi, '').trim()
    return [
      result ? `最终判定:${verdictToCn(result)}` : '',
      cleanRemarks ? `判定说明:${cleanRemarks}` : '',
    ]
      .filter(Boolean)
      .join(' | ')
  }

  /** 从任务备注中解析出「最终判定 + 判定说明」；无标记时返回 null（不回填） */
  const parseTaskRemark = (raw: string) => {
    const match = raw.match(
      /最终判定\s*[:：]\s*(pass|fail|partial_pass|合格|不合格|基本合格|符合|不符合)/i
    )
    if (!match) return null
    const val = match[1].toLowerCase()
    const result =
      val === 'pass' || val === '合格' || val === '符合'
        ? 'pass'
        : val === 'fail' || val === '不合格' || val === '不符合'
          ? 'fail'
          : 'partial_pass'
    const remarks = raw
      .replace(/^最终判定\s*[:：]\s*[^|｜]+[|｜]?/i, '')
      .replace(/^判定说明\s*[:：]\s*/i, '')
      .trim()
    return { result, remarks }
  }

  const loadTaskMode = async (task: any) => {
    setExecutionMode('task')
    setTaskId(String(task.id))
    setActualRecordId(null)

    if (task.status === 'pending') {
      try {
        await taskApi.startTask(task.id)
        task = { ...task, status: 'in_progress' }
      } catch (e) {
        console.warn('自动开始任务失败，继续加载', e)
      }
    }

    // 检查项加载失败不应让整页判死：任务基本信息仍然可展示，
    // 否则 setRecord 不会执行，页面会退化成误导性的"检查记录不存在"。
    let taskRecords: any[] = []
    try {
      const recordsRes: any = await taskApi.getTaskRecords(task.id)
      taskRecords = recordsRes.data || []
    } catch (e) {
      console.error('加载任务检查项失败:', e)
      message.error('检查项加载失败，请刷新重试')
    }
    const formItems = mapTaskRecordsToFormItems(taskRecords)

    setRecord({
      id: task.id,
      enterprise_name: task.target_name,
      enterprise_address: task.target_address,
      contact_person: task.target_contact,
      contact_phone: task.target_phone,
      remarks: task.remarks,
      status: task.status === 'completed' ? 'submitted' : 'draft',
      task_status: task.status,
      template: { name: task.title || '检查任务' },
      mode: 'task',
    })
    setItems(formItems)
    setFlatItems(formItems)
    if (task.remarks) {
      // 只在能识别出「最终判定:」标记时回填判定说明。
      // 否则任务备注原文会被整段灌进「判定说明」输入框（历史 bug）。
      const parsed = parseTaskRemark(task.remarks)
      if (parsed) {
        setFinalJudgment(parsed)
      }
    }
  }

  const fetchData = async () => {
    if (!id) {
      setLoadError('not_found')
      setLoading(false)
      return
    }
    setLoading(true)
    setLoadError('')
    // 只有「任务确实不存在」（404）才叫"记录不存在"；
    // 接口报错 / 无权限 / 网络异常都属于"加载失败"，两者必须分开提示，
    // 否则用户会误以为数据被删了（原实现一律显示"检查记录不存在"）。
    let notFound = false
    try {
      // 0) 同一路径既可能是独立检查记录 ID，也可能是任务 ID。
      // 原实现先试 /records，404 后再试 /tasks —— 任务场景下每次打开表单都
      // 固定多一次往返（远程库约 100~300ms）。两个 GET 互不影响，并发发出、
      // 按"记录优先"的顺序取用，失败分支的语义保持不变。
      const [recordResult, taskResult] = await Promise.allSettled([
        recordApi.getRecord(id),
        taskApi.getTask(id),
      ])

      // 1) 优先按独立检查记录加载
      if (recordResult.status === 'fulfilled') {
        const res: any = recordResult.value
        if (res?.code === 200 && res.data) {
          setExecutionMode('record')
          setTaskId(null)
          setActualRecordId(id)
          setRecord(res.data)
          const templateItems = res.data?.template?.items || []
          setItems(templateItems)
          setFlatItems(flattenItems(templateItems))
          if (res.data?.overall_result) {
            setFinalJudgment((prev) => ({ ...prev, result: res.data.overall_result }))
          }
          if (res.data?.judgment_note) {
            // 「判定说明」与「检查备注」是两个字段：这里必须读 judgment_note。
            // 读 remarks 会把「新建检查任务时填的备注」灌进判定说明输入框。
            setFinalJudgment((prev) => ({ ...prev, remarks: res.data.judgment_note }))
          }
          return
        }
      }

      // 2) 按任务加载：直接读写 task_item_records，禁止另建独立检查记录
      if (taskResult.status === 'fulfilled') {
        const taskRes: any = taskResult.value
        if (taskRes?.code === 200 && taskRes.data) {
          await loadTaskMode(taskRes.data)
          return
        }
      } else {
        console.error('Failed to load task inspection:', taskResult.reason)
        if ((taskResult.reason as any)?.response?.status === 404) notFound = true
      }

      setLoadError(notFound ? 'not_found' : 'failed')
    } catch (error: any) {
      console.error('Failed to fetch data:', error)
      setLoadError('failed')
    } finally {
      setLoading(false)
    }
  }

  const currentItem = flatItems[currentIndex]
  const recordId = actualRecordId || (executionMode === 'record' ? record?.id : null)
  const isTaskMode = executionMode === 'task'
  const isCompleted = record?.status === 'submitted' || record?.task_status === 'completed'

  /**
   * 「该项是否已完成」—— 进度条、步骤条、提交前校验共用同一判据。
   *
   * = 已填写（`classifyItem` 非 unfilled）且必传附件已上传。
   * 此前本文件有 3 处各自手写 `hasResult`，口径略有出入（如漏判 multi_value），
   * 收敛到一处，避免改了一处漏两处。
   */
  const isItemDone = (item: any): boolean => {
    if (classifyItem(item) === 'unfilled') return false
    return !item.attachment_required || (item.photos && item.photos.length > 0)
  }

  const buildTaskItemPayload = (item: any, field: string, value: any) => {
    const valueToSend =
      (field === 'numeric_value' || field === 'score_value') && typeof value === 'number'
        ? String(value)
        : value
    const payload: any = {}
    if (field === 'radio_value') {
      payload.result = valueToSend
    } else if (field === 'score_value' || field === 'numeric_value') {
      payload.result_value = valueToSend == null ? null : String(valueToSend)
      // BUG-11：数值/打分项按阈值自动判定；未配置阈值时不写 result，
      // 该类项在统计口径中归入「其他项」，避免虚增合规率。
      if (!item.radio_value && !item.result) {
        const numVal = Number(valueToSend)
        if (valueToSend !== null && valueToSend !== '' && !Number.isNaN(numVal)) {
          if (field === 'score_value') {
            if (item.pass_score !== null && item.pass_score !== undefined) {
              payload.result = numVal >= Number(item.pass_score) ? 'pass' : 'fail'
            }
          } else {
            const hasMin = item.min_value !== null && item.min_value !== undefined
            const hasMax = item.max_value !== null && item.max_value !== undefined
            if (hasMin || hasMax) {
              const inRange = (!hasMin || numVal >= Number(item.min_value))
                && (!hasMax || numVal <= Number(item.max_value))
              payload.result = inRange ? 'pass' : 'fail'
            }
          }
        }
      }
    } else if (field === 'text_value') {
      payload.result_text = valueToSend
    } else if (field === 'inspector_note') {
      payload.inspector_note = valueToSend
    } else if (field === 'multi_value') {
      payload.result_text = Array.isArray(valueToSend) ? valueToSend.join(',') : valueToSend
    } else {
      payload[field] = valueToSend
    }
    return { payload, valueToSend }
  }

  const handleResultChange = async (field: string, value: any) => {
    if (!currentItem) return
    setSaving(true)
    try {
      if (isTaskMode) {
        if (!taskId) return
        const { payload, valueToSend } = buildTaskItemPayload(currentItem, field, value)
        let res: any
        if (currentItem.id) {
          res = await taskApi.updateRecord(currentItem.id, payload)
        } else {
          res = await taskApi.createRecord(taskId, {
            template_item_id: currentItem.template_item_id,
            ...payload,
          })
        }
        const updatedItems = flatItems.map((item, idx) => {
          if (idx !== currentIndex) return item
          const next = {
            ...item,
            [field]: valueToSend,
            id: res.data?.id || item.id,
          }
          if (field === 'radio_value') next.result = valueToSend
          if (field === 'score_value' || field === 'numeric_value') next.result_value = valueToSend
          if (field === 'text_value') next.result_text = valueToSend
          return next
        })
        setFlatItems(updatedItems)
        message.success('已保存')
        return
      }

      if (!recordId) return
      const valueToSend =
        (field === 'numeric_value' || field === 'score_value') && typeof value === 'number'
          ? String(value)
          : value
      const res: any = await recordApi.createRecordItem(recordId, {
        template_item_id: currentItem.template_item_id || currentItem.id,
        [field]: valueToSend,
      })
      const updatedItems = flatItems.map((item, idx) => {
        if (idx === currentIndex) {
          return { ...item, [field]: valueToSend, id: res.data?.id || item.id }
        }
        return item
      })
      setFlatItems(updatedItems)
      message.success('已保存')
    } catch (error) {
      message.error((error as any)?.response?.data?.detail || (error as any)?.response?.data?.message || (error as any)?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleLLMRequest = async () => {
    if (!currentItem) return
    const llmTaskId = isTaskMode ? taskId : recordId
    if (!llmTaskId || !currentItem.id || currentItem.id === currentItem.template_item_id) {
      setLlmContent('请先填写检查结果后再获取AI建议')
      setDrawerVisible(true)
      return
    }
    setLlmLoading(true)
    setDrawerVisible(true)
    try {
      const res: any = await llmApi.getSuggestion({
        task_id: String(llmTaskId),
        record_id: currentItem.id,
        use_cache: false,
      })
      setLlmContent(res.data?.content || '暂无内容')
    } catch (error) {
      setLlmContent('获取失败，请稍后重试')
    } finally {
      setLlmLoading(false)
    }
  }

  // 采纳AI建议 - 填入审核记录
  const handleAcceptAISuggestion = async () => {
    if (!currentItem || !llmContent) return

    const updatedItems = flatItems.map((item, idx) => {
      if (idx === currentIndex) {
        return { ...item, inspector_note: llmContent }
      }
      return item
    })
    setFlatItems(updatedItems)

    try {
      if (isTaskMode) {
        if (currentItem.id) {
          await taskApi.updateRecord(currentItem.id, { inspector_note: llmContent })
        } else if (taskId) {
          await taskApi.createRecord(taskId, {
            template_item_id: currentItem.template_item_id,
            inspector_note: llmContent,
          })
        }
      } else if (recordId) {
        await recordApi.createRecordItem(recordId, {
          template_item_id: currentItem.template_item_id || currentItem.id,
          inspector_note: llmContent,
        })
      }
      message.success('已采纳AI建议')
    } catch (error) {
      message.error((error as any)?.response?.data?.detail || (error as any)?.response?.data?.message || (error as any)?.message || '保存失败')
    }

    setDrawerVisible(false)
    setLlmContent(null)
  }

  // 保存最终判定
  const handleSaveFinalJudgment = async () => {
    setSavingJudgment(true)
    try {
      if (isTaskMode && taskId) {
        await taskApi.updateTask(taskId, {
          remarks: buildTaskRemark(finalJudgment.result, finalJudgment.remarks),
        })
        message.success('最终判定已保存')
        return
      }
      if (!recordId) return
      await recordApi.updateRecord(recordId, {
        overall_result: finalJudgment.result,
        judgment_note: finalJudgment.remarks,
      })
      message.success('最终判定已保存')
    } catch (error: any) {
      const msg = error?.response?.data?.detail || error?.message || '保存失败'
      message.error(typeof msg === 'string' ? msg : '保存失败')
    } finally {
      setSavingJudgment(false)
    }
  }

  // AI生成最终判定
  const handleGenerateAIJudgment = async () => {
    if (!token) return
    const streamId = isTaskMode ? taskId : recordId
    if (!streamId) return
    setAiJudgmentLoading(true)
    setAiJudgmentThinking(true)
    setAiJudgmentThinkingContent('')
    setAiJudgmentResult('')
    setAiJudgmentResultType('')

    try {
      // 注意：不能用 'http://localhost:8000' 作 fallback。
      // 生产 .env.production 中 VITE_API_URL 为空，nginx 已在 3000/5173 端口反代
      // /api 到 127.0.0.1:8000；fetch 用空字符串会拼成相对路径 '/api/...'，
      // 由浏览器自动走同源 nginx 反代。若误指 localhost:8000，
      // 浏览器会把 SSE 发到用户本机，连不上后端 → 「AI生成失败，请稍后重试」，
      // 且后端日志完全无记录，难以定位（2026-09-19 实测）。
      const API_URL = import.meta.env.VITE_API_URL || ''
      const streamPath = isTaskMode
        ? `/api/tasks/${streamId}/final-judgment-stream`
        : `/api/records/${streamId}/final-judgment-stream`

      const response = await fetch(`${API_URL}${streamPath}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream',
        },
      })

      if (!response.ok) {
        throw new Error('请求失败')
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('无法读取响应')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              if (data.type === 'thinking') {
                setAiJudgmentThinkingContent(prev => prev + data.content)
              } else if (data.type === 'done') {
                setAiJudgmentResult(data.content)
                setAiJudgmentResultType(data.result || '')
                setAiJudgmentThinking(false)
                if (data.result) {
                  setFinalJudgment(prev => ({ ...prev, result: data.result }))
                }
              } else if (data.type === 'error') {
                message.error('AI 生成失败: ' + data.content)
                setAiJudgmentThinking(false)
              }
            } catch (e) {
              console.error('解析数据失败:', e)
            }
          }
        }
      }
    } catch (error) {
      console.error('AI生成失败:', error)
      message.error('AI生成失败，请稍后重试')
      setAiJudgmentThinking(false)
    } finally {
      setAiJudgmentLoading(false)
    }
  }

  // 采纳AI判定
  const handleAcceptAIJudgment = () => {
    if (aiJudgmentResultType) {
      setFinalJudgment(prev => ({ ...prev, result: aiJudgmentResultType }))
    }
    if (aiJudgmentResult) {
      setFinalJudgment(prev => ({ ...prev, remarks: aiJudgmentResult }))
    }
    message.success('已采纳AI建议')
  }

  // 清除AI判定
  const handleClearAIJudgment = () => {
    setAiJudgmentThinkingContent('')
    setAiJudgmentResult('')
    setAiJudgmentResultType('')
  }

  const handleSubmit = async () => {
    if (!isTaskMode && !recordId) return
    if (isTaskMode && !taskId) return

    // 校验必填项和必传附件
    const incompleteItems: string[] = []
    const missingAttachments: string[] = []

    flatItems.forEach((item, index) => {
      if (item.is_required !== false) {
        if (!isItemDone(item)) {
          incompleteItems.push(`第${index + 1}项: ${item.title || '未命名'}`)
        }
      }

      if (item.attachment_required) {
        const hasPhotos = item.photos && item.photos.length > 0
        if (!hasPhotos) {
          missingAttachments.push(`第${index + 1}项: ${item.title || '未命名'}`)
        }
      }
    })

    if (incompleteItems.length > 0 || missingAttachments.length > 0) {
      Modal.error({
        title: isCompleted ? '保存失败' : '提交失败',
        width: 520,
        content: (
          <div>
            {incompleteItems.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontWeight: 500, marginBottom: 4, color: '#ff4d4f' }}>
                  以下必填项未完成：
                </div>
                <ul style={{ margin: 0, paddingLeft: 20, color: '#666' }}>
                  {incompleteItems.slice(0, 10).map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                  {incompleteItems.length > 10 && <li>...还有 {incompleteItems.length - 10} 项</li>}
                </ul>
              </div>
            )}
            {missingAttachments.length > 0 && (
              <div>
                <div style={{ fontWeight: 500, marginBottom: 4, color: '#faad14' }}>
                  以下检查项需要上传照片：
                </div>
                <ul style={{ margin: 0, paddingLeft: 20, color: '#666' }}>
                  {missingAttachments.slice(0, 10).map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                  {missingAttachments.length > 10 && <li>...还有 {missingAttachments.length - 10} 项</li>}
                </ul>
              </div>
            )}
          </div>
        ),
      })
      return
    }

    // 最终判定为必填项：任务模式同样不能空着提交，
    // 否则会落库一条没有结论的「已完成」检查。
    if (!finalJudgment.result) {
      Modal.error({
        title: '提交失败',
        content: '请先选择最终判定结果（合格/基本合格/不合格）',
      })
      return
    }

    const alreadyDone = isCompleted
    Modal.confirm({
      title: alreadyDone ? '确认保存修改' : '确认提交',
      width: 480,
      content: (
        <div>
          <div style={{ marginBottom: 12 }}>检查结果汇总：</div>
          <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
            <span>✅ 合格：{passCount} 项</span>
            {failCount > 0 && <span style={{ color: '#ff4d4f' }}>❌ 不合格：{failCount} 项</span>}
            {otherCount > 0 && (
              <span style={{ color: '#0958d9' }}>🔵 其他（数值/描述等）：{otherCount} 项</span>
            )}
            {notApplicableCount > 0 && (
              <span style={{ color: '#999' }}>⚪ 不适用：{notApplicableCount} 项</span>
            )}
            {unfilledCount > 0 && (
              <span style={{ color: '#faad14' }}>🟡 未填写：{unfilledCount} 项</span>
            )}
            <span style={{ color: '#666' }}>共计：{flatItems.length} 项</span>
          </div>
          {finalJudgment.result && (
            <div style={{ marginBottom: 8 }}>
              <strong>最终判定：</strong>
              <Tag
                color={
                  finalJudgment.result === 'pass'
                    ? 'success'
                    : finalJudgment.result === 'partial_pass'
                      ? 'warning'
                      : 'error'
                }
              >
                {finalJudgment.result === 'pass'
                  ? '合格'
                  : finalJudgment.result === 'partial_pass'
                    ? '基本合格'
                    : '不合格'}
              </Tag>
            </div>
          )}
          <div style={{ color: '#999', fontSize: 12 }}>
            {alreadyDone
              ? '将保存您对检查结果的修改，可随时再次调整。'
              : isTaskMode
                ? '提交后任务将标记为已完成，之后仍可打开本页查看并修改结果。'
                : '提交后将无法修改，确定要提交吗？'}
          </div>
        </div>
      ),
      onOk: async () => {
        try {
          if (isTaskMode && taskId) {
            // 判定结论一律写中文，避免 pass/fail 等英文枚举落库并回显到备注里
            const remarkText = buildTaskRemark(finalJudgment.result, finalJudgment.remarks)
            if (remarkText) {
              await taskApi.updateTask(taskId, { remarks: remarkText })
            }
            if (!alreadyDone) {
              await taskApi.completeTask(taskId)
            }
            message.success(alreadyDone ? '检查结果已保存' : '检查任务已完成')
            setRecord((prev: any) =>
              prev
                ? {
                    ...prev,
                    status: 'submitted',
                    task_status: 'completed',
                    remarks: remarkText || prev.remarks,
                  }
                : prev
            )
            if (onComplete) onComplete()
            else if (!alreadyDone) navigate(backPath)
            return
          }

          await recordApi.updateRecord(recordId, {
            overall_result: finalJudgment.result,
            judgment_note: finalJudgment.remarks,
          })
          await recordApi.submitRecord(recordId)
          message.success('检查记录已提交')
          if (onComplete) onComplete()
          else navigate(backPath)
        } catch (error: any) {
          // 后端提交校验会返回具体原因（未填结论 / 必填检查项未填），必须透传给用户，
          // 否则用户只看到「提交失败」，不知道该补什么。
          const detail = error?.response?.data?.detail || error?.response?.data?.message
          message.error(
            typeof detail === 'string' && detail
              ? detail
              : alreadyDone
                ? '保存失败'
                : '提交失败'
          )
        }
      },
    })
  }

  const handleUpload = async (uploadInfo: any) => {
    const file = uploadInfo.file as File
    if (!currentItem) return
    try {
      const uploadOpts = isTaskMode
        ? { task_id: taskId || undefined, record_id: currentItem.id }
        : { record_id: currentItem.id || recordId || undefined }
      const res: any = await mediaApi.upload(file, uploadOpts)
      const photoUrl = res.data?.file_path
      if (photoUrl) {
        const currentPhotos = currentItem.photos || []
        const updatedPhotos = [...currentPhotos, photoUrl]
        const updatedItems = flatItems.map((item, idx) => {
          if (idx === currentIndex) {
            return { ...item, photos: updatedPhotos }
          }
          return item
        })
        setFlatItems(updatedItems)
        if (!isTaskMode && recordId) {
          await recordApi.createRecordItem(recordId, {
            template_item_id: currentItem.template_item_id || currentItem.id,
            photos: updatedPhotos,
          })
        }
      }
      message.success('上传成功')
      if (uploadInfo.onSuccess) uploadInfo.onSuccess({}, uploadInfo.file)
    } catch (error: any) {
      const msg = error?.response?.data?.detail || error?.response?.data?.message || error?.message || '上传失败'
      message.error(typeof msg === 'string' ? msg : '上传失败')
      if (uploadInfo.onError) uploadInfo.onError(error)
    }
  }

  // 计算完成进度
  const completedCount = flatItems.filter(isItemDone).length
  const progress = flatItems.length > 0 ? Math.round((completedCount / flatItems.length) * 100) : 0

  // 统计各项数量 —— 统一走 classifyItem 分档，保证
  // 「合格 + 不合格 + 不适用 + 其他 === 总检查项」的加法闭合。
  // 历史上这里只数三级判定，数值型/描述型项填了内容却不进任何一档，
  // 于是汇总卡出现「3 + 0 + 0 = 3 ≠ 总 4」的假象。
  const bucketCounts = countBuckets(flatItems)
  const passCount = bucketCounts.pass
  const failCount = bucketCounts.fail
  const notApplicableCount = bucketCounts.na
  // 其他项：数值型 / 描述型 / 打分型，以及观察项、待整改等中间态
  const otherCount = bucketCounts.other
  const unfilledCount = bucketCounts.unfilled

  // 任务模式：完成进度满即可提交/保存；记录模式：草稿 + 最终判定
  const canSubmit = isTaskMode
    ? progress === 100
    : progress === 100 && !!finalJudgment.result && record?.status === 'draft'

  const hasValue = (v: any) => v !== undefined && v !== null && v !== ''

  const getResultTag = (item: any) => {
    if (item.radio_value) {
      // 统一走公共映射，避免 observe / not_applicable 这类值直接以英文显示
      return (
        <Tag color={resultTagColor(item.radio_value)}>
          {resolveOptionLabel(item.radio_value, item.result_options)}
        </Tag>
      )
    }
    // 注意：numeric_value / score_value 在未填写时可能是空字符串，
    // 只判 undefined/null 会渲染出一个内容为空的标签。
    if (hasValue(item.numeric_value)) {
      return <Tag color="processing">{item.numeric_value} {item.unit || ''}</Tag>
    }
    if (hasValue(item.score_value)) {
      return <Tag color="processing">{item.score_value} 分</Tag>
    }
    if (item.text_value) {
      return <Tag color="default">已填写</Tag>
    }
    return <Tag>未填写</Tag>
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!record) {
    const notFound = loadError === 'not_found'
    return (
      <div style={{ padding: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(backPath)}>返回</Button>
        <div style={{ marginTop: 24, textAlign: 'center' }}>
          <div
            style={{
              fontSize: 15,
              color: notFound ? 'var(--text-muted)' : '#d4380d',
              marginBottom: 16,
            }}
          >
            {notFound ? '检查记录不存在' : '检查数据加载失败，请重试'}
          </div>
          {!notFound && (
            <Button type="primary" onClick={fetchData}>重新加载</Button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div style={{ background: '#f0f2f5', minHeight: '100vh' }}>
      {/* 顶部导航栏 */}
      <div style={{ background: '#fff', padding: '16px 24px', marginBottom: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(backPath)}>
              返回
            </Button>
            <span style={{ fontSize: 18, fontWeight: 600 }}>{record.enterprise_name}</span>
            <Tag color="blue">{record.template?.name}</Tag>
            <Tag color={isCompleted ? 'success' : 'warning'}>
              {isCompleted ? (isTaskMode ? '已完成（可修改）' : '已检查') : isTaskMode ? '进行中' : '草稿'}
            </Tag>
            {isTaskMode && <Tag color="processing">任务检查</Tag>}
          </Space>
          <Progress
            percent={progress}
            status={progress === 100 ? 'success' : 'active'}
            style={{ width: 200 }}
            format={() => `${completedCount}/${flatItems.length}`}
          />
        </div>
      </div>

      <div style={{ padding: '0 24px', maxWidth: 1200, margin: '0 auto' }}>
        {flatItems.length === 0 ? (
          <Card style={{ marginBottom: 16, textAlign: 'center', padding: '40px 20px', borderRadius: 8 }}>
            <div style={{ maxWidth: 600, margin: '0 auto' }}>
              <ExclamationCircleOutlined style={{ fontSize: 52, color: '#faad14', marginBottom: 16 }} />
              <h2 style={{ fontSize: 20, fontWeight: 600, color: '#1e293b', marginBottom: 12 }}>
                当前任务未关联模板（暂无检查项）
              </h2>
              <p style={{ color: '#64748b', fontSize: 14, lineHeight: 1.6, marginBottom: 24 }}>
                该审核计划项制定时未选定检查模板，导致当前无检查条目可执行。您可以直接在下方选择合适的检查模板并绑定，系统将自动载入全部检查项：
              </p>

              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <Select
                  placeholder="请选择要绑定的检查模板..."
                  style={{ width: 340, textAlign: 'left' }}
                  value={selectedTemplateIdForBind}
                  onChange={(val) => setSelectedTemplateIdForBind(val)}
                  options={availableTemplates.map((t) => ({
                    value: t.id,
                    label: `${t.name} (${t.item_count || t.items?.length || 0}项)`,
                  }))}
                />
                <Button
                  type="primary"
                  loading={bindingTemplate}
                  disabled={!selectedTemplateIdForBind}
                  onClick={handleBindTemplateAndGenerate}
                >
                  绑定模板并生成检查项
                </Button>
              </div>

              <div style={{ marginTop: 24 }}>
                <Button onClick={() => navigate(backPath || '/tasks')}>
                  返回上一页
                </Button>
              </div>
            </div>
          </Card>
        ) : (
          <>
            {/* 检查项快捷导航 */}
        <Card style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {flatItems.map((item, idx) => {
              const isDone = isItemDone(item)
              const isCur = idx === currentIndex
              // 分档统一走 classifyItem：数值型/描述型/观察项/待整改都归入 other，
              // 不再落到「既非合格也非不合格」的空档而被渲染成「·」。
              const bucket = classifyItem(item)
              const preset = isDone ? STEP_MARK[bucket] : undefined

              return (
                <Button
                  key={item.id}
                  size="small"
                  type={isCur ? 'primary' : 'default'}
                  className={!isCur && preset ? preset.cls : undefined}
                  onClick={() => setCurrentIndex(idx)}
                  style={{ marginBottom: 4 }}
                >
                  {idx + 1}
                  {preset ? preset.mark : ''}
                </Button>
              )
            })}
          </div>
        </Card>

        {/* 当前检查项 */}
        {currentItem && (
          <Card
            title={
              <Space>
                <span>检查条目 {currentIndex + 1}/{flatItems.length}</span>
                {getResultTag(currentItem)}
              </Space>
            }
            extra={
              <Space>
                <Button
                  icon={<BulbOutlined />}
                  onClick={handleLLMRequest}
                  style={{ background: '#faad14', borderColor: '#faad14', color: '#fff' }}
                >
                  AI审核建议
                </Button>
              </Space>
            }
          >
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ fontSize: 18, marginBottom: 8 }}>
                {currentItem.title}
                {currentItem.is_required !== false && (
                  <span style={{ color: '#ff4d4f', marginLeft: 4 }}>*</span>
                )}
              </h3>
              {currentItem.description && (
                <p style={{ color: '#666', marginBottom: 8 }}>{currentItem.description}</p>
              )}
              {currentItem.check_method && (
                <p style={{ color: '#1890ff', fontSize: 13 }}>
                  <strong>检查方法：</strong>{currentItem.check_method}
                </p>
              )}
              {currentItem.legal_basis && (
                <p style={{ color: '#52c41a', fontSize: 13 }}>
                  <strong>法律依据：</strong>{currentItem.legal_basis}
                </p>
              )}
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>检查结果</div>

              {(currentItem.result_type === 'pass_fail' ||
                currentItem.check_type === 'radio' ||
                (!currentItem.result_type && !currentItem.check_type)) && (
                <Space>
                  <Radio.Group
                    value={currentItem.radio_value}
                    onChange={(e) => handleResultChange('radio_value', e.target.value)}
                    buttonStyle="solid"
                    size="large"
                  >
                    {(currentItem.result_options?.options || currentItem.result_options || [
                      { value: 'pass', label: '合格' },
                      { value: 'fail', label: '不合格' },
                      { value: 'not_applicable', label: '不适用' },
                    ]).map((opt: any) => {
                      // 选项没配 label 时回落到统一中文映射，避免把 value 直接显示成英文
                      const label = opt.label
                        ? (opt.label === '未涉及' ? '不适用' : opt.label)
                        : resultLabel(opt.value)
                      return (
                        <Radio.Button key={opt.value || opt.label} value={opt.value}>
                          {label}
                        </Radio.Button>
                      )
                    })}
                  </Radio.Group>
                  <Tooltip title="「不适用」表示被检查对象不涉及该条款要求，不计入不合格，不触发整改，不纳入合规率分母">
                    <span style={{ fontSize: 12, color: '#8c8c8c', cursor: 'help', textDecoration: 'underline' }}>不适用说明</span>
                  </Tooltip>
                </Space>
              )}

              {(currentItem.result_type === 'score' || (currentItem.result_type === null && currentItem.check_type === 'score')) && (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Space>
                    <span>得分：</span>
                    <InputNumber
                      value={currentItem.score_value}
                      onChange={(value) => handleResultChange('score_value', value)}
                      min={0}
                      max={currentItem.max_score || 100}
                      step={currentItem.score_step || 1}
                      style={{ width: 120 }}
                    />
                    <span>/ {currentItem.max_score || 100} 分</span>
                  </Space>
                  {currentItem.pass_score && (
                    <div style={{ color: '#888', fontSize: 12 }}>合格线：{currentItem.pass_score} 分</div>
                  )}
                </Space>
              )}

              {(currentItem.result_type === 'numeric' || (currentItem.result_type === null && currentItem.check_type === 'numeric')) && (
                <Space>
                  <InputNumber
                    value={currentItem.numeric_value}
                    onChange={(value) => handleResultChange('numeric_value', value)}
                    min={currentItem.min_value}
                    max={currentItem.max_value}
                    placeholder={currentItem.min_value !== null && currentItem.max_value !== null
                      ? `范围: ${currentItem.min_value} ~ ${currentItem.max_value}`
                      : '请输入数值'}
                    style={{ width: 200 }}
                  />
                  {currentItem.unit && <span>{currentItem.unit}</span>}
                </Space>
              )}

              {(currentItem.result_type === 'text' || (currentItem.result_type === null && currentItem.check_type === 'text')) && (
                <TextArea
                  rows={4}
                  placeholder="请输入检查结果描述..."
                  value={currentItem.text_value || ''}
                  onChange={(e) => {
                    const updatedItems = flatItems.map((item, idx) => {
                      if (idx === currentIndex) return { ...item, text_value: e.target.value }
                      return item
                    })
                    setFlatItems(updatedItems)
                  }}
                  onBlur={() => handleResultChange('text_value', currentItem.text_value)}
                />
              )}

              {(currentItem.result_type === 'multi_check' || (currentItem.result_type === null && currentItem.check_type === 'multi_check')) && (
                <Select
                  mode="multiple"
                  style={{ width: '100%', maxWidth: 400 }}
                  value={currentItem.multi_value || []}
                  onChange={(value) => handleResultChange('multi_value', value)}
                  placeholder="请选择（可多选）"
                  options={(currentItem.result_options?.options || currentItem.result_options || []).map((opt: any) => ({
                    value: opt.value,
                    label: opt.label,
                  }))}
                />
              )}
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>审核记录</div>
              <TextArea
                rows={2}
                placeholder="请输入审核记录..."
                value={currentItem.inspector_note || ''}
                onChange={(e) => {
                  const updatedItems = flatItems.map((item, idx) => {
                    if (idx === currentIndex) return { ...item, inspector_note: e.target.value }
                    return item
                  })
                  setFlatItems(updatedItems)
                }}
                onBlur={() => handleResultChange('inspector_note', currentItem.inspector_note)}
              />
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>
                现场照片
                {currentItem.attachment_required && (
                  <span style={{ color: '#ff4d4f', marginLeft: 4 }}>*</span>
                )}
              </div>
              {currentItem.allow_attachment !== false ? (
                <>
                  {currentItem.attachment_required && (
                    <Alert type="warning" message="本检查项需要上传附件" style={{ marginBottom: 12, fontSize: 12 }} showIcon />
                  )}
                  <Upload customRequest={handleUpload} showUploadList={false} accept="image/*">
                    <Button icon={<CameraOutlined />}>上传照片</Button>
                  </Upload>
                  {currentItem.photos && currentItem.photos.length > 0 && (
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                      {currentItem.photos.map((url: string, idx: number) => {
                        const normalizedUrl = (!url || url.startsWith('/') || url.startsWith('http')) ? url : '/' + url
                        return (
                          <img
                            key={idx}
                            src={normalizedUrl}
                            alt={`附件图片 ${idx + 1}`}
                            style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 6, border: '1px solid #e2e8f0', cursor: 'pointer' }}
                            onClick={() => window.open(normalizedUrl, '_blank')}
                          />
                        )
                      })}
                    </div>
                  )}
                </>
              ) : (
                <div style={{ color: '#999', fontSize: 12 }}>本检查项不需要上传照片</div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 32 }}>
              <Button disabled={currentIndex === 0} onClick={() => setCurrentIndex(currentIndex - 1)}>
                上一条
              </Button>
              <Button type="primary" disabled={currentIndex === flatItems.length - 1} onClick={() => setCurrentIndex(currentIndex + 1)}>
                下一条
              </Button>
            </div>
          </Card>
        )}
          </>
        )}

        {/* 最终判定区域：记录草稿，或任务模式（含已完成可改） */}
        {progress === 100 && (isTaskMode || record.status === 'draft') && (
          <Card
            style={{ marginTop: 16 }}
            title={
              <Space>
                <SafetyCertificateOutlined style={{ color: '#4F46E5' }} />
                <span>最终判定结论</span>
              </Space>
            }
          >
            {/* 统计汇总 —— 五档相加必须等于「总检查项」，否则客户现场会质疑数字对不上账 */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontWeight: 500, marginBottom: 12 }}>检查结果汇总</div>
              <Row gutter={16}>
                <Col span={otherCount > 0 ? 4 : 5}>
                  <Card size="small" style={{ background: '#f6ffed', borderColor: '#b7eb8f' }}>
                    <Statistic title="合格项" value={passCount} valueStyle={{ color: '#52c41a' }} />
                  </Card>
                </Col>
                <Col span={otherCount > 0 ? 4 : 5}>
                  <Card size="small" style={{ background: '#fff2f0', borderColor: '#ffccc7' }}>
                    <Statistic title="不合格项" value={failCount} valueStyle={{ color: '#ff4d4f' }} />
                  </Card>
                </Col>
                <Col span={otherCount > 0 ? 4 : 5}>
                  <Card size="small" style={{ background: '#fafafa', borderColor: '#d9d9d9' }}>
                    <Statistic title="不适用项" value={notApplicableCount} valueStyle={{ color: '#8c8c8c' }} />
                  </Card>
                </Col>
                {/* 其他项：数值型 / 描述型 / 打分型，以及观察项、待整改等中间态。
                    不加这一格则「合格 + 不合格 + 不适用」小于「总检查项」，
                    与 H5 现场端（已含「其他项」）口径也不一致。 */}
                {otherCount > 0 && (
                  <Col span={4}>
                    <Card size="small" style={{ background: '#e6f4ff', borderColor: '#91caff' }}>
                      <Statistic title="其他项" value={otherCount} valueStyle={{ color: '#0958d9' }} />
                    </Card>
                  </Col>
                )}
                <Col span={otherCount > 0 ? 4 : 5}>
                  <Card size="small">
                    <Statistic title="总检查项" value={flatItems.length} />
                  </Card>
                </Col>
              </Row>
              {unfilledCount > 0 && (
                <div style={{ marginTop: 8, fontSize: 12, color: '#faad14' }}>
                  另有 {unfilledCount} 项未填写，未计入以上统计。
                </div>
              )}
            </div>

            <Divider />

            {/* 判定结果选择 */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontWeight: 500, marginBottom: 12 }}>判定结果 <span style={{ color: '#ff4d4f' }}>*</span></div>
              <Radio.Group
                value={finalJudgment.result}
                onChange={(e) => setFinalJudgment(prev => ({ ...prev, result: e.target.value }))}
                buttonStyle="solid"
                size="large"
              >
                <Radio.Button value="pass">
                  <span style={{ color: '#52c41a' }}>✅ 合格</span>
                </Radio.Button>
                <Radio.Button value="partial_pass">
                  <span style={{ color: '#faad14' }}>⚠️ 基本合格</span>
                </Radio.Button>
                <Radio.Button value="fail">
                  <span style={{ color: '#ff4d4f' }}>❌ 不合格</span>
                </Radio.Button>
              </Radio.Group>
            </div>

            {/* 判定说明 */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontWeight: 500, marginBottom: 12 }}>判定说明</div>
              <TextArea
                rows={4}
                placeholder="请输入判定说明..."
                value={finalJudgment.remarks}
                onChange={(e) => setFinalJudgment(prev => ({ ...prev, remarks: e.target.value }))}
              />
            </div>

            {/* AI生成区域 */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontWeight: 500, marginBottom: 12 }}>AI 辅助判定</div>
              <Space style={{ marginBottom: 12 }}>
                <Button
                  type="primary"
                  icon={<RobotOutlined />}
                  loading={aiJudgmentLoading}
                  onClick={handleGenerateAIJudgment}
                  disabled={aiJudgmentLoading}
                >
                  {aiJudgmentLoading ? 'AI 分析中...' : 'AI 生成最终判定'}
                </Button>
                {aiJudgmentResult && (
                  <Button onClick={handleAcceptAIJudgment} type="default">
                    采纳 AI 建议
                  </Button>
                )}
                {(aiJudgmentThinkingContent || aiJudgmentResult) && (
                  <Button onClick={handleClearAIJudgment} danger ghost>
                    清除
                  </Button>
                )}
              </Space>

              {/* AI 思考过程 - 流式显示 */}
              {aiJudgmentThinking && aiJudgmentThinkingContent && (
                <Card
                  size="small"
                  style={{
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    borderColor: '#667eea',
                    marginBottom: 12
                  }}
                >
                  <div style={{ color: '#fff', fontWeight: 500, marginBottom: 8 }}>
                    <LoadingOutlined spin style={{ marginRight: 8 }} />
                    AI 正在分析检查结果...
                  </div>
                  <div
                    style={{
                      color: 'rgba(255,255,255,0.9)',
                      fontSize: 13,
                      lineHeight: 1.6,
                      maxHeight: 200,
                      overflow: 'auto',
                      whiteSpace: 'pre-wrap'
                    }}
                  >
                    {aiJudgmentThinkingContent}
                  </div>
                </Card>
              )}

              {/* AI 分析结果 */}
              {aiJudgmentResult && !aiJudgmentThinking && (
                <Alert
                  type="success"
                  message="AI 分析完成"
                  description={
                    <div>
                      {aiJudgmentResultType && (
                        <div style={{ marginBottom: 12, fontWeight: 500 }}>
                          建议判定：
                          {aiJudgmentResultType === 'pass' && (
                            <Tag color="success" style={{ marginLeft: 8 }}>合格</Tag>
                          )}
                          {aiJudgmentResultType === 'partial_pass' && (
                            <Tag color="warning" style={{ marginLeft: 8 }}>基本合格</Tag>
                          )}
                          {aiJudgmentResultType === 'fail' && (
                            <Tag color="error" style={{ marginLeft: 8 }}>不合格</Tag>
                          )}
                        </div>
                      )}
                      <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                        {aiJudgmentResult}
                      </div>
                    </div>
                  }
                  style={{ marginTop: 12 }}
                  showIcon
                  action={
                    <Button size="small" type="primary" onClick={handleAcceptAIJudgment}>
                      采纳
                    </Button>
                  }
                />
              )}
            </div>

            {/* 提交按钮 */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
              <Button loading={savingJudgment} onClick={handleSaveFinalJudgment}>
                保存判定结论
              </Button>
              <Button
                type="primary"
                icon={<SendOutlined />}
                disabled={!canSubmit}
                onClick={handleSubmit}
              >
                {isCompleted ? '保存全部修改' : isTaskMode ? '完成检查任务' : '提交检查结果'}
              </Button>
            </div>

            {!isTaskMode && !finalJudgment.result && (
              <Alert
                type="info"
                message="请选择最终判定结果（合格/基本合格/不合格）后才能提交"
                style={{ marginTop: 16 }}
                showIcon
              />
            )}
            {isTaskMode && isCompleted && (
              <Alert
                type="success"
                message="任务已完成，可直接修改各项检查结果后点击「保存修改」"
                style={{ marginTop: 16 }}
                showIcon
              />
            )}
          </Card>
        )}

        {/* 提交提示 */}
        {progress === 100 && !finalJudgment.result && record.status === 'draft' && (
          <Alert
            type="info"
            message="检查项已全部完成，请在上方填写【最终判定结论】后提交"
            style={{ marginTop: 16 }}
            showIcon
          />
        )}
      </div>

      <Drawer
        title="AI 审核建议"
        placement="right"
        width={480}
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
      >
        {llmLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
            <p style={{ marginTop: 16, color: '#666' }}>AI 正在分析...</p>
          </div>
        ) : (
          <>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, marginBottom: 16 }}>
              {llmContent}
            </div>
            {llmContent && llmContent !== '请先填写检查结果后再获取AI建议' && llmContent !== '获取失败，请稍后重试' && (
              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 16 }}>
                <Button onClick={() => setDrawerVisible(false)}>取消</Button>
                <Button type="primary" onClick={handleAcceptAISuggestion}>采纳建议</Button>
              </div>
            )}
          </>
        )}
      </Drawer>
    </div>
  )
}