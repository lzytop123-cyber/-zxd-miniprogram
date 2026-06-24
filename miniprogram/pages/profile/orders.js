const { request } = require('../../utils/request')

Page({
  data: {
    orders: [],
    statusText: ['待入座', '使用中', '已完成', '已取消'],
  },

  onShow() {
    request({ url: '/reservation/list' }).then((orders) => {
      this.setData({ orders })
    })
  },
})
