const auth = require('../../utils/auth')
const { request } = require('../../utils/request')
const { normalizeUser, pickAvatarDisplay } = require('../../utils/user')
const routes = require('../../utils/routes')

const GOAL_OPTIONS = [
  { value: 'kaoyan', label: '考研' },
  { value: 'kaogong', label: '考公' },
  { value: 'other', label: '其他' },
]

Page({
  data: {
    loginState: 'loading',
    user: null,
    avatarDisplay: '',
    avatarUploading: false,
    saving: false,
    goalOptions: GOAL_OPTIONS,
    menuUrls: {
      wallet: routes.profileWallet,
      orders: routes.profileOrders,
      coupons: routes.profileCoupons,
      points: routes.profilePoints,
      invite: routes.profileInvite,
    },
  },

  onShow() {
    this.bootstrap({ silent: true })
  },

  onPullDownRefresh() {
    this.bootstrap({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  async bootstrap(options = {}) {
    const { force = false, silent = false } = options
    if (!auth.isLoggedIn()) {
      this.setData({ loginState: 'guest', user: null, avatarDisplay: '' })
      return
    }

    const hasUser = this.data.loginState === 'ready' && this.data.user
    if (!hasUser || force) {
      if (!silent || !hasUser) {
        this.setData({ loginState: 'loading' })
      }
    }

    try {
      await auth.waitForLogin()
      const user = await request({ url: '/user/profile', silent: true, force })
      auth.syncAppUser(user)
      if (user.needs_profile_setup) {
        auth.goLogin('/pages/profile/index')
        return
      }
      await this.applyUser(user)
    } catch (err) {
      const cached = wx.getStorageSync('userInfo')
      if (cached && auth.isLoggedIn() && !cached.needs_profile_setup) {
        await this.applyUser(cached)
        return
      }
      if (!hasUser) {
        auth.goLogin('/pages/profile/index')
      }
    }
  },

  async applyUser(user, localAvatar) {
    const normalized = await normalizeUser(user)
    this.setData({
      loginState: 'ready',
      user: normalized,
      avatarDisplay: pickAvatarDisplay(localAvatar, normalized),
    })
  },

  async onChooseAvatar(e) {
    const { avatarUrl } = e.detail
    if (!avatarUrl || this.data.avatarUploading) return

    this.setData({ avatarDisplay: avatarUrl, avatarUploading: true })
    wx.showLoading({ title: '更新头像...' })
    try {
      const user = await auth.uploadAvatar(avatarUrl)
      auth.syncAppUser(user)
      await this.applyUser(user, avatarUrl)
      wx.showToast({ title: '头像已更新', icon: 'success' })
    } catch (err) {
      wx.showToast({ title: err.detail || err.message || '更新失败', icon: 'none' })
    } finally {
      wx.hideLoading()
      this.setData({ avatarUploading: false })
    }
  },

  async saveStudyGoal(e) {
    const value = e.currentTarget.dataset.value
    const next = this.data.user?.study_goal === value ? '' : value
    if (this.data.saving) return
    this.setData({ saving: true })
    try {
      const user = await auth.saveProfile({ studyGoal: next })
      wx.showToast({ title: '已更新', icon: 'success' })
      await this.applyUser(user, this.data.avatarDisplay)
    } catch (err) {
      wx.showToast({ title: err.detail || '保存失败', icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },

  goLogin() {
    auth.goLogin('/pages/profile/index')
  },

  doLogout() {
    wx.showModal({
      title: '退出登录',
      content: '退出后需重新微信登录才能使用预约等功能',
      confirmColor: '#2D6A4F',
      success: (res) => {
        if (!res.confirm) return
        auth.logout()
        this.setData({ loginState: 'guest', user: null, avatarDisplay: '' })
        wx.showToast({ title: '已退出', icon: 'none' })
      },
    })
  },

  copyUserId() {
    const id = this.data.user?.id
    if (!id) return
    wx.setClipboardData({
      data: String(id),
      success: () => wx.showToast({ title: '学号已复制', icon: 'success' }),
    })
  },

  bindPhone(e) {
    const { code } = e.detail
    if (!code) return
    request({ url: '/user/bind-phone', method: 'POST', data: { code } })
      .then(async (user) => {
        wx.showToast({ title: '绑定成功' })
        await this.applyUser(user, this.data.avatarDisplay)
      })
  },

  go(e) {
    const url = e.currentTarget.dataset.url
    if (!auth.requireLogin(url)) return
    wx.navigateTo({ url })
  },

  goPackages() {
    wx.switchTab({ url: '/pages/packages/index' })
  },
})
