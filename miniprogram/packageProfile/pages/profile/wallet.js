const { request, invalidateCache, formatRequestError } = require('../../../utils/request')
const { completeWechatPay, ensureRechargePaid, isPayCancelled, isPayBanned } = require('../../../utils/pay')

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
    loading: true,
    loadError: '',
    recharging: false,
  },

  onShow() {
    this.loadWallet({ silent: true })
  },

  onPullDownRefresh() {
    this.loadWallet({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  retryLoad() {
    return this.loadWallet({ force: true })
  },

  loadWallet(options = {}) {
    const { force = false } = options
    const hasLoaded = this._walletLoaded
    this.setData({ loading: !hasLoaded, loadError: '' })
    return request({ url: '/user/wallet', silent: true, force })
      .then((data) => {
        this._walletLoaded = true
        const allLogs = (data.logs || []).map(formatLog)
        this.setData({
          balance: data.balance,
          allLogs,
          logs: this._filterLogs(allLogs, this.data.filter),
          loading: false,
          loadError: '',
        })
      })
      .catch((err) => {
        this.setData({
          loading: false,
          loadError: formatRequestError(err) || '钱包信息加载失败，请检查网络后重试',
        })
      })
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
    if (this._recharging || this.data.recharging) return
    this._recharging = true
    this.setData({ recharging: true })
    const amount = this.data.amount
    wx.showLoading({ title: '提交中...', mask: true })
    try {
      const res = await request({ url: '/user/recharge', method: 'POST', data: { amount } })
      await completeWechatPay(res.wechat_pay, () =>
        request({ url: `/user/recharge/${res.order_no}/mock?amount=${amount}`, method: 'POST' })
      )
      await ensureRechargePaid(res.order_no, res.wechat_pay)
      invalidateCache('/user/wallet')
      invalidateCache('/user/profile')
      wx.hideLoading()
      wx.showToast({ title: '充值成功', icon: 'success' })
      await this.loadWallet({ force: true })
    } catch (e) {
      wx.hideLoading()
      if (isPayCancelled(e)) {
        wx.showToast({ title: '已取消支付', icon: 'none' })
        return
      }
      if (isPayBanned(e)) {
        wx.showModal({
          title: '微信支付暂不可用',
          content: '你的微信支付未能发起，通常是账号未实名认证、未成年或支付被限制。请在微信完成实名认证后重试。',
          showCancel: false,
          confirmText: '知道了',
        })
        return
      }
      wx.showToast({ title: formatRequestError(e) || '充值失败', icon: 'none' })
    } finally {
      this._recharging = false
      this.setData({ recharging: false })
    }
  },
})
