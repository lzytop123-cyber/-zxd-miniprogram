/** 团购券扫码（轻量：走微信原生 scanCode，不用 jsQR） */

const CODE_KEYS = ['code', 'couponcode', 'receiptcode', 'voucher', 'c']

function parseScannedVoucherCode(raw) {
  if (raw == null) return ''
  let text = String(raw).trim()
  if (!text) return ''

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

/** 相机扫码（点输入框右侧图标） */
function scanFromCamera() {
  return scanVoucherCode({ onlyFromCamera: true })
}

/** 扫码页可切换相册，微信原生识别（比 js 解码快，且支持条形码） */
function scanWithAlbumSupport() {
  return scanVoucherCode({ onlyFromCamera: false })
}

function fillCodeFromScanResult(res) {
  const code = parseScannedVoucherCode(res && res.result)
  if (!code || code.length < 6) {
    return { ok: false, message: '未识别有效券码' }
  }
  return { ok: true, code }
}

module.exports = {
  parseScannedVoucherCode,
  scanFromCamera,
  scanWithAlbumSupport,
  fillCodeFromScanResult,
}
