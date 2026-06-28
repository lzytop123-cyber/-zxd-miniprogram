/** 定位与距离展示 */

function getUserLocation() {
  return new Promise((resolve, reject) => {
    wx.getLocation({
      type: 'gcj02',
      isHighAccuracy: true,
      highAccuracyExpireTime: 5000,
      success: resolve,
      fail: reject,
    })
  })
}

function isLocationDenied() {
  return new Promise((resolve) => {
    wx.getSetting({
      success: (res) => resolve(res.authSetting['scope.userLocation'] === false),
      fail: () => resolve(false),
    })
  })
}

function openLocationSettings() {
  return new Promise((resolve) => {
    wx.openSetting({
      success: (res) => resolve(!!res.authSetting['scope.userLocation']),
      fail: () => resolve(false),
    })
  })
}

function formatDistance(km) {
  if (km == null || km === '') return ''
  const n = Number(km)
  if (Number.isNaN(n)) return ''
  if (n < 1) return `${Math.max(1, Math.round(n * 1000))}m`
  return `${n}km`
}

function hasStoreCoords(store) {
  const lat = Number(store?.latitude)
  const lng = Number(store?.longitude)
  return !Number.isNaN(lat) && !Number.isNaN(lng) && lat !== 0 && lng !== 0
}

/** 打开微信地图（可继续选高德/百度等导航） */
function openStoreNavigation(store) {
  if (!store) {
    wx.showToast({ title: '门店信息无效', icon: 'none' })
    return Promise.reject(new Error('invalid store'))
  }
  if (!hasStoreCoords(store)) {
    wx.showToast({ title: '门店未配置坐标，暂无法导航', icon: 'none' })
    return Promise.reject(new Error('no coords'))
  }
  return new Promise((resolve, reject) => {
    wx.openLocation({
      latitude: Number(store.latitude),
      longitude: Number(store.longitude),
      name: store.name || '知行岛自习室',
      address: store.address || '',
      scale: 18,
      success: resolve,
      fail: () => {
        wx.showToast({ title: '无法打开地图', icon: 'none' })
        reject(new Error('openLocation failed'))
      },
    })
  })
}

module.exports = {
  getUserLocation,
  isLocationDenied,
  openLocationSettings,
  formatDistance,
  hasStoreCoords,
  openStoreNavigation,
}
