const { request } = require('../../../utils/request')

Page({
  data: {
    list: [],
    loading: false,
  },

  onLoad() {
    this.load()
  },

  onShow() {
    this.load({ silent: true })
  },

  onPullDownRefresh() {
    this.load({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  load(options = {}) {
    const { force = false, silent = false } = options
    if (!silent) this.setData({ loading: true })
    return request({ url: '/notifications/mine', force, silent })
      .then((data) => {
        const items = (data && data.items) || []
        this.setData({ list: items })
      })
      .catch(() => {})
      .finally(() => this.setData({ loading: false }))
  },

  onTap(e) {
    const id = e.currentTarget.dataset.id
    const linkPath = e.currentTarget.dataset.link
    const item = this.data.list.find((n) => n.id === id)
    if (item && !item.is_read) {
      request({ url: `/notifications/${id}/read`, method: 'POST', silent: true }).catch(() => {})
      const next = this.data.list.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      this.setData({ list: next })
    }
    if (linkPath) {
      const url = linkPath.startsWith('/') ? linkPath : `/${linkPath}`
      wx.navigateTo({ url, fail: () => wx.switchTab({ url }).catch(() => {}) })
    }
  },

  markAllRead() {
    request({ url: '/notifications/read-all', method: 'POST' })
      .then(() => {
        wx.showToast({ title: '全部已读', icon: 'success' })
        const next = this.data.list.map((n) => ({ ...n, is_read: true }))
        this.setData({ list: next })
      })
      .catch(() => {})
  },
})
