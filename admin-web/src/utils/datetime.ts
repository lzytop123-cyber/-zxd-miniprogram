/** 后台时间：统一按北京时间展示 */

const DATETIME_RE = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?/

/** 服务端 UTC 写入的字段（SQLite CURRENT_TIMESTAMP / func.now） */
const UTC_FIELD_RE =
  /^(created_at|updated_at|verified_at|invited_at|paid_at|cancelled_at|check_in_time|actual_end_time|last_.*_at)$/i

export function looksLikeDateTime(value: string): boolean {
  return DATETIME_RE.test(String(value).trim())
}

export function parseServerUtc(value?: string | null): Date | null {
  if (!value) return null
  const raw = String(value).trim()
  if (!raw) return null
  const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T')
  const hasTz = /Z$/i.test(normalized) || /[+-]\d{2}:?\d{2}$/.test(normalized)
  const d = new Date(hasTz ? normalized : `${normalized}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

/** UTC → 北京时间：2026-07-18 16:55:39 */
export function formatDateTime(value?: string | null): string {
  if (!value) return '-'
  const raw = String(value).trim()
  // 已格式化（拦截器转过）则原样返回，避免二次换算
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$/.test(raw)) {
    return raw.slice(0, 19)
  }
  const d = parseServerUtc(raw)
  if (!d) return raw
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

/** 业务本地时间（预约起止等已是墙钟时间）：只去掉 T，不做时区换算 */
export function formatWallClock(value?: string | null): string {
  if (!value) return '-'
  return String(value)
    .trim()
    .replace('T', ' ')
    .replace(/\.\d+/, '')
    .replace(/Z$/i, '')
    .slice(0, 19)
}

export function formatFieldDateTime(key: string, value: string): string {
  if (UTC_FIELD_RE.test(key) || /_at$/i.test(key)) {
    return formatDateTime(value)
  }
  return formatWallClock(value)
}

/** 递归把响应里的时间字段转成可读北京/墙钟时间 */
export function transformResponseTimes<T>(payload: T): T {
  return walk(payload) as T
}

function walk(node: unknown, parentKey = ''): unknown {
  if (node == null) return node
  if (typeof node === 'string') {
    if (parentKey && looksLikeDateTime(node)) {
      return formatFieldDateTime(parentKey, node)
    }
    return node
  }
  if (Array.isArray(node)) {
    return node.map((item) => walk(item, parentKey))
  }
  if (typeof node === 'object') {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
      out[k] = walk(v, k)
    }
    return out
  }
  return node
}
