const { request, routes, absUrl, guardMarketplace, auth, statusLabel } = require('../../utils/market')

Page({
  data: {
    id: 0,
    listing: null,
    similar: [],
    images: [],
  },

  onLoad(options) {
    if (!guardMarketplace(this)) return
    this.setData({ id: Number(options.id || 0) })
  },

  onShow() {
    if (this.data.id) this.load()
  },

  async load() {
    try {
      const data = await request({ url: `/market/listings/${this.data.id}`, silent: true })
      const listing = data.listing || {}
      listing.priceText = listing.is_free ? '免费' : `¥${listing.price}`
      listing.statusLabel = statusLabel(listing.status)
      if (listing.seller && listing.seller.avatar_url) {
        listing.seller.avatar_url = absUrl(listing.seller.avatar_url)
      }
      const images = (listing.images || []).map(absUrl)
      const similar = (data.similar || []).map((it) => ({
        ...it,
        cover: absUrl((it.images && it.images[0]) || ''),
        priceText: it.is_free ? '免费' : `¥${it.price}`,
      }))
      this.setData({ listing, images, similar })
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  previewImage(e) {
    const urls = this.data.images || []
    if (!urls.length) return
    const index = Number(e.currentTarget.dataset.index || 0)
    wx.previewImage({
      current: urls[index] || urls[0],
      urls,
    })
  },

  async toggleFavorite() {
    if (!auth.requireLogin(routes.marketDetail + `?id=${this.data.id}`)) return
    const fav = this.data.listing.favorited
    try {
      const data = await request({
        url: `/market/favorites/${this.data.id}`,
        method: fav ? 'DELETE' : 'POST',
      })
      this.setData({
        'listing.favorited': data.favorited,
        'listing.favorite_count': data.favorite_count,
      })
    } catch (e) {
      wx.showToast({ title: e.message || '操作失败', icon: 'none' })
    }
  },

  async contactSeller() {
    if (!auth.requireLogin(routes.marketDetail + `?id=${this.data.id}`)) return
    wx.showModal({
      title: '联系申请',
      editable: true,
      placeholderText: '可选留言',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await request({
            url: '/market/contact-requests',
            method: 'POST',
            data: { listing_id: this.data.id, message: res.content || '' },
          })
          wx.showToast({ title: '已发起申请', icon: 'success' })
        } catch (e) {
          wx.showToast({ title: e.message || '申请失败', icon: 'none' })
        }
      },
    })
  },

  async report() {
    if (!auth.requireLogin(routes.marketDetail + `?id=${this.data.id}`)) return
    wx.showActionSheet({
      itemList: ['疑似盗版侵权', '虚假信息', '骚扰广告', '其他'],
      success: async (res) => {
        const codes = ['piracy', 'fake', 'spam', 'other']
        try {
          await request({
            url: '/market/reports',
            method: 'POST',
            data: { listing_id: this.data.id, reason_code: codes[res.tapIndex] },
          })
          wx.showToast({ title: '已提交举报', icon: 'success' })
        } catch (e) {
          wx.showToast({ title: e.message || '提交失败', icon: 'none' })
        }
      },
    })
  },

  async ownerOff() {
    await request({ url: `/market/listings/${this.data.id}/off`, method: 'POST' })
    wx.showToast({ title: '已下架', icon: 'success' })
    this.load()
  },

  async ownerSold() {
    await request({ url: `/market/listings/${this.data.id}/sold`, method: 'POST' })
    wx.showToast({ title: '已标记已出', icon: 'success' })
    this.load()
  },

  goEdit() {
    wx.navigateTo({ url: `${routes.marketPublish}?id=${this.data.id}` })
  },

  goSimilar(e) {
    wx.navigateTo({ url: `${routes.marketDetail}?id=${e.currentTarget.dataset.id}` })
  },
})
