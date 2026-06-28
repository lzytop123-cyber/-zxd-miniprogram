const { request } = require('../../../utils/request')

Page({
  data: { logs: [], total: 0 },

  onShow() {
    this.loadPoints({ silent: true })
  },

  onPullDownRefresh() {
    this.loadPoints({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  loadPoints(options = {}) {
    const { force = false } = options
    return Promise.all([
      request({ url: '/user/points/logs', silent: true, force }),
      request({ url: '/user/profile', silent: true, force }),
    ])
      .then(([logs, user]) => {
        this.setData({ logs, total: user.total_points })
      })
      .catch(() => {})
  },
})
