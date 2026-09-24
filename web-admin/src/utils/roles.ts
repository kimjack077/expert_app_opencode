const ADMIN_ROLES = new Set(['admin', 'super_admin'])
const TEMPLATE_MANAGER_ROLES = new Set([...ADMIN_ROLES, 'expert'])

export function isAdminRole(role?: string | null): boolean {
  return !!role && ADMIN_ROLES.has(role)
}

export function canManageTemplates(role?: string | null): boolean {
  return !!role && TEMPLATE_MANAGER_ROLES.has(role)
}
