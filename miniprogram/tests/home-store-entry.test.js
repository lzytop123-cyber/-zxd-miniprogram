const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

test('study booking opens the dedicated store page', () => {
  let definition
  const filename = path.join(__dirname, '../pages/home/index.js')
  const calls = []
  const stubs = {
    '../../utils/request': { request() {} },
    '../../utils/auth': {},
    '../../utils/user': { normalizeUser() {} },
    '../../utils/routes': { storeSelect: '/pages/store/select' },
    '../../utils/tabbar': { handleTabScroll() {} },
    '../../utils/features': { syncTabBar() {}, setFeatures() {}, isMarketplaceEnabled: () => false },
    '../../utils/share': { enableShareMenu() {}, savePendingInvite() {}, shareAppMessage() {}, shareTimeline() {} },
  }
  vm.runInNewContext(fs.readFileSync(filename, 'utf8'), {
    Page(value) { definition = value },
    require(id) { return stubs[id] },
    wx: {
      navigateTo: ({ url }) => calls.push(url),
      pageScrollTo: () => calls.push('scrolled'),
    },
    Promise,
    Date,
    Set,
  }, { filename })

  definition.goSelectStore()

  assert.deepEqual(calls, ['/pages/store/select'])
})

test('opening home requests location for store distance', async () => {
  let definition
  const filename = path.join(__dirname, '../pages/home/index.js')
  const urls = []
  const stubs = {
    '../../utils/request': {
      request: async ({ url }) => {
        urls.push(url)
        return { stores: [], banners: { items: [] }, announcements: { items: [] } }
      },
    },
    '../../utils/auth': {},
    '../../utils/user': { normalizeUser() {} },
    '../../utils/routes': {},
    '../../utils/tabbar': { handleTabScroll() {} },
    '../../utils/features': { syncTabBar() {}, setFeatures() {}, isMarketplaceEnabled: () => false },
    '../../utils/share': { enableShareMenu() {}, savePendingInvite() {}, shareAppMessage() {}, shareTimeline() {} },
    '../../utils/location': {
      getUserLocation: async () => ({ latitude: 30.1, longitude: 120.2 }),
      isLocationDenied: async () => false,
      formatDistance: () => '',
    },
    '../../utils/media': { resolveStoreList: (stores) => stores || [] },
  }
  vm.runInNewContext(fs.readFileSync(filename, 'utf8'), {
    Page(value) { definition = value },
    require(id) {
      if (!(id in stubs)) throw new Error(`Missing test stub: ${id}`)
      return stubs[id]
    },
    wx: { getStorageSync: () => null },
    Promise,
    Date,
    Set,
  }, { filename })
  const page = {
    ...definition,
    data: { ...definition.data },
    setData(patch) { Object.assign(this.data, patch) },
  }

  await page.loadBootstrap()

  assert.equal(page.data.storesLoading, false)
  assert.ok(urls.some((url) => url.includes('latitude=30.1') && url.includes('longitude=120.2')))
})
