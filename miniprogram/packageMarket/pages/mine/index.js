const { request, routes, absUrl, guardMarketplace, statusLabel } = require('../../utils/market')

Page({
  data: {
    tab: 'listings',
    listings: [],
    favorites: [],
    reports: [],
  },

  onShow() {
    if (!guardMarketplace()) return
    this.reload()
  },

  onPullDownRefresh() {
    this.reload().finally(() => wx.stopPullDownRefresh())
  },

  switchTab(e) {
    this.setData({ tab: e.currentTarget.dataset.tab }, () => this.reload())
  },

  async reload() {
    const tab = this.data.tab
    try {
      if (tab === 'listings') {
        const data = await request({ url: '/market/mine/listings?page=1&page_size=50' })
        this.setData({
          listings: (data.items || []).map((it) => ({
            ...it,
            cover: absUrl((it.images && it.images[0]) || ''),
            statusLabel: statusLabel(it.status),
            priceText: it.is_free ? '免费' : `¥${it.price}`,
          })),
        })
      } else if (tab === 'favorites') {
        const data = await request({ url: '/market/mine/favorites?page=1&page_size=50' })
        this.setData({
          favorites: (data.items || []).map((it) => ({
            ...it,
            cover: absUrl((it.images && it.images[0]) || ''),
            priceText: it.is_free ? '免费' : `¥${it.price}`,
          })),
        })
      } else if (tab === 'reports') {
        const data = await request({ url: '/market/mine/reports' })
        this.setData({ reports: data.items || [] })
      }
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  goPublish() {
    wx.navigateTo({ url: routes.marketPublish })
  },

  goContacts() {
    wx.navigateTo({ url: routes.marketContacts })
  },

  goDetail(e) {
    wx.navigateTo({ url: `${routes.marketDetail}?id=${e.currentTarget.dataset.id}` })
  },
})
