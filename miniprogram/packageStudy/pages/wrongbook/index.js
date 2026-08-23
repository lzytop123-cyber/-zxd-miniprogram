const { request } = require('../../../utils/request')
const routes = require('../../../utils/routes')
const { decorateQuestion } = require('../../utils/wrongbook')

const STATUS_FILTERS = [
  { value: null, label: '全部' },
  { value: 0, label: '未掌握' },
  { value: 1, label: '仍然错' },
  { value: 2, label: '已掌握' },
]

Page({
  data: {
    subjects: [],
    subjectId: null,
    statusFilters: STATUS_FILTERS,
    status: null,
    tags: [],
    tag: '',
    keyword: '',
    items: [],
    page: 1,
    finished: false,
    loading: false,
  },

  onShow() {
    this.reload()
  },

  onPullDownRefresh() {
    this.reload().finally(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.finished || this.data.loading) return
    this.loadList()
  },

  reload() {
    this.setData({ page: 1, finished: false, items: [] })
    return Promise.all([this.loadSubjects(), this.loadTags(), this.loadList()])
  },

  loadSubjects() {
    return request({ url: '/wrongbook/subjects', force: true }).then((rows) => {
      this.setData({ subjects: rows || [] })
    })
  },

  loadTags() {
    return request({ url: '/wrongbook/tags', force: true, silent: true }).then((rows) => {
      this.setData({ tags: rows || [] })
    }).catch(() => {})
  },

  loadList() {
    if (this.data.loading) return Promise.resolve()
    this.setData({ loading: true })
    const { subjectId, status, tag, keyword, page } = this.data
    const query = [
      `page=${page}`,
      'page_size=20',
      subjectId != null ? `subject_id=${subjectId}` : '',
      status != null ? `status=${status}` : '',
      tag ? `tag=${encodeURIComponent(tag)}` : '',
      keyword ? `keyword=${encodeURIComponent(keyword)}` : '',
    ].filter(Boolean).join('&')
    return request({ url: `/wrongbook/list?${query}`, force: true })
      .then(async (res) => {
        const rows = (res && res.items) || []
        const decorated = await Promise.all(rows.map((row) => decorateQuestion(row)))
        const items = page === 1 ? decorated : this.data.items.concat(decorated)
        this.setData({
          items,
          page: page + 1,
          finished: items.length >= (res.total || 0),
          loading: false,
        })
      })
      .catch(() => {
        this.setData({ loading: false })
      })
  },

  onSubject(e) {
    const id = e.currentTarget.dataset.id
    const subjectId = id === '' || id == null ? null : Number(id)
    if (subjectId === this.data.subjectId) return
    this.setData({ subjectId, page: 1, finished: false, items: [] })
    this.loadList()
  },

  onStatus(e) {
    const raw = e.currentTarget.dataset.value
    const status = raw === '' || raw == null ? null : Number(raw)
    if (status === this.data.status) return
    this.setData({ status, page: 1, finished: false, items: [] })
    this.loadList()
  },

  onTag(e) {
    const tag = e.currentTarget.dataset.tag || ''
    const next = tag === this.data.tag ? '' : tag
    this.setData({ tag: next, page: 1, finished: false, items: [] })
    this.loadList()
  },

  onKeyword(e) {
    this.setData({ keyword: e.detail.value || '' })
  },

  onSearch() {
    this.setData({ page: 1, finished: false, items: [] })
    this.loadList()
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `${routes.wrongbookDetail}?id=${id}` })
  },

  goCreate() {
    wx.navigateTo({ url: routes.wrongbookEdit })
  },

  goSubjects() {
    wx.navigateTo({ url: routes.wrongbookSubjects })
  },
})
