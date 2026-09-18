/** 现场端展示文案 */

export function roleLabel(role) {
  const map = {
    super_admin: '系统管理员',
    admin: '管理员',
    expert: '审核员',
    auditor: '审核员',
    manager: '主管',
  }
  return map[role] || role || '用户'
}

export function formatTaskDisplay(task = {}) {
  const raw = String(task.title || '').trim()
  if (!raw) {
    return {
      primary: task.target_name || task.area_name || '未命名任务',
      secondary: '',
    }
  }
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
      primary: project || parts[0] || cleaned,
      secondary: [area, dateHint].filter(Boolean).join(' · '),
      area,
      dateHint,
    }
  }
  if (parts.length === 2) {
    // BUG-39：两段拆分仅在首段足够完整时生效，避免 "QA-H5执行任务"
    // 这类含连字符的短前缀名称被割裂成 "QA" + 副标题的误导性展示。
    if (parts[0].length >= 4) {
      return {
        primary: parts[0],
        secondary: parts[1],
        area: parts[1],
      }
    }
    return {
      primary: cleaned,
      secondary: '',
    }
  }
  return {
    primary: cleaned || task.target_name || task.area_name || '未命名任务',
    secondary: '',
  }
}

/**
 * 模板是否真的配置了量化计分项。
 * 用于兜住「定性模板被误标 is_quantified=true」的情况，避免对外显示「总分 0 分」。
 */
export function hasQuantifiedItems(template) {
  const walk = (list) =>
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

export function citationSourceLabel(citation = {}) {
  const scope = citation.source_scope || citation.scope || citation.source || ''
  if (scope === 'project' || scope === 'project_document' || /项目/.test(String(scope))) {
    return '项目资料'
  }
  if (scope === 'global' || scope === 'knowledge' || /法规|知识/.test(String(scope))) {
    return '全局法规'
  }
  if (citation.document_title || citation.file_name) {
    return citation.source_scope === 'project' ? '项目资料' : '参考资料'
  }
  return '引用'
}
