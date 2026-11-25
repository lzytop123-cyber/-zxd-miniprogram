const { request, formatRequestError } = require('../../utils/request')

Page({
  data: { records: [], loading: true, loadError: '' },

  onShow() {
    this.loadRecords({ silent: true })
  },

  onPullDownRefresh() {
    this.loadRecords({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  retryLoad() {
    return this.loadRecords({ force: true })
  },

  loadRecords(options = {}) {
    const { force = false } = options
    const hasData = (this.data.records || []).length > 0
    this.setData({ loading: !hasData, loadError: '' })
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
        this.setData({ records: list, loading: false, loadError: '' })
      })
      .catch((err) => {
        this.setData({
          loading: false,
          loadError: formatRequestError(err) || '加载失败，请检查网络后重试',
        })
      })
  },
})
