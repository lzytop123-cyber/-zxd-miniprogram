const { request } = require('../../../utils/request')

Page({
  data: {
    inviteCode: '',
    inputCode: '',
  },

  onShow() {
    this.loadInvite({ silent: true })
  },

  onPullDownRefresh() {
    this.loadInvite({ force: true }).finally(() => wx.stopPullDownRefresh())
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
      wx.showToast({ title: '领取成功' })
      this.setData({ inputCode: '' })
    })
  },
})
