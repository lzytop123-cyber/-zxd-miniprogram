const { request } = require('../../../utils/request')
const {
  enableShareMenu,
  shareAppMessage,
  shareTimeline,
  peekPendingInvite,
  clearPendingInvite,
  HOME_PATH,
} = require('../../../utils/share')

Page({
  data: {
    inviteCode: '',
    inputCode: '',
  },

  onShow() {
    enableShareMenu()
    const pending = peekPendingInvite()
    if (pending && !this.data.inputCode) {
      this.setData({ inputCode: pending })
    }
    this.loadInvite({ silent: true })
  },

  onPullDownRefresh() {
    this.loadInvite({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  onShareAppMessage() {
    const code = this.data.inviteCode || ''
    return shareAppMessage({
      title: '送你知行岛自习室邀请福利',
      path: code ? `${HOME_PATH}?invite=${encodeURIComponent(code)}` : HOME_PATH,
    })
  },

  onShareTimeline() {
    const code = this.data.inviteCode || ''
    return shareTimeline({
      title: '送你知行岛自习室邀请福利',
      query: code ? `invite=${encodeURIComponent(code)}` : '',
    })
  },

  loadInvite(options = {}) {
    const { force = false } = options
    return request({ url: '/user/profile', silent: true, force })
      .then((user) => {
        this.setData({ inviteCode: user.invite_code || '' })
      })
      .catch(() => {})
  },

  onInput(e) {
    this.setData({ inputCode: e.detail.value.trim().toUpperCase() })
  },

  copyCode() {
    if (!this.data.inviteCode) return
    wx.setClipboardData({
      data: this.data.inviteCode,
      success: () => wx.showToast({ title: '邀请码已复制' }),
    })
  },

  submit() {
    if (!this.data.inputCode) {
      wx.showToast({ title: '请输入邀请码', icon: 'none' })
      return
    }
    request({
      url: '/user/invite/apply',
      method: 'POST',
      data: { invite_code: this.data.inputCode },
    }).then(() => {
      clearPendingInvite()
      wx.showToast({ title: '领取成功' })
      this.setData({ inputCode: '' })
    })
  },
})
