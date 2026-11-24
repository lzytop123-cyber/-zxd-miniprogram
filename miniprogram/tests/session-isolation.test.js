const test = require('node:test')
const assert = require('node:assert/strict')

function setup() {
  for (const name of ['../utils/request', '../utils/requestCache', '../utils/auth']) delete require.cache[require.resolve(name)]
  const storage = new Map([['token', 'A']])
  const pending = []
  global.wx = {
    getStorageSync: (key) => storage.get(key),
    setStorageSync: (key, value) => storage.set(key, value),
    removeStorageSync: (key) => storage.delete(key),
    request: (options) => pending.push(options),
    showToast() {},
  }
  const app = { globalData: {} }
  global.getApp = () => app
  const { request } = require('../utils/request')
  const auth = require('../utils/auth')
  return { storage, pending, request, auth, app }
}
function succeed(req, owner) { req.success({ statusCode: 200, data: { code: 0, data: { owner } } }) }

test('late profile normalization cannot restore a logged-out user', async () => {
  const { auth, app, storage } = setup()
  auth.syncAppUser({ id: 'A', nickname: 'A' })
  auth.logout()
  await Promise.resolve()
  assert.equal(app.globalData.user, null)
  assert.equal(storage.get('userInfo'), undefined)
})

test('logout clears cached exchange records before another user opens them', async () => {
  const { request, auth, storage, pending } = setup()
  const first = request({ url: '/exchange/records' })
  succeed(pending[0], 'A'); await first
  auth.logout(); storage.set('token', 'B')
  const second = request({ url: '/exchange/records' })
  assert.equal(pending.length, 2)
  succeed(pending[1], 'B')
  assert.deepEqual(await second, { owner: 'B' })
})

test('old inflight success cannot resolve into or populate the next session', async () => {
  const { request, auth, storage, pending } = setup()
  const old = request({ url: '/user/wallet' })
  const rejected = assert.rejects(old, { code: 'SESSION_CHANGED' })
  auth.logout(); storage.set('token', 'B')
  const fresh = request({ url: '/user/wallet' })
  assert.equal(pending.length, 2)
  succeed(pending[0], 'A'); await rejected
  // An old finally must not detach B's inflight request.
  const same = request({ url: '/user/wallet' })
  assert.equal(pending.length, 2)
  succeed(pending[1], 'B')
  assert.deepEqual(await fresh, { owner: 'B' })
  assert.deepEqual(await same, { owner: 'B' })
  assert.deepEqual(await request({ url: '/user/wallet' }), { owner: 'B' })
})

test('old 401 and network retry cannot clear or send requests with a new token', async () => {
  const { request, storage, pending } = setup()
  const old401 = request({ url: '/user/profile', force: true })
  const oldRetry = request({ url: '/user/wallet', force: true })
  const checks = [assert.rejects(old401, { code: 'SESSION_CHANGED' }), assert.rejects(oldRetry, { code: 'SESSION_CHANGED' })]
  storage.set('token', 'B')
  pending[0].success({ statusCode: 401, data: { detail: 'expired' } })
  pending[1].fail({ errMsg: 'network error' })
  await Promise.all(checks)
  assert.equal(storage.get('token'), 'B')
  assert.equal(pending.length, 2)
})

test('invalidation detaches inflight and prevents its late result from replacing fresh cache', { timeout: 1000 }, async () => {
  const cache = require('../utils/requestCache')
  cache.invalidate()
  let done
  const key = cache.buildKey('GET', '/report/summary')
  const old = cache.runDeduped(key, 60000, () => new Promise(resolve => { done = resolve }))
  cache.invalidate('/report/')
  assert.deepEqual(await cache.runDeduped(key, 60000, async () => ({ owner: 'B' })), { owner: 'B' })
  done({ owner: 'A' }); await old
  assert.deepEqual(await cache.runDeduped(key, 60000, async () => ({ owner: 'unexpected' })), { owner: 'B' })
})
