import { ref } from 'vue'
import { NAV_PATH_ORDER, STORE_DEFAULT_PERMISSIONS, pathToModule } from './adminModules'

const DASHBOARD_SHELL_PATH = '/dashboard'

export type AdminRole = 'hq' | 'store'

export interface AdminProfile {
  token: string
  username: string
  name?: string | null
  role: AdminRole
  store_id?: number | null
  store_name?: string | null
  permissions?: string[] | null
}

const KEYS = {
  token: 'admin_token',
  role: 'admin_role',
  storeId: 'admin_store_id',
  storeName: 'admin_store_name',
  username: 'admin_username',
  name: 'admin_name',
  permissions: 'admin_permissions',
} as const

/** Bumped on save/clear so layout/menu recompute against localStorage. */
export const adminSessionTick = ref(0)

function bumpSession() {
  adminSessionTick.value += 1
}

export function saveAdminSession(data: AdminProfile) {
  localStorage.setItem(KEYS.token, data.token)
  localStorage.setItem(KEYS.role, data.role || 'hq')
  localStorage.setItem(KEYS.username, data.username || '')
  if (data.name) localStorage.setItem(KEYS.name, data.name)
  else localStorage.removeItem(KEYS.name)
  if (data.role === 'store' && data.store_id) {
    localStorage.setItem(KEYS.storeId, String(data.store_id))
    localStorage.setItem(KEYS.storeName, data.store_name || '')
  } else {
    localStorage.removeItem(KEYS.storeId)
    localStorage.removeItem(KEYS.storeName)
  }
  if (data.role === 'hq') {
    localStorage.removeItem(KEYS.permissions)
  } else if (Array.isArray(data.permissions)) {
    localStorage.setItem(KEYS.permissions, JSON.stringify(data.permissions))
  } else {
    localStorage.setItem(KEYS.permissions, JSON.stringify([...STORE_DEFAULT_PERMISSIONS]))
  }
  bumpSession()
}

export function clearAdminSession() {
  Object.values(KEYS).forEach((k) => localStorage.removeItem(k))
  bumpSession()
}

export function getAdminRole(): AdminRole {
  return localStorage.getItem(KEYS.role) === 'store' ? 'store' : 'hq'
}

export function getAdminStoreId(): number | null {
  const v = localStorage.getItem(KEYS.storeId)
  return v ? Number(v) : null
}

export function isHqAdmin(): boolean {
  return getAdminRole() === 'hq'
}

/** null = HQ full access; store always returns a string[]. */
export function getAdminPermissions(): string[] | null {
  if (isHqAdmin()) return null
  const raw = localStorage.getItem(KEYS.permissions)
  if (!raw) return [...STORE_DEFAULT_PERMISSIONS]
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return [...STORE_DEFAULT_PERMISSIONS]
    return parsed.map(String)
  } catch {
    return [...STORE_DEFAULT_PERMISSIONS]
  }
}

export function setAdminPermissions(permissions: string[]) {
  if (isHqAdmin()) {
    localStorage.removeItem(KEYS.permissions)
  } else {
    localStorage.setItem(KEYS.permissions, JSON.stringify(permissions))
  }
  bumpSession()
}

function normalizePath(path: string): string {
  return path.split('?')[0]
}

/** Menu / module gate — requires explicit permission. */
export function canAccessPath(path: string): boolean {
  if (isHqAdmin()) return true
  const mod = pathToModule(normalizePath(path))
  if (!mod) return false
  const perms = getAdminPermissions()
  return Array.isArray(perms) && perms.includes(mod)
}

/** Router gate — dashboard shell always reachable for logged-in store admins. */
export function canAccessRoute(path: string): boolean {
  if (isHqAdmin()) return true
  const p = normalizePath(path)
  if (p === DASHBOARD_SHELL_PATH) return true
  return canAccessPath(p)
}

/** First menu-order path the user may open; falls back to dashboard shell. */
export function firstAccessiblePath(): string {
  for (const path of NAV_PATH_ORDER) {
    if (canAccessPath(path)) return path
  }
  return DASHBOARD_SHELL_PATH
}
