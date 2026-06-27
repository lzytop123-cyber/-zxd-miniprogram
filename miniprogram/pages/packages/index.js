const auth = require('../../utils/auth')
const { request } = require('../../utils/request')
const {
  PKG_CATEGORY_TABS,
  formatCard,
  isCardUsable,
  enrichPackage,
  filterPackages,
  buildCardDetail,
  buildPackageDetail,
} = require('../../utils/cardDisplay')

Page({
  data: {
    loggedIn: false,
    cards: [],
    activeCount: 0,
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

  onShow() {
    this.setData({ loggedIn: auth.isLoggedIn() })
    this.loadCards()
    this.ensureBuyLoaded()
  },

  loadCards() {
    if (!auth.isLoggedIn()) {
      this.setData({ cards: [], activeCount: 0, loggedIn: false })
      return
    }
    request({ url: '/user/cards', silent: true })
      .then((cards) => {
        const list = (cards || []).filter(isCardUsable).map(formatCard)
        this.setData({ cards: list, activeCount: list.length, loggedIn: true })
      })
      .catch(() => this.setData({ cards: [], activeCount: 0 }))
  },

  ensureBuyLoaded() {
    if (this.data.buyLoaded && this.data.stores.length) return
    this.loadStores()
  },

  loadStores() {
    request({ url: '/store/list', silent: true })
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
        if (store?.id) this.loadPackages(store.id)
      })
      .catch(() => wx.showToast({ title: '加载门店失败', icon: 'none' }))
  },

  onStoreChange(e) {
    const idx = Number(e.detail.value)
    const store = this.data.stores[idx]
    if (!store) return
    this.setData({ storeId: store.id, storeName: store.name, activeCategory: 'all' })
    this.loadPackages(store.id)
  },

  loadPackages(storeId) {
    this.setData({ loading: true, packages: [], displayPackages: [] })
    request({ url: `/card/packages?store_id=${storeId}`, silent: true })
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
        wx.showToast({ title: '加载套餐失败', icon: 'none' })
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
    this.setData({ detailVisible: false, detail: null })
  },

  noop() {},

  goExchange() {
    wx.navigateTo({ url: '/pages/exchange/index?platform=meituan' })
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
      if (wp && wp.package && String(wp.package).includes('mock_prepay')) {
        await request({ url: `/card/purchase/${res.order_no}/mock`, method: 'POST' })
      } else if (wp) {
        await new Promise((resolve, reject) => {
          wx.requestPayment({
            timeStamp: wp.timeStamp,
            nonceStr: wp.nonceStr,
            package: wp.package,
            signType: wp.signType || 'RSA',
            paySign: wp.paySign,
            success: resolve,
            fail: (err) => reject(new Error(err.errMsg || '支付取消')),
          })
        })
      }

      wx.hideLoading()
      wx.showModal({
        title: '购买成功',
        content: `已购买：${res.label || '期限卡'}`,
        showCancel: false,
        success: () => this.loadCards(),
      })
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.detail || err.message || '购买失败', icon: 'none' })
    } finally {
      this.setData({ buying: false })
    }
  },
})
