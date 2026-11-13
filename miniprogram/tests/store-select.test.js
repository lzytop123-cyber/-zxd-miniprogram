const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const stores = [
  { id: 1, name: '知行岛自习室（千峰南路店）', address: '千峰南路 10 号', latitude: 37.8, longitude: 112.5, distance: 1.2, status: 1, cover_images: ['https://example.com/1.jpg'] },
  { id: 2, name: '知行岛自习室（理工大店）', address: '理工大街 20 号', latitude: 37.7, longitude: 112.6, distance: 3.4, status: 1, cover_images: ['https://example.com/2.jpg'] },
]

function loadPage(wx, request = async () => stores, denied = true, auth = { requireLogin: () => true }) {
  let definition
  const filename = path.join(__dirname, '../pages/store/select.js')
  const stubs = {
    '../../utils/request': { request },
    '../../utils/auth': auth,
    '../../utils/routes': { bookingIndex: '/pages/booking/index' },
    '../../utils/location': {
      isLocationDenied: async () => denied,
      getUserLocation: async () => ({ latitude: 37, longitude: 112 }),
      formatDistance: (value) => value == null ? '' : `${value}km`,
      openStoreNavigation: async (store) => { wx.mapOpened = store.id },
      openLocationSettings: async () => true,
    },
    '../../utils/media': { resolveStoreList: async (items) => items },
  }
  vm.runInNewContext(fs.readFileSync(filename, 'utf8'), {
    Page(value) { definition = value },
    require(id) {
      if (!(id in stubs)) throw new Error(`Missing test stub: ${id}`)
      return stubs[id]
    },
    wx,
    Promise,
    console,
  }, { filename })
  return {
    ...definition,
    data: { ...definition.data },
    setData(patch) { Object.assign(this.data, patch) },
  }
}

test('the store page shows the nearby stores with their original details', async () => {
  const page = loadPage({ getStorageSync: () => 2 }, async () => stores, false)

  await page.loadStores()

  assert.equal(page.data.stores[0].id, 1)
  assert.equal(page.data.stores[0].name, '知行岛自习室（千峰南路店）')
  assert.equal(page.data.stores[0].address, '千峰南路 10 号')
  assert.equal(page.data.stores[0].distanceLabel, '1.2km')
  assert.equal(page.data.stores[0].cover_images[0], 'https://example.com/1.jpg')
})

test('selecting an original store card opens that store booking page', async () => {
  const calls = []
  const page = loadPage({
    getStorageSync: () => null,
    navigateTo: ({ url }) => calls.push(`navigate:${url}`),
  })
  await page.loadStores()

  page.selectStore({ detail: { id: 2 } })

  assert.deepEqual(calls, ['navigate:/pages/booking/index?storeId=2'])
})
