const { request, routes, absUrl, guardMarketplace } = require('../../utils/market')

Page({
  data: {
    keyword: '',
    examCategories: [],
    materialCategories: [],
    latest: [],
    loading: true,
  },

  onShow() {
    if (!guardMarketplace(this)) return
    this.load()
  },

  onPullDownRefresh() {
    this.load().finally(() => wx.stopPullDownRefresh())
  },

  async load() {
    this.setData({ loading: true })
    try {
      const data = await request({ url: '/market/home', silent: true })
      const mapItems = (items) =>
        (items || []).map((it) => ({
          ...it,
          cover: absUrl((it.images && it.images[0]) || ''),
          priceText: it.is_free ? '免费' : `¥${it.price}`,
        }))
      this.setData({
        examCategories: data.exam_categories || [],
        materialCategories: data.material_categories || [],
        latest: mapItems(data.latest),
        loading: false,
      })
    } catch (e) {
      this.setData({ loading: false })
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  onSearchInput(e) {
    this.setData({ keyword: e.detail.value })
  },

  goSearch() {
    const q = (this.data.keyword || '').trim()
    wx.navigateTo({
      url: `${routes.marketList}${q ? `?q=${encodeURIComponent(q)}` : ''}`,
    })
  },

  goExam(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `${routes.marketList}?exam_category_id=${id}` })
  },

  goMaterial(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `${routes.marketList}?material_category_id=${id}` })
  },

  goList() {
    wx.navigateTo({ url: routes.marketList })
  },

  goDetail(e) {
    wx.navigateTo({ url: `${routes.marketDetail}?id=${e.currentTarget.dataset.id}` })
  },

  goPublish() {
    wx.navigateTo({ url: routes.marketPublish })
  },

  goMine() {
    wx.navigateTo({ url: routes.marketMine })
  },
})
