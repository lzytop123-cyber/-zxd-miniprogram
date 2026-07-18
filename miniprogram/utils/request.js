const { getApiBase } = require('../config')
const requestCache = require('./requestCache')

function getErrorMessage(res) {
  const data = res.data || {}
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail) && data.detail[0]) {
    const item = data.detail[0]
    if (item.loc && item.loc.includes('code')) return '请输入券码'
    return item.msg || '请求参数错误'
  }
  if (data.detail && typeof data.detail === 'object') {
    try {
      return JSON.stringify(data.detail)
    } catch (e) {
      return '请求失败'
    }
  }
  if (typeof data.message === 'string' && data.message) return data.message
  return `请求失败(${res.statusCode})`
}

function toRequestError(payload, fallback) {
  const msg = formatRequestError(payload) || fallback || '请求失败'
  const err = new Error(msg)
  if (payload && typeof payload === 'object') {
    err.detail = typeof payload.detail === 'string' ? payload.detail : msg
    err.statusCode = payload.statusCode
    err.code = payload.code
  }
  return err
}

let _redirectingToLogin = false

function currentPagePath() {
  try {
    const pages = getCurrentPages()
    if (!pages.length) return ''
    const cur = pages[pages.length - 1]
    const opts = cur.options || {}
    const qs = Object.keys(opts)
      .map((k) => `${k}=${opts[k]}`)
      .join('&')
    return '/' + cur.route + (qs ? `?${qs}` : '')
  } catch (e) {
    return ''
  }
}

/** 登录态失效（401）：清理本地登录信息并引导重新登录。 */
function handleUnauthorized() {
  try {
    wx.removeStorageSync('token')
    wx.removeStorageSync('userInfo')
  } catch (e) {
    // ignore
  }
  try {
    requestCache.invalidate() // 清空全部缓存，避免读到旧用户数据
  } catch (e) {
    // ignore
  }
  try {
    const app = getApp({ allowDefault: true })
    if (app && app.globalData) {
      app.globalData.user = null
      app.globalData.loginReady = false
      app.globalData.loginPromise = null
    }
  } catch (e) {
    // ignore
  }

  if (_redirectingToLogin) return
  _redirectingToLogin = true
  setTimeout(() => {
    _redirectingToLogin = false
  }, 3000)
  try {
    const routes = require('./routes')
    const redirect = currentPagePath()
    if (redirect && redirect.indexOf(routes.profileLogin) === 0) return
    const query = redirect ? `?redirect=${encodeURIComponent(redirect)}` : ''
    wx.navigateTo({ url: routes.profileLogin + query })
  } catch (e) {
    // ignore
  }
}

const REQUEST_TIMEOUT = 15000

function rawRequest({ url, method = 'GET', data, silent = false, retries }) {
  const payload = data === undefined ? undefined : data
  // GET 幂等，弱网下默认重试 1 次
  const maxRetries = retries != null ? retries : method.toUpperCase() === 'GET' ? 1 : 0
  return new Promise((resolve, reject) => {
    wx.request({
      url: getApiBase() + url,
      method,
      timeout: REQUEST_TIMEOUT,
      ...(payload !== undefined ? { data: payload } : {}),
      header: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${wx.getStorageSync('token') || ''}`,
      },
      success(res) {
        if (res.statusCode === 401) {
          handleUnauthorized()
          const msg = getErrorMessage(res)
          reject(toRequestError({ ...(res.data || {}), detail: msg, statusCode: 401 }, msg))
          return
        }
        if (res.statusCode >= 400) {
          const msg = getErrorMessage(res)
          if (!silent) {
            wx.showToast({ title: String(msg).slice(0, 40), icon: 'none', duration: 2500 })
          }
          reject(toRequestError({ ...(res.data || {}), detail: msg, statusCode: res.statusCode }, msg))
          return
        }
        if (res.data && res.data.code === 0) {
          resolve(res.data.data)
        } else {
          const msg = (res.data && res.data.message) || '请求失败'
          if (!silent) {
            wx.showToast({ title: String(msg).slice(0, 40), icon: 'none' })
          }
          reject(toRequestError(res.data || { message: msg }, msg))
        }
      },
      fail(err) {
        if (maxRetries > 0) {
          resolve(rawRequest({ url, method, data, silent, retries: maxRetries - 1 }))
          return
        }
        const msg = (err && (err.errMsg || err.message)) || '网络异常，请稍后重试'
        if (!silent) {
          wx.showToast({ title: '网络异常，请稍后重试', icon: 'none' })
        }
        reject(toRequestError({ message: msg, errMsg: msg }, msg))
      },
    })
  })
}

/**
 * @param {object} options
 * @param {number} [options.cacheTtl] 毫秒；0 不缓存
 * @param {boolean} [options.force] 跳过缓存并强制请求
 */
function request(options) {
  const { url, method = 'GET', data, silent = false, force = false } = options
  const ttl = requestCache.resolveTtl(url, method, options)
  const key = requestCache.buildKey(method, url, data)

  if (!force && method.toUpperCase() === 'GET') {
    return requestCache.runDeduped(key, ttl, () => rawRequest({ url, method, data, silent }))
  }

  return rawRequest({ url, method, data, silent })
}

function invalidateCache(match) {
  requestCache.invalidate(match)
}

function formatRequestError(err) {
  if (!err) return '请求失败'
  if (typeof err === 'string') return err
  if (typeof err.detail === 'string') return err.detail
  if (typeof err.message === 'string' && err.message && err.message !== '[object Object]') {
    return err.message
  }
  if (typeof err.errMsg === 'string' && err.errMsg) return err.errMsg
  if (err.detail && typeof err.detail === 'object') {
    try {
      return JSON.stringify(err.detail)
    } catch (e) {
      return '请求失败'
    }
  }
  return '请求失败'
}

module.exports = { request, invalidateCache, getErrorMessage, formatRequestError }
