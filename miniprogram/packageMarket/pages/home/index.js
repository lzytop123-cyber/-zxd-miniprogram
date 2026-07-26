const { request, routes, absUrl, guardMarketplace } = require('../../utils/market')

Page({
  data: {
    keyword: '',
    exam_category_id: '',
    material_category_id: '',
    examCategories: [],
    materialCategories: [],
    latest: [],
    loading: false,
    page: 1,
    finished: false,
    filtered: false,
  },

  onShow() {
    if (!guardMarketplace(this)) return
    this.ensureMeta().then(() => this.reload())
  },

  onPullDownRefresh() {
    this.reload().finally(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (!this.data.finished && !this.data.loading) this.loadMore()
  },

  async ensureMeta() {
    if (this.data.examCategories.length && this.data.materialCategories.length) return
    const data = await request({ url: '/market/meta', silent: true })
    this.setData({
      examCategories: data.exam_categories || [],
      materialCategories: data.material_categories || [],
    })
  },

  buildQuery(page) {
    const d = this.data
    const parts = [`page=${page}`, 'page_size=20']
    const q = (d.keyword || '').trim()
    if (q) parts.push(`q=${encodeURIComponent(q)}`)
    if (d.exam_category_id) parts.push(`exam_category_id=${d.exam_category_id}`)
    if (d.material_category_id) parts.push(`material_category_id=${d.material_category_id}`)
    return parts.join('&')
  },

  async reload() {
    const filtered = !!(
      (this.data.keyword || '').trim() ||
      this.data.exam_category_id ||
      this.data.material_category_id
    )
    this.setData({ page: 1, finished: false, latest: [], filtered })
    await this.loadMore(true)
  },

  async loadMore(reset) {
    if (this.data.loading) return
    this.setData({ loading: true })
    try {
      const page = reset ? 1 : this.data.page
      const data = await request({
        url: `/market/listings?${this.buildQuery(page)}`,
        silent: true,
      })
      const mapped = (data.items || []).map((it) => ({
        ...it,
        cover: absUrl((it.images && it.images[0]) || ''),
        priceText: it.is_free ? '免费' : `¥${it.price}`,
      }))
      const latest = reset ? mapped : this.data.latest.concat(mapped)
      const finished = latest.length >= (data.total || 0)
      this.setData({
        latest,
        page: page + 1,
        finished,
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
    this.reload()
  },

  goExam(e) {
    const id = String(e.currentTarget.dataset.id)
    const next = String(this.data.exam_category_id) === id ? '' : id
    this.setData({ exam_category_id: next }, () => this.reload())
  },

  goMaterial(e) {
    const id = String(e.currentTarget.dataset.id)
    const next = String(this.data.material_category_id) === id ? '' : id
    this.setData({ material_category_id: next }, () => this.reload())
  },

  clearFilters() {
    this.setData(
      {
        keyword: '',
        exam_category_id: '',
        material_category_id: '',
      },
      () => this.reload()
    )
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
