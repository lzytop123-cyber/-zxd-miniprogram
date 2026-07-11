/** 团购券扫码：相机走微信原生；相册直接选图 + 按需加载 jsQR 解码 */

const CODE_KEYS = ['code', 'couponcode', 'receiptcode', 'voucher', 'c']

let jsQRModule = null

function getJsQR() {
  if (!jsQRModule) {
    jsQRModule = require('./jsqr')
  }
  return jsQRModule
}

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

function chooseAlbumImage() {
  return new Promise((resolve, reject) => {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album'],
      sizeType: ['compressed'],
      success(res) {
        const file = res.tempFiles && res.tempFiles[0]
        if (!file || !file.tempFilePath) {
          reject(new Error('未选择图片'))
          return
        }
        resolve(file.tempFilePath)
      },
      fail: reject,
    })
  })
}

function compressForDecode(filePath) {
  return new Promise((resolve) => {
    if (typeof wx.compressImage !== 'function') {
      resolve(filePath)
      return
    }
    wx.compressImage({
      src: filePath,
      quality: 68,
      compressedWidth: 640,
      success: (res) => resolve(res.tempFilePath || filePath),
      fail: () => resolve(filePath),
    })
  })
}

function decodeQrFromImage(filePath) {
  return new Promise((resolve, reject) => {
    wx.getImageInfo({
      src: filePath,
      success(info) {
        let dw = info.width
        let dh = info.height
        const maxSide = 480
        if (Math.max(dw, dh) > maxSide) {
          const scale = maxSide / Math.max(dw, dh)
          dw = Math.floor(dw * scale)
          dh = Math.floor(dh * scale)
        }
        try {
          const jsQR = getJsQR()
          const canvas = wx.createOffscreenCanvas({ type: '2d', width: dw, height: dh })
          const ctx = canvas.getContext('2d')
          const img = canvas.createImage()
          img.onload = () => {
            ctx.drawImage(img, 0, 0, dw, dh)
            const imageData = ctx.getImageData(0, 0, dw, dh)
            const result = jsQR(imageData.data, imageData.width, imageData.height, {
              inversionAttempts: 'dontInvert',
            })
            if (result && result.data) {
              resolve(result.data)
              return
            }
            reject(new Error('未识别到二维码，条形码请用相机扫码'))
          }
          img.onerror = () => reject(new Error('图片加载失败'))
          img.src = filePath
        } catch (e) {
          reject(e)
        }
      },
      fail: reject,
    })
  })
}

/** 直接打开相册选图并识别（二维码） */
async function pickFromAlbumAndDecode() {
  const filePath = await chooseAlbumImage()
  const compressed = await compressForDecode(filePath)
  const text = await decodeQrFromImage(compressed)
  return { result: text, scanType: 'QR_CODE' }
}

function pickScanSource() {
  return new Promise((resolve, reject) => {
    wx.showActionSheet({
      itemList: ['相机扫码', '从相册选择'],
      success(res) {
        if (res.tapIndex === 0) resolve('camera')
        else if (res.tapIndex === 1) resolve('album')
        else reject(new Error('cancel'))
      },
      fail: reject,
    })
  })
}

async function pickAndScanVoucher(hooks = {}) {
  const source = await pickScanSource()
  if (source === 'album' && typeof hooks.onAlbumStart === 'function') {
    hooks.onAlbumStart()
  }
  if (source === 'camera') {
    return scanFromCamera()
  }
  return pickFromAlbumAndDecode()
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
  pickFromAlbumAndDecode,
  pickAndScanVoucher,
  fillCodeFromScanResult,
}
