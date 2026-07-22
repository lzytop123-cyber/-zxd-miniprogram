const { request } = require('../../utils/request')
const { handleTabScroll } = require('../../utils/tabbar')
const { syncTabBar, isStudyAssistantEnabled } = require('../../utils/features')
const { enableShareMenu, shareAppMessage, shareTimeline } = require('../../utils/share')

Page({
  data: {
    tab: 'assistant',

    // 学习报告
    summary: null,
    leaderboard: [],
    daily: [],
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
  },

  onShareAppMessage() {
    return shareAppMessage({ title: '知行岛自习空间 · 学习助手' })
  },

  onShareTimeline() {
    return shareTimeline({ title: '知行岛自习空间 · 学习助手' })
  },

  onShow() {
    enableShareMenu()
    syncTabBar(this, '/pages/report/index')
    if (!isStudyAssistantEnabled()) {
      wx.switchTab({ url: '/pages/home/index' })
      return
    }
    this._tabbarLastTop = 0
    this.load({ silent: true })
    if (this.data.tab === 'assistant' && !this.data.introLoaded) {
      this.loadIntro()
    }
  },

  onPullDownRefresh() {
    const tasks = [this.load({ force: true })]
    if (this.data.tab === 'assistant') {
      this.setData({ introLoaded: false })
      tasks.push(this.loadIntro({ force: true }))
    }
    Promise.all(tasks).finally(() => wx.stopPullDownRefresh())
  },

  onPageScroll(e) {
    handleTabScroll(this, e.scrollTop)
  },

  onChatScroll(e) {
    handleTabScroll(this, e.detail.scrollTop)
  },

  load(options = {}) {
    const { force = false } = options
    return Promise.all([
      request({ url: '/report/summary', silent: true, force }).then((summary) => {
        this.setData({ summary })
      }).catch(() => {}),
      this.loadLeaderboard({ force }),
      this.loadDaily({ force }),
    ])
  },

  loadLeaderboard(options = {}) {
    const { force = false } = options
    const params = this.data.storeId ? `?store_id=${this.data.storeId}` : ''
    return request({ url: `/report/leaderboard${params}`, silent: true, force }).then((leaderboard) => {
      this.setData({ leaderboard })
    }).catch(() => {})
  },

  loadDaily(options = {}) {
    const { force = false } = options
    return request({ url: `/report/daily?days=${this.data.days}`, silent: true, force })
      .then((rows) => {
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
      .catch(() => {})
  },

  setDays(e) {
    const days = Number(e.currentTarget.dataset.d)
    if (days === this.data.days) return
    this.setData({ days })
    this.loadDaily({ force: true })
  },

  onScopeChange(e) {
    const idx = Number(e.detail.value)
    if (idx === 0) {
      this.setData({ scopeLabel: '全平台', storeId: null })
      this.loadLeaderboard({ force: true })
      return
    }
    this.setData({ scopeLabel: '本店' })
    this.resolveStoreId().then((storeId) => {
      this.setData({ storeId: storeId || null })
      this.loadLeaderboard({ force: true })
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
      .catch(() => null)
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    if (tab === this.data.tab) return
    this.setData({ tab })
    if (tab === 'assistant' && !this.data.introLoaded) {
      this.loadIntro()
    }
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
