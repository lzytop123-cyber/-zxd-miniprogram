const auth = require('../../utils/auth')
const { request, invalidateCache, formatRequestError } = require('../../utils/request')
const routes = require('../../utils/routes')
const { completeWechatPay, ensureCardPurchasePaid } = require('../../utils/pay')
const { handleTabScroll } = require('../../utils/tabbar')
const { syncTabBar } = require('../../utils/features')
const { enableShareMenu, shareAppMessage, shareTimeline } = require('../../utils/share')
const {
  PKG_CATEGORY_TABS,
  formatCard,
  isCardUsable,
  enrichPackage,
  filterPackages,
  buildCardDetail,
  buildPackageDetail,
  cardBillTypeForBooking,
} = require('../../utils/cardDisplay')

Page({
  data: {
    loggedIn: false,
    cards: [],
    activeCount: 0,
    detailCard: null,
    myCardsSheetVisible: false,
    stores: [],
    storeId: null,
    storeName: '',
    packages: [],
    displayPackages: [],
    categoryTabs: PKG_CATEGORY_TABS,
    activeCategory: 'all',
    loading: false,
    buying: false,
    detailVisible: false,
    detail: null,
    buyLoaded: false,
  },

  onShareAppMessage() {
    return shareAppMessage({ title: '知行岛自习空间 · 套餐选购' })
  },

  onShareTimeline() {
    return shareTimeline({ title: '知行岛自习空间 · 套餐选购' })
  },

  onShow() {
    enableShareMenu()
    syncTabBar(this, '/pages/packages/index')
    this._tabbarLastTop = 0
    this.setData({ loggedIn: auth.isLoggedIn() })
    this.refreshPage({ silent: true })
  },

  onPageScroll(e) {
    handleTabScroll(this, e.scrollTop)
  },

  onPullDownRefresh() {
    this.refreshPage({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  refreshPage(options = {}) {
    const { force = false, silent = false } = options
    this.loadCards({ force, silent })
    return this.ensureBuyLoaded({ force, silent })
  },

  loadCards(options = {}) {
    const { force = false } = options
    if (!auth.isLoggedIn()) {
      this.setData({ cards: [], activeCount: 0, loggedIn: false })
      return Promise.resolve()
    }
    if (force) invalidateCache('/user/cards')
    return request({ url: '/user/cards', silent: true, force })
      .then((cards) => {
        const list = (cards || []).filter(isCardUsable).map(formatCard)
        this.setData({ cards: list, activeCount: list.length, loggedIn: true })
      })
      .catch(() => {
        if (!this.data.cards.length) {
          this.setData({ cards: [], activeCount: 0 })
        }
      })
  },

  ensureBuyLoaded(options = {}) {
    const { force = false, silent = false } = options
    if (!force && this.data.buyLoaded && this.data.stores.length) {
      if (this.data.storeId) {
        return this.loadPackages(this.data.storeId, { silent: true })
      }
      return Promise.resolve()
    }
    return this.loadStores({ force, silent })
  },

  loadStores(options = {}) {
    const { force = false, silent = false } = options
    const hasStores = this.data.stores.length > 0
    return request({ url: '/store/list', silent: true, force })
      .then((stores) => {
        const list = stores || []
        const storeId = this.data.storeId || list[0]?.id || null
        const store = list.find((s) => s.id === storeId) || list[0]
        this.setData({
          stores: list,
          storeId: store?.id || null,
          storeName: store?.name || '',
          buyLoaded: true,
        })
        if (store?.id) return this.loadPackages(store.id, { force, silent: silent || hasStores })
      })
      .catch(() => {
        if (!hasStores) wx.showToast({ title: '加载门店失败', icon: 'none' })
      })
  },

  onStoreChange(e) {
    const idx = Number(e.detail.value)
    const store = this.data.stores[idx]
    if (!store) return
    this.setData({ storeId: store.id, storeName: store.name, activeCategory: 'all' })
    this.loadPackages(store.id, { force: true })
  },

  loadPackages(storeId, options = {}) {
    const { force = false, silent = false } = options
    const hasPackages = this.data.packages.length > 0 && this.data.storeId === storeId
    if (!hasPackages || force) {
      if (!silent || !hasPackages) {
        this.setData({ loading: !hasPackages, packages: hasPackages ? this.data.packages : [], displayPackages: hasPackages ? this.data.displayPackages : [] })
      }
    }
    return request({ url: `/card/packages?store_id=${storeId}`, silent: true, force })
      .then((data) => {
        const packages = (data.items || []).map(enrichPackage)
        this.setData({
          packages,
          displayPackages: filterPackages(packages, this.data.activeCategory),
          storeName: data.store_name || this.data.storeName,
          loading: false,
        })
      })
      .catch(() => {
        this.setData({ loading: false })
        if (!hasPackages) wx.showToast({ title: '加载套餐失败', icon: 'none' })
      })
  },

  switchCategory(e) {
    const key = e.currentTarget.dataset.key
    if (key === this.data.activeCategory) return
    this.setData({
      activeCategory: key,
      displayPackages: filterPackages(this.data.packages, key),
    })
  },

  openMyCardsSheet() {
    if (!auth.isLoggedIn()) {
      auth.goLogin('/pages/packages/index')
      return
    }
    this.setData({ myCardsSheetVisible: true, detailVisible: false })
  },

  closeMyCardsSheet() {
    this.setData({ myCardsSheetVisible: false })
  },

  showCardDetail(e) {
    const idx = Number(e.currentTarget.dataset.index)
    const card = this.data.cards[idx]
    if (!card) return
    this.setData({
      myCardsSheetVisible: false,
      detailVisible: true,
      detailCard: card,
      detail: buildCardDetail(card),
    })
  },

  showPackageDetail(e) {
    const idx = Number(e.currentTarget.dataset.index)
    const pkg = this.data.displayPackages[idx]
    if (!pkg) return
    this.setData({ detailVisible: true, detail: buildPackageDetail(pkg) })
  },

  closeDetail() {
    this.setData({ detailVisible: false, detail: null, detailCard: null })
  },

  goBookWithCard() {
    const card = this.data.detailCard
    const storeId = this.data.storeId
    if (!card || !storeId) {
      wx.showToast({ title: '请先选择门店', icon: 'none' })
      return
    }
    const billType = cardBillTypeForBooking(card)
    if (!billType) {
      wx.showToast({ title: '该卡暂不支持在线预约', icon: 'none' })
      return
    }
    wx.setStorageSync('pendingBooking', { storeId, billType })
    invalidateCache('/user/cards')
    this.setData({ detailVisible: false, detail: null, detailCard: null })
    wx.navigateTo({ url: `${routes.bookingIndex}?storeId=${storeId}&billType=${billType}` })
  },

  noop() {},

  goExchange() {
    wx.navigateTo({ url: routes.exchangeIndex })
  },

  goLogin() {
    auth.goLogin('/pages/packages/index')
  },

  buy(e) {
    const billType = e?.currentTarget?.dataset?.type || this.data.detail?.bill_type
    if (!billType) return
    if (!auth.requireLogin('/pages/packages/index')) return
    this.doPurchase(billType)
  },

  buyFromDetail() {
    const billType = this.data.detail?.bill_type
    if (!billType) return
    if (!auth.requireLogin('/pages/packages/index')) return
    this.closeDetail()
    this.doPurchase(billType)
  },

  async doPurchase(billType) {
    const { storeId, buying } = this.data
    if (buying || !storeId || !billType) return

    this.setData({ buying: true })
    wx.showLoading({ title: '提交订单...' })
    try {
      const res = await request({
        url: '/card/purchase',
        method: 'POST',
        data: { store_id: storeId, bill_type: billType, pay_type: 'wechat' },
      })

      const wp = res.wechat_pay
      await completeWechatPay(wp, () =>
        request({ url: `/card/purchase/${res.order_no}/mock`, method: 'POST' })
      )
      const confirmed = await ensureCardPurchasePaid(res.order_no, wp)

      wx.hideLoading()
      invalidateCache('/user/cards')
      wx.showModal({
        title: '购买成功',
        content: `已购买：${(confirmed && confirmed.card_name) || res.label || '期限卡'}`,
        showCancel: false,
        success: () => this.loadCards({ force: true }),
      })
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: formatRequestError(err) || '购买失败', icon: 'none' })
    } finally {
      this.setData({ buying: false })
    }
  },
})
