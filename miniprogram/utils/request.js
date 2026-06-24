const app = getApp()

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

function request({ url, method = 'GET', data, silent = false }) {
  const payload = data === undefined ? undefined : data
  return new Promise((resolve, reject) => {
    wx.request({
      url: app.globalData.apiBase + url,
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
          wx.showToast({ title: res.data.message || '请求失败', icon: 'none' })
          reject(res.data)
        }
      },
      fail(err) {
        wx.showToast({ title: '网络错误，请确认后端已启动', icon: 'none' })
        reject(err)
      },
    })
  })
}

module.exports = { request }
