const { request } = require('../../utils/request')

Page({
  data: { cards: [] },
  onShow() {
    request({ url: '/user/cards' }).then((cards) => this.setData({ cards }))
  },
})
