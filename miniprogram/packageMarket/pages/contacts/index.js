const { request, routes, guardMarketplace } = require('../../utils/market')

Page({
  data: { items: [], revealMap: {} },

  onShow() {
    if (!guardMarketplace()) return
    this.load()
  },

  onPullDownRefresh() {
    this.load().finally(() => wx.stopPullDownRefresh())
  },

  async load() {
    try {
      const data = await request({ url: '/market/contact-requests' })
      this.setData({ items: data.items || [] })
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  async approve(e) {
    const id = e.currentTarget.dataset.id
    wx.showActionSheet({
      itemList: ['同意并展示我的手机号', '同意并展示微信号'],
      success: async (res) => {
        const reveal_type = res.tapIndex === 0 ? 'phone' : 'wechat'
        let wechat_id = ''
        if (reveal_type === 'wechat') {
          const modal = await new Promise((resolve) => {
            wx.showModal({
              title: '填写微信号',
              editable: true,
              placeholderText: '微信号',
              success: resolve,
              fail: () => resolve({ confirm: false }),
            })
          })
          if (!modal.confirm) return
          wechat_id = modal.content || ''
        }
        try {
          const data = await request({
            url: `/market/contact-requests/${id}/decide`,
            method: 'POST',
            data: { approve: true, reveal_type, wechat_id },
          })
          wx.showToast({ title: '已同意', icon: 'success' })
          this.setData({ [`revealMap.${id}`]: data })
          this.load()
        } catch (err) {
          wx.showToast({ title: err.message || '失败', icon: 'none' })
        }
      },
    })
  },

  async reject(e) {
    const id = e.currentTarget.dataset.id
    try {
      await request({
        url: `/market/contact-requests/${id}/decide`,
        method: 'POST',
        data: { approve: false },
      })
      wx.showToast({ title: '已拒绝', icon: 'success' })
      this.load()
    } catch (err) {
      wx.showToast({ title: err.message || '失败', icon: 'none' })
    }
  },

  async reveal(e) {
    const id = e.currentTarget.dataset.id
    try {
      const data = await request({ url: `/market/contact-requests/${id}/reveal` })
      this.setData({ [`revealMap.${id}`]: data })
      wx.showModal({
        title: data.reveal_type === 'phone' ? '对方手机号' : '对方微信号',
        content: data.reveal_value || '',
        showCancel: false,
      })
    } catch (err) {
      wx.showToast({ title: err.message || '暂不可查看', icon: 'none' })
    }
  },

  goDetail(e) {
    wx.navigateTo({ url: `${routes.marketDetail}?id=${e.currentTarget.dataset.listingId}` })
  },
})
