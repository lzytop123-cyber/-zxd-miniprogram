const { request } = require('../../utils/request')
const auth = require('../../utils/auth')
const { normalizeUser } = require('../../utils/user')
const TAB_PAGES = [
  '/pages/home/index',
  '/pages/packages/index',
  '/pages/checkin/index',
  '/pages/report/index',
  '/pages/profile/index',
]

Page({
  data: {
    stores: [],
    user: null,
    banners: [],
    showBanners: false,
    carousel: {
      autoplay: true,
      interval: 5000,
      circular: true,
      indicator_dots: true,
      hero_height: 680,
      hero_mode: 'fullscreen',
    },
    heroHeight: 680,
    cardCount: 0,
  },

  onShow() {
    this.loadBanners()
    this.loadStores()
    this.loadUser()
    this.loadCardCount()
  },

  loadBanners() {
    const { resolveBannerImages } = require('../../utils/media')
    request({ url: '/home/banners', silent: true })
      .then(async (data) => {
        const raw = data.items || []
        const banners = await resolveBannerImages(raw)
        const carousel = data.carousel || this.data.carousel
        const heroHeight = carousel.hero_height || 680
        this.setData({
          banners,
          showBanners: banners.length > 0,
          carousel,
          heroHeight,
        })
      })
      .catch(() => {
        this.setData({ banners: [], showBanners: false, heroHeight: 520 })
      })
  },

  loadUser() {
    if (!auth.isLoggedIn()) {
      this.setData({ user: null, cardCount: 0 })
      return
    }
    request({ url: '/user/profile', silent: true })
      .then(async (user) => {
        auth.syncAppUser(user)
        const normalized = await normalizeUser(user)
        const avatar_url = normalized.avatar_url || ''
        this.setData({ user: { ...normalized, avatar_url } })
      })
      .catch(() => {
        this.setData({ user: null, cardCount: 0 })
      })
  },

  loadCardCount() {
    if (!auth.isLoggedIn()) {
      this.setData({ cardCount: 0 })
      return
    }
    request({ url: '/user/cards', silent: true })
      .then((cards) => this.setData({ cardCount: (cards || []).length }))
      .catch(() => this.setData({ cardCount: 0 }))
  },

  loadStores() {
    const { resolveStoreList } = require('../../utils/media')
    const applyStores = async (stores) => {
      const list = await resolveStoreList(stores)
      this.setData({ stores: list || [] })
    }

    const fetchList = (query = '') =>
      request({ url: `/store/list${query}`, silent: true })
        .then(applyStores)
        .catch(() => applyStores([]))

    // 默认不带定位，避免一进首页就弹出位置授权
    fetchList()

    // 仅当用户此前已授权时，静默刷新距离排序（不再弹窗）
    wx.getSetting({
      success: (res) => {
        if (!res.authSetting['scope.userLocation']) return
        wx.getLocation({
          type: 'gcj02',
          success: ({ latitude, longitude }) => {
            fetchList(`?latitude=${latitude}&longitude=${longitude}`)
          },
        })
      },
    })
  },

  goStore(e) {
    const id = e.detail?.id ?? e.currentTarget.dataset.id
    const bookingUrl = `/pages/booking/index?storeId=${id}`
    if (!auth.requireLogin(bookingUrl)) return
    wx.navigateTo({ url: bookingUrl })
  },

  goNearestStore() {
    const { stores } = this.data
    const storeId = stores && stores[0] ? stores[0].id : ''
    const bookingUrl = storeId ? `/pages/booking/index?storeId=${storeId}` : '/pages/profile/login'

    if (!auth.isLoggedIn()) {
      auth.goLogin(storeId ? bookingUrl : '')
      return
    }

    if (!storeId) {
      wx.showToast({ title: '正在获取门店…', icon: 'none' })
      this.loadStores()
      return
    }

    wx.navigateTo({ url: bookingUrl })
  },

  onCampaignTap(e) {
    const idx = Number(e.currentTarget.dataset.index)
    const item = this.data.banners[idx]
    if (!item) return

    const { link_path: linkPath, cta_text: ctaText, layout_type: layoutType } = item
    if (linkPath) {
      const url = linkPath.startsWith('/') ? linkPath : `/${linkPath}`
      const base = url.split('?')[0]
      if (TAB_PAGES.includes(base)) {
        wx.switchTab({ url: base })
      } else {
        wx.navigateTo({ url })
      }
      return
    }
    if (layoutType === 'image') return
    if (ctaText) {
      this.goNearestStore()
    }
  },

  goExchange() {
    wx.navigateTo({ url: '/pages/exchange/index?platform=meituan' })
  },

  goPackages() {
    wx.switchTab({ url: '/pages/packages/index' })
  },

  goReport() {
    wx.switchTab({ url: '/pages/report/index' })
  },

  goCoupons() {
    wx.navigateTo({ url: '/pages/profile/coupons' })
  },

  goWallet() {
    wx.navigateTo({ url: '/pages/profile/wallet' })
  },

  goPoints() {
    wx.navigateTo({ url: '/pages/profile/points' })
  },

  goOrders() {
    wx.navigateTo({ url: '/pages/profile/orders' })
  },

  goInvite() {
    wx.navigateTo({ url: '/pages/profile/invite' })
  },

  goCheckin() {
    wx.switchTab({ url: '/pages/checkin/index' })
  },

  goProfile() {
    wx.switchTab({ url: '/pages/profile/index' })
  },
})
