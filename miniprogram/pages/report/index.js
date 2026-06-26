const { request } = require('../../utils/request')

Page({
  data: {
    summary: null,
    leaderboard: [],
    days: 7,
    scopeLabel: '全平台',
    storeId: null,
  },

  onShow() {
    this.load()
  },

  load() {
    request({ url: '/report/summary' }).then((summary) => {
      this.setData({ summary })
    })
    this.loadLeaderboard()
  },

  loadLeaderboard() {
    const params = this.data.storeId ? `?store_id=${this.data.storeId}` : ''
    request({ url: `/report/leaderboard${params}` }).then((leaderboard) => {
      this.setData({ leaderboard })
    })
  },

  setDays(e) {
    this.setData({ days: Number(e.currentTarget.dataset.d) })
    request({ url: `/report/daily?days=${this.data.days}` })
  },

  onScopeChange(e) {
    const idx = Number(e.detail.value)
    this.setData({
      scopeLabel: idx === 0 ? '全平台' : '本店',
      storeId: idx === 0 ? null : 1,
    })
    this.loadLeaderboard()
  },

  goAssistant() {
    wx.navigateTo({ url: '/pages/assistant/index' })
  },
})
