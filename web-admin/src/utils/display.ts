/** 展示层文案与标题格式化（面向业务用户，隐藏技术编号噪音） */

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
