const { request } = require('../../../utils/request')
const { completeWechatPay } = require('../../../utils/pay')

Page({
  data: { balance: 0, logs: [], amount: 100 },

  onShow() {
    request({ url: '/user/wallet' }).then((data) => {
      this.setData({ balance: data.balance, logs: data.logs.filter((l) => l.type === 'recharge') })
    })
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
      const data = await request({ url: '/user/wallet' })
      wx.hideLoading()
      wx.showToast({ title: '充值成功' })
      this.setData({ balance: data.balance, logs: data.logs.filter((l) => l.type === 'recharge') })
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: e.message || '充值失败', icon: 'none' })
    }
  },
})
