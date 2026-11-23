/**
 * 「记住登录状态」支持。
 *
 * 登录态由 zustand persist 存在 localStorage（auth-storage）。用户登录时若未勾选
 * 「记住登录状态」，会写入 efis-session-only 标记，并设置一个不带过期时间的会话 Cookie。
 * 会话 Cookie 在所有标签页间共享、在浏览器关闭后失效。本模块在应用启动、store 水合之前执行：
 * 若存在 session-only 标记但会话 Cookie 已不存在（浏览器已关闭重开），则清除登录态。
 *
 * 必须在 main.tsx 中作为第一个 import，保证先于 stores/auth 执行。
 */
export const SESSION_ONLY_KEY = 'efis-session-only'
const ALIVE_COOKIE = 'efis_session_alive'

const hasAliveCookie = () =>
  typeof document !== 'undefined' && document.cookie.split(';').some((c) => c.trim().startsWith(`${ALIVE_COOKIE}=`))

try {
  if (localStorage.getItem(SESSION_ONLY_KEY) === '1' && !hasAliveCookie()) {
    localStorage.removeItem('auth-storage')
    localStorage.removeItem(SESSION_ONLY_KEY)
  }
} catch {
  // 隐私模式等禁用存储的环境下忽略
}

export function applyRememberChoice(remember: boolean) {
  try {
    if (remember) localStorage.removeItem(SESSION_ONLY_KEY)
    else localStorage.setItem(SESSION_ONLY_KEY, '1')
    // 不设置 expires/max-age，即为会话 Cookie
    document.cookie = `${ALIVE_COOKIE}=1; path=/; SameSite=Lax`
  } catch {
    /* ignore */
  }
}
