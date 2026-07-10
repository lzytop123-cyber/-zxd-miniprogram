/**
 * 悬浮 tabBar 滚动收起/展开
 * 页面在 onPageScroll（或 scroll-view bindscroll）里调用 handleTabScroll(this, scrollTop)
 */

const COLLAPSE_AFTER = 60
const DELTA = 10

function handleTabScroll(page, scrollTop) {
  const tabBar = typeof page.getTabBar === 'function' ? page.getTabBar() : null
  if (!tabBar || typeof tabBar.setCollapsed !== 'function') return

  const last = page._tabbarLastTop || 0
  const top = scrollTop || 0

  if (top <= COLLAPSE_AFTER) {
    tabBar.setCollapsed(false)
  } else if (top - last > DELTA) {
    tabBar.setCollapsed(true)
  } else if (last - top > DELTA) {
    tabBar.setCollapsed(false)
  }

  page._tabbarLastTop = top
}

module.exports = { handleTabScroll }
