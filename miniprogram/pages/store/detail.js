const { request } = require('../../utils/request')
const auth = require('../../utils/auth')

Page({
  data: { store: null, storeId: null },

  onLoad(options) {
    const { resolveStoreList } = require('../../utils/media')
    this.setData({ storeId: options.id })
    request({ url: `/store/${options.id}` })
      .then(async (store) => {
        const list = await resolveStoreList([store])
        this.setData({ store: list[0] || store })
      })
  },

  goBooking() {
    const url = `/pages/booking/index?storeId=${this.data.storeId}`
    if (!auth.requireLogin(url)) return
    wx.navigateTo({ url })
  },
})
