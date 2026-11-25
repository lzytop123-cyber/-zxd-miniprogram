/** 小程序分享：开启菜单 + 支持后台动态配置标题与封面图 */

const { resolveStaticUrl } = require('../config')

const SHARE_TITLE = '沉浸自习，来知行岛'
const SHARE_IMAGE = '/assets/share-cover.jpg'
const HOME_PATH = '/pages/home/index'
const PENDING_INVITE_KEY = 'pending_invite_code'
const SHARE_CONFIG_KEY = 'mp_share_config_v1'

let memoryShareConfig = null

function getShareConfig() {
  if (memoryShareConfig) return memoryShareConfig
  try {
    const cached = wx.getStorageSync(SHARE_CONFIG_KEY)
    if (cached && typeof cached === 'object') {
      memoryShareConfig = cached
      return cached
    }
  } catch (e) {
    // ignore
  }
  return { share_title: '', share_image_url: '' }
}

function setShareConfig(config = {}) {
  const title = typeof config.share_title === 'string' ? config.share_title.trim() : ''
  const rawImg = typeof config.share_image_url === 'string' ? config.share_image_url.trim() : ''
  const image = rawImg ? (resolveStaticUrl(rawImg) || rawImg) : ''
  const next = { share_title: title, share_image_url: image }
  memoryShareConfig = next
  try {
    wx.setStorageSync(SHARE_CONFIG_KEY, next)
  } catch (e) {
    // ignore
  }
  return next
}

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

function resolveShareTitle(extraTitle) {
  const cfg = getShareConfig()
  if (extraTitle && String(extraTitle).includes('邀请')) return extraTitle
  if (cfg.share_title) return cfg.share_title
  return extraTitle || SHARE_TITLE
}

function resolveShareImage(extraImage) {
  if (extraImage) return extraImage
  const cfg = getShareConfig()
  return cfg.share_image_url || SHARE_IMAGE
}

function shareAppMessage(extra = {}) {
  return {
    title: resolveShareTitle(extra.title),
    path: extra.path || HOME_PATH,
    imageUrl: resolveShareImage(extra.imageUrl),
  }
}

function shareTimeline(extra = {}) {
  return {
    title: resolveShareTitle(extra.title),
    query: extra.query || '',
    imageUrl: resolveShareImage(extra.imageUrl),
  }
}

module.exports = {
  SHARE_TITLE,
  SHARE_IMAGE,
  HOME_PATH,
  getShareConfig,
  setShareConfig,
  enableShareMenu,
  savePendingInvite,
  peekPendingInvite,
  clearPendingInvite,
  shareAppMessage,
  shareTimeline,
}
