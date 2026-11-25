const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const axios = require('axios')
const { parse, compileScript } = require('@vue/compiler-sfc')
function storage() {
  const values = new Map()
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, String(value)), removeItem: key => values.delete(key) }
}
function setup() {
  const localStorage = storage(), sessionStorage = storage(), redirects = [], messages = []
  const modules = new Map()
  function load(file) {
    if (modules.has(file)) return modules.get(file).exports
    const module = { exports: {} }; modules.set(file, module)
    let source = fs.readFileSync(file, 'utf8').replace('import.meta.env.VITE_API_BASE', "'/api'")
    if (file.endsWith('.vue')) source = compileScript(parse(source).descriptor, { id: 'test' }).content
    const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
    vm.runInNewContext(js, { module, exports: module.exports, localStorage, sessionStorage,
      window: { location: { pathname: '/dashboard', replace: url => redirects.push(url) } },
      require: name => {
        if (name === 'vue-router') return { useRouter: () => ({ push: url => redirects.push(url) }), useRoute: () => ({ query: {} }) }
        if (name === 'element-plus') return { ElMessage: { error: value => messages.push(value), success: value => messages.push(value) }, ElMessageBox: { confirm: async () => true } }
        if (name === 'vue') return { ...require('vue'), onMounted() {}, onUnmounted() {} }
        return name.startsWith('.') ? load(path.resolve(path.dirname(file), name + '.ts')) : require(name)
      },
    }, { filename: file })
    return module.exports
  }
  const auth = load(path.resolve(__dirname, '../src/utils/adminAuth.ts'))
  return { localStorage, sessionStorage, redirects, auth, load, messages }
}
const profile = { token: 'token-A', username: 'manager', role: 'store', store_id: 7, permissions: ['seats'] }
test('unremembered login is tab scoped and clears any remembered identity', () => {
  const { auth, localStorage, sessionStorage } = setup()
  auth.saveAdminSession({ ...profile, token: 'old' })
  auth.saveAdminSession(profile, false)
  assert.equal(localStorage.getItem('admin_token'), null)
  assert.equal(sessionStorage.getItem('admin_token'), 'token-A')
  assert.equal(auth.getAdminToken(), 'token-A')
  assert.equal(auth.getAdminStoreId(), 7)
  assert.equal(auth.canAccessPath('/seats'), true)
  assert.equal(auth.canAccessPath('/admins'), false)
  auth.clearAdminSession()
  assert.equal(sessionStorage.getItem('admin_token'), null)
  assert.equal(auth.getAdminToken(), null)
})
test('remembered login removes previous tab identity', () => {
  const { auth, localStorage, sessionStorage } = setup()
  auth.saveAdminSession(profile, false)
  assert.equal(sessionStorage.getItem('admin_token'), 'token-A')
  auth.saveAdminSession({ ...profile, token: 'token-B' }, true)
  assert.equal(sessionStorage.getItem('admin_token'), null)
  assert.equal(localStorage.getItem('admin_token'), 'token-B')
})
test('submitting the login form honors the unchecked remember option', async () => {
  const { load, localStorage, sessionStorage, redirects } = setup()
  const previousAdapter = axios.defaults.adapter
  axios.defaults.adapter = async config => ({ config, status: 200, data: { code: 0, data: profile } })
  try {
    const page = load(path.resolve(__dirname, '../src/views/Login.vue')).default.setup({}, { expose() {} })
    page.form.username = 'manager'
    page.form.password = 'test-only-password'
    page.remember.value = false
    await page.onSubmit()
    assert.equal(localStorage.getItem('admin_token'), null)
    assert.equal(sessionStorage.getItem('admin_token'), 'token-A')
    assert.deepEqual(redirects, ['/dashboard'])
  } finally { axios.defaults.adapter = previousAdapter }
})
test('401 clears the active session and navigates to login', async () => {
  const { auth, load, redirects, localStorage, sessionStorage } = setup()
  auth.saveAdminSession(profile, false)
  const previousAdapter = axios.defaults.adapter
  axios.defaults.adapter = async config => { throw { config, response: { status: 401 } } }
  try {
    const http = load(path.resolve(__dirname, '../src/api/http.ts')).default
    await assert.rejects(http.get('/admin/me'))
    assert.equal(localStorage.getItem('admin_token'), null)
    assert.equal(sessionStorage.getItem('admin_token'), null)
    assert.deepEqual(redirects, ['/login'])
  } finally { axios.defaults.adapter = previousAdapter }
})
test('a late 401 from an old identity preserves the new session', async () => {
  const { auth, load, redirects, localStorage, sessionStorage } = setup()
  auth.saveAdminSession(profile)
  const previousAdapter = axios.defaults.adapter
  let rejectRequest
  axios.defaults.adapter = config => new Promise((resolve, reject) => { rejectRequest = () => reject({ config, response: { status: 401 } }) })
  try {
    const http = load(path.resolve(__dirname, '../src/api/http.ts')).default
    const request = http.get('/admin/me')
    await new Promise(resolve => setImmediate(resolve))
    auth.saveAdminSession({ ...profile, token: 'token-B' }, false)
    rejectRequest(); await assert.rejects(request)
    assert.equal(sessionStorage.getItem('admin_token') || localStorage.getItem('admin_token'), 'token-B')
    assert.deepEqual(redirects, [])
  } finally { axios.defaults.adapter = previousAdapter }
})

test('pending refund retries the cancellation endpoint and refreshes the orders', async () => {
  const { load } = setup()
  const previousAdapter = axios.defaults.adapter
  const requests = []
  axios.defaults.adapter = async config => {
    requests.push(config.url)
    return { config, status: 200, data: { code: 0, data: { items: [{ id: 42, refund_state: 'wechat_confirmed' }], total: 1 } } }
  }
  try {
    const component = load(path.resolve(__dirname, '../src/views/Reservations.vue')).default
    const page = component.setup({}, { expose() {} })
    assert.equal(typeof page.retryRefund, 'function')
    await page.retryRefund({ id: 42, order_no: 'ORDER-42', status: 3, pay_type: 'wechat', pay_status: 1, refund_state: 'pending' })
    assert.deepEqual(requests, ['/admin/reservations/42/cancel', '/admin/reservations'])
    assert.equal(page.list.value[0].refund_state, 'wechat_confirmed')
  } finally { axios.defaults.adapter = previousAdapter }
})

test('a 503 retry keeps the pending order visible for another attempt', async () => {
  const { load, messages } = setup()
  const previousAdapter = axios.defaults.adapter
  axios.defaults.adapter = async config => { throw { config, response: { status: 503, data: { detail: '退款待确认' } } } }
  try {
    const component = load(path.resolve(__dirname, '../src/views/Reservations.vue')).default
    const page = component.setup({}, { expose() {} })
    assert.equal(typeof page.retryRefund, 'function')
    page.list.value = [{ id: 42, order_no: 'ORDER-42', status: 3, pay_type: 'wechat', pay_status: 1, refund_state: 'pending' }]
    await page.retryRefund(page.list.value[0])
    assert.equal(page.list.value[0].refund_state, 'pending')
    assert.deepEqual(messages, ['退款待确认'])
  } finally { axios.defaults.adapter = previousAdapter }
})
