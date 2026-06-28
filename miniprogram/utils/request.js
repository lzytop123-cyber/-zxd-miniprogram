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
  return data.message || `请求失败(${res.statusCode})`
}

function rawRequest({ url, method = 'GET', data, silent = false }) {
  const payload = data === undefined ? undefined : data
  return new Promise((resolve, reject) => {
    wx.request({
      url: getApiBase() + url,
      method,
      ...(payload !== undefined ? { data: payload } : {}),
      header: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${wx.getStorageSync('token') || ''}`,
      },
      success(res) {
        if (res.statusCode >= 400) {
          const msg = getErrorMessage(res)
          if (!silent) {
            wx.showToast({ title: msg, icon: 'none', duration: 2500 })
          }
          reject({ ...(res.data || {}), detail: msg })
          return
        }
        if (res.data.code === 0) {
          resolve(res.data.data)
        } else {
          if (!silent) {
            wx.showToast({ title: res.data.message || '请求失败', icon: 'none' })
          }
          reject(res.data)
        }
      },
      fail(err) {
        if (!silent) {
          wx.showToast({ title: '网络异常，请稍后重试', icon: 'none' })
        }
        reject(err)
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

module.exports = { request, invalidateCache }
