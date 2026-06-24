const { request } = require('../../utils/request')

Page({
  data: { user: null },

  onShow() {
    request({ url: '/user/profile' }).then((user) => {
      this.setData({ user })
      wx.setStorageSync('userInfo', user)
    }).catch(() => {
      this.setData({ user: wx.getStorageSync('userInfo') })
    })
  },

  bindPhone(e) {
    const { code } = e.detail
    if (!code) return
    request({ url: '/user/bind-phone', method: 'POST', data: { code } }).then((user) => {
      wx.showToast({ title: '绑定成功' })
      this.setData({ user })
    })
  },

  go(e) {
    wx.navigateTo({ url: e.currentTarget.dataset.url })
  },
})
