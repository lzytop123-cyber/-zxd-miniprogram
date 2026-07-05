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
        const list = (records || []).map((item) => {
          let validityText = ''
          if (item.validity_range) {
            validityText = `卡面效期 ${item.validity_range}`
          } else if (item.start_date && item.end_date) {
            validityText = `卡面效期 ${item.start_date} ~ ${item.end_date}`
          } else if (item.end_date) {
            validityText = `卡面效期至 ${item.end_date}`
          }
          return { ...item, validityText }
        })
        this.setData({ records: list })
      })
      .catch(() => {})
  },
})
