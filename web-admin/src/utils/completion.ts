/**
 * 检查项「是否已评定」的唯一判据（Web 端）。
 *
 * 业务口径（2026-09-18 确认）：
 *   - 合格 / 不合格 / 不适用 —— 都算「已完成」
 *   - 描述型 / 数值型 / 打分型 —— 只要填了内容就算「已完成」
 *   - 全部为空 —— 「未评定」，不算完成
 *
 * 与 H5 现场端 `InspectionExecution.vue` 的 `isItemCompleted` 保持同一口径：
 * 判定型项必须落到结论字段；备注（inspector_note）不算完成。
 *
 * 两套记录模型的字段名不同，本判据同时兼容：
 *   - `task_item_records`（H5 表格式检查）：result / result_value / result_text
 *   - `inspection_record_items`（Web 检查记录）：radio_value / numeric_value /
 *     text_value / score_value / multi_value
 */

/** 非空判定：null / undefined / 空串 / 字面量 "null" 都视为空 */
const has = (v: unknown): boolean => {
  if (v === null || v === undefined) return false
  const s = String(v).trim()
  return s !== '' && s !== 'null'
}

/** 判定值：兼容 radio_value（inspection_record_items）与 result（task_item_records） */
const verdictOf = (r: any): string | null => {
  const v = r?.radio_value ?? r?.result ?? r?.evaluation_3level ?? null
  return has(v) ? String(v).trim() : null
}

/**
 * 取检查项的真实类型。
 *
 * `template_items` 上 `check_type` 与 `result_type` **两个字段并存**，各自带一个默认值：
 *   - `check_type` 默认 `'radio'`（列默认值；模板编辑器并不写它，只有 AI 导入路径写）
 *   - `result_type` 默认 `'pass_fail'`（模板编辑器实际写的就是它）
 *
 * 实测：某模板的「数值」「文字描述」检查项在库里是
 * `check_type='radio', result_type='numeric'/'text'` —— 只看 `check_type`
 * 会把描述型/数值型误判为判定型。因此取**非默认**的那个字段；
 * 两个都非默认时以 `check_type` 为准。与后端 `app/utils/item_completion.py` 同口径。
 */
export function resolveCheckType(item: any): string {
  const pick = (...keys: string[]): string => {
    for (const key of keys) {
      const value = item?.[key]
      if (value) return String(value).trim().toLowerCase()
    }
    return ''
  }

  const checkType = pick('check_type', 'item_check_type')
  const resultType = pick('result_type')

  if (checkType && checkType !== 'radio') return normalizeCheckType(checkType)
  if (resultType && resultType !== 'pass_fail') return normalizeCheckType(resultType)
  return 'radio'
}

function normalizeCheckType(kind: string): string {
  if (!kind || kind === 'radio' || kind === 'pass_fail') return 'radio'
  if (kind === 'score') return 'score'
  if (kind === 'numeric') return 'numeric'
  if (kind === 'text' || kind === 'textarea') return 'text'
  if (kind === 'multi' || kind === 'multiselect' || kind === 'multi_check') return 'multi'
  return 'radio'
}

/**
 * 该检查项是否已评定。
 *
 * @param item  承载检查项类型（check_type / result_type）的对象
 * @param record 承载结果值的对象；省略时用 `item` 自身
 */
export function isItemAssessed(item: any, record?: any): boolean {
  const r = record ?? item
  if (!r) return false

  switch (resolveCheckType(item)) {
    case 'radio':
      // 判定型：必须有明确结论（合格/不合格/不适用），仅写备注不算完成
      return verdictOf(r) !== null
    case 'score':
      return has(r.score_value) || has(r.result_value)
    case 'numeric':
      return has(r.numeric_value) || has(r.result_value)
    case 'text':
      return has(r.text_value) || has(r.result_text)
    case 'multi':
      return Array.isArray(r.multi_value)
        ? r.multi_value.length > 0
        : has(r.multi_value)
    default:
      return verdictOf(r) !== null
  }
}

/** 统计一组叶子检查项中的已评定数 */
export function countAssessed(items: any[]): number {
  return (items || []).filter((it) => isItemAssessed(it)).length
}
