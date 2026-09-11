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
  SafetyCertificateOutlined, RobotOutlined
} from '@ant-design/icons'
import { recordApi, llmApi, mediaApi, taskApi } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const { TextArea } = Input

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
  const [items, setItems] = useState<any[]>([])
  const [flatItems, setFlatItems] = useState<any[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [llmLoading, setLlmLoading] = useState(false)
  const [llmContent, setLlmContent] = useState<string | null>(null)
  const [drawerVisible, setDrawerVisible] = useState(false)

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
          photos: [],
          llm_suggestion: tr.llm_suggestion,
        }
      })
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

    const recordsRes: any = await taskApi.getTaskRecords(task.id)
    const taskRecords = recordsRes.data || []
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
      let savedResult = ''
      let savedRemarks = task.remarks
      const match = task.remarks.match(/最终判定\s*[:：]\s*(pass|fail|partial_pass|合格|不合格|基本合格|符合|不符合)/i)
      if (match) {
        const val = match[1].toLowerCase()
        if (val === 'pass' || val === '合格' || val === '符合') savedResult = 'pass'
        else if (val === 'fail' || val === '不合格' || val === '不符合') savedResult = 'fail'
        else if (val === 'partial_pass' || val === '基本合格') savedResult = 'partial_pass'
        savedRemarks = task.remarks.replace(/^最终判定\s*[:：]\s*[^|]+(\||\s*)/i, '').trim()
      }
      setFinalJudgment({ result: savedResult, remarks: savedRemarks })
    }
  }

  const fetchData = async () => {
    if (!id) return
    setLoading(true)
    try {
      // 1) 优先按独立检查记录加载
      try {
        const res: any = await recordApi.getRecord(id)
        if (res.code === 200 && res.data) {
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
          if (res.data?.remarks) {
            setFinalJudgment((prev) => ({ ...prev, remarks: res.data.remarks }))
          }
          return
        }
      } catch {
        // 不是检查记录，继续按任务处理
      }

      // 2) 按任务加载：直接读写 task_item_records，禁止另建独立检查记录
      try {
        const taskRes: any = await taskApi.getTask(id)
        if (taskRes.code === 200 && taskRes.data) {
          await loadTaskMode(taskRes.data)
          return
        }
      } catch (e) {
        console.error('Failed to load task inspection:', e)
      }

      message.error('获取检查数据失败')
    } catch (error) {
      console.error('Failed to fetch data:', error)
      message.error('获取检查数据失败')
    } finally {
      setLoading(false)
    }
  }

  const currentItem = flatItems[currentIndex]
  const recordId = actualRecordId || (executionMode === 'record' ? record?.id : null)
  const isTaskMode = executionMode === 'task'
  const isCompleted = record?.status === 'submitted' || record?.task_status === 'completed'

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
      if (!item.radio_value && !item.result) payload.result = 'pass'
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
      message.error('保存失败')
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
      message.error('保存失败')
    }

    setDrawerVisible(false)
    setLlmContent(null)
  }

  // 保存最终判定
  const handleSaveFinalJudgment = async () => {
    setSavingJudgment(true)
    try {
      if (isTaskMode && taskId) {
        const verdictCn = finalJudgment.result === 'pass' ? '合格' : finalJudgment.result === 'fail' ? '不合格' : finalJudgment.result === 'partial_pass' ? '基本合格' : finalJudgment.result
        const remarkText = [
          verdictCn ? `最终判定:${verdictCn}` : '',
          finalJudgment.remarks || '',
        ]
          .filter(Boolean)
          .join(' | ')
        await taskApi.updateTask(taskId, { remarks: remarkText })
        message.success('最终判定已保存')
        return
      }
      if (!recordId) return
      await recordApi.updateRecord(recordId, {
        overall_result: finalJudgment.result,
        remarks: finalJudgment.remarks,
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
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
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
        const hasResult =
          item.radio_value ||
          (item.numeric_value !== undefined && item.numeric_value !== '' && item.numeric_value !== null) ||
          item.text_value ||
          (item.score_value !== undefined && item.score_value !== '' && item.score_value !== null)
        if (!hasResult) {
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

    // 任务模式：最终判定可选（写入 remarks）；记录模式：首次提交必填
    if (!isTaskMode && !finalJudgment.result) {
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
            {pendingRectificationCount > 0 && (
              <span style={{ color: '#faad14' }}>⚠️ 待整改：{pendingRectificationCount} 项</span>
            )}
            {notApplicableCount > 0 && (
              <span style={{ color: '#999' }}>⚪ 不适用：{notApplicableCount} 项</span>
            )}
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
            const verdictCn =
              finalJudgment.result === 'pass'
                ? '合格'
                : finalJudgment.result === 'fail'
                  ? '不合格'
                  : finalJudgment.result === 'partial_pass'
                    ? '基本合格'
                    : finalJudgment.result
            const remarkText = [
              verdictCn ? `最终判定:${verdictCn}` : '',
              finalJudgment.remarks || '',
            ]
              .filter(Boolean)
              .join(' | ')
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
            remarks: finalJudgment.remarks,
          })
          await recordApi.submitRecord(recordId)
          message.success('检查记录已提交')
          if (onComplete) onComplete()
          else navigate(backPath)
        } catch (error) {
          message.error(alreadyDone ? '保存失败' : '提交失败')
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
  const completedCount = flatItems.filter((item) => {
    const hasResult =
      item.radio_value ||
      (item.numeric_value !== undefined && item.numeric_value !== '' && item.numeric_value !== null) ||
      item.text_value ||
      (item.score_value !== undefined && item.score_value !== '' && item.score_value !== null)
    const hasRequiredAttachment =
      !item.attachment_required || (item.photos && item.photos.length > 0)
    return hasResult && hasRequiredAttachment
  }).length
  const progress = flatItems.length > 0 ? Math.round((completedCount / flatItems.length) * 100) : 0

  // 统计各项数量
  const passCount = flatItems.filter(
    (item) => item.radio_value === 'pass' || item.radio_value === 'compliant'
  ).length
  const failCount = flatItems.filter(
    (item) => item.radio_value === 'fail' || item.radio_value === 'non_compliant'
  ).length
  const pendingRectificationCount = flatItems.filter(
    (item) => item.radio_value === 'pending_rectification'
  ).length
  const notApplicableCount = flatItems.filter(
    (item) => item.radio_value === 'not_applicable' || item.radio_value === 'na'
  ).length

  // 任务模式：完成进度满即可提交/保存；记录模式：草稿 + 最终判定
  const canSubmit = isTaskMode
    ? progress === 100
    : progress === 100 && !!finalJudgment.result && record?.status === 'draft'

  const getResultTag = (item: any) => {
    if (item.radio_value) {
      const valueMap: Record<string, { color: string; text: string }> = {
        'pass': { color: 'success', text: '合格' },
        'fail': { color: 'error', text: '不合格' },
        'pending_rectification': { color: 'warning', text: '待整改' },
        'not_applicable': { color: 'default', text: '不适用' },
        'na': { color: 'default', text: '不适用' },
      }
      const info = valueMap[item.radio_value] || { color: 'default', text: item.radio_value }
      return <Tag color={info.color}>{info.text}</Tag>
    }
    if (item.numeric_value !== undefined && item.numeric_value !== null) {
      return <Tag color="processing">{item.numeric_value} {item.unit || ''}</Tag>
    }
    if (item.score_value !== undefined && item.score_value !== null) {
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
    return (
      <div style={{ padding: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(backPath)}>返回</Button>
        <div style={{ marginTop: 24, textAlign: 'center' }}>检查记录不存在</div>
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
              {isCompleted ? (isTaskMode ? '已完成（可修改）' : '已提交') : isTaskMode ? '进行中' : '草稿'}
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
        {/* 检查项快捷导航 */}
        <Card style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {flatItems.map((item, idx) => {
              const hasResult = item.radio_value || item.numeric_value || item.text_value || item.score_value
              const hasRequiredAttachment = !item.attachment_required || (item.photos && item.photos.length > 0)
              const isDone = hasResult && hasRequiredAttachment
              const isCur = idx === currentIndex
              const val = String(item.radio_value || '').toLowerCase()
              const isPass = val === 'pass' || val === 'compliant' || val === '合格'
              const isFail = val === 'fail' || val === 'non_compliant' || val === '不合格'
              const isNa = val === 'not_applicable' || val === 'na' || val === '不适用'

              let btnStyle: React.CSSProperties = { marginBottom: 4 }
              if (!isCur) {
                if (isPass) {
                  btnStyle = { ...btnStyle, borderColor: '#52c41a', color: '#389e0d', background: '#f6ffed' }
                } else if (isFail) {
                  btnStyle = { ...btnStyle, borderColor: '#ff4d4f', color: '#cf1322', background: '#fff1f0' }
                } else if (isNa) {
                  btnStyle = { ...btnStyle, borderColor: '#d9d9d9', color: '#8c8c8c', background: '#fafafa' }
                }
              }

              return (
                <Button
                  key={item.id}
                  size="small"
                  type={isCur ? 'primary' : 'default'}
                  onClick={() => setCurrentIndex(idx)}
                  style={btnStyle}
                >
                  {idx + 1}
                  {isDone ? (isPass ? ' ✓' : isFail ? ' ✕' : ' ·') : ''}
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
                      const label = (opt.label === '未涉及' ? '不适用' : opt.label)
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
            {/* 统计汇总 */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontWeight: 500, marginBottom: 12 }}>检查结果汇总</div>
              <Row gutter={16}>
                <Col span={6}>
                  <Card size="small" style={{ background: '#f6ffed', borderColor: '#b7eb8f' }}>
                    <Statistic title="合格项" value={passCount} valueStyle={{ color: '#52c41a' }} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small" style={{ background: '#fff2f0', borderColor: '#ffccc7' }}>
                    <Statistic title="不合格项" value={failCount} valueStyle={{ color: '#ff4d4f' }} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small" style={{ background: '#fafafa', borderColor: '#d9d9d9' }}>
                    <Statistic title="不适用项" value={notApplicableCount} valueStyle={{ color: '#8c8c8c' }} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic title="总检查项" value={flatItems.length} />
                  </Card>
                </Col>
              </Row>
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