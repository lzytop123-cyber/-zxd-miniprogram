// API 环境：仅开发者工具模拟器 → 本机；真机调试 / 体验版 / 正式版 → 生产
const PROD_API_BASE = 'https://api.islandspace.xyz/api'
const PROD_STATIC_BASE = 'https://api.islandspace.xyz'

const DEV_LAN_HOST = '192.168.0.104'
const DEV_LOCAL_HOST = '127.0.0.1'
const DEV_API_PORT = 8000

function getEnvVersion() {
  try {
    return wx.getAccountInfoSync().miniProgram.envVersion || 'release'
  } catch (e) {
    return 'release'
  }
}

/**
 * 生产 API：体验版 / 正式版 / 真机调试
 * 仅开发者工具模拟器 + develop 走本地 API
 */
function useProdApi() {
  if (getEnvVersion() === 'develop' && isWechatDevtools()) return false
  return true
}

/** 仅开发者工具 / develop 环境允许 mock 支付 */
function isDevEnv() {
  return getEnvVersion() === 'develop'
}

function isWechatDevtools() {
  try {
    if (typeof wx.getAppBaseInfo === 'function') {
      const { host } = wx.getAppBaseInfo()
      if (host && host.env === 'WeChatDevTools') return true
    }
    const info = wx.getSystemInfoSync()
    if (info.platform === 'devtools') return true
  } catch (e) {
    // ignore
  }
  return false
}

function getDevHost() {
  if (isWechatDevtools()) return DEV_LOCAL_HOST
  return DEV_LAN_HOST
}

function getApiBase() {
  if (useProdApi()) return PROD_API_BASE
  return `http://${getDevHost()}:${DEV_API_PORT}/api`
}

function getStaticBase() {
  if (useProdApi()) return PROD_STATIC_BASE
  return `http://${getDevHost()}:${DEV_API_PORT}`
}

function resolveStaticUrl(url) {
  if (!url) return ''
  // 已经是完整 HTTPS URL 就不拆了，直接返回
  if (url.startsWith('https://')) return url
  const marker = '/static/'
  const idx = url.indexOf(marker)
  if (idx >= 0) {
    return getStaticBase() + url.slice(idx)
  }
  if (url.startsWith('http://')) {
    return url.replace(/^http:\/\//i, 'https://')
  }
  return url
}

module.exports = {
  getEnvVersion,
  useProdApi,
  isDevEnv,
  USE_PROD: useProdApi(),
  DEV_LAN_HOST,
  DEV_LOCAL_HOST,
  DEV_API_PORT,
  isWechatDevtools,
  getDevHost,
  getApiBase,
  getStaticBase,
  resolveStaticUrl,
}
