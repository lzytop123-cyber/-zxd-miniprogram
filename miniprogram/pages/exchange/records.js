const { request } = require('../../utils/request')

Page({
  data: { records: [] },

  onShow() {
    this.loadRecords({ silent: true })
  },

  onPullDownRefresh() {
    this.loadRecords({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  loadRecords(options = {}) {
    const { force = false } = options
    return request({ url: '/exchange/records', silent: true, force })
      .then((records) => {
        this.setData({ records: records || [] })
      })
      .catch(() => {})
  },
})
