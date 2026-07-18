/** 后台时间展示：SQLite/服务端多为 UTC 无时区，按北京时间格式化 */

export function parseServerDate(value?: string | null): Date | null {
  if (!value) return null
  const raw = String(value).trim()
  if (!raw) return null
  const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T')
  const hasTz = /Z$/i.test(normalized) || /[+-]\d{2}:?\d{2}$/.test(normalized)
  const d = new Date(hasTz ? normalized : `${normalized}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

/** 例：2026-07-18 16:55:39 */
export function formatDateTime(value?: string | null): string {
  const d = parseServerDate(value)
  if (!d) return value ? String(value) : '-'
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(d)
  const get = (type: string) => parts.find((p) => p.type === type)?.value || ''
  return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}`
}
