const { request, formatRequestError } = require('../../utils/request')
const auth = require('../../utils/auth')
const routes = require('../../utils/routes')

Page({
  data: { store: null, storeId: null, canNavigate: false, loading: true, loadError: '' },

  onLoad(options) {
    this.setData({ storeId: options.id })
  },

  onShow() {
    this.loadStore({ silent: true })
  },

  onPullDownRefresh() {
    this.loadStore({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  retryLoad() {
    return this.loadStore({ force: true })
  },

  loadStore(options = {}) {
    const { force = false } = options
    const storeId = this.data.storeId
    if (!storeId) return Promise.resolve()

    const { resolveStoreList } = require('../../utils/media')
    const { hasStoreCoords } = require('../../utils/location')
    this.setData({ loading: !this.data.store, loadError: '' })

    return request({ url: `/store/${storeId}`, silent: true, force })
      .then(async (store) => {
        const list = await resolveStoreList([store])
        const item = list[0] || store
        this.setData({
          store: item,
          canNavigate: hasStoreCoords(item),
          loading: false,
          loadError: '',
        })
      })
      .catch((err) => {
        this.setData({
          loading: false,
          loadError: formatRequestError(err) || '门店信息加载失败，请检查网络后重试',
        })
      })
  },

  openNavigation() {
    const { openStoreNavigation } = require('../../utils/location')
    openStoreNavigation(this.data.store).catch(() => {})
  },

  goBooking() {
    try {
      if (this.data.storeId) wx.setStorageSync('lastSelectedStoreId', Number(this.data.storeId))
    } catch (_) {}
    const url = `${routes.bookingIndex}?storeId=${this.data.storeId}`
    if (!auth.requireLogin(url)) return
    wx.navigateTo({ url })
  },
})
