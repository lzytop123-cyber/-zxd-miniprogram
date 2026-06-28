const { request } = require('../../utils/request')
const auth = require('../../utils/auth')
const routes = require('../../utils/routes')

Page({
  data: { store: null, storeId: null, canNavigate: false },

  onLoad(options) {
    const { resolveStoreList } = require('../../utils/media')
    const { hasStoreCoords } = require('../../utils/location')
    this.setData({ storeId: options.id })
    request({ url: `/store/${options.id}` })
      .then(async (store) => {
        const list = await resolveStoreList([store])
        const item = list[0] || store
        this.setData({
          store: item,
          canNavigate: hasStoreCoords(item),
        })
      })
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
