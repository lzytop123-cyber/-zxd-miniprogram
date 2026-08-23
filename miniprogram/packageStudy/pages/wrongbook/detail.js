const { request } = require('../../../utils/request')
const routes = require('../../../utils/routes')
const { decorateQuestion } = require('../../utils/wrongbook')

Page({
  data: {
    id: 0,
    item: null,
    answerOpen: false,
    bumped: false,
  },

  onLoad(options) {
    this.setData({ id: Number(options.id || 0) })
  },

  onShow() {
    if (this.data.id) this.load()
  },

  async load() {
    try {
      const row = await request({ url: `/wrongbook/${this.data.id}`, force: true })
      const item = await decorateQuestion(row)
      this.setData({ item })
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  preview(e) {
    const urls = e.currentTarget.dataset.urls || []
    const current = e.currentTarget.dataset.current || urls[0]
    if (!urls.length) return
    wx.previewImage({ current, urls })
  },

  async openAnswer() {
    if (this.data.answerOpen) {
      this.setData({ answerOpen: false })
      return
    }
    this.setData({ answerOpen: true })
    if (this.data.bumped || !this.data.id) return
    try {
      const row = await request({
        url: `/wrongbook/${this.data.id}`,
        method: 'PUT',
        data: { bump_review: true },
        silent: true,
      })
      const item = await decorateQuestion(row)
      this.setData({ item, bumped: true })
    } catch (e) {
      this.setData({ bumped: true })
    }
  },

  async setStatus(e) {
    const status = Number(e.currentTarget.dataset.status)
    if (!this.data.item || this.data.item.status === status) return
    try {
      const row = await request({
        url: `/wrongbook/${this.data.id}`,
        method: 'PUT',
        data: { status },
      })
      const item = await decorateQuestion(row)
      this.setData({ item })
      wx.showToast({ title: item.status_label, icon: 'none' })
    } catch (e) {}
  },

  goEdit() {
    wx.navigateTo({ url: `${routes.wrongbookEdit}?id=${this.data.id}` })
  },

  onDelete() {
    wx.showModal({
      title: '删除错题',
      content: '删除后无法恢复，确定删除？',
      confirmColor: '#C95C5C',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await request({ url: `/wrongbook/${this.data.id}`, method: 'DELETE' })
          wx.showToast({ title: '已删除', icon: 'success' })
          setTimeout(() => wx.navigateBack(), 400)
        } catch (e) {}
      },
    })
  },
})
