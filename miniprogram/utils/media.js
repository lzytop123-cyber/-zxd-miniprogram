const {
  resolveStaticUrl,
  useProdApi,
  DEV_LAN_HOST,
  DEV_LOCAL_HOST,
} = require('../config')

const IMAGE_CACHE_META_KEY = 'image_cache_meta_v1'
const DISK_CACHE_TTL = 7 * 24 * 60 * 60 * 1000

const localCache = {}

function fileExt(url) {
  const match = url.match(/\.(jpe?g|png|webp|gif)(\?|$)/i)
  if (!match) return 'jpg'
  const ext = match[1].toLowerCase()
  return ext === 'jpeg' ? 'jpg' : ext
}

function cachePath(url) {
  const name = url.split('/').pop()?.split('?')[0]?.replace(/[^\w.-]/g, '_') || 'img'
  let hash = 0
  for (let i = 0; i < url.length; i += 1) {
    hash = ((hash << 5) - hash + url.charCodeAt(i)) | 0
  }
  return `${wx.env.USER_DATA_PATH}/img_${Math.abs(hash)}_${name}.${fileExt(url)}`
}

function markDiskCache(fullUrl, path) {
  localCache[fullUrl] = path
  try {
    const meta = wx.getStorageSync(IMAGE_CACHE_META_KEY) || {}
    meta[fullUrl] = { path, at: Date.now() }
    wx.setStorageSync(IMAGE_CACHE_META_KEY, meta)
  } catch (e) {
    // ignore
  }
}

function readDiskCache(fullUrl) {
  if (localCache[fullUrl]) {
    return localCache[fullUrl]
  }

  const target = cachePath(fullUrl)
  const fs = wx.getFileSystemManager()

  try {
    const meta = wx.getStorageSync(IMAGE_CACHE_META_KEY) || {}
    const entry = meta[fullUrl]
    if (entry && entry.path === target && Date.now() - entry.at < DISK_CACHE_TTL) {
      fs.accessSync(target)
      localCache[fullUrl] = target
      return target
    }
    if (entry && Date.now() - entry.at >= DISK_CACHE_TTL) {
      delete meta[fullUrl]
      wx.setStorageSync(IMAGE_CACHE_META_KEY, meta)
    }
  } catch (e) {
    // ignore
  }

  try {
    fs.accessSync(target)
    markDiskCache(fullUrl, target)
    return target
  } catch (e) {
    return null
  }
}

function isLocalPath(url) {
  return (
    !url
    || url.startsWith('wxfile://')
    || url.startsWith('http://tmp/')
    || url.startsWith('https://tmp/')
    || (!url.startsWith('http://') && !url.startsWith('https://'))
  )
}

/** 生产 HTTPS 在真机可直接用于 <image>（需配置 downloadFile 域名） */
function canUseRemoteDirectly(url) {
  if (!url.startsWith('https://')) return false
  return useProdApi()
}

function downloadHttpsImage(fullUrl) {
  const cached = readDiskCache(fullUrl)
  if (cached) return Promise.resolve(cached)

  const target = cachePath(fullUrl)
  const fs = wx.getFileSystemManager()

  return new Promise((resolve, reject) => {
    wx.downloadFile({
      url: fullUrl,
      success(res) {
        if (res.statusCode !== 200 || !res.tempFilePath) {
          reject(new Error(`download failed: ${res.statusCode}`))
          return
        }
        fs.copyFile({
          srcPath: res.tempFilePath,
          destPath: target,
          success() {
            markDiskCache(fullUrl, target)
            resolve(target)
          },
          fail() {
            markDiskCache(fullUrl, res.tempFilePath)
            resolve(res.tempFilePath)
          },
        })
      },
      fail: reject,
    })
  })
}

function downloadViaRequest(fullUrl) {
  const cached = readDiskCache(fullUrl)
  if (cached) return Promise.resolve(cached)

  const target = cachePath(fullUrl)
  const fs = wx.getFileSystemManager()

  return new Promise((resolve, reject) => {
    wx.request({
      url: fullUrl,
      responseType: 'arraybuffer',
      success(res) {
        if (res.statusCode !== 200) {
          reject(new Error(`request download failed: ${res.statusCode}`))
          return
        }
        fs.writeFile({
          filePath: target,
          data: res.data,
          success() {
            markDiskCache(fullUrl, target)
            resolve(target)
          },
          fail: reject,
        })
      },
      fail: reject,
    })
  })
}

function downloadHttpImage(fullUrl) {
  const cached = readDiskCache(fullUrl)
  if (cached) return Promise.resolve(cached)

  return downloadViaRequest(fullUrl).catch((err) => {
    if (!useProdApi() && fullUrl.includes(`${DEV_LAN_HOST}:`)) {
      const fallback = fullUrl.replace(DEV_LAN_HOST, DEV_LOCAL_HOST)
      return downloadViaRequest(fallback)
    }
    return Promise.reject(err)
  })
}

function downloadRemoteImage(fullUrl) {
  if (fullUrl.startsWith('https://')) {
    return downloadHttpsImage(fullUrl)
  }
  return downloadHttpImage(fullUrl)
}

/** 供 <image src> 使用：真机先下载到本地，开发者工具生产环境可 HTTPS 直链 */
function resolveImageForDisplay(url) {
  if (!url) return Promise.resolve('')
  const fullUrl = resolveStaticUrl(url)
  if (!fullUrl) return Promise.resolve('')
  if (isLocalPath(fullUrl)) return Promise.resolve(fullUrl)
  if (canUseRemoteDirectly(fullUrl)) return Promise.resolve(fullUrl)

  return downloadRemoteImage(fullUrl)
}

function getImageInfoPath(fullUrl) {
  return new Promise((resolve, reject) => {
    wx.getImageInfo({
      src: fullUrl,
      success(res) {
        if (res.path) {
          markDiskCache(fullUrl, res.path)
          resolve(res.path)
        } else {
          reject(new Error('getImageInfo empty path'))
        }
      },
      fail: reject,
    })
  })
}

async function resolveBannerImageUrl(fullUrl) {
  if (!fullUrl || isLocalPath(fullUrl)) return fullUrl

  try {
    return await downloadRemoteImage(fullUrl)
  } catch (err1) {
    console.warn('[media] banner downloadFile fail, try request', fullUrl, err1)
  }

  try {
    return await downloadViaRequest(fullUrl)
  } catch (err2) {
    console.warn('[media] banner request fail, try getImageInfo', fullUrl, err2)
  }

  try {
    return await getImageInfoPath(fullUrl)
  } catch (err3) {
    console.error('[media] banner image fail', fullUrl, err3)
    return fullUrl
  }
}

async function resolveBannerImages(banners) {
  const list = banners || []
  const out = []
  for (const item of list) {
    if (!item.image_url) {
      out.push(item)
      continue
    }
    const remote = resolveStaticUrl(item.image_url)
    const image_url = await resolveBannerImageUrl(remote)
    out.push({ ...item, image_url, _remote_url: remote })
  }
  return out
}

/** 同步解析 Banner URL，用于 API 返回后立即展示，避免占位图闪烁 */
function prepareBannerItems(banners) {
  return (banners || []).map((item) => ({
    ...item,
    image_url: item.image_url ? resolveStaticUrl(item.image_url) : '',
  }))
}

async function resolveStoreList(stores) {
  const list = stores || []
  return Promise.all(
    list.map(async (store) => {
      if (!store?.cover_images?.length) return store
      try {
        const cover_images = await Promise.all(
          store.cover_images.map((url) => resolveImageForDisplay(url))
        )
        return { ...store, cover_images }
      } catch (err) {
        console.error('[media] store cover fail', store.id, err)
        return store
      }
    })
  )
}

module.exports = {
  resolveImageForDisplay,
  resolveBannerImages,
  resolveBannerImageUrl,
  prepareBannerItems,
  resolveStoreList,
}
