const { API_BASE } = require('./config')

App({
  globalData: {
    apiBase: API_BASE,
    user: wx.getStorageSync('userInfo') || null,
    loginReady: !!wx.getStorageSync('token'),
    loginError: '',
    loginPromise: null,
  },

  onLaunch() {
    const auth = require('./utils/auth')
    this.globalData.loginPromise = auth.login({ silent: true }).catch(() => null)
  },

  relogin() {
    const auth = require('./utils/auth')
    this.globalData.loginPromise = auth.login({ silent: false })
    return this.globalData.loginPromise
  },
})
