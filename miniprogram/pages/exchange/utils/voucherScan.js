/** 团购券扫码：统一走微信原生 wx.scanCode（支持二维码 + 条形码，可相册） */

const CODE_KEYS = ['code', 'couponcode', 'receiptcode', 'voucher', 'c']

function isDouyinCouponNumber(raw) {
  const compact = String(raw || '').replace(/\s/g, '')
  return /^\d{12,20}$/.test(compact)
}

function isDouyinScanPayload(raw) {
  const text = String(raw || '').trim().toLowerCase()
  return (
    text.includes('douyin.com') ||
    text.includes('iesdouyin.com') ||
    text.includes('object_id=') ||
    text.includes('encrypted_data=')
  )
}

function isDouyinShortLinkSlug(raw) {
  const text = String(raw || '').trim()
  // 抖音短链扫码常只返回 v.douyin.com 路径片段，如 iCkM1ma6
  return /^[A-Za-z0-9]{6,16}$/.test(text) && !/^\d+$/.test(text)
}

function extractDouyinShortSlug(raw) {
  const text = String(raw || '').trim()
  if (isDouyinShortLinkSlug(text)) return text
  const match = text.match(/v\.douyin\.com\/([A-Za-z0-9]{6,16})\/?/i)
  return match ? match[1] : ''
}

/** 提交核销时把展示用短码还原成抖音可识别的链接/券号 */
function toDouyinSubmitCode(code) {
  const text = String(code || '').trim()
  if (!text) return ''
  const compact = text.replace(/\s/g, '')
  if (isDouyinCouponNumber(compact)) return compact
  if (isDouyinShortLinkSlug(text)) return `https://v.douyin.com/${text}/`
  if (isDouyinScanPayload(text)) {
    const slug = extractDouyinShortSlug(text)
    if (slug) return `https://v.douyin.com/${slug}/`
    return text.includes('://') ? text : `https://${text.replace(/^\/+/, '')}`
  }
  return text
}

function parseScannedVoucherCode(raw, options = {}) {
  if (raw == null) return ''
  let text = String(raw).trim()
  if (!text) return ''

  if (options.platform === 'douyin') {
    if (isDouyinCouponNumber(text)) {
      return text.replace(/\s/g, '')
    }
    if (isDouyinScanPayload(text) || isDouyinShortLinkSlug(text)) {
      const slug = extractDouyinShortSlug(text)
      if (slug) return slug
      return text.includes('://') ? text : `https://${text.replace(/^\/+/, '')}`
    }
  }

  if (/^[A-Za-z0-9-]{6,32}$/.test(text)) return text

  const tryUrl = text.includes('://') ? text : (text.includes('.') ? `https://${text}` : text)
  if (tryUrl.includes('?') || tryUrl.includes('://')) {
    try {
      const queryStart = tryUrl.indexOf('?')
      if (queryStart >= 0) {
        const query = tryUrl.slice(queryStart + 1).split('#')[0]
        query.split('&').forEach((pair) => {
          const eq = pair.indexOf('=')
          if (eq <= 0) return
          const key = decodeURIComponent(pair.slice(0, eq)).toLowerCase()
          const val = decodeURIComponent(pair.slice(eq + 1)).trim()
          if (CODE_KEYS.includes(key) && val.length >= 6 && val.length <= 32) {
            text = val
          }
        })
        if (/^[A-Za-z0-9-]{6,32}$/.test(text)) return text
      }
      const path = tryUrl.split('?')[0].split('#')[0]
      const last = path.split('/').filter(Boolean).pop() || ''
      if (/^[A-Za-z0-9-]{6,32}$/.test(last)) return last
    } catch (e) {
      // ignore
    }
  }

  const matches = text.match(/[A-Za-z0-9-]{6,32}/g)
  if (matches && matches.length) {
    return matches.sort((a, b) => b.length - a.length)[0]
  }

  const compact = text.replace(/\s/g, '')
  return compact.length >= 6 ? compact.slice(0, 32) : ''
}

function scanVoucherCode(options = {}) {
  const onlyFromCamera = options.onlyFromCamera !== false
  return new Promise((resolve, reject) => {
    wx.scanCode({
      onlyFromCamera,
      scanType: ['qrCode', 'barCode'],
      success: resolve,
      fail: reject,
    })
  })
}

function scanFromCamera() {
  return scanVoucherCode({ onlyFromCamera: true })
}

/** 原生扫码：相机 + 相册入口（支持二维码/条形码） */
function pickAndScanVoucher() {
  return scanVoucherCode({ onlyFromCamera: false })
}

function fillCodeFromScanResult(res, options = {}) {
  const code = parseScannedVoucherCode(res && res.result, options)
  if (!code || code.length < 6) {
    return { ok: false, message: '未识别有效券码' }
  }
  return { ok: true, code }
}

module.exports = {
  isDouyinScanPayload,
  parseScannedVoucherCode,
  toDouyinSubmitCode,
  scanFromCamera,
  pickAndScanVoucher,
  fillCodeFromScanResult,
}
