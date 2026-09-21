const { request } = require('../../utils/request')
const { handleTabScroll } = require('../../utils/tabbar')
const { syncTabBar, isStudyAssistantEnabled, leaveStudyAssistantIfDisabled } = require('../../utils/features')
const { enableShareMenu, shareAppMessage, shareTimeline } = require('../../utils/share')
const { resolveStaticUrl } = require('../../config')
const { resolveImageForDisplay } = require('../../utils/media')
const routes = require('../../utils/routes')

/** 排行榜头像：优先下载到本地；失败时回退 HTTPS/完整 URL，避免被吞成空占位 */
async function resolveLeaderboardAvatar(url) {
  if (!url) return ''
  const fallback = resolveStaticUrl(url) || url
  try {
    return (await resolveImageForDisplay(url)) || fallback
  } catch (err) {
    return fallback
  }
}

const WB_STATUS_FILTERS = [
  { value: null, label: '全部' },
  { value: 0, label: '未掌握' },
  { value: 1, label: '仍然错' },
  { value: 2, label: '已掌握' },
]
const WB_STATUS_LABELS = { 0: '未掌握', 1: '仍然错', 2: '已掌握' }

async function decorateWbItem(row) {
  const item = row || {}
  const urls = item.image_urls || []
  const display = await Promise.all(urls.map((u) => resolveImageForDisplay(u)))
  return {
    ...item,
    cover: display[0] || '',
    status_label: item.status_label || WB_STATUS_LABELS[item.status] || '未掌握',
  }
}

// 将累计分钟数格式化为易读的「X时Y分」（不足 1 小时显示「X分钟」）
function formatStudyMinutes(minutes) {
  const total = Math.max(0, Math.round(Number(minutes) || 0))
  if (total < 60) return `${total}分钟`
  const hours = Math.floor(total / 60)
  const rem = total % 60
  return rem > 0 ? `${hours}时${rem}分` : `${hours}时`
}

Page({
  data: {
    tab: 'assistant',
    blocked: false,

    // 学习报告
    summary: null,
    leaderboard: [],
    daily: [],
    reportLoading: false,
    reportError: '',
    days: 7,
    scopeLabel: '全平台',
    storeId: null,

    // AI 助手
    greeting: '',
    suggestions: [],
    messages: [],
    draft: '',
    loading: false,
    scrollInto: '',
    introLoaded: false,

    wbSubjects: [],
    wbSubjectId: null,
    wbStatusFilters: WB_STATUS_FILTERS,
    wbStatus: null,
    wbTags: [],
    wbTag: '',
    wbKeyword: '',
    wbItems: [],
    wbPage: 1,
    wbFinished: false,
    wbLoading: false,
    wbLoaded: false,
  },

  onShareAppMessage() {
    return shareAppMessage({ title: '知行岛自习空间 · 学习助手' })
  },

  onShareTimeline() {
    return shareTimeline({ title: '知行岛自习空间 · 学习助手' })
  },

  onLoad() {
    if (!isStudyAssistantEnabled()) {
      this.setData({ blocked: true })
      leaveStudyAssistantIfDisabled()
    }
  },

  onShow() {
    enableShareMenu()
    syncTabBar(this, '/pages/report/index')
    if (!isStudyAssistantEnabled()) {
      this.setData({ blocked: true })
      leaveStudyAssistantIfDisabled()
      return
    }
    this.setData({ blocked: false })
    this._tabbarLastTop = 0
    this.load({ silent: true })
    if (this.data.tab === 'assistant' && !this.data.introLoaded) {
      this.loadIntro()
    }
    if (this.data.tab === 'wrongbook') {
      this.reloadWrongbook()
    }
  },

  onPullDownRefresh() {
    const tasks = [this.load({ force: true })]
    if (this.data.tab === 'assistant') {
      this.setData({ introLoaded: false })
      tasks.push(this.loadIntro({ force: true }))
    }
    if (this.data.tab === 'wrongbook') {
      tasks.push(this.reloadWrongbook())
    }
    Promise.all(tasks).finally(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.tab !== 'wrongbook' || this.data.wbFinished || this.data.wbLoading) return
    this.loadWrongbookList()
  },

  onPageScroll(e) {
    handleTabScroll(this, e.scrollTop)
  },

  onChatScroll(e) {
    handleTabScroll(this, e.detail.scrollTop)
  },

  load(options = {}) {
    const { force = false } = options
    this.setData({ reportLoading: true, reportError: '' })
    return Promise.all([
      request({ url: '/report/summary', silent: true, force }).then((summary) => {
        this.setData({ summary })
      }),
      this.loadLeaderboard({ force }),
      this.loadDaily({ force }),
    ]).then(() => {
      this.setData({ reportLoading: false, reportError: '' })
    }).catch(() => {
      this.setData({
        reportLoading: false,
        reportError: '学习报告加载失败，请检查网络后重试',
      })
    })
  },

  retryReport() {
    if (this.data.scopeLabel === '本店' && !this.data.storeId) {
      this.setData({ reportLoading: true, reportError: '' })
      return this.resolveStoreId()
        .then((storeId) => {
          if (!storeId) throw new Error('未找到可用门店')
          this.setData({ storeId })
          return this.load({ force: true })
        })
        .catch(() => this.setData({
          reportLoading: false,
          reportError: '本店信息加载失败，请检查网络后重试',
        }))
    }
    return this.load({ force: true })
  },

  loadLeaderboard(options = {}) {
    const { force = false } = options
    const requestId = (this._leaderboardRequestId || 0) + 1
    this._leaderboardRequestId = requestId
    const params = this.data.storeId ? `?store_id=${this.data.storeId}` : ''
    return request({ url: `/report/leaderboard${params}`, silent: true, force }).then(async (leaderboard) => {
      const list = await Promise.all(
        (leaderboard || []).map(async (item) => ({
          ...item,
          time_label: formatStudyMinutes(item.total_minutes),
          avatar_url: await resolveLeaderboardAvatar(item.avatar_url),
        }))
      )
      if (requestId !== this._leaderboardRequestId) return
      this.setData({ leaderboard: list })
    })
  },

  loadDaily(options = {}) {
    const { force = false } = options
    const requestId = (this._dailyRequestId || 0) + 1
    this._dailyRequestId = requestId
    return request({ url: `/report/daily?days=${this.data.days}`, silent: true, force })
      .then((rows) => {
        if (requestId !== this._dailyRequestId) return
        const list = rows || []
        const max = list.reduce((m, r) => Math.max(m, r.total_minutes || 0), 0)
        const daily = list.map((r) => {
          const md = String(r.stat_date || '').slice(5).replace('-', '/')
          return {
            label: md,
            minutes: r.total_minutes || 0,
            height: max > 0 ? Math.max(4, Math.round((r.total_minutes / max) * 100)) : 0,
          }
        })
        this.setData({ daily })
      })
  },

  setDays(e) {
    const days = Number(e.currentTarget.dataset.d)
    if (days === this.data.days) return
    this.setData({ days, reportLoading: true, reportError: '' })
    this.loadDaily({ force: true })
      .then(() => this.setData({ reportLoading: false }))
      .catch(() => this.setData({
        reportLoading: false,
        reportError: '学习趋势加载失败，请检查网络后重试',
      }))
  },

  onScopeChange(e) {
    const idx = Number(e.detail.value)
    const requestId = (this._scopeRequestId || 0) + 1
    this._scopeRequestId = requestId
    if (idx === 0) {
      this.setData({ scopeLabel: '全平台', storeId: null, reportLoading: true, reportError: '' })
      return this.loadLeaderboard({ force: true })
        .then(() => {
          if (requestId === this._scopeRequestId) this.setData({ reportLoading: false })
        })
        .catch(() => {
          if (requestId !== this._scopeRequestId) return
          this.setData({
            reportLoading: false,
            reportError: '排行榜加载失败，请检查网络后重试',
          })
        })
    }
    this.setData({
      scopeLabel: '本店',
      storeId: null,
      leaderboard: [],
      reportLoading: true,
      reportError: '',
    })
    return this.resolveStoreId()
      .then((storeId) => {
        if (requestId !== this._scopeRequestId) return null
        if (!storeId) throw new Error('未找到可用门店')
        this.setData({ storeId })
        return this.loadLeaderboard({ force: true })
      })
      .then(() => {
        if (requestId === this._scopeRequestId) this.setData({ reportLoading: false })
      })
      .catch(() => {
        if (requestId !== this._scopeRequestId) return
        this.setData({
          reportLoading: false,
          reportError: '本店信息或排行榜加载失败，请重试',
        })
      })
  },

  /** 解析「本店」对应的门店 id（取门店列表首个，结果缓存）。 */
  resolveStoreId() {
    if (this._storeId) return Promise.resolve(this._storeId)
    return request({ url: '/store/list', silent: true })
      .then((list) => {
        const first = Array.isArray(list) && list.length ? list[0] : null
        this._storeId = first ? first.id : null
        return this._storeId
      })
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    if (tab === this.data.tab) return
    this.setData({ tab })
    if (tab === 'assistant' && !this.data.introLoaded) {
      this.loadIntro()
    }
    if (tab === 'wrongbook') {
      this.reloadWrongbook()
    }
  },

  reloadWrongbook() {
    this.setData({ wbPage: 1, wbFinished: false, wbItems: [] })
    return Promise.all([
      request({ url: '/wrongbook/subjects', force: true }).then((rows) => {
        this.setData({ wbSubjects: rows || [] })
      }),
      request({ url: '/wrongbook/tags', force: true, silent: true }).then((rows) => {
        this.setData({ wbTags: rows || [] })
      }).catch(() => {}),
      this.loadWrongbookList(),
    ])
  },

  loadWrongbookList() {
    if (this.data.wbLoading) return Promise.resolve()
    this.setData({ wbLoading: true })
    const { wbSubjectId, wbStatus, wbTag, wbKeyword, wbPage } = this.data
    const query = [
      `page=${wbPage}`,
      'page_size=20',
      wbSubjectId != null ? `subject_id=${wbSubjectId}` : '',
      wbStatus != null ? `status=${wbStatus}` : '',
      wbTag ? `tag=${encodeURIComponent(wbTag)}` : '',
      wbKeyword ? `keyword=${encodeURIComponent(wbKeyword)}` : '',
    ].filter(Boolean).join('&')
    return request({ url: `/wrongbook/list?${query}`, force: true })
      .then(async (res) => {
        const rows = (res && res.items) || []
        const decorated = await Promise.all(rows.map((row) => decorateWbItem(row)))
        const wbItems = wbPage === 1 ? decorated : this.data.wbItems.concat(decorated)
        this.setData({
          wbItems,
          wbPage: wbPage + 1,
          wbFinished: wbItems.length >= (res.total || 0),
          wbLoading: false,
          wbLoaded: true,
        })
      })
      .catch(() => {
        this.setData({ wbLoading: false })
      })
  },

  onWbSubject(e) {
    const id = e.currentTarget.dataset.id
    const wbSubjectId = id === '' || id == null ? null : Number(id)
    if (wbSubjectId === this.data.wbSubjectId) return
    this.setData({ wbSubjectId, wbPage: 1, wbFinished: false, wbItems: [] })
    this.loadWrongbookList()
  },

  onWbStatus(e) {
    const raw = e.currentTarget.dataset.value
    const wbStatus = raw === '' || raw == null ? null : Number(raw)
    if (wbStatus === this.data.wbStatus) return
    this.setData({ wbStatus, wbPage: 1, wbFinished: false, wbItems: [] })
    this.loadWrongbookList()
  },

  onWbTag(e) {
    const tag = e.currentTarget.dataset.tag || ''
    const wbTag = tag === this.data.wbTag ? '' : tag
    this.setData({ wbTag, wbPage: 1, wbFinished: false, wbItems: [] })
    this.loadWrongbookList()
  },

  onWbKeyword(e) {
    this.setData({ wbKeyword: e.detail.value || '' })
  },

  onWbSearch() {
    this.setData({ wbPage: 1, wbFinished: false, wbItems: [] })
    this.loadWrongbookList()
  },

  goWbDetail(e) {
    wx.navigateTo({ url: `${routes.wrongbookDetail}?id=${e.currentTarget.dataset.id}` })
  },

  goWbCreate() {
    wx.navigateTo({ url: routes.wrongbookEdit })
  },

  goWbSubjects() {
    wx.navigateTo({ url: routes.wrongbookSubjects })
  },

  loadIntro(options = {}) {
    const { force = false } = options
    this.setData({ introLoaded: true })
    return request({ url: '/assistant/intro', silent: true, force })
      .then((intro) => {
        this.setData({
          greeting: intro.greeting,
          suggestions: intro.suggestions || [],
        })
      })
      .catch(() => {
        if (!this.data.greeting) {
          this.setData({ greeting: 'Hi，我是知行岛学习助手小岛 🌱，有什么可以帮你的？' })
        }
      })
  },

  onInput(e) {
    this.setData({ draft: e.detail.value })
  },

  onSuggestionTap(e) {
    if (this.data.loading) return
    this.sendMessage(e.currentTarget.dataset.q)
  },

  onSend() {
    const text = (this.data.draft || '').trim()
    if (!text || this.data.loading) return
    this.sendMessage(text)
  },

  sendMessage(text) {
    this._seq = (this._seq || 0) + 1
    const messages = this.data.messages.concat({ _id: `m${this._seq}`, role: 'user', content: text })
    this.setData({ messages, draft: '', loading: true })
    this.scrollToBottom()

    const payload = messages.map((m) => ({ role: m.role, content: m.content }))
    request({
      url: '/assistant/chat',
      method: 'POST',
      data: { messages: payload },
      silent: true,
    })
      .then((res) => {
        this._seq += 1
        this.setData({
          messages: this.data.messages.concat({ _id: `m${this._seq}`, role: 'assistant', content: res.reply }),
          loading: false,
        })
        this.scrollToBottom()
      })
      .catch(() => {
        this._seq += 1
        this.setData({
          messages: this.data.messages.concat({
            _id: `m${this._seq}`,
            role: 'assistant',
            content: '网络有点问题，没能回复你，请稍后再试～',
          }),
          loading: false,
        })
        this.scrollToBottom()
      })
  },

  scrollToBottom() {
    this.setData({ scrollInto: '' }, () => {
      this.setData({ scrollInto: 'chat-bottom' })
    })
  },
})
