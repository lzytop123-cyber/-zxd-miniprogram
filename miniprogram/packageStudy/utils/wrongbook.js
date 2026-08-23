const { getApiBase } = require('../../config')
const { resolveImageForDisplay } = require('../../utils/media')

const STATUS_LABELS = {
  0: '未掌握',
  1: '仍然错',
  2: '已掌握',
}

function uploadWrongbookImage(filePath, type) {
  const token = wx.getStorageSync('token') || ''
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${getApiBase().replace(/\/$/, '')}/wrongbook/upload`,
      filePath,
      name: 'file',
      formData: { type: type || 'question' },
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
          resolve((data.data && data.data) || {})
        } catch (e) {
          reject(new Error('上传解析失败'))
        }
      },
      fail: (err) => reject(err),
    })
  })
}

async function decorateQuestion(row) {
  const item = row || {}
  const imageUrls = item.image_urls || []
  const answerUrls = item.answer_image_urls || []
  const displayImages = await Promise.all(imageUrls.map((u) => resolveImageForDisplay(u)))
  const displayAnswers = await Promise.all(answerUrls.map((u) => resolveImageForDisplay(u)))
  return {
    ...item,
    display_images: displayImages,
    display_answers: displayAnswers,
    status_label: item.status_label || STATUS_LABELS[item.status] || '未掌握',
    cover: displayImages[0] || '',
  }
}

module.exports = {
  STATUS_LABELS,
  uploadWrongbookImage,
  decorateQuestion,
}
