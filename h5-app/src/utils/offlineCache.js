/**
 * 出发前离线缓存（读缓存）
 *
 * 现场审核员进厂后经常没有信号，本模块让他们在出发前把「等下要用的东西」
 * 存到手机本地：任务/记录详情、模板检查项、企业信息。
 *
 * 边界：只做读缓存，不做离线写队列。断网时页面用缓存渲染检查项，
 * 填写内容不会被排队上传（避免给审核员「已保存」的错觉）。
 *
 * 实现用 localStorage，不引入任何依赖。
 */

import { getRecord, getEnterprise } from '../api/records.js'
import { getTask, getTaskRecords, getTemplateItems } from '../api/tasks.js'

/** 缓存结构版本：结构变更时 +1，旧版本条目会被自动清理 */
export const CACHE_SCHEMA_VERSION = 1

const STORAGE_PREFIX = 'efis:offline'
const VERSION_PREFIX = `${STORAGE_PREFIX}:v${CACHE_SCHEMA_VERSION}`
const INDEX_KEY = `${VERSION_PREFIX}:index`

/** 缓存变化事件：横幅、列表徽标等靠它刷新 */
export const CACHE_EVENT = 'efis:offline-cache-updated'

/** 缓存条目最长保留天数，避免旧检查表一直占地方 */
const MAX_AGE_DAYS = 30
/** 最多保留的条目数，超出时淘汰最旧的 */
const MAX_ENTRIES = 20

const entryKey = (kind, id) => `${VERSION_PREFIX}:${kind}:${id}`

const storage = () => {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch (e) {
    return null
  }
}

const readJson = (key, fallback = null) => {
  const store = storage()
  if (!store) return fallback
  try {
    const raw = store.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch (e) {
    return fallback
  }
}

const writeJson = (key, value) => {
  const store = storage()
  if (!store) return false
  try {
    store.setItem(key, JSON.stringify(value))
    return true
  } catch (e) {
    return false
  }
}

const removeKey = (key) => {
  const store = storage()
  if (!store) return
  try {
    store.removeItem(key)
  } catch (e) {
    // ignore
  }
}

const notifyChanged = () => {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(CACHE_EVENT))
}

/** 清理旧结构版本遗留的键 */
const purgeOtherVersions = () => {
  const store = storage()
  if (!store) return
  const stale = []
  for (let i = 0; i < store.length; i++) {
    const key = store.key(i)
    if (key && key.startsWith(`${STORAGE_PREFIX}:`) && !key.startsWith(`${VERSION_PREFIX}:`)) {
      stale.push(key)
    }
  }
  stale.forEach(removeKey)
}

purgeOtherVersions()

const readIndex = () => {
  const list = readJson(INDEX_KEY, [])
  return Array.isArray(list) ? list : []
}

const writeIndex = (list) => writeJson(INDEX_KEY, list)

/** 是否联网（SSR / 老浏览器缺 navigator.onLine 时按在线处理） */
export const isOnline = () => typeof navigator === 'undefined' || navigator.onLine !== false

/** 统计模板里真正的检查项数量（跳过分类节点） */
export const countCheckItems = (items) => {
  let count = 0
  const walk = (list) => {
    for (const item of list || []) {
      if (item?.is_category !== true) count++
      if (item?.children?.length) walk(item.children)
    }
  }
  walk(items)
  return count
}

/** 已缓存条目摘要列表，按缓存时间倒序 */
export const listCachedEntries = () =>
  readIndex()
    .slice()
    .sort((a, b) => (b.cachedAt || 0) - (a.cachedAt || 0))

/** 读取某条缓存的完整内容；结构版本不符或已过期返回 null */
export const getCachedEntry = (kind, id) => {
  if (!kind || !id) return null
  const entry = readJson(entryKey(kind, String(id)))
  if (!entry || entry.schemaVersion !== CACHE_SCHEMA_VERSION) return null
  return entry
}

export const isCached = (kind, id) => !!getCachedEntry(kind, id)

/** 缓存总览：条数 + 最近一次缓存时间 */
export const getCacheSummary = () => {
  const entries = listCachedEntries()
  return {
    count: entries.length,
    lastCachedAt: entries.length > 0 ? entries[0].cachedAt || 0 : 0,
  }
}

export const removeCachedEntry = (kind, id) => {
  removeKey(entryKey(kind, String(id)))
  writeIndex(readIndex().filter((e) => !(e.kind === kind && e.id === String(id))))
  notifyChanged()
}

export const clearCache = () => {
  readIndex().forEach((e) => removeKey(entryKey(e.kind, e.id)))
  removeKey(INDEX_KEY)
  notifyChanged()
}

/** 淘汰过期与超量的条目 */
const pruneEntries = () => {
  const deadline = Date.now() - MAX_AGE_DAYS * 24 * 60 * 60 * 1000
  const kept = []
  for (const entry of listCachedEntries()) {
    if ((entry.cachedAt || 0) < deadline || kept.length >= MAX_ENTRIES) {
      removeKey(entryKey(entry.kind, entry.id))
      continue
    }
    kept.push(entry)
  }
  writeIndex(kept)
  return kept
}

/**
 * 写入一条缓存。
 * @returns {Object} 写入后的条目摘要
 */
export const saveCachedEntry = ({ kind, id, title, subtitle, itemCount, payload }) => {
  const key = String(id)
  const summary = {
    kind,
    id: key,
    title: title || '',
    subtitle: subtitle || '',
    itemCount: itemCount || 0,
    cachedAt: Date.now(),
  }

  const ok = writeJson(entryKey(kind, key), {
    ...summary,
    schemaVersion: CACHE_SCHEMA_VERSION,
    payload,
  })
  if (!ok) {
    throw new Error('本机存储空间不足，缓存失败')
  }

  const list = pruneEntries().filter((e) => !(e.kind === kind && e.id === key))
  list.unshift(summary)
  writeIndex(list.slice(0, MAX_ENTRIES))
  notifyChanged()
  return summary
}

/** 缓存时间的人话展示 */
export const formatCachedAt = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const minutes = Math.floor((Date.now() - timestamp) / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (minutes < 24 * 60) return `${Math.floor(minutes / 60)} 小时前`
  const days = Math.floor(minutes / (60 * 24))
  if (days < 7) return `${days} 天前`
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

/**
 * 缓存一个检查任务：任务详情 + 模板检查项 + 已填结果 + 企业信息。
 * 需要联网调用，通常在出发前点击。
 */
export const cacheTaskForOffline = async (taskId) => {
  const id = String(taskId)
  const taskRes = await getTask(id)
  const task = taskRes?.data
  if (!task) throw new Error('任务不存在，无法缓存')

  let taskRecords = []
  try {
    const recordsRes = await getTaskRecords(id)
    if (Array.isArray(recordsRes?.data)) taskRecords = recordsRes.data
  } catch (e) {
    console.warn('缓存任务检查项失败，继续缓存其余内容', e)
  }

  // 历史任务可能没有 template_id：从已有检查项反推
  let templateId = task.template_id
  if (!templateId) {
    const linked = taskRecords.find((r) => r?.template_item?.template_id)
    templateId = linked?.template_item?.template_id || null
  }

  let template = null
  if (templateId) {
    const tplRes = await getTemplateItems(templateId)
    template = tplRes?.data || null
  }

  let enterprise = null
  const enterpriseId = task.enterprise_id || task.target_enterprise_id
  if (enterpriseId) {
    try {
      const entRes = await getEnterprise(enterpriseId)
      enterprise = entRes?.data || null
    } catch (e) {
      console.warn('缓存企业信息失败', e)
    }
  }

  return saveCachedEntry({
    kind: 'task',
    id,
    title: task.title || '检查任务',
    subtitle: task.target_name || enterprise?.name || '',
    itemCount: countCheckItems(template?.items),
    payload: { task, template, taskRecords, enterprise },
  })
}

/**
 * 缓存一条检查记录：记录详情（内含模板检查项与已填结果）+ 企业信息。
 */
export const cacheRecordForOffline = async (recordId) => {
  const id = String(recordId)
  const res = await getRecord(id)
  const record = res?.data
  if (!record) throw new Error('检查记录不存在，无法缓存')

  let enterprise = null
  if (record.enterprise_id) {
    try {
      const entRes = await getEnterprise(record.enterprise_id)
      enterprise = entRes?.data || null
    } catch (e) {
      console.warn('缓存企业信息失败', e)
    }
  }

  return saveCachedEntry({
    kind: 'record',
    id,
    title: record.template?.name || '现场检查记录',
    subtitle: record.enterprise_name || enterprise?.name || '',
    itemCount: countCheckItems(record.template?.items),
    payload: { record, enterprise },
  })
}

export default {
  CACHE_EVENT,
  CACHE_SCHEMA_VERSION,
  cacheRecordForOffline,
  cacheTaskForOffline,
  clearCache,
  countCheckItems,
  formatCachedAt,
  getCacheSummary,
  getCachedEntry,
  isCached,
  isOnline,
  listCachedEntries,
  removeCachedEntry,
  saveCachedEntry,
}
