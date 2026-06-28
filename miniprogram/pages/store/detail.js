const { request } = require('../../utils/request')
const auth = require('../../utils/auth')
const routes = require('../../utils/routes')

Page({
  data: { store: null, storeId: null, canNavigate: false },

  onLoad(options) {
    this.setData({ storeId: options.id })
  },

  onShow() {
    this.loadStore({ silent: true })
  },

  onPullDownRefresh() {
    this.loadStore({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  loadStore(options = {}) {
    const { force = false } = options
    const storeId = this.data.storeId
    if (!storeId) return Promise.resolve()

    const { resolveStoreList } = require('../../utils/media')
    const { hasStoreCoords } = require('../../utils/location')

    return request({ url: `/store/${storeId}`, silent: true, force })
      .then(async (store) => {
        const list = await resolveStoreList([store])
        const item = list[0] || store
        this.setData({
          store: item,
          canNavigate: hasStoreCoords(item),
        })
      })
      .catch(() => {})
  },

  openNavigation() {
    const { openStoreNavigation } = require('../../utils/location')
    openStoreNavigation(this.data.store).catch(() => {})
  },

  goBooking() {
    const url = `${routes.bookingIndex}?storeId=${this.data.storeId}`
    if (!auth.requireLogin(url)) return
    wx.navigateTo({ url })
  },
})
