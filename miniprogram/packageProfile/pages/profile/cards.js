const auth = require('../../../utils/auth')
const { request, invalidateCache } = require('../../../utils/request')
const routes = require('../../../utils/routes')
const { formatCard, isCardUsable } = require('../../../utils/cardDisplay')

Page({
  data: {
    cards: [],
    activeCount: 0,
  },

  onShow() {
    this.loadCards()
  },

  onPullDownRefresh() {
    this.loadCards({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  loadCards(options = {}) {
    const { force = false } = options
    if (!auth.requireLogin('/packageProfile/pages/profile/cards')) {
      return Promise.resolve()
    }
    if (force) invalidateCache('/user/cards')
    return request({ url: '/user/cards', silent: true, force })
      .then((cards) => {
        const list = (cards || []).filter(isCardUsable).map(formatCard)
        this.setData({ cards: list, activeCount: list.length })
      })
      .catch(() => {
        wx.showToast({ title: '加载失败', icon: 'none' })
      })
  },

  goBuy() {
    wx.switchTab({ url: '/pages/packages/index' })
  },

  goExchange() {
    wx.navigateTo({ url: routes.exchangeIndex })
  },
})
