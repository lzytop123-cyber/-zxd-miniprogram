const { request } = require('../../utils/request')

Page({
  data: {
    tab: 'assistant',

    // 学习报告
    summary: null,
    leaderboard: [],
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

  onShow() {
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

  load(options = {}) {
    const { force = false } = options
    return Promise.all([
      request({ url: '/report/summary', silent: true, force }).then((summary) => {
        this.setData({ summary })
      }).catch(() => {}),
      this.loadLeaderboard({ force }),
    ])
  },

  loadLeaderboard(options = {}) {
    const { force = false } = options
    const params = this.data.storeId ? `?store_id=${this.data.storeId}` : ''
    return request({ url: `/report/leaderboard${params}`, silent: true, force }).then((leaderboard) => {
      this.setData({ leaderboard })
    }).catch(() => {})
  },

  setDays(e) {
    this.setData({ days: Number(e.currentTarget.dataset.d) })
    request({ url: `/report/daily?days=${this.data.days}` })
  },

  onScopeChange(e) {
    const idx = Number(e.detail.value)
    this.setData({
      scopeLabel: idx === 0 ? '全平台' : '本店',
      storeId: idx === 0 ? null : 1,
    })
    this.loadLeaderboard({ force: true })
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
