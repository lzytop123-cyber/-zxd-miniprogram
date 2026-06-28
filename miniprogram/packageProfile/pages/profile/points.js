const { request } = require('../../../utils/request')

Page({
  data: { logs: [], total: 0 },

  onShow() {
    Promise.all([
      request({ url: '/user/points/logs' }),
      request({ url: '/user/profile' }),
    ]).then(([logs, user]) => {
      this.setData({ logs, total: user.total_points })
    })
  },
})
