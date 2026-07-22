const { request } = require('./request')

let _cachedTmplId = null
let _tmplLoadedAt = 0

async function getCardExpireTmplId() {
  const now = Date.now()
  if (_cachedTmplId !== null && now - _tmplLoadedAt < 10 * 60 * 1000) {
    return _cachedTmplId
  }
  try {
    const data = await request({ url: '/user/subscribe-config', silent: true, force: true })
    _cachedTmplId = (data && data.enabled && data.card_expire_tmpl_id) || ''
    _tmplLoadedAt = now
    return _cachedTmplId
  } catch (e) {
    return ''
  }
}

function saveSubscriptions(result) {
  if (!result || typeof result !== 'object') return Promise.resolve()
  const subscriptions = {}
  Object.keys(result).forEach((tmplId) => {
    const status = result[tmplId]
    if (status === 'accept' || status === 'reject') {
      subscriptions[tmplId] = status
    }
  })
  if (!Object.keys(subscriptions).length) return Promise.resolve()
  return request({
    url: '/user/subscribe',
    method: 'POST',
    data: { subscriptions },
    silent: true,
  }).catch(() => null)
}

/**
 * 请求「期限卡到期提醒」订阅授权。
 * 每天最多主动弹一次，避免套餐页 onShow 过于打扰。
 */
function requestCardExpireSubscribe(options = {}) {
  const { force = false } = options
  return getCardExpireTmplId().then((tmplId) => {
    if (!tmplId) return null
    if (!force) {
      try {
        const day = new Date().toISOString().slice(0, 10)
        const key = `subscribe_card_expire_asked_${day}`
        if (wx.getStorageSync(key)) return null
        wx.setStorageSync(key, 1)
      } catch (e) {
        // ignore
      }
    }
    return new Promise((resolve) => {
      wx.requestSubscribeMessage({
        tmplIds: [tmplId],
        success: (res) => {
          saveSubscriptions(res).finally(() => resolve(res))
        },
        fail: () => resolve(null),
      })
    })
  })
}

module.exports = {
  getCardExpireTmplId,
  requestCardExpireSubscribe,
  saveSubscriptions,
}
