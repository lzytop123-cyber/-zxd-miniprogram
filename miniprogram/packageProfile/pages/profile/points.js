const { request, invalidateCache } = require('../../../utils/request')
const routes = require('../../../utils/routes')

const REDEEM_TIERS = [
  { code: 'coupon_5', points: 50, title: '5元自习立减券', desc: '满 15 元可用 · 有效期 30 天' },
  { code: 'coupon_12', points: 100, title: '12元自习立减券', desc: '满 30 元可用 · 有效期 30 天' },
]

Page({
  data: {
    logs: [],
    total: 0,
    tiers: REDEEM_TIERS,
    redeeming: false,
  },

  onShow() {
    this.loadPoints({ silent: true })
  },

  onPullDownRefresh() {
    this.loadPoints({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  loadPoints(options = {}) {
    const { force = false } = options
    return Promise.all([
      request({ url: '/user/points/logs', silent: true, force }),
      request({ url: '/user/profile', silent: true, force }),
    ])
      .then(([logs, user]) => {
        const formatted = (logs || []).map((l) => ({
          ...l,
          pointsText: Number(l.points) > 0 ? `+${l.points}` : `${l.points}`,
          isNegative: Number(l.points) < 0,
        }))
        this.setData({ logs: formatted, total: user.total_points || 0 })
      })
      .catch(() => {})
  },

  redeem(e) {
    if (this.data.redeeming) return
    const code = e.currentTarget.dataset.code
    const tier = REDEEM_TIERS.find((t) => t.code === code)
    if (!tier) return
    if (this.data.total < tier.points) {
      wx.showToast({ title: `积分不足（需 ${tier.points} 积分）`, icon: 'none' })
      return
    }
    wx.showModal({
      title: '确认兑换',
      content: `消耗 ${tier.points} 积分兑换「${tier.title}」？`,
      confirmColor: '#2D6A4F',
      success: (res) => {
        if (!res.confirm) return
        this.setData({ redeeming: true })
        request({
          url: '/user/points/redeem',
          method: 'POST',
          data: { tier_code: code },
        })
          .then((data) => {
            invalidateCache('/user/profile')
            invalidateCache('/user/points/logs')
            invalidateCache('/user/coupons')
            wx.showModal({
              title: '兑换成功',
              content: `已放入「我的优惠券」：${(data && data.coupon_name) || tier.title}`,
              confirmText: '查看优惠券',
              cancelText: '留在当前页',
              confirmColor: '#2D6A4F',
              success: (r) => {
                if (r.confirm) wx.navigateTo({ url: routes.profileCoupons })
              },
            })
            this.loadPoints({ force: true })
          })
          .catch(() => {})
          .finally(() => this.setData({ redeeming: false }))
      },
    })
  },
})
