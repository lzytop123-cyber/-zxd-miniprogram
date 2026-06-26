const { request } = require('../../utils/request')

Page({
  data: { stores: [] },

  onShow() {
    this.loadStores()
  },

  loadStores() {
    wx.getLocation({
      type: 'gcj02',
      success: ({ latitude, longitude }) => {
        request({ url: `/store/list?latitude=${latitude}&longitude=${longitude}` }).then((stores) => {
          this.setData({ stores })
        })
      },
      fail: () => {
        request({ url: '/store/list' }).then((stores) => {
          this.setData({ stores })
        })
      },
    })
  },

  goStore(e) {
    const id = e.detail?.id ?? e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/store/detail?id=${id}` })
  },

  goExchange() {
    wx.navigateTo({ url: '/pages/exchange/index?platform=meituan' })
  },

  goDouyin() {
    wx.navigateTo({ url: '/pages/exchange/index?platform=douyin' })
  },

  goCards() {
    wx.navigateTo({ url: '/pages/profile/cards' })
  },

  goCoupons() {
    wx.navigateTo({ url: '/pages/profile/coupons' })
  },
})
