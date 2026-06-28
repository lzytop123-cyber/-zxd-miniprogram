const { request } = require('../../../utils/request')
const { completeWechatPay } = require('../../../utils/pay')

Page({
  data: { balance: 0, logs: [], amount: 100 },

  onShow() {
    this.loadWallet({ silent: true })
  },

  onPullDownRefresh() {
    this.loadWallet({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  loadWallet(options = {}) {
    const { force = false } = options
    return request({ url: '/user/wallet', silent: true, force })
      .then((data) => {
        this.setData({
          balance: data.balance,
          logs: data.logs.filter((l) => l.type === 'recharge'),
        })
      })
      .catch(() => {})
  },

  setAmount(e) {
    this.setData({ amount: Number(e.currentTarget.dataset.a) })
  },

  async recharge() {
    const amount = this.data.amount
    wx.showLoading({ title: '提交中...' })
    try {
      const res = await request({ url: '/user/recharge', method: 'POST', data: { amount } })
      await completeWechatPay(res.wechat_pay, () =>
        request({ url: `/user/recharge/${res.order_no}/mock?amount=${amount}`, method: 'POST' })
      )
      wx.hideLoading()
      wx.showToast({ title: '充值成功' })
      await this.loadWallet({ force: true })
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: e.message || '充值失败', icon: 'none' })
    }
  },
})
