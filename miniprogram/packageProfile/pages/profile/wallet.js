const { request, invalidateCache } = require('../../../utils/request')
const { completeWechatPay, ensureRechargePaid, isPayCancelled } = require('../../../utils/pay')

function formatLog(item) {
  const isPlus = item.type === 'recharge' || item.type === 'refund' || (item.type === 'admin_adjust' && Number(item.amount) >= 0)
  const absAmt = Math.abs(Number(item.amount || 0)).toFixed(2).replace(/\.00$/, '')
  return {
    ...item,
    isPlus,
    amountText: `${isPlus ? '+' : '-'}¥${absAmt}`,
  }
}

Page({
  data: {
    balance: 0,
    allLogs: [],
    logs: [],
    filter: 'all',
    amount: 100,
  },

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
        const allLogs = (data.logs || []).map(formatLog)
        this.setData({
          balance: data.balance,
          allLogs,
          logs: this._filterLogs(allLogs, this.data.filter),
        })
      })
      .catch(() => {})
  },

  _filterLogs(allLogs, filter) {
    if (filter === 'recharge') return allLogs.filter((l) => l.type === 'recharge')
    if (filter === 'consume') return allLogs.filter((l) => l.type !== 'recharge')
    return allLogs
  },

  setFilter(e) {
    const filter = e.currentTarget.dataset.filter || 'all'
    this.setData({
      filter,
      logs: this._filterLogs(this.data.allLogs, filter),
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
      await ensureRechargePaid(res.order_no, res.wechat_pay)
      invalidateCache('/user/wallet')
      invalidateCache('/user/profile')
      wx.hideLoading()
      wx.showToast({ title: '充值成功' })
      await this.loadWallet({ force: true })
    } catch (e) {
      wx.hideLoading()
      if (isPayCancelled(e)) {
        wx.showToast({ title: '已取消支付', icon: 'none' })
        return
      }
      wx.showToast({ title: e.message || '充值失败', icon: 'none' })
    }
  },
})
