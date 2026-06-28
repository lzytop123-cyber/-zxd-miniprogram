/** 解析后台分页响应（兼容 data 为 PageResult 或直接数组） */
export function parsePageResult(res: { data?: unknown }) {
  const d = res?.data
  if (Array.isArray(d)) {
    return { items: d, total: d.length }
  }
  if (d && typeof d === 'object' && 'items' in d) {
    const page = d as { items?: unknown[]; total?: number }
    return {
      items: Array.isArray(page.items) ? page.items : [],
      total: page.total ?? (Array.isArray(page.items) ? page.items.length : 0),
    }
  }
  return { items: [], total: 0 }
}
