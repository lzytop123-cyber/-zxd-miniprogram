const { request, routes, guardMarketplace } = require('../../utils/market')

Page({
  data: {
    items: [],
    revealed: {},
    statusText: {
      pending: '待处理',
      approved: '已同意',
      rejected: '已拒绝',
      cancelled: '已取消',
      expired: '已过期',
    },
  },

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
      const items = data.items || []
      this.setData({ items })
      // 已同意的自动拉取一次联系方式，方便买卖双方查看
      for (const row of items) {
        if (row.status === 'approved' && !this.data.revealed[row.id]) {
          this.fetchReveal(row.id, true)
        }
      }
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  async fetchReveal(id, silent) {
    try {
      const data = await request({
        url: `/market/contact-requests/${id}/reveal`,
        silent: !!silent,
      })
      this.setData({ [`revealed.${id}`]: data })
      return data
    } catch (err) {
      if (!silent) {
        wx.showToast({ title: err.message || '暂不可查看', icon: 'none' })
      }
      return null
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
          this.setData({ [`revealed.${id}`]: data })
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
    await this.fetchReveal(id, false)
  },

  copyContact(e) {
    const id = e.currentTarget.dataset.id
    const row = this.data.revealed[id]
    if (!row || !row.reveal_value) return
    wx.setClipboardData({
      data: String(row.reveal_value),
      success: () => wx.showToast({ title: '已复制', icon: 'success' }),
    })
  },

  goDetail(e) {
    wx.navigateTo({ url: `${routes.marketDetail}?id=${e.currentTarget.dataset.listingId}` })
  },
})
