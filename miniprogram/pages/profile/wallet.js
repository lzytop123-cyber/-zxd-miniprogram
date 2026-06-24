const { request } = require('../../utils/request')

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

  recharge() {
    const amount = this.data.amount
    request({ url: '/user/recharge', method: 'POST', data: { amount } }).then((res) => {
      const orderNo = res.order_no
      request({ url: `/user/recharge/${orderNo}/mock?amount=${amount}`, method: 'POST' }).then((data) => {
        wx.showToast({ title: '充值成功' })
        this.setData({ balance: data.balance, logs: data.logs.filter((l) => l.type === 'recharge') })
      })
    })
  },
})
