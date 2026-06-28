/** GET 请求内存缓存 + 并发去重 */

const DEFAULT_TTL = {
  '/user/cards': 60 * 1000,
  '/user/profile': 60 * 1000,
  '/store/list': 120 * 1000,
  '/home/banners': 180 * 1000,
  '/home/announcements': 120 * 1000,
  '/home/bootstrap': 120 * 1000,
  '/report/summary': 60 * 1000,
  '/report/leaderboard': 60 * 1000,
  '/assistant/intro': 300 * 1000,
  '/reservation/active/list': 15 * 1000,
}

const memory = new Map()
const inflight = new Map()

function buildKey(method, url, data) {
  const payload = data === undefined ? '' : JSON.stringify(data)
  return `${method.toUpperCase()}:${url}:${payload}`
}

function resolveTtl(url, method, options = {}) {
  if (options.force) return 0
  if (options.cacheTtl != null) return Math.max(0, options.cacheTtl)
  if (method.toUpperCase() !== 'GET') return 0
  const path = url.split('?')[0]
  if (DEFAULT_TTL[path] != null) return DEFAULT_TTL[path]
  if (path.startsWith('/card/packages')) return 120 * 1000
  if (/\/store\/\d+\/pricing$/.test(path)) return 300 * 1000
  return 0
}

function getCached(key) {
  const hit = memory.get(key)
  if (!hit) return null
  if (hit.expiresAt <= Date.now()) {
    memory.delete(key)
    return null
  }
  return hit.data
}

function setCached(key, data, ttl) {
  if (!ttl) return
  memory.set(key, { data, expiresAt: Date.now() + ttl })
}

function invalidate(match) {
  if (!match) {
    memory.clear()
    return
  }
  const needle = String(match)
  for (const key of memory.keys()) {
    if (key.includes(needle)) memory.delete(key)
  }
}

function runDeduped(key, ttl, runner) {
  if (ttl > 0) {
    const cached = getCached(key)
    if (cached !== null) return Promise.resolve(cached)
  }

  if (inflight.has(key)) {
    return inflight.get(key)
  }

  const promise = runner()
    .then((data) => {
      setCached(key, data, ttl)
      return data
    })
    .finally(() => {
      inflight.delete(key)
    })

  inflight.set(key, promise)
  return promise
}

module.exports = {
  buildKey,
  resolveTtl,
  runDeduped,
  invalidate,
  clear: () => memory.clear(),
}
