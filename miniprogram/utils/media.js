const {
  resolveStaticUrl,
  USE_PROD,
  DEV_LAN_HOST,
  DEV_LOCAL_HOST,
  isWechatDevtools,
} = require('../config')

const localCache = {}

function fileExt(url) {
  const match = url.match(/\.(jpe?g|png|webp|gif)(\?|$)/i)
  if (!match) return 'jpg'
  const ext = match[1].toLowerCase()
  return ext === 'jpeg' ? 'jpg' : ext
}

function cachePath(url) {
  let hash = 0
  for (let i = 0; i < url.length; i += 1) {
    hash = ((hash << 5) - hash + url.charCodeAt(i)) | 0
  }
  return `${wx.env.USER_DATA_PATH}/img_${Math.abs(hash)}.${fileExt(url)}`
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

/** 真机必须走 downloadFile/request，且域名需在公众平台配置；仅开发者工具可 HTTPS 直链 */
function canUseRemoteDirectly(url) {
  if (!url.startsWith('https://')) return false
  return isWechatDevtools() && USE_PROD
}

function downloadHttpsImage(fullUrl) {
  if (localCache[fullUrl]) {
    return Promise.resolve(localCache[fullUrl])
  }
  return new Promise((resolve, reject) => {
    wx.downloadFile({
      url: fullUrl,
      success(res) {
        if (res.statusCode !== 200 || !res.tempFilePath) {
          reject(new Error(`download failed: ${res.statusCode}`))
          return
        }
        localCache[fullUrl] = res.tempFilePath
        resolve(res.tempFilePath)
      },
      fail: reject,
    })
  })
}

function downloadHttpImage(fullUrl) {
  if (localCache[fullUrl]) {
    return Promise.resolve(localCache[fullUrl])
  }

  const target = cachePath(fullUrl)
  const fs = wx.getFileSystemManager()

  try {
    fs.accessSync(target)
    localCache[fullUrl] = target
    return Promise.resolve(target)
  } catch (e) {
    // cache miss
  }

  const attempt = (url) =>
    new Promise((resolve, reject) => {
      wx.request({
        url,
        responseType: 'arraybuffer',
        success(res) {
          if (res.statusCode !== 200) {
            reject(new Error(`download failed: ${res.statusCode}`))
            return
          }
          fs.writeFile({
            filePath: target,
            data: res.data,
            success() {
              localCache[fullUrl] = target
              localCache[url] = target
              resolve(target)
            },
            fail: reject,
          })
        },
        fail: reject,
      })
    })

  return attempt(fullUrl).catch((err) => {
    if (!USE_PROD && fullUrl.includes(`${DEV_LAN_HOST}:`)) {
      const fallback = fullUrl.replace(DEV_LAN_HOST, DEV_LOCAL_HOST)
      return attempt(fallback)
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
  if (isLocalPath(url)) return Promise.resolve(url)

  const fullUrl = resolveStaticUrl(url)
  if (!fullUrl) return Promise.resolve('')
  if (canUseRemoteDirectly(fullUrl)) return Promise.resolve(fullUrl)

  return downloadRemoteImage(fullUrl)
}

async function resolveBannerImages(banners) {
  const list = banners || []
  return Promise.all(
    list.map(async (item) => {
      if (!item.image_url) return item
      try {
        const image_url = await resolveImageForDisplay(item.image_url)
        return { ...item, image_url }
      } catch (err) {
        console.error('[media] banner image fail', item.image_url, err)
        return item
      }
    })
  )
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
  resolveStoreList,
}
