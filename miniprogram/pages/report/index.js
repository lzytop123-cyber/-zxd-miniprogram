const { request } = require('../../utils/request')

Page({
  data: {
    tab: 'report',

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
    this.load()
  },

  load() {
    request({ url: '/report/summary' }).then((summary) => {
      this.setData({ summary })
    })
    this.loadLeaderboard()
  },

  loadLeaderboard() {
    const params = this.data.storeId ? `?store_id=${this.data.storeId}` : ''
    request({ url: `/report/leaderboard${params}` }).then((leaderboard) => {
      this.setData({ leaderboard })
    })
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
    this.loadLeaderboard()
  },

  // ===== 分段切换 =====
  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    if (tab === this.data.tab) return
    this.setData({ tab })
    if (tab === 'assistant' && !this.data.introLoaded) {
      this.loadIntro()
    }
  },

  // ===== AI 助手 =====
  loadIntro() {
    this.setData({ introLoaded: true })
    request({ url: '/assistant/intro', silent: true })
      .then((intro) => {
        this.setData({
          greeting: intro.greeting,
          suggestions: intro.suggestions || [],
        })
      })
      .catch(() => {
        this.setData({ greeting: 'Hi，我是知行岛学习助手小岛 🌱，有什么可以帮你的？' })
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
