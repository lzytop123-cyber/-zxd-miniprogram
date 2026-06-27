const { request } = require('../../utils/request')
const auth = require('../../utils/auth')

Page({
  data: { store: null, storeId: null },

  onLoad(options) {
    this.setData({ storeId: options.id })
    request({ url: `/store/${options.id}` }).then((store) => {
      this.setData({ store })
    })
  },

  goBooking() {
    const url = `/pages/booking/index?storeId=${this.data.storeId}`
    if (!auth.requireLogin(url)) return
    wx.navigateTo({ url })
  },
})
