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
    return {
      primary: task.target_name || parts[0],
      secondary: [area, dateHint].filter(Boolean).join(' · '),
      area,
      dateHint,
    }
  }
  return {
    primary: task.target_name || task.area_name || cleaned,
    secondary: parts.length === 2 ? parts[1] : '',
  }
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
