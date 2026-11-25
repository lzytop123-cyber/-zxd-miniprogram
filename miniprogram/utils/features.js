/**
 * 自定义 tabBar 与功能开关
 */

const ALL_TABS = [
  { pagePath: '/pages/home/index', text: '首页', icon: '/assets/tab-home.png', selectedIcon: '/assets/tab-home-active.png' },
  {
    pagePath: '/pages/packages/index',
    text: '套餐',
    icon: '/assets/tab-packages.png',
    selectedIcon: '/assets/tab-packages-active.png',
  },
  { pagePath: '/pages/checkin/index', text: '入座', icon: '/assets/tab-checkin.png', selectedIcon: '/assets/tab-checkin-active.png' },
  {
    pagePath: '/pages/report/index',
    text: '学习报告',
    icon: '/assets/tab-report.png',
    selectedIcon: '/assets/tab-report-active.png',
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
    marketplace: Boolean(features && features.marketplace === true),
  }
  const app = getApp()
  if (app && app.globalData) {
    app.globalData.features = next
  }
  writeCachedFeatures(next)
  return next
}

function isMarketplaceEnabled() {
  return getFeatures().marketplace === true
}

function buildTabList() {
  return ALL_TABS.slice()
}

function indexOfPath(path, list) {
  const tabs = list || buildTabList()
  const normalized = path && path.startsWith('/') ? path : `/${path || ''}`
  return tabs.findIndex((t) => t.pagePath === normalized)
}

/** 页面 onShow：同步 tab 列表与选中项 */
function syncTabBar(page, pagePath) {
  const tabBar = typeof page.getTabBar === 'function' ? page.getTabBar() : null
  const list = buildTabList()
  const idx = indexOfPath(pagePath, list)
  const selected = idx >= 0 ? idx : 0
  if (tabBar) {
    tabBar.setData({ list, selected, collapsed: false })
  }
}

module.exports = {
  ALL_TABS,
  getFeatures,
  setFeatures,
  isMarketplaceEnabled,
  buildTabList,
  indexOfPath,
  syncTabBar,
}
