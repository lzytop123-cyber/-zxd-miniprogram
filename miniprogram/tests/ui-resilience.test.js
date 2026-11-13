const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const ROOT = path.resolve(__dirname, '..')

function loadPage(relativePath, stubs, wx = {}) {
  let definition
  const filename = path.join(ROOT, relativePath)
  const context = {
    Page(value) { definition = value },
    require(id) {
      if (!(id in stubs)) throw new Error(`Missing test stub: ${id}`)
      return stubs[id]
    },
    wx,
    console,
    Date,
    Promise,
    Set,
    clearInterval,
    clearTimeout,
    decodeURIComponent,
    encodeURIComponent,
    setInterval,
    setTimeout,
  }
  vm.runInNewContext(fs.readFileSync(filename, 'utf8'), context, { filename })
  return definition
}

function pageInstance(definition, data = {}) {
  return {
    ...definition,
    data: { ...definition.data, ...data },
    setData(patch, callback) {
      Object.assign(this.data, patch)
      if (callback) callback()
    },
  }
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((ok, fail) => {
    resolve = ok
    reject = fail
  })
  return { promise, resolve, reject }
}

function contrastRatio(foreground, background) {
  const luminance = (hex) => {
    const channels = hex.slice(1).match(/.{2}/g).map((value) => parseInt(value, 16) / 255)
    const linear = channels.map((value) => (
      value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
    ))
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
  }
  const first = luminance(foreground)
  const second = luminance(background)
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05)
}

function orderStubs(request) {
  return {
    '../../utils/request': { request, formatRequestError: (error) => error.message, invalidateCache() {} },
    '../../utils/seat-layout': { getLayout: () => ({ seatDisplay: () => ({ mapLabel: '08', zoneName: '标准区' }) }) },
    '../../utils/cardDisplay': {
      dailyPassDays: () => 1,
      isOfficeNightMonthlyCard: () => false,
      OFFICE_NIGHT_BOOKING_HINT: '',
      cardValidUntil: () => '',
      withinCardValidity: () => true,
      weeklyPassDays: () => 7,
      monthlyPassDays: () => 30,
      quarterlyPassDays: () => 90,
      officeNightPassDays: () => 30,
    },
    '../../utils/pay': {
      completeWechatPay: async () => {},
      ensureReservationPaid: async () => {},
      isPayCancelled: () => false,
    },
  }
}

test('switching from a period card to WeChat refreshes the displayed price', async () => {
  const calls = []
  const request = async (options) => {
    calls.push(options)
    return { final_price: 88, discount_price: 12, original_price: 100 }
  }
  const definition = loadPage('pages/booking/order.js', orderStubs(request))
  const page = pageInstance(definition, {
    payType: 'period_card',
    originalPrice: 100,
    price: 0,
    storeId: 1,
    seatId: 8,
    startTime: '2026-09-21 08:00:00',
    endTime: '2026-09-21 10:00:00',
  })

  await page.setPay({ currentTarget: { dataset: { type: 'wechat' } } })

  assert.equal(page.data.payType, 'wechat')
  assert.equal(page.data.price, 88)
  assert.equal(page.data.priceLoading, false)
  assert.equal(calls.filter((call) => call.url === '/reservation/preview').length, 1)
})

test('an expired selected card falls back to WeChat with a fresh price', async () => {
  const calls = []
  const request = async (options) => {
    calls.push(options)
    if (options.url === '/user/cards' || options.url === '/user/coupons') return []
    return { final_price: 68, discount_price: 0, original_price: 68 }
  }
  const definition = loadPage('pages/booking/order.js', orderStubs(request))
  const page = pageInstance(definition, {
    payType: 'period_card',
    selectedCardId: 9,
    selectedCardName: '月卡',
    originalPrice: 68,
    price: 0,
    storeId: 1,
    seatId: 8,
    startTime: '2026-09-21 08:00:00',
    endTime: '2026-09-21 10:00:00',
  })

  await page.loadPayOptions({ force: true })

  assert.equal(page.data.payType, 'wechat')
  assert.equal(page.data.price, 68)
  assert.equal(calls.filter((call) => call.url === '/reservation/preview').length, 1)
})

test('the confirmation page keeps the store name from booking context', () => {
  const definition = loadPage('pages/booking/order.js', orderStubs(async () => []))
  const page = pageInstance(definition)

  page.onLoad({
    storeId: '1',
    storeName: encodeURIComponent('知行岛东城店'),
    start: encodeURIComponent('2026-09-21 08:00:00'),
    end: encodeURIComponent('2026-09-21 10:00:00'),
    seatId: '8',
    seatCode: 'A08',
    price: '100',
    billType: 'hourly',
  })

  assert.equal(page.data.storeName, '知行岛东城店')
})

test('a failed active-order request is not represented as an empty order list', async () => {
  let navigatedTo = ''
  const definition = loadPage('pages/checkin/index.js', {
    '../../utils/request': { request: async () => { throw new Error('offline') } },
    '../../utils/auth': {},
    '../../utils/routes': { profileContact: '/packageProfile/pages/profile/contact' },
    '../../utils/tabbar': { handleTabScroll() {} },
    '../../utils/features': { syncTabBar() {} },
    '../../utils/share': { enableShareMenu() {}, shareAppMessage() {}, shareTimeline() {} },
    '../../utils/bleUnlock': { computeCanOpen: () => false, getOpenWindowHint: () => '', mapBleOpenFailure: () => ({ content: '' }) },
  }, { navigateTo: ({ url }) => { navigatedTo = url } })
  const page = pageInstance(definition)

  await page.loadActive({ force: true })

  assert.equal(page.data.pageLoading, false)
  assert.match(page.data.loadError, /加载失败/)
  page.goContact()
  assert.equal(navigatedTo, '/packageProfile/pages/profile/contact')
})

const bookingExtraStubs = {
  '../../utils/seat-map-image': {
    buildImageMarkers: () => [],
    seatDisplayImage: () => ({ mapLabel: '', zoneName: '', seatCode: '' }),
  },
  '../../config': { resolveStaticUrl: (url) => url },
}

test('a failed seat refresh clears stale availability and exposes retry state', async () => {
  const request = async () => { throw new Error('offline') }
  const definition = loadPage('pages/booking/index.js', {
    '../../utils/request': { request, formatRequestError: () => '网络连接失败' },
    '../../utils/auth': {},
    '../../utils/routes': {},
    '../../utils/seat-layout': { getLayout: () => ({}) },
    ...bookingExtraStubs,
    './utils/debounce': { debounce: (fn) => fn },
    '../../utils/cardDisplay': {
      dailyPassDays: () => 1, isOfficeNightMonthlyCard: () => false, isCardUsable: () => false,
      cardValidUntil: () => '', officeNightPassDays: () => 30, monthlyPassDays: () => 30,
      weeklyPassDays: () => 7, quarterlyPassDays: () => 90, periodPassSpan: () => 1,
      formatPassDurationLabel: () => '', periodPassRuleText: () => '', formatCard: (x) => x,
      cardValidityHint: () => '', OFFICE_NIGHT_USAGE_RULE: '', OFFICE_NIGHT_BOOKING_HINT: '',
    },
    '../../utils/storeHours': {
      STORE_HOURS_LABEL: '07:00-23:00', defaultHourlyStartClock: () => '08:00',
      validateStoreTimeRange: () => {}, clampHourlyClocks: (x) => x,
      STORE_OPEN: { start: '07:00', end: '23:00' }, compareClock: () => 0,
      storeRangeDateTimes: () => ({}), nightRangeDateTimes: () => ({}),
      clockRangeDateTimes: () => ({}), defaultDailyClocks: () => ({}),
    },
    './utils/datetime': {
      formatLocalDateTime: () => '', todayStr: () => '2026-09-21', addDays: (x) => x,
      combineDateTime: () => new Date(), nowTimeStr: () => '08:00', pad: (x) => String(x),
    },
  })
  const page = pageInstance(definition, {
    storeId: 1,
    seats: [{ id: 9, status: 'available', map_slot: 9 }],
    seatId: 9,
    selectedId: 9,
    selectedLabel: '09',
    selectedZone: '标准区',
  })
  page._layout = { applySeats: (seats) => seats }
  page._hasSeatAvailability = () => true

  page.data.seatMapReady = false
  await page.loadSeats('2026-09-21 08:00:00', '2026-09-21 10:00:00', { force: true })
  assert.equal(page.data.seatId, 9, 'availability must wait for the store map mode')
  page.data.seatMapReady = true

  await page.loadSeats('2026-09-21 08:00:00', '2026-09-21 10:00:00', { force: true })

  assert.deepEqual(JSON.parse(JSON.stringify(page.data.seats)), [])
  assert.equal(page.data.seatId, null)
  assert.match(page.data.seatLoadError, /重新加载/)
})

test('a late booking preview cannot overwrite a newer time range', async () => {
  const first = deferred()
  const second = deferred()
  let requestCount = 0
  const definition = loadPage('pages/booking/index.js', {
    '../../utils/request': {
      request: () => (++requestCount === 1 ? first.promise : second.promise),
      formatRequestError: (error) => error.message,
    },
    '../../utils/auth': {}, '../../utils/routes': {}, '../../utils/seat-layout': { getLayout: () => ({}) },
    ...bookingExtraStubs,
    './utils/debounce': { debounce: (fn) => fn },
    '../../utils/cardDisplay': {
      dailyPassDays: () => 1, isOfficeNightMonthlyCard: () => false, isCardUsable: () => false,
      cardValidUntil: () => '', officeNightPassDays: () => 30, monthlyPassDays: () => 30,
      weeklyPassDays: () => 7, quarterlyPassDays: () => 90, periodPassSpan: () => 1,
      formatPassDurationLabel: () => '', periodPassRuleText: () => '', formatCard: (x) => x,
      cardValidityHint: () => '', OFFICE_NIGHT_USAGE_RULE: '', OFFICE_NIGHT_BOOKING_HINT: '',
    },
    '../../utils/storeHours': {
      STORE_HOURS_LABEL: '', defaultHourlyStartClock: () => '08:00', validateStoreTimeRange: () => {},
      clampHourlyClocks: (x) => x, STORE_OPEN: { start: '07:00', end: '23:00' }, compareClock: () => 0,
      storeRangeDateTimes: () => ({}), nightRangeDateTimes: () => ({}), clockRangeDateTimes: () => ({}), defaultDailyClocks: () => ({}),
    },
    './utils/datetime': { formatLocalDateTime: () => '', todayStr: () => '2026-09-21', addDays: (x) => x, combineDateTime: () => new Date(), nowTimeStr: () => '08:00', pad: (x) => String(x) },
  })
  const page = pageInstance(definition, { storeId: 1, billType: 'hourly', seatId: 3 })
  const ranges = [
    { start: '2026-09-21 08:00:00', end: '2026-09-21 10:00:00' },
    { start: '2026-09-21 10:00:00', end: '2026-09-21 12:00:00' },
  ]
  page._calcTimes = () => ranges.shift()
  page._formatSummary = (start, end) => `${start}-${end}`
  page.loadSeats = () => Promise.resolve()

  const oldPreview = page._doRefreshPreview()
  const currentPreview = page._doRefreshPreview()
  second.resolve({ seat_id: 3, start_time: '2026-09-21 10:00:00', end_time: '2026-09-21 12:00:00', final_price: 200 })
  await currentPreview
  first.resolve({ seat_id: 3, start_time: '2026-09-21 08:00:00', end_time: '2026-09-21 10:00:00', final_price: 100 })
  await oldPreview

  assert.equal(page.data.preview.final_price, 200)
  assert.equal(page.data.startTime, '2026-09-21 10:00:00')
})

test('available seats are grouped by zone for the one-handed list picker', () => {
  const definition = loadPage('pages/booking/index.js', {
    '../../utils/request': { request: async () => [], formatRequestError: (error) => error.message },
    '../../utils/auth': {}, '../../utils/routes': {}, '../../utils/seat-layout': { getLayout: () => ({}) },
    ...bookingExtraStubs,
    './utils/debounce': { debounce: (fn) => fn },
    '../../utils/cardDisplay': {
      dailyPassDays: () => 1, isOfficeNightMonthlyCard: () => false, isCardUsable: () => false,
      cardValidUntil: () => '', officeNightPassDays: () => 30, monthlyPassDays: () => 30,
      weeklyPassDays: () => 7, quarterlyPassDays: () => 90, periodPassSpan: () => 1,
      formatPassDurationLabel: () => '', periodPassRuleText: () => '', formatCard: (x) => x,
      cardValidityHint: () => '', OFFICE_NIGHT_USAGE_RULE: '', OFFICE_NIGHT_BOOKING_HINT: '',
    },
    '../../utils/storeHours': {
      STORE_HOURS_LABEL: '', defaultHourlyStartClock: () => '08:00', validateStoreTimeRange: () => {},
      clampHourlyClocks: (x) => x, STORE_OPEN: { start: '07:00', end: '23:00' }, compareClock: () => 0,
      storeRangeDateTimes: () => ({}), nightRangeDateTimes: () => ({}), clockRangeDateTimes: () => ({}), defaultDailyClocks: () => ({}),
    },
    './utils/datetime': { formatLocalDateTime: () => '', todayStr: () => '2026-09-21', addDays: (x) => x, combineDateTime: () => new Date(), nowTimeStr: () => '08:00', pad: (x) => String(x) },
  })
  const page = pageInstance(definition)
  page._layout = { seatDisplay: (seat) => ({ mapLabel: seat.map_label, zoneName: seat.zone }) }

  const groups = page.buildSeatGroups([
    { id: 1, status: 'available', map_label: '01', zone: '沉浸区 A' },
    { id: 2, status: 'reserved', map_label: '02', zone: '沉浸区 A' },
    { id: 3, status: 'available', map_label: '03', zone: '标准区' },
  ])

  assert.deepEqual(JSON.parse(JSON.stringify(groups)), [
    { name: '沉浸区 A', seats: [{ id: 1, label: '01', status: 'available' }] },
    { name: '标准区', seats: [{ id: 3, label: '03', status: 'available' }] },
  ])

  page.data.seats = [{ id: 3, seat_code: 'A03', status: 'available' }]
  page.data.seatTipDismissed = true
  page.refreshPreview = () => Promise.resolve()
  page.selectSeat({
    currentTarget: { dataset: { id: 3, code: 'A03', status: 'available' } },
  })
  assert.equal(page.data.seatId, 3)
  assert.equal(page.data.seatCode, 'A03')
})

test('changing stores does not leave packages from the previous store visible after failure', async () => {
  const definition = loadPage('pages/packages/index.js', {
    '../../utils/auth': { isLoggedIn: () => true },
    '../../utils/request': { request: async () => { throw new Error('offline') }, invalidateCache() {}, formatRequestError: () => '网络连接失败' },
    '../../utils/routes': {},
    '../../utils/pay': { completeWechatPay() {}, ensureCardPurchasePaid() {}, isPayCancelled: () => false, isPayBanned: () => false },
    '../../utils/tabbar': { handleTabScroll() {} },
    '../../utils/features': { syncTabBar() {} },
    '../../utils/share': { enableShareMenu() {}, shareAppMessage() {}, shareTimeline() {} },
    '../../utils/subscribe': { requestCardExpireSubscribe() {} },
    '../../utils/cardDisplay': { PKG_CATEGORY_TABS: [], enrichPackage: (x) => x, filterPackages: (x) => x, buildPackageDetail: (x) => x },
  }, { showToast() {} })
  const page = pageInstance(definition, {
    stores: [{ id: 1, name: '一店' }, { id: 2, name: '二店' }],
    storeId: 1,
    packages: [{ pricing_rule_id: 1 }],
    displayPackages: [{ pricing_rule_id: 1 }],
  })

  await page.onStoreChange({ detail: { value: 1 } })

  assert.equal(page.data.storeId, 2)
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.displayPackages)), [])
  assert.match(page.data.loadError, /加载失败/)
})

test('a late package response cannot replace the currently selected store', async () => {
  const first = deferred()
  const second = deferred()
  const definition = loadPage('pages/packages/index.js', {
    '../../utils/auth': { isLoggedIn: () => true },
    '../../utils/request': {
      request: ({ url }) => url.includes('store_id=1') ? first.promise : second.promise,
      invalidateCache() {}, formatRequestError: () => '',
    },
    '../../utils/routes': {},
    '../../utils/pay': { completeWechatPay() {}, ensureCardPurchasePaid() {}, isPayCancelled: () => false, isPayBanned: () => false },
    '../../utils/tabbar': { handleTabScroll() {} },
    '../../utils/features': { syncTabBar() {} },
    '../../utils/share': { enableShareMenu() {}, shareAppMessage() {}, shareTimeline() {} },
    '../../utils/subscribe': { requestCardExpireSubscribe() {} },
    '../../utils/cardDisplay': { PKG_CATEGORY_TABS: [], enrichPackage: (x) => x, filterPackages: (x) => x, buildPackageDetail: (x) => x },
  })
  const page = pageInstance(definition, { storeId: 1 })

  const oldLoad = page.loadPackages(1, { force: true })
  page.setData({ storeId: 2 })
  const currentLoad = page.loadPackages(2, { force: true })
  second.resolve({ items: [{ pricing_rule_id: 2 }], store_name: '二店' })
  await currentLoad
  first.resolve({ items: [{ pricing_rule_id: 1 }], store_name: '一店' })
  await oldLoad

  assert.equal(page.data.storeId, 2)
  assert.equal(page.data.displayPackages[0].pricing_rule_id, 2)
})

test('a late active-order failure cannot replace a newer successful refresh', async () => {
  const first = deferred()
  const second = deferred()
  let call = 0
  const definition = loadPage('pages/checkin/index.js', {
    '../../utils/request': { request: () => (++call === 1 ? first.promise : second.promise) },
    '../../utils/auth': {}, '../../utils/routes': {},
    '../../utils/tabbar': { handleTabScroll() {} }, '../../utils/features': { syncTabBar() {} },
    '../../utils/share': { enableShareMenu() {}, shareAppMessage() {}, shareTimeline() {} },
    '../../utils/bleUnlock': { computeCanOpen: () => false, getOpenWindowHint: () => '', mapBleOpenFailure: () => ({ content: '' }) },
  })
  const page = pageInstance(definition)

  const oldLoad = page.loadActive({ force: true })
  const currentLoad = page.loadActive({ force: true })
  second.resolve([])
  await currentLoad
  first.reject(new Error('offline'))
  await oldLoad

  assert.equal(page.data.loadError, '')
  assert.equal(page.data.pageLoading, false)
})

test('a failed report request is shown as an error instead of an empty report', async () => {
  const definition = loadPage('pages/report/index.js', {
    '../../utils/request': { request: async () => { throw new Error('offline') } },
    '../../utils/tabbar': { handleTabScroll() {} },
    '../../utils/features': { syncTabBar() {}, isStudyAssistantEnabled: () => true, leaveStudyAssistantIfDisabled() {} },
    '../../utils/share': { enableShareMenu() {}, shareAppMessage() {}, shareTimeline() {} },
    '../../config': { resolveStaticUrl: (url) => url },
    '../../utils/media': { resolveImageForDisplay: async (url) => url },
    '../../utils/routes': {},
  })
  const page = pageInstance(definition)

  await page.load({ force: true })

  assert.equal(page.data.reportLoading, false)
  assert.match(page.data.reportError, /加载失败/)
})

test('a failed store lookup never labels the global leaderboard as the local store', async () => {
  const calls = []
  const definition = loadPage('pages/report/index.js', {
    '../../utils/request': { request: async (options) => { calls.push(options.url); throw new Error('offline') } },
    '../../utils/tabbar': { handleTabScroll() {} },
    '../../utils/features': { syncTabBar() {}, isStudyAssistantEnabled: () => true, leaveStudyAssistantIfDisabled() {} },
    '../../utils/share': { enableShareMenu() {}, shareAppMessage() {}, shareTimeline() {} },
    '../../config': { resolveStaticUrl: (url) => url },
    '../../utils/media': { resolveImageForDisplay: async (url) => url },
    '../../utils/routes': {},
  })
  const page = pageInstance(definition, { leaderboard: [{ user_id: 1 }] })

  await page.onScopeChange({ detail: { value: 1 } })

  assert.deepEqual(calls, ['/store/list'])
  assert.equal(page.data.scopeLabel, '本店')
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.leaderboard)), [])
  assert.match(page.data.reportError, /本店/)
})

test('global navigation and secondary text colors meet WCAG AA contrast', () => {
  const appConfig = JSON.parse(fs.readFileSync(path.join(ROOT, 'app.json'), 'utf8'))
  const styles = fs.readFileSync(path.join(ROOT, 'app.wxss'), 'utf8')
  const secondary = styles.match(/--neutral-700:\s*(#[0-9A-F]{6})/i)[1]

  assert.ok(contrastRatio(appConfig.window.navigationBarBackgroundColor, '#FFFFFF') >= 4.5)
  assert.ok(contrastRatio(appConfig.tabBar.color, '#FFFFFF') >= 4.5)
  assert.ok(contrastRatio(appConfig.tabBar.selectedColor, '#FFFFFF') >= 4.5)
  assert.ok(contrastRatio(secondary, '#FFFFFF') >= 4.5)
})
