const { request } = require('../../utils/request')

Page({
  data: { store: null, storeId: null },

  onLoad(options) {
    this.setData({ storeId: options.id })
    request({ url: `/store/${options.id}` }).then((store) => {
      this.setData({ store })
    })
  },

  goBooking() {
    wx.navigateTo({ url: `/pages/booking/index?storeId=${this.data.storeId}` })
  },
})
