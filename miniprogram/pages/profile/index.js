const auth = require('../../utils/auth')
const { request } = require('../../utils/request')

Page({
  data: {
    loginState: 'loading',
    loginError: '',
    user: null,
    needsSetup: false,
    draftNickname: '',
    draftAvatar: '',
    saving: false,
    defaultAvatar: auth.DEFAULT_AVATAR,
  },

  onShow() {
    this.bootstrap()
  },

  async bootstrap() {
    this.setData({ loginState: 'loading', loginError: '' })
    try {
      await auth.waitForLogin()
      const user = await request({ url: '/user/profile', silent: true })
      auth.syncAppUser(user)
      this.applyUser(user)
    } catch (err) {
      const app = getAppSafe()
      const cached = wx.getStorageSync('userInfo')
      if (cached && wx.getStorageSync('token')) {
        this.applyUser(cached)
        return
      }
      this.setData({
        loginState: 'error',
        loginError: (app && app.globalData && app.globalData.loginError) || err.detail || '登录失败，请重试',
        user: null,
      })
    }
  },

  applyUser(user) {
    this.setData({
      loginState: 'ready',
      user,
      needsSetup: !!user.needs_profile_setup,
      draftNickname: user.nickname === auth.DEFAULT_NICKNAME ? '' : (user.nickname || ''),
      draftAvatar: '',
      loginError: '',
    })
  },

  onChooseAvatar(e) {
    const { avatarUrl } = e.detail
    if (avatarUrl) this.setData({ draftAvatar: avatarUrl })
  },

  onNicknameInput(e) {
    this.setData({ draftNickname: e.detail.value })
  },

  async saveProfile() {
    const { draftNickname, draftAvatar, saving, needsSetup } = this.data
    if (saving) return

    const nickname = draftNickname.trim()
    if (needsSetup && !draftAvatar && !this.data.user.avatar_url) {
      wx.showToast({ title: '请选择头像', icon: 'none' })
      return
    }
    if (needsSetup && !nickname) {
      wx.showToast({ title: '请填写昵称', icon: 'none' })
      return
    }

    this.setData({ saving: true })
    wx.showLoading({ title: '保存中...' })
    try {
      const user = await auth.saveProfile({
        nickname: nickname || undefined,
        avatarTempPath: draftAvatar || undefined,
      })
      wx.hideLoading()
      wx.showToast({ title: '保存成功', icon: 'success' })
      this.applyUser(user)
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.detail || err.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },

  retryLogin() {
    const app = getApp({ allowDefault: true })
    if (app && app.relogin) {
      app.relogin().then(() => this.bootstrap())
      return
    }
    const auth = require('../../utils/auth')
    auth.login({ silent: false }).then(() => this.bootstrap())
  },

  bindPhone(e) {
    const { code } = e.detail
    if (!code) return
    request({ url: '/user/bind-phone', method: 'POST', data: { code } })
      .then((user) => {
        wx.showToast({ title: '绑定成功' })
        this.applyUser(user)
      })
  },

  go(e) {
    if (this.data.loginState !== 'ready') {
      wx.showToast({ title: '请先完成登录', icon: 'none' })
      return
    }
    wx.navigateTo({ url: e.currentTarget.dataset.url })
  },
})
