export function normalizeResultOptions(raw: any): Array<{ value: string; label: string }> {
  const options = Array.isArray(raw) ? raw : raw?.options || raw?.values || raw?.items || raw?.choices
  if (!Array.isArray(options)) return []
  return options.filter((option) => option != null).map((option) => {
    if (typeof option !== 'object') return { value: String(option), label: String(option) }
    const value = option.value ?? option.key ?? option.label
    return { ...option, value: String(value ?? ''), label: String(option.label ?? value ?? '') }
  }).filter((option) => option.value !== '')
}
