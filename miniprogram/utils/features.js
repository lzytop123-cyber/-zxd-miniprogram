/**
 * 自定义 tabBar：按服务端 features 显示/隐藏「学习助手」
 * 审核期 FEATURE_STUDY_ASSISTANT=false，通过后改 true 并重启后端即可。
 */

const ALL_TABS = [
  { pagePath: '/pages/home/index', text: '首页', icon: '/assets/tab-home.png', selectedIcon: '/assets/tab-home-active.png' },
  {
    pagePath: '/pages/packages/index',
    text: '套餐',
    // ponytail: SVG data URI 内联，避免 tab-packages.png 与 tab-home.png 视觉重复
    icon: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM4QzlCQTUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMiA5YTMgMyAwIDAgMSAwIDZ2MmEyIDIgMCAwIDAgMiAyaDE2YTIgMiAwIDAgMCAyLTJ2LTJhMyAzIDAgMCAxIDAtNlY3YTIgMiAwIDAgMC0yLTJINGEyIDIgMCAwIDAtMiAyWiIvPjxwYXRoIGQ9Ik0xMyA1djIiLz48cGF0aCBkPSJNMTMgMTd2MiIvPjxwYXRoIGQ9Ik0xMyAxMXYyIi8+PC9zdmc+',
    selectedIcon: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiMyRDZBNEYiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMiA5YTMgMyAwIDAgMSAwIDZ2MmEyIDIgMCAwIDAgMiAyaDE2YTIgMiAwIDAgMCAyLTJ2LTJhMyAzIDAgMCAxIDAtNlY3YTIgMiAwIDAgMC0yLTJINGEyIDIgMCAwIDAtMiAyWiIvPjxwYXRoIGQ9Ik0xMyA1djIiLz48cGF0aCBkPSJNMTMgMTd2MiIvPjxwYXRoIGQ9Ik0xMyAxMXYyIi8+PC9zdmc+',
  },
  { pagePath: '/pages/checkin/index', text: '入座', icon: '/assets/tab-checkin.png', selectedIcon: '/assets/tab-checkin-active.png' },
  {
    pagePath: '/pages/report/index',
    text: '学习助手',
    icon: '/assets/tab-report.png',
    selectedIcon: '/assets/tab-report-active.png',
    feature: 'study_assistant',
  },
  { pagePath: '/pages/profile/index', text: '我的', icon: '/assets/tab-profile.png', selectedIcon: '/assets/tab-profile-active.png' },
]

const FEATURES_CACHE_KEY = 'mp_features_v1'

function readCachedFeatures() {
  try {
    return wx.getStorageSync(FEATURES_CACHE_KEY) || {}
  } catch (e) {
    return {}
  }
}

function writeCachedFeatures(features) {
  try {
    wx.setStorageSync(FEATURES_CACHE_KEY, features || {})
  } catch (e) {
    // ignore
  }
}

function getFeatures() {
  const app = getApp()
  if (app && app.globalData && app.globalData.features) {
    return app.globalData.features
  }
  return readCachedFeatures()
}

function setFeatures(features) {
  const next = {
    study_assistant: !(features && features.study_assistant === false),
    marketplace: !(features && features.marketplace === false),
  }
  const app = getApp()
  if (app && app.globalData) {
    app.globalData.features = next
  }
  writeCachedFeatures(next)
  return next
}

function isStudyAssistantEnabled() {
  return getFeatures().study_assistant !== false
}

function isMarketplaceEnabled() {
  return getFeatures().marketplace !== false
}

function buildTabList(features) {
  const f = features || getFeatures()
  return ALL_TABS.filter((tab) => {
    if (tab.feature === 'study_assistant') return f.study_assistant !== false
    return true
  })
}

function indexOfPath(path, list) {
  const tabs = list || buildTabList()
  const normalized = path && path.startsWith('/') ? path : `/${path || ''}`
  return tabs.findIndex((t) => t.pagePath === normalized)
}

/** 关闭学习助手时强制离开该页（switchTab 失败则 reLaunch） */
function leaveStudyAssistantIfDisabled() {
  if (isStudyAssistantEnabled()) return false
  wx.switchTab({
    url: '/pages/home/index',
    fail: () => {
      wx.reLaunch({ url: '/pages/home/index' })
    },
  })
  return true
}

/** 页面 onShow：同步 tab 列表与选中项 */
function syncTabBar(page, pagePath) {
  const tabBar = typeof page.getTabBar === 'function' ? page.getTabBar() : null
  const list = buildTabList()
  // 当前页若不在可见 Tab 中，不要误标成「首页选中」造成假象
  const idx = indexOfPath(pagePath, list)
  const selected = idx >= 0 ? idx : 0
  if (tabBar) {
    tabBar.setData({ list, selected, collapsed: false })
  }

  if (pagePath === '/pages/report/index') {
    leaveStudyAssistantIfDisabled()
  }
}

module.exports = {
  ALL_TABS,
  getFeatures,
  setFeatures,
  isStudyAssistantEnabled,
  isMarketplaceEnabled,
  buildTabList,
  indexOfPath,
  syncTabBar,
  leaveStudyAssistantIfDisabled,
}
