const { request } = require('../../utils/request')

Page({
  data: { coupons: [] },

  onShow() {
    request({ url: '/user/coupons' }).then((coupons) => {
      this.setData({ coupons: (coupons || []).filter((c) => c.status === 0) })
    })
  },
})
