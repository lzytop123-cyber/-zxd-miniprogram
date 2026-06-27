// 环境切换：USE_PROD=true 连服务器，false 连本机
const USE_PROD = true

const PROD_API_BASE = 'https://api.islandspace.xyz/api'
const PROD_STATIC_BASE = 'https://api.islandspace.xyz'

// 真机调试/预览时使用的局域网 IP（cmd 里 ipconfig 查看 IPv4）
const DEV_LAN_HOST = '192.168.0.104'
const DEV_LOCAL_HOST = '127.0.0.1'
const DEV_API_PORT = 8002

/**
 * 是否在微信开发者工具的模拟器里。
 * 模拟 iPhone 时 platform 是 ios/android，不是 devtools，必须用 host.env 判断。
 */
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

/** 模拟器 → 127.0.0.1；真机预览 → 局域网 IP */
function getDevHost() {
  if (isWechatDevtools()) return DEV_LOCAL_HOST
  // 本地开发时 API 走局域网，便于真机；图片会通过 media.js 下载到本地再展示
  return DEV_LAN_HOST
}

function getApiBase() {
  if (USE_PROD) return PROD_API_BASE
  return `http://${getDevHost()}:${DEV_API_PORT}/api`
}

function getStaticBase() {
  if (USE_PROD) return PROD_STATIC_BASE
  return `http://${getDevHost()}:${DEV_API_PORT}`
}

/** 把 /static/... 或旧完整 URL 转成当前环境可访问地址 */
function resolveStaticUrl(url) {
  if (!url) return ''
  const marker = '/static/'
  const idx = url.indexOf(marker)
  if (idx >= 0) {
    return getStaticBase() + url.slice(idx)
  }
  // 生产环境真机禁止 http 直链，统一升 HTTPS
  if (USE_PROD && url.startsWith('http://')) {
    return url.replace(/^http:\/\//i, 'https://')
  }
  return url
}

module.exports = {
  USE_PROD,
  DEV_LAN_HOST,
  DEV_LOCAL_HOST,
  DEV_API_PORT,
  isWechatDevtools,
  getDevHost,
  getApiBase,
  getStaticBase,
  resolveStaticUrl,
}
