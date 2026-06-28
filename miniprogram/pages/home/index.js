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

const BANNER_CACHE_KEY = 'home_banners_v1'

Page({
  data: {
    stores: [],
    user: null,
    banners: [],
    showBanners: false,
    bannersLoading: true,
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
    storesLoading: true,
    locationHint: '',
  },

  onLoad() {
    try {
      const cached = wx.getStorageSync(BANNER_CACHE_KEY)
      if (cached?.items?.length) {
        const carousel = cached.carousel || this.data.carousel
        this.setData({
          banners: cached.items,
          showBanners: true,
          bannersLoading: false,
          carousel,
          heroHeight: carousel.hero_height || 680,
        })
      }
    } catch (e) {
      // ignore
    }
  },

  onShow() {
    this.loadBanners()
    this.loadStores()
    this.loadUser()
    this.loadCardCount()
  },

  loadBanners() {
    const { resolveBannerImages, prepareBannerItems } = require('../../utils/media')
    request({ url: '/home/banners', silent: true })
      .then(async (data) => {
        const raw = data.items || []
        const carousel = data.carousel || this.data.carousel
        const heroHeight = carousel.hero_height || 680
        const prepared = prepareBannerItems(raw)

        if (prepared.length) {
          this.setData({
            banners: prepared,
            showBanners: true,
            bannersLoading: false,
            carousel,
            heroHeight,
          })
          try {
            wx.setStorageSync(BANNER_CACHE_KEY, { items: prepared, carousel })
          } catch (e) {
            // ignore
          }
        } else {
          this.setData({
            banners: [],
            showBanners: false,
            bannersLoading: false,
            carousel,
            heroHeight,
          })
        }

        const resolved = await resolveBannerImages(raw)
        if (resolved.length) {
          this.setData({
            banners: resolved,
            showBanners: true,
            carousel,
            heroHeight,
          })
          try {
            wx.setStorageSync(BANNER_CACHE_KEY, { items: resolved, carousel })
          } catch (e) {
            // ignore
          }
        }
      })
      .catch(() => {
        if (!this.data.banners.length) {
          this.setData({ banners: [], showBanners: false, heroHeight: 520 })
        }
        this.setData({ bannersLoading: false })
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
    this.setData({ storesLoading: true })

    const applyStores = async (stores) => {
      const list = await resolveStoreList(stores)
      this.setData({ stores: list || [], storesLoading: false })
    }

    const fetchList = (query = '') =>
      request({ url: `/store/list${query}`, silent: true })
        .then(applyStores)
        .catch(() => {
          this.setData({ stores: [], storesLoading: false })
        })

    fetchList()

    wx.getSetting({
      success: (res) => {
        const authSetting = res.authSetting['scope.userLocation']
        if (authSetting === true) {
          this.setData({ locationHint: '' })
          wx.getLocation({
            type: 'gcj02',
            success: ({ latitude, longitude }) => {
              fetchList(`?latitude=${latitude}&longitude=${longitude}`)
            },
            fail: () => {
              this.setData({ locationHint: '定位失败，暂无法显示距离' })
            },
          })
          return
        }
        if (authSetting === false) {
          this.setData({ locationHint: '开启定位查看距离' })
          return
        }
        this.setData({ locationHint: '开启定位查看距离' })
      },
      fail: () => {
        this.setData({ locationHint: '开启定位查看距离' })
      },
    })
  },

  openLocationSetting() {
    wx.openSetting({
      success: (res) => {
        if (res.authSetting['scope.userLocation']) {
          this.loadStores()
        }
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
