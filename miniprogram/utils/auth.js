const { request } = require('./request')
const { normalizeUser } = require('./user')
const routes = require('./routes')

const DEFAULT_NICKNAME = '知行岛学员'
const DEFAULT_AVATAR = ''
const MANUAL_LOGOUT_KEY = 'manualLogout'
const LOGIN_PAGE = routes.profileLogin
const TAB_PAGES = [
  '/pages/home/index',
  '/pages/packages/index',
  '/pages/checkin/index',
  '/pages/report/index',
  '/pages/profile/index',
]

function getAppSafe() {
  try {
    return getApp({ allowDefault: true })
  } catch (e) {
    return null
  }
}

function isLoggedIn() {
  return !!(wx.getStorageSync('token') && !wx.getStorageSync(MANUAL_LOGOUT_KEY))
}

function syncAppUser(user) {
  const app = getAppSafe()
  if (!app) return
  if (!app.globalData) app.globalData = {}
  app.globalData.user = user
  app.globalData.loginReady = true
  app.globalData.loginError = ''
  if (user) {
    wx.setStorageSync('userInfo', user)
    normalizeUser(user).then((normalized) => {
      if (!app.globalData) return
      app.globalData.user = normalized
      wx.setStorageSync('userInfo', normalized)
    })
  }
}

function syncAppError(message) {
  const app = getAppSafe()
  if (!app) return
  if (!app.globalData) app.globalData = {}
  app.globalData.loginReady = false
  app.globalData.loginError = message || '登录失败'
}

function logout() {
  wx.setStorageSync(MANUAL_LOGOUT_KEY, true)
  wx.removeStorageSync('token')
  wx.removeStorageSync('userInfo')
  try {
    const { invalidateCache } = require('./request')
    invalidateCache('/user/')
    invalidateCache('/reservation/')
  } catch (e) {
    // ignore
  }
  const app = getAppSafe()
  if (app?.globalData) {
    app.globalData.user = null
    app.globalData.loginReady = false
    app.globalData.loginError = ''
    app.globalData.loginPromise = null
  }
}

function login(options = {}) {
  const { silent = true, force = false } = options
  if (!force && wx.getStorageSync(MANUAL_LOGOUT_KEY)) {
    return Promise.reject(new Error('logged out'))
  }

  return new Promise((resolve, reject) => {
    wx.login({
      success: ({ code }) => {
        if (!code) {
          syncAppError('微信登录失败')
          reject(new Error('no code'))
          return
        }
        request({
          url: '/user/login',
          method: 'POST',
          data: { code },
          silent,
        })
          .then((res) => {
            wx.removeStorageSync(MANUAL_LOGOUT_KEY)
            wx.setStorageSync('token', res.token)
            syncAppUser(res.user)
            resolve(res)
          })
          .catch((err) => {
            const msg = err.detail || err.message || '登录失败，请稍后重试'
            syncAppError(msg)
            if (!silent) wx.showToast({ title: msg, icon: 'none' })
            reject(err)
          })
      },
      fail: () => {
        syncAppError('微信登录失败')
        reject(new Error('wx.login fail'))
      },
    })
  })
}

function waitForLogin() {
  if (!isLoggedIn()) {
    return Promise.reject(new Error('not logged in'))
  }
  const app = getAppSafe()
  if (app?.globalData?.loginReady && app.globalData.user) {
    return Promise.resolve(app.globalData.user)
  }
  if (app?.globalData?.loginPromise) {
    return app.globalData.loginPromise.then((res) => (res ? res.user : null))
  }
  return login({ silent: true }).then((res) => res.user)
}

function readAvatarBase64(tempPath) {
  return new Promise((resolve, reject) => {
    wx.getFileSystemManager().readFile({
      filePath: tempPath,
      encoding: 'base64',
      success: (file) => resolve(file.data),
      fail: reject,
    })
  })
}

async function uploadAvatar(tempPath) {
  const lower = String(tempPath || '').toLowerCase()
  let mime = 'jpeg'
  if (lower.includes('.png')) mime = 'png'
  else if (lower.includes('.webp')) mime = 'webp'
  const data = await readAvatarBase64(tempPath)
  return request({
    url: '/user/avatar',
    method: 'POST',
    data: { avatar_image: `data:image/${mime};base64,${data}` },
  })
}

async function updateProfile(fields) {
  return request({
    url: '/user/profile',
    method: 'PUT',
    data: fields,
  })
}

async function updateNickname(nickname) {
  const name = String(nickname || '').trim()
  if (!name) throw new Error('请输入昵称')
  return updateProfile({ nickname: name })
}

async function saveProfile({ nickname, avatarTempPath, studyGoal }) {
  let user = null
  if (avatarTempPath) {
    user = await uploadAvatar(avatarTempPath)
  }
  if (nickname !== undefined && nickname !== null) {
    user = await updateNickname(nickname)
  }
  if (studyGoal !== undefined) {
    user = await updateProfile({ study_goal: studyGoal || '' })
  }
  if (user) syncAppUser(user)
  return user
}

function goLogin(redirect, options = {}) {
  const query = redirect ? `?redirect=${encodeURIComponent(redirect)}` : ''
  const url = `${LOGIN_PAGE}${query}`
  if (options.replace) {
    wx.redirectTo({ url })
  } else {
    wx.navigateTo({ url })
  }
}

function requireLogin(redirect) {
  if (isLoggedIn()) return true
  goLogin(redirect || '')
  return false
}

function finishLoginRedirect(redirect, fallback) {
  const target = redirect || fallback || '/pages/profile/index'
  const path = target.split('?')[0]
  if (TAB_PAGES.includes(path)) {
    wx.switchTab({ url: path })
    return
  }
  wx.redirectTo({
    url: target,
    fail: () => {
      if (getCurrentPages().length > 1) {
        wx.navigateBack()
      } else {
        wx.switchTab({ url: '/pages/profile/index' })
      }
    },
  })
}

module.exports = {
  DEFAULT_NICKNAME,
  DEFAULT_AVATAR,
  MANUAL_LOGOUT_KEY,
  LOGIN_PAGE,
  TAB_PAGES,
  getAppSafe,
  isLoggedIn,
  login,
  logout,
  goLogin,
  requireLogin,
  finishLoginRedirect,
  waitForLogin,
  saveProfile,
  updateProfile,
  uploadAvatar,
  updateNickname,
  syncAppUser,
}
