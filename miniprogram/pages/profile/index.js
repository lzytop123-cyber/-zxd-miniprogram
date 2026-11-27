const auth = require('../../utils/auth')
const { request } = require('../../utils/request')
const { normalizeUser, pickAvatarDisplay } = require('../../utils/user')
const routes = require('../../utils/routes')
const { handleTabScroll } = require('../../utils/tabbar')
const { syncTabBar, isMarketplaceEnabled } = require('../../utils/features')
const { enableShareMenu, shareAppMessage, shareTimeline } = require('../../utils/share')

function maskPhone(phone) {
  const s = String(phone || '').replace(/\D/g, '')
  if (s.length < 7) return ''
  return `${s.slice(0, 3)}****${s.slice(-4)}`
}

Page({
  data: {
    loginState: 'loading',
    user: null,
    phoneMasked: '',
    avatarDisplay: '',
    avatarUploading: false,
    showMarketplace: isMarketplaceEnabled(),
    menuUrls: {
      wallet: routes.profileWallet,
      orders: routes.profileOrders,
      coupons: routes.profileCoupons,
      wrongbook: routes.wrongbookIndex,
      points: routes.profilePoints,
      invite: routes.profileInvite,
      contact: routes.profileContact,
      messages: routes.profileMessages,
    },
    unreadCount: 0,
  },

  onShareAppMessage() {
    return shareAppMessage({ title: '知行岛自习空间' })
  },

  onShareTimeline() {
    return shareTimeline({ title: '知行岛自习空间' })
  },

  onShow() {
    enableShareMenu()
    this.setData({ showMarketplace: isMarketplaceEnabled() })
    syncTabBar(this, '/pages/profile/index')
    this._tabbarLastTop = 0
    this.bootstrap({ silent: true })
    this.loadUnread()
  },

  loadUnread() {
    if (!auth.isLoggedIn()) return
    request({ url: '/notifications/unread-count', silent: true })
      .then((d) => this.setData({ unreadCount: (d && d.count) || 0 }))
      .catch(() => {})
  },

  onPageScroll(e) {
    handleTabScroll(this, e.scrollTop)
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
        // 资料未完善：仍展示「我的」，由用户主动去完善；不得 replace 回登录页卡死返回键
        await this.applyUser(user)
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
      phoneMasked: maskPhone(normalized && normalized.phone),
      avatarDisplay: pickAvatarDisplay(localAvatar, normalized),
    })
  },

  async onChooseAvatar(e) {
    const avatarUrl = e?.detail?.avatarUrl
    if (!avatarUrl) {
      this.goEdit()
      return
    }
    await this._uploadAvatarFile(avatarUrl)
  },

  onChooseAvatarError() {
    this.goEdit()
  },

  async _uploadAvatarFile(avatarUrl) {
    if (!avatarUrl || this.data.avatarUploading) return

    const prevAvatar = this.data.avatarDisplay
    this.setData({ avatarDisplay: avatarUrl, avatarUploading: true })
    wx.showLoading({ title: '更新头像...', mask: true })
    try {
      const user = await auth.uploadAvatar(avatarUrl)
      auth.syncAppUser(user)
      await this.applyUser(user, avatarUrl)
      wx.showToast({ title: '头像已更新', icon: 'success' })
    } catch (err) {
      this.setData({ avatarDisplay: prevAvatar })
      wx.showToast({ title: err.detail || err.message || '更新失败', icon: 'none' })
    } finally {
      wx.hideLoading()
      this.setData({ avatarUploading: false })
    }
  },

  goEdit() {
    if (!auth.requireLogin('/pages/profile/index')) return
    wx.navigateTo({ url: routes.profileEdit })
  },

  goLogin() {
    auth.goLogin('/pages/profile/index', { replace: true })
  },

  copyUserId() {
    const id = this.data.user?.id
    if (!id) return
    wx.setClipboardData({
      data: String(id),
      success: () => wx.showToast({ title: '学号已复制', icon: 'success' }),
    })
  },

  go(e) {
    const url = e.currentTarget.dataset.url
    if (!auth.requireLogin(url)) return
    wx.navigateTo({ url })
  },

  goPackages() {
    wx.navigateTo({ url: '/packageProfile/pages/profile/cards' })
  },

  goMarket() {
    if (!isMarketplaceEnabled()) {
      wx.showToast({ title: '功能暂未开放', icon: 'none' })
      return
    }
    wx.navigateTo({ url: routes.marketMine })
  },

  openAgreement(e) {
    const type = e.currentTarget.dataset.type || 'user'
    wx.navigateTo({ url: `${routes.profileAgreement}?type=${type}` })
  },
})
