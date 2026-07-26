const { getApiBase, resolveStaticUrl } = require('../../config')
const { request } = require('../../utils/request')
const { isMarketplaceEnabled } = require('../../utils/features')
const routes = require('../../utils/routes')
const auth = require('../../utils/auth')

function absUrl(path) {
  return resolveStaticUrl(path)
}

function guardMarketplace() {
  if (!isMarketplaceEnabled()) {
    wx.showModal({
      title: '提示',
      content: '功能暂未开放',
      showCancel: false,
      success: () => wx.switchTab({ url: '/pages/home/index' }),
    })
    return false
  }
  return true
}

function statusLabel(status) {
  const map = {
    draft: '草稿',
    pending: '待审核',
    published: '已发布',
    rejected: '已驳回',
    off: '已下架',
    sold: '已出',
    violation: '违规下架',
  }
  return map[status] || status
}

async function uploadMarketImage(filePath) {
  const token = wx.getStorageSync('token') || ''
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${getApiBase().replace(/\/$/, '')}/market/upload`,
      filePath,
      name: 'file',
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success: (res) => {
        try {
          const data = JSON.parse(res.data || '{}')
          if (res.statusCode >= 400) {
            const msg =
              (typeof data.detail === 'string' && data.detail) ||
              data.message ||
              '上传失败'
            reject(new Error(msg))
            return
          }
          if (data.code && data.code !== 0) {
            reject(new Error(data.message || '上传失败'))
            return
          }
          resolve((data.data && data.data.path) || '')
        } catch (e) {
          reject(new Error('上传解析失败'))
        }
      },
      fail: (err) => reject(err),
    })
  })
}

module.exports = {
  request,
  routes,
  auth,
  absUrl,
  guardMarketplace,
  statusLabel,
  uploadMarketImage,
  isMarketplaceEnabled,
}
