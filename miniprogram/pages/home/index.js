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

const BANNER_CACHE_KEY = 'home_banners_v4'
const ANNOUNCE_SEEN_KEY = 'announce_seen_v1'

function bannerSignature(items) {
  return (items || [])
    .map((b) => `${b.id || ''}:${b.image_url || ''}:${b.updated_at || ''}`)
    .join('|')
}

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
    announcements: [],
    popupAnnouncement: null,
    showAnnouncementPopup: false,
    bannerReady: false,
    swiperKey: 0,
  },

  onLoad() {
    this._hydrateBannerCache()
  },

  onShow() {
    this.refreshHome({ silent: true })
  },

  onPullDownRefresh() {
    this.refreshHome({ force: true }).finally(() => {
      wx.stopPullDownRefresh()
    })
  },

  refreshHome(options = {}) {
    const { silent = false, force = false } = options
    return Promise.all([
      this.loadBanners({ silent, force }),
      this.loadAnnouncements(),
      this.loadStores({ silent, force }),
      this.loadUser(),
      this.loadCardCount(),
    ])
  },

  _hydrateBannerCache() {
    try {
      const cached = wx.getStorageSync(BANNER_CACHE_KEY)
      if (!cached) return

      const carousel = cached.carousel || this.data.carousel
      const heroHeight = carousel.hero_height || 680
      this.setData({ carousel, heroHeight })

      if (!cached.items?.length) return

      const { prepareBannerItems } = require('../../utils/media')
      this.setData({
        banners: prepareBannerItems(cached.items),
        showBanners: true,
        bannerReady: true,
        bannersLoading: false,
      })
      this._bannerSignature = bannerSignature(cached.items)
    } catch (e) {
      // ignore
    }
  },

  loadAnnouncements() {
    return request({ url: '/home/announcements', silent: true })
      .then((data) => {
        const items = data.items || []
        this.setData({ announcements: items })
        if (!items.length) return
        const popup = items.find((a) => a.popup_once) || items[0]
        if (popup.popup_once) {
          try {
            const seen = wx.getStorageSync(ANNOUNCE_SEEN_KEY) || []
            if (seen.includes(popup.id)) return
          } catch (e) {
            // ignore
          }
        }
        this.setData({ popupAnnouncement: popup, showAnnouncementPopup: true })
      })
      .catch(() => {})
  },

  closeAnnouncement() {
    const item = this.data.popupAnnouncement
    if (item && item.popup_once) {
      try {
        const seen = wx.getStorageSync(ANNOUNCE_SEEN_KEY) || []
        if (!seen.includes(item.id)) {
          wx.setStorageSync(ANNOUNCE_SEEN_KEY, [...seen, item.id])
        }
      } catch (e) {
        // ignore
      }
    }
    this.setData({ showAnnouncementPopup: false })
  },

  onAnnouncementBarTap() {
    const item = this.data.announcements[0]
    if (!item) return
    if (item.link_path) {
      const url = item.link_path.startsWith('/') ? item.link_path : `/${item.link_path}`
      const base = url.split('?')[0]
      if (TAB_PAGES.includes(base)) {
        wx.switchTab({ url: base })
      } else {
        wx.navigateTo({ url })
      }
      return
    }
    this.setData({ popupAnnouncement: item, showAnnouncementPopup: true })
  },

  loadBanners(options = {}) {
    const hasBanners = this.data.banners.length > 0

    if (!hasBanners) {
      this.setData({ bannerReady: false, bannersLoading: true })
    }

    return request({ url: '/home/banners', silent: true })
      .then(async (data) => {
        const raw = data.items || []
        const carousel = data.carousel || this.data.carousel
        const heroHeight = carousel.hero_height || 680
        const nextSig = bannerSignature(raw)

        if (!raw.length) {
          this.setData({
            banners: [],
            showBanners: false,
            bannersLoading: false,
            bannerReady: false,
            carousel,
            heroHeight,
          })
          this._bannerSignature = nextSig
          return
        }

        const { resolveBannerImages } = require('../../utils/media')
        const resolved = await resolveBannerImages(raw)
        const patch = {
          banners: resolved,
          showBanners: true,
          bannersLoading: false,
          bannerReady: true,
          carousel,
          heroHeight,
        }
        if (nextSig !== this._bannerSignature) {
          patch.swiperKey = Date.now()
          this._bannerSignature = nextSig
        }
        this.setData(patch)
        try {
          wx.setStorageSync(BANNER_CACHE_KEY, { items: raw, carousel })
        } catch (e) {
          // ignore
        }
      })
      .catch(() => {
        if (!this.data.banners.length) {
          this.setData({ banners: [], showBanners: false, heroHeight: 520, bannersLoading: false })
        } else {
          this.setData({ bannersLoading: false })
        }
      })
  },

  loadUser() {
    if (!auth.isLoggedIn()) {
      this.setData({ user: null, cardCount: 0 })
      return Promise.resolve()
    }
    return request({ url: '/user/profile', silent: true })
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
      return Promise.resolve()
    }
    return request({ url: '/user/cards', silent: true })
      .then((cards) => this.setData({ cardCount: (cards || []).length }))
      .catch(() => this.setData({ cardCount: 0 }))
  },

  loadStores(options = {}) {
    const hasStores = this.data.stores.length > 0
    const { resolveStoreList } = require('../../utils/media')
    const { getUserLocation, isLocationDenied, formatDistance } = require('../../utils/location')

    this._storeFetchToken = (this._storeFetchToken || 0) + 1
    const token = this._storeFetchToken

    if (!hasStores) {
      this.setData({ storesLoading: true })
    }

    const finishList = async (stores, hint) => {
      if (token !== this._storeFetchToken) return
      const list = await resolveStoreList(stores || [])
      if (token !== this._storeFetchToken) return
      const withDistance = list.map((s) => ({
        ...s,
        distanceLabel: formatDistance(s.distance),
      }))
      this.setData({
        stores: withDistance,
        storesLoading: false,
        locationHint: hint || '',
      })
    }

    const fetchWithoutLocation = (hint) => {
      return request({ url: '/store/list', silent: true })
        .then((stores) => finishList(stores, hint))
        .catch(() => {
          if (token !== this._storeFetchToken) return
          if (!this.data.stores.length) {
            this.setData({ stores: [], storesLoading: false, locationHint: hint || '加载门店失败' })
          } else {
            this.setData({ storesLoading: false })
          }
        })
    }

    const fetchWithLocation = () => {
      return getUserLocation()
        .then(({ latitude, longitude }) =>
          request({
            url: `/store/list?latitude=${latitude}&longitude=${longitude}`,
            silent: true,
          })
        )
        .then((stores) => finishList(stores, ''))
        .catch(async () => {
          if (token !== this._storeFetchToken) return
          const denied = await isLocationDenied()
          return fetchWithoutLocation(denied ? '开启定位查看距离' : '定位失败，点击重试')
        })
    }

    return isLocationDenied().then((denied) => {
      if (token !== this._storeFetchToken) return
      if (denied) {
        return fetchWithoutLocation('开启定位查看距离')
      }
      return fetchWithLocation()
    })
  },

  openLocationSetting() {
    const { isLocationDenied, openLocationSettings } = require('../../utils/location')
    isLocationDenied().then((denied) => {
      if (denied) {
        openLocationSettings().then((ok) => {
          if (ok) this.loadStores({ force: true })
        })
        return
      }
      this.loadStores({ force: true })
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
      this.loadStores({ force: true })
      return
    }

    wx.navigateTo({ url: bookingUrl })
  },

  onBannerImageError(e) {
    const idx = Number(e.currentTarget.dataset.index)
    const item = this.data.banners[idx]
    if (!item || !item._remote_url || item._imageRetried) return
    const { resolveBannerImageUrl } = require('../../utils/media')
    resolveBannerImageUrl(item._remote_url).then((path) => {
      if (!path || path === item.image_url) return
      this.setData({
        [`banners[${idx}].image_url`]: path,
        [`banners[${idx}]._imageRetried`]: true,
      })
    })
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
