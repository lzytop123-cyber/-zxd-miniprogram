const { request } = require('../../utils/request')

Page({
  data: {
    stores: [],
    user: null,
  },

  onShow() {
    this.loadStores()
    this.loadUser()
  },

  loadUser() {
    request({ url: '/user/profile', silent: true })
      .then((user) => this.setData({ user }))
      .catch(() => {})
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

  goNearestStore() {
    const { stores } = this.data
    if (!stores || !stores.length) {
      wx.showToast({ title: '正在获取门店…', icon: 'none' })
      this.loadStores()
      return
    }
    wx.navigateTo({ url: `/pages/store/detail?id=${stores[0].id}` })
  },

  goExchange() {
    wx.navigateTo({ url: '/pages/exchange/index?platform=meituan' })
  },

  goCards() {
    wx.navigateTo({ url: '/pages/profile/cards' })
  },

  goCoupons() {
    wx.navigateTo({ url: '/pages/profile/coupons' })
  },

  goWallet() {
    wx.navigateTo({ url: '/pages/profile/wallet' })
  },

  goPoints() {
    wx.navigateTo({ url: '/pages/profile/points' })
  },

  goOrders() {
    wx.navigateTo({ url: '/pages/profile/orders' })
  },

  goInvite() {
    wx.navigateTo({ url: '/pages/profile/invite' })
  },

  goCheckin() {
    wx.switchTab({ url: '/pages/checkin/index' })
  },

  goProfile() {
    wx.switchTab({ url: '/pages/profile/index' })
  },
})
