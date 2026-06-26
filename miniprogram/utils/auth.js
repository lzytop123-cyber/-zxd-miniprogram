const { request } = require('./request')

const DEFAULT_NICKNAME = '知行岛学员'
const DEFAULT_AVATAR = ''

function getAppSafe() {
  try {
    return getApp({ allowDefault: true })
  } catch (e) {
    return null
  }
}

function syncAppUser(user) {
  const app = getAppSafe()
  if (!app) return
  if (!app.globalData) app.globalData = {}
  app.globalData.user = user
  app.globalData.loginReady = true
  app.globalData.loginError = ''
  if (user) wx.setStorageSync('userInfo', user)
}

function syncAppError(message) {
  const app = getAppSafe()
  if (!app) return
  if (!app.globalData) app.globalData = {}
  app.globalData.loginReady = false
  app.globalData.loginError = message || '登录失败'
}

function login(options = {}) {
  const { silent = true } = options
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
  const app = getAppSafe()
  if (app && app.globalData) {
    if (app.globalData.loginReady && app.globalData.user) {
      return Promise.resolve(app.globalData.user)
    }
    if (app.globalData.loginPromise) {
      return app.globalData.loginPromise.then((res) => (res ? res.user : null))
    }
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
  const data = await readAvatarBase64(tempPath)
  return request({
    url: '/user/avatar',
    method: 'POST',
    data: { avatar_image: `data:image/jpeg;base64,${data}` },
  })
}

async function updateNickname(nickname) {
  const name = String(nickname || '').trim()
  if (!name) throw new Error('请输入昵称')
  return request({
    url: '/user/profile',
    method: 'PUT',
    data: { nickname: name },
  })
}

async function saveProfile({ nickname, avatarTempPath }) {
  let user = null
  if (avatarTempPath) {
    user = await uploadAvatar(avatarTempPath)
  }
  if (nickname !== undefined && nickname !== null) {
    user = await updateNickname(nickname)
  }
  if (user) syncAppUser(user)
  return user
}

module.exports = {
  DEFAULT_NICKNAME,
  DEFAULT_AVATAR,
  login,
  waitForLogin,
  saveProfile,
  uploadAvatar,
  updateNickname,
  syncAppUser,
}
