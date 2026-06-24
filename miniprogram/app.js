const { API_BASE } = require('./config')

App({
  globalData: {
    apiBase: API_BASE,
  },
  onLaunch() {
    this.login()
  },
  login() {
    wx.login({
      success: ({ code }) => {
        const { request } = require('./utils/request')
        request({ url: '/user/login', method: 'POST', data: { code } }).then((res) => {
          wx.setStorageSync('token', res.token)
          wx.setStorageSync('userInfo', res.user)
        })
      },
    })
  },
})
