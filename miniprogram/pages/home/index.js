const { request } = require('../../utils/request')
const auth = require('../../utils/auth')
const { normalizeUser } = require('../../utils/user')
const routes = require('../../utils/routes')
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
    return this.loadBootstrap({ silent, force }).catch(() =>
      Promise.all([
        this.loadBanners({ silent, force }),
        this.loadAnnouncements({ force }),
        this.loadStores({ silent, force }),
        this.loadUser({ force }),
        this.loadCardCount({ force }),
      ])
    )
  },

  _applyAnnouncementPopup(items) {
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
  },

  async _applyBannersFromRaw(raw, carousel) {
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
  },

  loadBootstrap(options = {}) {
    const { force = false } = options
    const { getUserLocation, isLocationDenied, formatDistance } = require('../../utils/location')
    const { resolveStoreList } = require('../../utils/media')
    const hasBanners = this.data.banners.length > 0
    const hasStores = this.data.stores.length > 0

    if (!hasBanners) {
      this.setData({ bannerReady: false, bannersLoading: true })
    }
    if (!hasStores) {
      this.setData({ storesLoading: true })
    }

    this._storeFetchToken = (this._storeFetchToken || 0) + 1
    const token = this._storeFetchToken

    const applyBootstrap = async (data, hint = '') => {
      if (token !== this._storeFetchToken) return

      this._applyAnnouncementPopup(data.announcements?.items || [])

      const carousel = data.banners?.carousel || this.data.carousel
      await this._applyBannersFromRaw(data.banners?.items || [], carousel)

      if (token !== this._storeFetchToken) return
      const list = await resolveStoreList(data.stores || [])
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

      if (data.user) {
        auth.syncAppUser(data.user)
        const normalized = await normalizeUser(data.user)
        const avatar_url = normalized.avatar_url || ''
        this.setData({
          user: { ...normalized, avatar_url },
          cardCount: data.card_count || 0,
        })
      } else {
        this.setData({ user: null, cardCount: 0 })
      }
    }

    const fetchBootstrap = (query = '') =>
      request({ url: `/home/bootstrap${query}`, silent: true, force })

    const fetchWithoutLocation = (hint) =>
      fetchBootstrap('')
        .then((data) => applyBootstrap(data, hint))
        .catch(() => {
          if (token !== this._storeFetchToken) return Promise.reject(new Error('bootstrap failed'))
          if (!this.data.stores.length) {
            this.setData({ stores: [], storesLoading: false, locationHint: hint || '加载门店失败' })
          } else {
            this.setData({ storesLoading: false })
          }
          if (!this.data.banners.length) {
            this.setData({ bannersLoading: false, bannerReady: false })
          } else {
            this.setData({ bannersLoading: false })
          }
          return Promise.reject(new Error('bootstrap failed'))
        })

    const fetchWithLocation = () =>
      getUserLocation()
        .then(({ latitude, longitude }) =>
          fetchBootstrap(`?latitude=${latitude}&longitude=${longitude}`)
        )
        .then((data) => applyBootstrap(data, ''))
        .catch(async () => {
          if (token !== this._storeFetchToken) return Promise.reject(new Error('bootstrap failed'))
          const denied = await isLocationDenied()
          return fetchWithoutLocation(denied ? '开启定位查看距离' : '定位失败，点击重试')
        })

    return isLocationDenied().then((denied) => {
      if (token !== this._storeFetchToken) return
      if (denied) {
        return fetchWithoutLocation('开启定位查看距离')
      }
      return fetchWithLocation()
    })
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

  loadAnnouncements(options = {}) {
    const { force = false } = options
    return request({ url: '/home/announcements', silent: true, force })
      .then((data) => this._applyAnnouncementPopup(data.items || []))
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
    const { force = false } = options
    const hasBanners = this.data.banners.length > 0

    if (!hasBanners) {
      this.setData({ bannerReady: false, bannersLoading: true })
    }

    return request({ url: '/home/banners', silent: true, force })
      .then(async (data) => {
        const carousel = data.carousel || this.data.carousel
        await this._applyBannersFromRaw(data.items || [], carousel)
      })
      .catch(() => {
        if (!this.data.banners.length) {
          this.setData({ banners: [], showBanners: false, heroHeight: 520, bannersLoading: false })
        } else {
          this.setData({ bannersLoading: false })
        }
      })
  },

  loadUser(options = {}) {
    const { force = false } = options
    if (!auth.isLoggedIn()) {
      this.setData({ user: null, cardCount: 0 })
      return Promise.resolve()
    }
    return request({ url: '/user/profile', silent: true, force })
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

  loadCardCount(options = {}) {
    const { force = false } = options
    if (!auth.isLoggedIn()) {
      this.setData({ cardCount: 0 })
      return Promise.resolve()
    }
    return request({ url: '/user/cards', silent: true, force })
      .then((cards) => this.setData({ cardCount: (cards || []).length }))
      .catch(() => this.setData({ cardCount: 0 }))
  },

  loadStores(options = {}) {
    const { force = false } = options
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
      return request({ url: '/store/list', silent: true, force })
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
            force,
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
          if (ok) this.refreshHome({ force: true })
        })
        return
      }
      this.refreshHome({ force: true })
    })
  },

  goStore(e) {
    const id = e.detail?.id ?? e.currentTarget.dataset.id
    const bookingUrl = `${routes.bookingIndex}?storeId=${id}`
    if (!auth.requireLogin(bookingUrl)) return
    wx.navigateTo({ url: bookingUrl })
  },

  goNearestStore() {
    const { stores } = this.data
    const storeId = stores && stores[0] ? stores[0].id : ''
    const bookingUrl = storeId ? `${routes.bookingIndex}?storeId=${storeId}` : routes.profileLogin

    if (!auth.isLoggedIn()) {
      auth.goLogin(storeId ? bookingUrl : '')
      return
    }

    if (!storeId) {
      wx.showToast({ title: '正在获取门店…', icon: 'none' })
      this.refreshHome({ force: true })
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
    wx.navigateTo({ url: `${routes.exchangeIndex}?platform=meituan` })
  },

  goPackages() {
    wx.switchTab({ url: '/pages/packages/index' })
  },

  goReport() {
    wx.switchTab({ url: '/pages/report/index' })
  },

  goCoupons() {
    wx.navigateTo({ url: routes.profileCoupons })
  },

  goWallet() {
    wx.navigateTo({ url: routes.profileWallet })
  },

  goPoints() {
    wx.navigateTo({ url: routes.profilePoints })
  },

  goOrders() {
    wx.navigateTo({ url: routes.profileOrders })
  },

  goInvite() {
    wx.navigateTo({ url: routes.profileInvite })
  },

  goCheckin() {
    wx.switchTab({ url: '/pages/checkin/index' })
  },

  goProfile() {
    wx.switchTab({ url: '/pages/profile/index' })
  },
})
