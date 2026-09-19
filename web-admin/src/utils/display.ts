/** 展示层文案与标题格式化（面向业务用户，隐藏技术编号噪音） */

import dayjs from 'dayjs'

/**
 * 业务日期格式化（唯一来源）。
 *
 * 后端返回的是带时区的 ISO-8601 串（如 `2026-07-20T01:00:00+00:00`），
 * **绝不能直接渲染到界面**——客户会看到一串原始时间戳。
 *
 * 也不能简单 `slice(0, 10)`：那取的是 UTC 日期，对 `2026-09-10T16:00:00+00:00`
 * 会显示成 09-10，而按业务时区（UTC+8）实际是 09-11，与列表页差一天。
 * 这里统一按浏览器本地时区（业务时区 UTC+8）格式化，与
 * `AuditProjects/index.tsx` 的 `toLocaleDateString()` 口径一致。
 */
export function formatBusinessDate(value?: string | null): string {
  if (!value) return '-'
  const d = dayjs(value)
  return d.isValid() ? d.format('YYYY-MM-DD') : String(value).slice(0, 10)
}

/** 起止区间：`2026-07-20 ~ 2026-07-22`；两端皆空时返回 '-' */
export function formatDateRange(start?: string | null, end?: string | null): string {
  if (!start && !end) return '-'
  return `${formatBusinessDate(start)} ~ ${formatBusinessDate(end)}`
}

export function roleLabel(role?: string | null): string {
  const map: Record<string, string> = {
    super_admin: '系统管理员',
    admin: '管理员',
    expert: '审核员',
    auditor: '审核员',
    manager: '主管',
  }
  return map[role || ''] || role || '用户'
}

/**
 * 将冗长任务标题拆成人可读结构。
 * 常见格式：`项目名 - 区域 - 日期` 或带 E2E 前缀的测试标题。
 */
export function formatTaskDisplay(task: {
  title?: string
  target_name?: string
  task_no?: string
}): { primary: string; secondary?: string; area?: string; dateHint?: string } {
  const raw = (task.title || '').trim()
  if (!raw) {
    return { primary: task.target_name || task.task_no || '未命名任务' }
  }

  // 去掉常见测试前缀噪音
  const cleaned = raw
    .replace(/^E2E[-_]FULL[-_]\d+[-\s]*/i, '')
    .replace(/^Codex\s+P\d+\s+/i, '')
    .trim()

  const parts = cleaned.split(/\s*[-–—]\s*/).map((p) => p.trim()).filter(Boolean)
  if (parts.length >= 3) {
    const dateHint = parts[parts.length - 1]
    const area = parts[parts.length - 2]
    const project = parts.slice(0, -2).join(' · ')
    return {
      primary: project || cleaned,
      area,
      dateHint: /^\d{4}/.test(dateHint) || /\d{2}-\d{2}/.test(dateHint) ? dateHint : undefined,
      secondary: [area, dateHint].filter(Boolean).join(' · '),
    }
  }
  if (parts.length === 2) {
    return {
      primary: parts[0],
      secondary: parts[1],
      area: parts[1],
    }
  }
  return {
    primary: cleaned || task.target_name || '未命名任务',
    secondary: undefined,
  }
}

export function shortEnterpriseName(name?: string | null, max = 18): string {
  if (!name) return '未指定企业'
  return name.length > max ? `${name.slice(0, max)}…` : name
}

/**
 * 备注兜底格式化：历史数据里可能残留 `最终判定:pass` / `最终判定:fail` 英文枚举，
 * 展示前统一映射为中文，避免对外暴露英文。
 */
export function formatRemarksForDisplay(remarks?: string | null): string {
  if (!remarks) return ''
  return remarks
    .replace(/最终判定\s*[:：]\s*partial_pass\b/gi, '最终判定:基本合格')
    .replace(/最终判定\s*[:：]\s*pass\b/gi, '最终判定:合格')
    .replace(/最终判定\s*[:：]\s*fail\b/gi, '最终判定:不合格')
}

/**
 * 模板是否真的配置了量化计分项。
 * 用于兜住「定性模板被误标 is_quantified=true」的情况，避免报告里出现「量化总分 0 分」。
 */
export function hasQuantifiedItems(template?: any): boolean {
  const walk = (list: any[]): boolean =>
    (list || []).some((it) => {
      if (Array.isArray(it?.children) && it.children.length > 0 && walk(it.children)) {
        return true
      }
      if (it?.is_category) return false
      const rt = it?.result_type || it?.check_type
      const hasScoreMeta =
        (it?.max_score !== null && it?.max_score !== undefined) ||
        (it?.score_weight !== null && it?.score_weight !== undefined) ||
        (it?.default_score !== null && it?.default_score !== undefined)
      return rt === 'score' || hasScoreMeta
    })
  return walk(template?.items || [])
}

/**
 * 检查结果取值 → 中文文案 的统一映射。
 *
 * 后端与模板里并存多套取值（pass/fail/na/not_applicable/observe/pending_rectification 等），
 * 各页面曾各自维护一份不完整的映射表，导致 observe、not_applicable 这类值直接以英文暴露给业务用户。
 * 展示层一律走这里，不要再各写一份。
 */
export const RESULT_LABELS: Record<string, string> = {
  pass: '合格',
  compliant: '合格',
  qualified: '合格',
  fail: '不合格',
  non_compliant: '不合格',
  unqualified: '不合格',
  partial_pass: '基本合格',
  na: '不适用',
  'n/a': '不适用',
  not_applicable: '不适用',
  未涉及: '不适用',
  observe: '观察项',
  observation: '观察项',
  pending_rectification: '待整改',
  corrected: '已整改',
  pending_verification: '待验证',
  verified: '已验证',
  closed: '已关闭',
}

/** 结果值 → 中文文案；未命中时原样返回，便于发现新枚举 */
export function resultLabel(value?: string | null): string {
  const key = String(value ?? '').trim()
  if (!key) return ''
  return RESULT_LABELS[key] || RESULT_LABELS[key.toLowerCase()] || key
}

/** 结果值 → Ant Design Tag 颜色 */
export function resultTagColor(value?: string | null): string {
  const key = String(value ?? '').trim().toLowerCase()
  if (key === 'pass' || key === 'compliant' || key === 'qualified') return 'success'
  if (key === 'fail' || key === 'non_compliant' || key === 'unqualified') return 'error'
  if (key === 'partial_pass' || key === 'pending_rectification') return 'warning'
  if (key === 'observe' || key === 'observation') return 'blue'
  return 'default'
}

/**
 * 优先使用模板项自带 result_options 里的 label（业务方自定义的叫法优先），
 * 没有配置时再回落到统一映射。
 */
export function resolveOptionLabel(value: any, resultOptions?: any): string {
  const key = String(value ?? '')
  const raw = resultOptions?.options ?? resultOptions
  if (Array.isArray(raw)) {
    const hit = raw.find((o: any) => String(o?.value ?? o?.name ?? '') === key)
    const label = hit?.label ?? hit?.name
    if (label) return String(label)
  }
  return resultLabel(key)
}

/** 检查任务状态 → 中文（导出、表格共用，避免把英文枚举写进交付文件） */
export const TASK_STATUS_LABELS: Record<string, string> = {
  pending: '待开始',
  in_progress: '进行中',
  completed: '已完成',
  cancelled: '已取消',
}

export function taskStatusLabel(status?: string | null): string {
  const key = String(status ?? '').trim()
  if (!key) return ''
  return TASK_STATUS_LABELS[key] || key
}

/**
 * 审核项目状态 → 展示文案 / 颜色 / 含义说明。
 *
 * 状态流转对用户是个谜（测试问题清单第 16 条），列表里必须能悬停看到解释。
 * 当前真实流转：创建时为 planning → 关联检查任务开始后置 in_progress → completed / cancelled。
 */
export const PROJECT_STATUS_META: Record<
  string,
  { text: string; color: string; desc: string }
> = {
  planning: {
    text: '策划中',
    color: 'default',
    desc: '项目已建立，尚未开始现场审核。此阶段需要完善审核计划、组建审核组并分配审核员。',
  },
  in_progress: {
    text: '进行中',
    color: 'processing',
    desc: '已生成检查任务或已开始现场审核，审核活动正在推进。',
  },
  completed: {
    text: '已完成',
    color: 'success',
    desc: '全部审核活动结束，审核报告与不符合项处理均已完成。',
  },
  cancelled: {
    text: '已取消',
    color: 'error',
    desc: '项目中途终止，不再继续审核。',
  },
}

export function projectStatusMeta(status?: string | null) {
  const key = String(status ?? '')
  return (
    PROJECT_STATUS_META[key] || {
      text: key || '-',
      color: 'default',
      desc: '未知状态',
    }
  )
}

/** 审核类型 → 中文 */
export const AUDIT_TYPE_LABELS: Record<string, string> = {
  initial: '初审',
  surveillance: '监督',
  recertification: '再认证',
  expansion: '扩项',
}

export function auditTypeLabel(type?: string | null): string {
  const key = String(type ?? '')
  return AUDIT_TYPE_LABELS[key] || key
}
