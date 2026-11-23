/** 现场端本地偏好设置（存于 localStorage.app_settings） */
const KEY = 'app_settings'

export function getAppSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || '{}')
    return { notification: true, ...saved }
  } catch {
    return { notification: true }
  }
}

export function saveAppSettings(patch) {
  const next = { ...getAppSettings(), ...patch }
  localStorage.setItem(KEY, JSON.stringify(next))
  return next
}

/** 是否在「我的」页显示智审提醒未读角标 */
export function isNotificationEnabled() {
  return getAppSettings().notification !== false
}
