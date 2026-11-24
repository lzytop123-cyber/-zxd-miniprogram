const auth = require('../../../utils/auth')
const { request, invalidateCache } = require('../../../utils/request')
const routes = require('../../../utils/routes')
const { formatCard, isCardUsable } = require('../../../utils/cardDisplay')

Page({
  data: {
    tab: 'active',
    activeCards: [],
    historyCards: [],
    cards: [],
    activeCount: 0,
    historyCount: 0,
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
    if (force) {
      invalidateCache('/user/cards')
    }
    return request({ url: '/user/cards?include_history=true', silent: true, force })
      .then((rows) => {
        const all = (rows || []).map(formatCard)
        const activeCards = all.filter((c) => c.status === 1 && isCardUsable(c))
        const historyCards = all.filter((c) => !(c.status === 1 && isCardUsable(c)))
        const tab = this.data.tab || 'active'
        this.setData({
          activeCards,
          historyCards,
          cards: tab === 'active' ? activeCards : historyCards,
          activeCount: activeCards.length,
          historyCount: historyCards.length,
        })
      })
      .catch(() => {
        wx.showToast({ title: '加载失败', icon: 'none' })
      })
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab || 'active'
    if (tab === this.data.tab) return
    this.setData({
      tab,
      cards: tab === 'active' ? this.data.activeCards : this.data.historyCards,
    })
  },

  goBookCard(e) {
    const idx = Number(e.currentTarget.dataset.index)
    const card = this.data.cards[idx]
    if (!card) return
    const billType = card.card_type === 'night_monthly' || card.usage_rule ? 'night' : (card.card_type || 'hourly')
    if (card.store_id) {
      wx.navigateTo({
        url: `${routes.bookingIndex}?storeId=${card.store_id}&billType=${billType}`,
      })
      return
    }
    wx.navigateTo({ url: routes.storeSelect })
  },

  goBuy() {
    wx.switchTab({ url: '/pages/packages/index' })
  },

  goExchange() {
    const { buildExchangeUrl } = require('../../../pages/exchange/utils/storePick')
    wx.navigateTo({ url: buildExchangeUrl() })
  },

  goExchangeRecords() {
    wx.navigateTo({ url: routes.exchangeRecords })
  },
})
