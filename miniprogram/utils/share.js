/** 小程序分享：开启菜单 + 统一卡片文案 */

const SHARE_TITLE = '知行岛自习空间'
const HOME_PATH = '/pages/home/index'
const PENDING_INVITE_KEY = 'pending_invite_code'

function enableShareMenu() {
  try {
    wx.showShareMenu({
      withShareTicket: true,
      menus: ['shareAppMessage', 'shareTimeline'],
    })
  } catch (e) {
    // 低版本基础库忽略
  }
}

function savePendingInvite(code) {
  const c = String(code || '').trim().toUpperCase()
  if (!c) return
  try {
    wx.setStorageSync(PENDING_INVITE_KEY, c)
  } catch (e) {
    // ignore
  }
}

function peekPendingInvite() {
  try {
    return String(wx.getStorageSync(PENDING_INVITE_KEY) || '').trim().toUpperCase()
  } catch (e) {
    return ''
  }
}

function clearPendingInvite() {
  try {
    wx.removeStorageSync(PENDING_INVITE_KEY)
  } catch (e) {
    // ignore
  }
}

function shareAppMessage(extra = {}) {
  return {
    title: extra.title || SHARE_TITLE,
    path: extra.path || HOME_PATH,
  }
}

function shareTimeline(extra = {}) {
  return {
    title: extra.title || SHARE_TITLE,
    query: extra.query || '',
  }
}

module.exports = {
  SHARE_TITLE,
  HOME_PATH,
  enableShareMenu,
  savePendingInvite,
  peekPendingInvite,
  clearPendingInvite,
  shareAppMessage,
  shareTimeline,
}
