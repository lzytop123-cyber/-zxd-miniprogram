/**
 * 后台时间：统一按北京时间展示。
 * 后端所有时间戳（含 created_at/updated_at）均由应用层 datetime.now() 写入，
 * 已经是北京时间的墙钟值，不是 UTC，因此不做任何时区换算，只统一格式。
 */

const DATETIME_RE = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?/

export function looksLikeDateTime(value: string): boolean {
  return DATETIME_RE.test(String(value).trim())
}

/** 墙钟时间：只统一格式（去掉 T/毫秒/Z），不做时区换算 */
export function formatWallClock(value?: string | null): string {
  if (!value) return '-'
  return String(value)
    .trim()
    .replace('T', ' ')
    .replace(/\.\d+/, '')
    .replace(/Z$/i, '')
    .slice(0, 19)
}

/** 保留原函数名以兼容既有调用方，行为等同 formatWallClock */
export function formatDateTime(value?: string | null): string {
  return formatWallClock(value)
}

export function formatFieldDateTime(_key: string, value: string): string {
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
