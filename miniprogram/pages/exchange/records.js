const { request } = require('../../utils/request')

Page({
  data: { records: [] },

  onShow() {
    request({ url: '/exchange/records' }).then((records) => {
      this.setData({ records: records || [] })
    })
  },
})
