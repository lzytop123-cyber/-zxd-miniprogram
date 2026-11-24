const { request } = require('../../../utils/request')
const routes = require('../../../utils/routes')

Page({
  data: {
    tab: 0,
    allCoupons: [],
    coupons: [],
    unusedCount: 0,
    usedCount: 0,
    expiredCount: 0,
  },

  onShow() {
    this.loadCoupons({ silent: true })
  },

  onPullDownRefresh() {
    this.loadCoupons({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  loadCoupons(options = {}) {
    const { force = false } = options
    return request({ url: '/user/coupons', silent: true, force })
      .then((rows) => {
        const allCoupons = rows || []
        const tab = this.data.tab
        this.setData({
          allCoupons,
          coupons: allCoupons.filter((c) => c.status === tab),
          unusedCount: allCoupons.filter((c) => c.status === 0).length,
          usedCount: allCoupons.filter((c) => c.status === 1).length,
          expiredCount: allCoupons.filter((c) => c.status === 2).length,
        })
      })
      .catch(() => {})
  },

  switchTab(e) {
    const tab = Number(e.currentTarget.dataset.tab || 0)
    this.setData({
      tab,
      coupons: (this.data.allCoupons || []).filter((c) => c.status === tab),
    })
  },

  goUse() {
    wx.navigateTo({ url: routes.storeSelect })
  },

  goPoints() {
    wx.navigateTo({ url: routes.profilePoints })
  },
})
