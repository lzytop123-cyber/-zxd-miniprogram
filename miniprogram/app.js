const { getApiBase } = require('./config')

App({
  globalData: {
    apiBase: '',
    user: wx.getStorageSync('userInfo') || null,
    loginReady: !!wx.getStorageSync('token'),
    loginError: '',
    loginPromise: null,
    packagesTab: null,
  },

  onLaunch() {
    this.globalData.apiBase = getApiBase()
    wx.getImageInfo({ src: '/assets/floor-plan-clean.png' })
    const auth = require('./utils/auth')
    // 不再启动时静默 wx.login；仅恢复已有 token 的会话
    if (auth.isLoggedIn()) {
      this.globalData.loginReady = true
      this.globalData.loginPromise = Promise.resolve(this.globalData.user)
    } else {
      this.globalData.loginPromise = Promise.resolve(null)
      this.globalData.loginReady = false
      this.globalData.user = null
    }
  },

  relogin() {
    const auth = require('./utils/auth')
    this.globalData.loginPromise = auth.login({ silent: false, force: true })
    return this.globalData.loginPromise
  },
})
