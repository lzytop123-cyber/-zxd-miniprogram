/**
 * 自定义 tabBar：按服务端 features 显示/隐藏「学习助手」
 * 审核期 FEATURE_STUDY_ASSISTANT=false，通过后改 true 并重启后端即可。
 */

const ALL_TABS = [
  { pagePath: '/pages/home/index', text: '首页', icon: '/assets/tab-home.png', selectedIcon: '/assets/tab-home-active.png' },
  { pagePath: '/pages/packages/index', text: '套餐', icon: '/assets/tab-packages.png', selectedIcon: '/assets/tab-packages-active.png' },
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

/** 页面 onShow：同步 tab 列表与选中项 */
function syncTabBar(page, pagePath) {
  const tabBar = typeof page.getTabBar === 'function' ? page.getTabBar() : null
  if (!tabBar) return

  const list = buildTabList()
  const selected = Math.max(0, indexOfPath(pagePath, list))
  tabBar.setData({ list, selected, collapsed: false })

  if (pagePath === '/pages/report/index' && !isStudyAssistantEnabled()) {
    wx.switchTab({ url: '/pages/home/index' })
  }
}

module.exports = {
  ALL_TABS,
  getFeatures,
  setFeatures,
  isStudyAssistantEnabled,
  buildTabList,
  indexOfPath,
  syncTabBar,
}
