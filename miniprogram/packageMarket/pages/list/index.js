const { request, routes, absUrl, guardMarketplace } = require('../../utils/market')

Page({
  data: {
    q: '',
    exam_category_id: '',
    material_category_id: '',
    store_id: '',
    is_free: '',
    stores: [],
    examCategories: [],
    materialCategories: [],
    items: [],
    page: 1,
    total: 0,
    loading: false,
    finished: false,
  },

  onLoad(options) {
    if (!guardMarketplace(this)) return
    this.setData({
      q: options.q ? decodeURIComponent(options.q) : '',
      exam_category_id: options.exam_category_id || '',
      material_category_id: options.material_category_id || '',
      store_id: options.store_id || '',
    })
    this.loadMeta().then(() => this.reload())
  },

  onPullDownRefresh() {
    this.reload().finally(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (!this.data.finished) this.loadMore()
  },

  async loadMeta() {
    const meta = await request({ url: '/market/meta', silent: true })
    this.setData({
      stores: meta.stores || [],
      examCategories: meta.exam_categories || [],
      materialCategories: meta.material_categories || [],
    })
  },

  buildQuery(page) {
    const d = this.data
    const parts = [`page=${page}`, 'page_size=20']
    if (d.q) parts.push(`q=${encodeURIComponent(d.q)}`)
    if (d.exam_category_id) parts.push(`exam_category_id=${d.exam_category_id}`)
    if (d.material_category_id) parts.push(`material_category_id=${d.material_category_id}`)
    if (d.store_id) parts.push(`store_id=${d.store_id}`)
    if (d.is_free !== '') parts.push(`is_free=${d.is_free}`)
    return parts.join('&')
  },

  async reload() {
    this.setData({ page: 1, finished: false, items: [] })
    await this.loadMore(true)
  },

  async loadMore(reset) {
    if (this.data.loading) return
    this.setData({ loading: true })
    try {
      const page = reset ? 1 : this.data.page
      const data = await request({ url: `/market/listings?${this.buildQuery(page)}`, silent: true })
      const mapped = (data.items || []).map((it) => ({
        ...it,
        cover: absUrl((it.images && it.images[0]) || ''),
        priceText: it.is_free ? '免费' : `¥${it.price}`,
      }))
      const items = reset ? mapped : this.data.items.concat(mapped)
      const finished = items.length >= (data.total || 0)
      this.setData({
        items,
        total: data.total || 0,
        page: page + 1,
        finished,
        loading: false,
      })
    } catch (e) {
      this.setData({ loading: false })
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  onExamPick(e) {
    const item = this.data.examCategories[e.detail.value]
    this.setData({ exam_category_id: item ? item.id : '' }, () => this.reload())
  },

  onMaterialPick(e) {
    const item = this.data.materialCategories[e.detail.value]
    this.setData({ material_category_id: item ? item.id : '' }, () => this.reload())
  },

  onStorePick(e) {
    const item = this.data.stores[e.detail.value]
    this.setData({ store_id: item ? item.id : '' }, () => this.reload())
  },

  toggleFree() {
    const next = this.data.is_free === true ? '' : true
    this.setData({ is_free: next }, () => this.reload())
  },

  goDetail(e) {
    wx.navigateTo({ url: `${routes.marketDetail}?id=${e.currentTarget.dataset.id}` })
  },
})
