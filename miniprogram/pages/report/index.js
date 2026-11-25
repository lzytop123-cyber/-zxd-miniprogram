const { request } = require('../../utils/request')
const auth = require('../../utils/auth')
const { handleTabScroll } = require('../../utils/tabbar')
const { syncTabBar } = require('../../utils/features')
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
    notLoggedIn: false,

    // 学习报告
    summary: null,
    leaderboard: [],
    daily: [],
    reportLoading: false,
    reportError: '',
    days: 7,
    scopeLabel: '全平台',
    storeId: null,
  },

  onShareAppMessage() {
    return shareAppMessage({ title: '知行岛自习空间 · 学习报告' })
  },

  onShareTimeline() {
    return shareTimeline({ title: '知行岛自习空间 · 学习报告' })
  },

  onShow() {
    enableShareMenu()
    syncTabBar(this, '/pages/report/index')
    this._tabbarLastTop = 0
    if (typeof auth.isLoggedIn === 'function' && !auth.isLoggedIn()) {
      this.setData({ notLoggedIn: true, reportLoading: false, reportError: '' })
      return
    }
    this.setData({ notLoggedIn: false })
    this.load({ silent: true })
  },

  goLogin() {
    if (typeof auth.goLogin === 'function') {
      auth.goLogin('/pages/report/index')
    } else if (routes.profileLogin) {
      wx.navigateTo({ url: `${routes.profileLogin}?redirect=${encodeURIComponent('/pages/report/index')}` })
    }
  },

  onPullDownRefresh() {
    if (typeof auth.isLoggedIn === 'function' && !auth.isLoggedIn()) {
      wx.stopPullDownRefresh()
      return
    }
    this.load({ force: true }).finally(() => wx.stopPullDownRefresh())
  },

  onPageScroll(e) {
    handleTabScroll(this, e.scrollTop)
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
    const span = Number(this.data.days) || 7
    return request({ url: `/report/daily?days=${span}`, silent: true, force })
      .then((rows) => {
        if (requestId !== this._dailyRequestId) return
        const list = Array.isArray(rows) ? rows : []
        const byDate = {}
        list.forEach((r) => {
          const key = String(r.stat_date || '').slice(0, 10)
          if (key) byDate[key] = Math.max(0, Math.round(Number(r.total_minutes) || 0))
        })

        // 补齐连续日期轴（避免仅有 1 天记录时画面孤零零一根柱子）
        const pad = (n) => (n < 10 ? `0${n}` : `${n}`)
        const now = new Date()
        const filled = []
        for (let i = span - 1; i >= 0; i -= 1) {
          const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i)
          const iso = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
          filled.push({
            label: `${pad(d.getMonth() + 1)}/${pad(d.getDate())}`,
            minutes: byDate[iso] || 0,
          })
        }
        const max = filled.reduce((m, r) => Math.max(m, r.minutes), 0)
        const daily = max > 0
          ? filled.map((r) => ({
            label: r.label,
            minutes: r.minutes,
            valueLabel: r.minutes > 0
              ? (r.minutes >= 60 ? `${+(r.minutes / 60).toFixed(1)}h` : `${r.minutes}m`)
              : '',
            height: r.minutes > 0 ? Math.max(8, Math.round((r.minutes / max) * 100)) : 0,
          }))
          : []
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

  setScope(e) {
    const idx = Number(e.currentTarget.dataset.scope)
    if ((idx === 0 && this.data.scopeLabel === '全平台') || (idx === 1 && this.data.scopeLabel === '本店')) {
      return
    }
    return this.onScopeChange({ detail: { value: idx } })
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

  /** 解析「本店」对应的门店 id（优先取用户最近选择的门店，否则取门店列表首个）。 */
  resolveStoreId() {
    let savedId = null
    try {
      const v = wx.getStorageSync('lastSelectedStoreId')
      if (v) savedId = Number(v) || null
    } catch (_) {}
    if (this._storeId && (!savedId || Number(this._storeId) === savedId)) {
      return Promise.resolve(this._storeId)
    }
    return request({ url: '/store/list', silent: true })
      .then((list) => {
        const stores = Array.isArray(list) ? list : []
        const matched = savedId ? stores.find((s) => Number(s.id) === savedId) : null
        const picked = matched || (stores.length ? stores[0] : null)
        this._storeId = picked ? picked.id : null
        return this._storeId
      })
  },
})
