const { request } = require('../../../utils/request')

Page({
  data: { coupons: [] },

  onShow() {
    this.loadCoupons({ silent: true })
  },

  onPullDownRefresh() {
    this.loadCoupons({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  loadCoupons(options = {}) {
    const { force = false } = options
    return request({ url: '/user/coupons', silent: true, force })
      .then((coupons) => {
        this.setData({ coupons: (coupons || []).filter((c) => c.status === 0) })
      })
      .catch(() => {})
  },
})
