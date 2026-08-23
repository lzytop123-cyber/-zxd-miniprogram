const { request } = require('../../../utils/request')

Page({
  data: {
    subjects: [],
    name: '',
  },

  onShow() {
    this.load()
  },

  load() {
    return request({ url: '/wrongbook/subjects', force: true }).then((rows) => {
      this.setData({ subjects: rows || [] })
    })
  },

  onName(e) {
    this.setData({ name: e.detail.value || '' })
  },

  async add() {
    const name = (this.data.name || '').trim()
    if (!name) {
      wx.showToast({ title: '请填写学科名称', icon: 'none' })
      return
    }
    try {
      await request({ url: '/wrongbook/subjects', method: 'POST', data: { name } })
      this.setData({ name: '' })
      wx.showToast({ title: '已添加', icon: 'success' })
      this.load()
    } catch (e) {}
  },

  onDelete(e) {
    const id = e.currentTarget.dataset.id
    const name = e.currentTarget.dataset.name
    wx.showModal({
      title: '删除学科',
      content: `确定删除「${name}」？该学科下仍有错题时无法删除。`,
      confirmColor: '#C95C5C',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await request({ url: `/wrongbook/subjects/${id}`, method: 'DELETE' })
          wx.showToast({ title: '已删除', icon: 'success' })
          this.load()
        } catch (e) {}
      },
    })
  },
})
