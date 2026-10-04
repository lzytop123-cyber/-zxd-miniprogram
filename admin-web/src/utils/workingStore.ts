import { getAdminStoreId, isHqAdmin } from './adminAuth'

const KEY = 'admin_working_store_id'
export const WORKING_STORE_EVENT = 'admin-working-store-change'

/** null = 全部门店（仅总部） */
export function getWorkingStoreId(): number | null {
  if (!isHqAdmin()) {
    return getAdminStoreId()
  }
  const raw = localStorage.getItem(KEY)
  if (!raw || raw === '0' || raw === 'all') return null
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : null
}

export function setWorkingStoreId(id: number | null) {
  if (!isHqAdmin()) return
  if (id == null || id <= 0) {
    localStorage.removeItem(KEY)
  } else {
    localStorage.setItem(KEY, String(id))
  }
  window.dispatchEvent(new CustomEvent(WORKING_STORE_EVENT, { detail: { storeId: getWorkingStoreId() } }))
}

/** 必须单店的页面：有工作门店用它，否则回退 firstId */
export function resolveRequiredStoreId(firstId: number | null | undefined): number | null {
  const working = getWorkingStoreId()
  if (working) return working
  if (!isHqAdmin()) return getAdminStoreId()
  return firstId ?? null
}

/** 列表筛选：工作门店有值则用之；全部则为 null */
export function resolveFilterStoreId(): number | null {
  return getWorkingStoreId()
}

export function onWorkingStoreChange(handler: (storeId: number | null) => void) {
  const fn = (e: Event) => {
    const detail = (e as CustomEvent).detail
    handler(detail?.storeId ?? getWorkingStoreId())
  }
  window.addEventListener(WORKING_STORE_EVENT, fn)
  return () => window.removeEventListener(WORKING_STORE_EVENT, fn)
}

/** API 查询参数：有工作门店才带 store_id */
export function workingStoreParams(extra: Record<string, unknown> = {}) {
  const sid = getWorkingStoreId()
  if (sid) return { ...extra, store_id: sid }
  return { ...extra }
}
