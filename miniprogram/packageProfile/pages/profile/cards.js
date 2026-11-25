const auth = require('../../../utils/auth')
const { request, invalidateCache, formatRequestError } = require('../../../utils/request')
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
    loading: true,
    loadError: '',
  },

  onShow() {
    this.loadCards()
  },

  onPullDownRefresh() {
    this.loadCards({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  retryLoad() {
    return this.loadCards({ force: true })
  },

  loadCards(options = {}) {
    const { force = false } = options
    if (!auth.requireLogin('/packageProfile/pages/profile/cards')) {
      this.setData({ loading: false })
      return Promise.resolve()
    }
    const hasData = (this.data.activeCards || []).length > 0 || (this.data.historyCards || []).length > 0
    this.setData({ loading: !hasData, loadError: '' })
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
          loading: false,
          loadError: '',
        })
      })
      .catch((err) => {
        this.setData({
          loading: false,
          loadError: formatRequestError(err) || '加载失败，请检查网络后重试',
        })
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
    wx.navigateTo({ url: routes.buildExchangeUrl() })
  },

  goExchangeRecords() {
    wx.navigateTo({ url: routes.exchangeRecords })
  },
})
